#!/usr/bin/env python3
"""Generate Croissant 1.1 dataset metadata with external recordset CSV files.

Each WordPress download is modeled as a Croissant ``RecordSet``. Its rows live
in a human-readable CSV ``FileObject`` and its fields formally describe how to
extract each CSV column. One Croissant document contains all recordsets for a
dataset; route-specific CSVs remain independently selectable by recordset ID.
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import json
import math
import re
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

import pandas as pd


CROISSANT_11 = "http://mlcommons.org/croissant/1.1"
RAI_10 = "http://mlcommons.org/croissant/RAI/1.0"
TCIA_USAGE = "https://www.cancerimagingarchive.net/data-usage-policies-and-restrictions/"
TCIA_CONTROLLED = "https://www.cancerimagingarchive.net/nih-controlled-data-access-policy/"
NIH_RAS = "https://auth.nih.gov/docs/RAS/"
GA4GH_DRS = "https://www.ga4gh.org/product/data-repository-service-drs/"
EXTERNAL_CSV_NOTE = (
    "The complete record inventory is stored in a route-specific CSV FileObject. "
    "Each Croissant Field identifies its CSV column through a DataSource."
)


@dataclass(frozen=True)
class Source:
    name: str
    url: str
    path: Path | None = None
    sha256: str = ""
    note: str = ""


@dataclass
class RecordSetDraft:
    dataset_short_title: str
    slug: str
    download_id: str
    filename: str
    name: str
    description: str
    record_grain: str
    retrieval_key: str
    access_level: str
    license_value: str
    rows: list[dict[str, Any]]
    fields: list[dict[str, Any]]
    sources: list[Source]
    conditions: str
    usage_info: list[dict[str, Any]]
    constant_fields: dict[str, Any]
    additional_properties: list[dict[str, Any]]
    distributions: list[dict[str, Any]]

    @property
    def recordset_id(self) -> str:
        return f"recordsets/{self.download_id}/records"

    @property
    def csv_id(self) -> str:
        return f"recordsets/{self.filename}"


CANONICAL_NAMES = {
    "drsuri": "drs_uri",
    "ctdcstudyaccession": "dbGaPStudyAccession",
    "ctdcfilename": "FileName",
    "ctdcsize": "CTDCSize",
    "ctdcdescription": "CTDCDescription",
    "ctdcdiagnosis": "Diagnosis",
    "tciacollection": "Collection",
    "patientid": "PatientID",
    "patientname": "PatientName",
    "patientbirthdate": "PatientBirthDate",
    "patientsex": "PatientSex",
    "ethnicgroup": "EthnicGroup",
    "phantom": "Phantom",
    "speciescode": "SpeciesCode",
    "speciesdescription": "SpeciesDescription",
    "studyinstanceuid": "StudyInstanceUID",
    "studydate": "StudyDate",
    "studydescription": "StudyDescription",
    "studydesc": "StudyDescription",
    "admittingdiagnosisdescription": "AdmittingDiagnosisDescription",
    "studyid": "StudyID",
    "patientage": "PatientAge",
    "longitudinaltemporaleventtype": "LongitudinalTemporalEventType",
    "longitudinaltemporaloffsetfromevent": "LongitudinalTemporalOffsetFromEvent",
    "seriesinstanceuid": "SeriesInstanceUID",
    "project": "Collection",
    "collection": "Collection",
    "site": "Site",
    "modality": "Modality",
    "protocolname": "ProtocolName",
    "seriesdate": "SeriesDate",
    "seriesdescription": "SeriesDescription",
    "bodypartexamined": "BodyPartExamined",
    "seriesnumber": "SeriesNumber",
    "annotationsflag": "AnnotationsFlag",
    "manufacturer": "Manufacturer",
    "manufacturermodelname": "ManufacturerModelName",
    "softwareversions": "SoftwareVersions",
    "imagecount": "ImageCount",
    "maxsubmissiontimestamp": "MaxSubmissionTimestamp",
    "licensename": "LicenseName",
    "licenseuri": "LicenseURI",
    "collectionuri": "CollectionURI",
    "datadescriptionuri": "DataDescriptionURI",
    "filesize": "FileSize",
    "datereleased": "DateReleased",
    "releasedstatus": "ReleasedStatus",
    "thirdpartyanalysis": "ThirdPartyAnalysis",
    "authorized": "Authorized",
    "pixelspacingmmrow": "PixelSpacingRowMm",
    "slicethicknessmm": "SliceThicknessMm",
    "wsiimageurl": "imageUrl",
    "imageurl": "imageUrl",
    "camicroscopeurl": "viewerUrl",
    "camicid": "caMicroscopeSlideID",
    "slideid": "SlideID",
    "patient_id": "PatientID",
    "dataformat": "FileFormat",
    "cancertype": "CancerType",
    "cancerlocation": "CancerLocation",
    "magnification": "Magnification",
    "update": "SourceUpdated",
    "updatevalue": "SourceUpdated",
}

URL_FIELDS = {
    "drs_uri",
    "imageUrl",
    "viewerUrl",
    "LicenseURI",
    "CollectionURI",
    "DataDescriptionURI",
    "source_url",
    "access_url",
    "viewer_url",
    "manifest_url",
    "packageUrl",
}

INTEGER_FIELDS = {
    "ImageCount",
    "FileSize",
    "CTDCSize",
    "size_bytes",
    "represented_file_count",
    "participant_link_count",
    "location_count",
    "populated_field_count",
    "conflict_field_count",
}


def compact(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", value.casefold())


def safe_name(value: str) -> str:
    mapped = CANONICAL_NAMES.get(compact(value))
    if mapped:
        return mapped
    candidate = re.sub(r"[^A-Za-z0-9_]+", "_", value.strip()).strip("_")
    if not candidate:
        raise ValueError(f"Cannot make a field name from {value!r}")
    if candidate[0].isdigit():
        candidate = "field_" + candidate
    return candidate


def sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def clean_value(value: Any) -> Any | None:
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    if isinstance(value, (dt.datetime, dt.date, pd.Timestamp)):
        return value.isoformat()
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        if math.isnan(value):
            return None
        if value.is_integer():
            return int(value)
        return value
    if isinstance(value, (dict, list)):
        return value
    text = str(value).strip()
    return text if text else None


def context(base: str) -> dict[str, Any]:
    return {
        "@language": "en",
        "@vocab": "https://schema.org/",
        "@base": base,
        "sc": "https://schema.org/",
        "cr": "http://mlcommons.org/croissant/",
        "rai": "http://mlcommons.org/croissant/RAI/",
        "dct": "http://purl.org/dc/terms/",
        "prov": "http://www.w3.org/ns/prov#",
        "odrl": "http://www.w3.org/ns/odrl/2/",
        "duo": "http://purl.obolibrary.org/obo/DUO_",
        "description": {"@container": "@language"},
        "arrayShape": "cr:arrayShape",
        "citeAs": "cr:citeAs",
        "conformsTo": "dct:conformsTo",
        "data": {"@id": "cr:data", "@type": "@json"},
        "dataType": {"@id": "cr:dataType", "@type": "@vocab"},
        "field": "cr:field",
        "isLiveDataset": "cr:isLiveDataset",
        "isArray": "cr:isArray",
        "key": "cr:key",
        "recordSet": "cr:recordSet",
        "sdVersion": "cr:sdVersion",
        "sha256": "cr:sha256",
        "value": "cr:value",
        "annotation": "cr:annotation",
        "source": "cr:source",
        "fileObject": "cr:fileObject",
        "fileSet": "cr:fileSet",
        "extract": "cr:extract",
        "column": "cr:column",
        "fileProperty": "cr:fileProperty",
        "format": "cr:format",
        "transform": "cr:transform",
        "separator": "cr:separator",
        "regex": "cr:regex",
        "readLines": "cr:readLines",
        "unArchive": "cr:unArchive",
        "jsonPath": "cr:jsonPath",
        "examples": {"@id": "cr:examples", "@type": "@json"},
        "subField": "cr:subField",
        "parentField": "cr:parentField",
        "references": "cr:references",
        "equivalentProperty": "cr:equivalentProperty",
        "includes": "cr:includes",
        "excludes": "cr:excludes",
        "containedIn": "cr:containedIn",
        "md5": "cr:md5",
        "name": {"@container": "@language"},
        "path": "cr:path",
        "repeated": "cr:repeated",
        "replace": "cr:replace",
        "samplingRate": "cr:samplingRate",
    }


def property_value(name: str, value: Any) -> dict[str, Any]:
    return {"@type": "sc:PropertyValue", "name": name, "value": value}


def source_entity(source: Source) -> dict[str, Any]:
    entity: dict[str, Any] = {
        "@type": ["sc:CreativeWork", "prov:Entity"],
        "@id": source.url,
        "name": source.name,
        "url": source.url,
    }
    digest = source.sha256 or (sha256_path(source.path) if source.path else "")
    if digest:
        entity["sha256"] = digest
    if source.note:
        entity["description"] = source.note
    return entity


def usage_info(access_level: str, license_value: str, dbgap_accession: str = "") -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = [
        {
            "@type": "sc:CreativeWork",
            "@id": TCIA_USAGE,
            "name": "TCIA Data Usage Policies and Restrictions",
            "url": TCIA_USAGE,
        }
    ]
    if license_value and license_value != TCIA_USAGE:
        items.append(
            {
                "@type": "sc:CreativeWork",
                "@id": license_value,
                "name": "License or access policy supplied by TCIA",
                "url": license_value,
            }
        )
    if access_level == "controlled":
        items.append(
            {
                "@type": "sc:CreativeWork",
                "@id": TCIA_CONTROLLED,
                "name": "TCIA NIH Controlled Data Access Policy",
                "url": TCIA_CONTROLLED,
            }
        )
        if dbgap_accession:
            items.append(
                {
                    "@type": "sc:DefinedTerm",
                    "name": f"dbGaP study {dbgap_accession}",
                    "termCode": dbgap_accession,
                    "url": f"https://www.ncbi.nlm.nih.gov/projects/gap/cgi-bin/study.cgi?study_id={dbgap_accession}",
                    "description": "Authorization authority for the controlled payload; this term is not a credential or access grant.",
                }
            )
    return items


def conditions(access_level: str) -> str:
    if access_level == "controlled":
        return (
            "The record metadata and DRS identifiers are public. Access to the referenced payloads "
            "requires authorization through the applicable dbGaP process and is enforced by the "
            "downstream CRDC service. This Croissant file grants no access and contains no credentials."
        )
    if access_level == "open_noncommercial":
        return "Open metadata and payloads subject to the listed noncommercial-use license and TCIA usage policy."
    return "Open metadata and payloads subject to the listed license and TCIA usage policy."


def field_specs(rows: list[dict[str, Any]], source_names: dict[str, str], descriptions: dict[str, str] | None = None) -> list[dict[str, Any]]:
    descriptions = descriptions or {}
    ordered: list[str] = []
    seen: set[str] = set()
    for row in rows:
        for name in row:
            if name not in seen:
                seen.add(name)
                ordered.append(name)
    specs: list[dict[str, Any]] = []
    for name in ordered:
        values = [row.get(name) for row in rows if row.get(name) is not None]
        data_type = "sc:Text"
        if name in URL_FIELDS:
            data_type = "sc:URL"
        elif name in INTEGER_FIELDS and values and all(isinstance(v, int) and not isinstance(v, bool) for v in values):
            data_type = "sc:Integer"
        elif values and all(isinstance(v, bool) for v in values):
            data_type = "sc:Boolean"
        elif values and all(isinstance(v, (dict, list)) for v in values):
            data_type = "sc:StructuredValue"
        spec: dict[str, Any] = {
            "name": name,
            "dataType": data_type,
            "description": descriptions.get(name, f"Source field {source_names.get(name, name)!r}; values are retained without semantic substitution."),
        }
        source_name = source_names.get(name, name)
        if source_name != name:
            spec["alternateName"] = source_name
        specs.append(spec)
    return specs


def canonicalize_rows(raw_rows: Iterable[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, str]]:
    output: list[dict[str, Any]] = []
    source_names: dict[str, str] = {}
    for raw in raw_rows:
        row: dict[str, Any] = {}
        for original, raw_value in raw.items():
            name = safe_name(str(original))
            value = clean_value(raw_value)
            source_names.setdefault(name, str(original))
            if value is not None:
                if name in row and row[name] != value:
                    raise ValueError(f"Field collision for {original!r} -> {name!r}")
                row[name] = value
        output.append(row)
    return output, source_names


def parse_tcia(path: Path) -> list[str]:
    lines = path.read_text(encoding="utf-8-sig").splitlines()
    try:
        start = lines.index("ListOfSeriesToDownload=") + 1
    except ValueError as exc:
        raise ValueError(f"{path} has no ListOfSeriesToDownload marker") from exc
    values = [line.strip() for line in lines[start:] if line.strip()]
    if len(values) != len(set(values)):
        raise ValueError(f"{path} contains duplicate SeriesInstanceUID values")
    return values


def excel_rows(path: Path) -> tuple[list[dict[str, Any]], dict[str, str]]:
    frame = pd.read_excel(path, sheet_name=0, dtype=object)
    return canonicalize_rows(frame.to_dict(orient="records"))


def csv_rows(path: Path) -> tuple[list[dict[str, Any]], dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        return canonicalize_rows(csv.DictReader(stream))


def reconcile_uid_manifest(manifest_path: Path, metadata_path: Path) -> tuple[list[dict[str, Any]], dict[str, str]]:
    uids = parse_tcia(manifest_path)
    rows, source_names = excel_rows(metadata_path)
    by_uid: dict[str, dict[str, Any]] = {}
    for row in rows:
        uid = str(row.get("SeriesInstanceUID", "")).strip()
        if not uid:
            raise ValueError(f"Metadata row in {metadata_path} lacks SeriesInstanceUID")
        if uid in by_uid:
            raise ValueError(f"Duplicate metadata SeriesInstanceUID {uid}")
        by_uid[uid] = row
    manifest_set = set(uids)
    metadata_set = set(by_uid)
    if manifest_set != metadata_set:
        raise ValueError(
            f"UID/metadata mismatch: manifest-only={len(manifest_set-metadata_set)}, "
            f"metadata-only={len(metadata_set-manifest_set)}"
        )
    return [by_uid[uid] for uid in uids], source_names


def sqlite_rows(db: Path, sql: str, params: tuple[Any, ...]) -> list[dict[str, Any]]:
    conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    try:
        return [dict(row) for row in conn.execute(sql, params)]
    finally:
        conn.close()


def dataset_metadata(snapshot_db: Path, short_title: str) -> dict[str, Any]:
    rows = sqlite_rows(
        snapshot_db,
        "SELECT * FROM agent_datasets WHERE lower(short_title)=lower(?) AND hidden=0",
        (short_title,),
    )
    if len(rows) != 1:
        raise ValueError(f"Expected one visible dataset for {short_title}, found {len(rows)}")
    return rows[0]


def first_release_date(snapshot_db: Path, short_title: str) -> str:
    rows = sqlite_rows(
        snapshot_db,
        "SELECT v1_release_date FROM agent_dataset_v1_releases WHERE lower(short_title)=lower(?) LIMIT 1",
        (short_title,),
    )
    return str(rows[0].get("v1_release_date") or "") if rows else ""


def snapshot_provenance(snapshot_db: Path) -> tuple[str, str]:
    values = sqlite_rows(snapshot_db, "SELECT key, value FROM snapshot_meta", ())
    meta: dict[str, Any] = {}
    for row in values:
        value = row["value"]
        if isinstance(value, str):
            try:
                value = json.loads(value)
            except json.JSONDecodeError:
                pass
        meta[str(row["key"])] = value
    manifest_path = snapshot_db.with_name("tcia_snapshot_manifest.json")
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        meta = {**manifest, **{key: value for key, value in meta.items() if value not in (None, "")}}
    return str(meta.get("content_sha256") or sha256_path(snapshot_db)), str(meta.get("generated_at_utc") or meta.get("created_at") or "")


def absolute_id(root: str, relative_id: str) -> str:
    return f"{root.rstrip('/')}/{relative_id.lstrip('/')}"


def make_recordset(draft: RecordSetDraft, root: str) -> dict[str, Any]:
    rs_id = absolute_id(root, draft.recordset_id)
    csv_id = absolute_id(root, draft.csv_id)
    fields: list[dict[str, Any]] = []
    for spec in draft.fields:
        item = {"@type": "cr:Field", "@id": f"{rs_id}/{spec['name']}"}
        item.update(spec)
        item["source"] = {
            "fileObject": {"@id": csv_id},
            "extract": {"column": spec["name"]},
        }
        fields.append(item)
    for name, value in draft.constant_fields.items():
        fields.append(
            {
                "@type": "cr:Field",
                "@id": f"{rs_id}/{name}",
                "name": name,
                "description": "Constant recordset-level value applied to every record.",
                "dataType": "sc:URL" if name.endswith("Url") else "sc:Text",
                "source": {
                    "fileObject": {"@id": csv_id},
                    "extract": {"column": name},
                },
            }
        )
    additional = [
        property_value("TCIA WordPress download id", draft.download_id),
        property_value("Record grain", draft.record_grain),
        property_value("Retrieval key field", draft.retrieval_key),
        property_value("CSV record count", len(draft.rows)),
        property_value("External CSV model", EXTERNAL_CSV_NOTE),
    ] + draft.additional_properties
    return {
        "@type": "cr:RecordSet",
        "@id": rs_id,
        "name": draft.name,
        "description": draft.description,
        "key": {"@id": f"{rs_id}/{draft.retrieval_key}"},
        "field": fields,
        "conditionsOfAccess": draft.conditions,
        "usageInfo": draft.usage_info,
        "prov:wasDerivedFrom": [source_entity(source) for source in draft.sources],
        "additionalProperty": additional,
    }


def dataset_identifier(dataset: dict[str, Any]) -> str:
    doi = str(dataset.get("doi") or "").strip()
    return f"https://doi.org/{doi}" if doi else f"{str(dataset['link']).rstrip('/')}/#dataset"


def dataset_document(
    dataset: dict[str, Any],
    drafts: list[RecordSetDraft],
    *,
    release_date: str,
    csv_files: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    root = str(dataset["link"]).rstrip("/") + "/croissant/"
    licenses = [draft.license_value for draft in drafts if draft.license_value]
    access_levels = {draft.access_level for draft in drafts}
    access_level = "mixed" if len(access_levels) > 1 else next(iter(access_levels))
    doc: dict[str, Any] = {
        "@context": context(root),
        "@type": "sc:Dataset",
        "@id": dataset_identifier(dataset),
        "conformsTo": CROISSANT_11,
        "name": str(dataset["title"]),
        "alternateName": str(dataset["short_title"]),
        "description": str(dataset.get("summary") or dataset.get("abstract") or dataset["title"]),
        "url": str(dataset["link"]),
        "identifier": dataset_identifier(dataset),
        "license": sorted(set(licenses)) or [TCIA_USAGE],
        "citeAs": dataset_identifier(dataset),
        "dateModified": str(dataset.get("date_updated") or ""),
        "version": str(dataset.get("current_version_number") or "unknown"),
        "sdVersion": "0.2.0-draft",
        "isLiveDataset": True,
        "conditionsOfAccess": conditions(access_level) if access_level != "mixed" else (
            "Mixed open and controlled access. Each RecordSet states its own license, access conditions, "
            "retrieval key, and authorization boundary."
        ),
        "usageInfo": usage_info("controlled" if "controlled" in access_levels else "open", ""),
        "recordSet": [make_recordset(draft, root) for draft in drafts],
        "prov:wasGeneratedBy": {
            "@type": "prov:Activity",
            "name": "TCIA Croissant recordset draft generation",
            "description": "Deterministic projection from explicit TCIA query-skill artifacts and official manifest inputs.",
        },
        "additionalProperty": [
            property_value("Document role", "dataset Croissant with external recordset CSV files"),
            property_value("Recordset count", len(drafts)),
            property_value("External CSV model", EXTERNAL_CSV_NOTE),
        ],
    }
    if release_date:
        doc["datePublished"] = release_date
    distributions = []
    seen_ids: set[str] = set()
    for draft in drafts:
        csv_metadata = csv_files[draft.download_id]
        csv_url = absolute_id(root, draft.csv_id)
        distributions.append(
            {
                "@type": "cr:FileObject",
                "@id": csv_url,
                "name": draft.filename,
                "description": f"Complete tabular inventory for the {draft.name} recordset.",
                "contentUrl": csv_url,
                "encodingFormat": "text/csv",
                "contentSize": f"{csv_metadata['bytes']} B",
                "sha256": csv_metadata["sha256"],
                "license": draft.license_value,
            }
        )
        seen_ids.add(csv_url)
        for distribution in draft.distributions:
            key = str(distribution.get("@id") or distribution.get("contentUrl"))
            if key not in seen_ids:
                seen_ids.add(key)
                distributions.append(distribution)
    if distributions:
        doc["distribution"] = distributions
    return doc


def make_excel_dicom_draft(
    *,
    short_title: str,
    slug: str,
    download_id: str,
    name: str,
    manifest_path: Path,
    metadata_path: Path,
    manifest_url: str,
    metadata_url: str,
    license_value: str,
) -> RecordSetDraft:
    rows, source_names = reconcile_uid_manifest(manifest_path, metadata_path)
    descriptions = {
        "SeriesInstanceUID": "DICOM Series Instance UID and retrieval key for this record.",
        "PatientID": "De-identified patient identifier supplied in the TCIA series metadata workbook.",
        "StudyInstanceUID": "DICOM Study Instance UID.",
        "StudyDate": "Study date retained exactly as supplied; no date shifting or normalization is inferred here.",
        "StudyDescription": "DICOM Study Description retained from the source metadata.",
        "SeriesDescription": "DICOM Series Description retained from the source metadata.",
    }
    return RecordSetDraft(
        dataset_short_title=short_title,
        slug=slug,
        download_id=download_id,
        filename=f"{download_id}-public-dicom-series.csv",
        name=name,
        description="One CSV row per DICOM series. The sparse legacy .tcia UID list is exactly reconciled to the complete official series metadata workbook.",
        record_grain="DICOM series",
        retrieval_key="SeriesInstanceUID",
        access_level="open",
        license_value=license_value,
        rows=rows,
        fields=field_specs(rows, source_names, descriptions),
        sources=[
            Source("Legacy TCIA Series UID manifest", manifest_url, manifest_path),
            Source("TCIA series metadata workbook", metadata_url, metadata_path),
        ],
        conditions=conditions("open"),
        usage_info=usage_info("open", license_value),
        constant_fields={"accessLevel": "open", "retrievalRoute": "SeriesInstanceUID"},
        additional_properties=[
            property_value("UID reconciliation status", "exact match"),
            property_value("Legacy manifest UID count", len(rows)),
            property_value("Metadata workbook series count", len(rows)),
        ],
        distributions=[],
    )


def make_pathdb_draft(snapshot_db: Path) -> RecordSetDraft:
    raw = sqlite_rows(
        snapshot_db,
        "SELECT collection, patient_id, slide_id, camic_id, camicroscope_url, wsiimage_url, species, "
        "cancer_type, cancer_location, data_format, modality, protocol, par, magnification, \"update\" AS update_value "
        "FROM agent_pathdb_slides WHERE lower(collection)=lower(?) ORDER BY patient_id, slide_id, wsiimage_url",
        ("HNSCC-mIF-mIHC-comparison",),
    )
    rows, source_names = canonicalize_rows(raw)
    if any(not row.get("imageUrl") for row in rows):
        raise ValueError("PathDB example contains a row without imageUrl")
    snapshot_hash, generated_at = snapshot_provenance(snapshot_db)
    descriptions = {
        "imageUrl": "Direct public image byte URL and retrieval key.",
        "viewerUrl": "Public caMicroscope viewer URL; this is not the payload URL.",
        "PatientID": "Dataset-scoped participant identifier supplied by PathDB metadata.",
    }
    return RecordSetDraft(
        dataset_short_title="HNSCC-mIF-mIHC-comparison",
        slug="hnscc-mif-mihc-comparison",
        download_id="pathdb-images",
        filename="pathdb-images.csv",
        name="PathDB public image files",
        description="One CSV row per directly downloadable PathDB image, with the original PathDB discovery and scientific metadata retained.",
        record_grain="public image file",
        retrieval_key="imageUrl",
        access_level="open",
        license_value="https://creativecommons.org/licenses/by/4.0/",
        rows=rows,
        fields=field_specs(rows, source_names, descriptions),
        sources=[
            Source(
                "TCIA query-skill snapshot PathDB projection",
                "https://github.com/kirbyju/tcia-query-skill/releases/tag/tcia-metadata-v2-latest",
                snapshot_db,
                sha256=snapshot_hash,
                note=f"Snapshot timestamp: {generated_at or 'not recorded'}.",
            )
        ],
        conditions=conditions("open"),
        usage_info=usage_info("open", "https://creativecommons.org/licenses/by/4.0/"),
        constant_fields={"accessLevel": "open", "retrievalRoute": "imageUrl"},
        additional_properties=[],
        distributions=[],
    )


def make_controlled_draft(path: Path) -> RecordSetDraft:
    rows, source_names = csv_rows(path)
    for row in rows:
        if "SeriesInstanceUID" in row:
            row["DICOMSeriesInstanceUID"] = row.pop("SeriesInstanceUID")
    if "SeriesInstanceUID" in source_names:
        source_names["DICOMSeriesInstanceUID"] = source_names.pop("SeriesInstanceUID")
    if any(not str(row.get("drs_uri", "")).startswith("drs://") for row in rows):
        raise ValueError("Controlled example contains a missing or malformed drs_uri")
    descriptions = {
        "drs_uri": (
            "Published GA4GH DRS object identifier and retrieval key. It identifies an object but grants no access; "
            "resolution depends on current authorization and service availability."
        ),
        "dbGaPStudyAccession": "dbGaP study accession governing authorization for the controlled payload.",
        "PatientID": "De-identified dataset-scoped patient identifier in the public metadata manifest.",
        "StudyInstanceUID": "DICOM Study Instance UID from the public controlled-access metadata.",
        "DICOMSeriesInstanceUID": (
            "DICOM Series Instance UID from the public controlled-access metadata. The CSV header is namespaced "
            "so drs_uri remains the only Data Retriever routing column; alternateName retains the source header."
        ),
    }
    accessions = {str(row.get("dbGaPStudyAccession")) for row in rows if row.get("dbGaPStudyAccession")}
    if accessions != {"phs002192"}:
        raise ValueError(f"Unexpected dbGaP accessions: {sorted(accessions)}")
    return RecordSetDraft(
        dataset_short_title="CMB-AML",
        slug="cmb-aml",
        download_id="48107",
        filename="48107-controlled-drs-files.csv",
        name="Controlled head imaging files",
        description="One CSV row per public controlled-access metadata record. Each row retains the published DRS identifier and all original manifest columns.",
        record_grain="controlled DICOM series archive",
        retrieval_key="drs_uri",
        access_level="controlled",
        license_value=TCIA_CONTROLLED,
        rows=rows,
        fields=field_specs(rows, source_names, descriptions),
        sources=[
            Source(
                "TCIA CMB-AML controlled-access metadata manifest",
                "https://www.cancerimagingarchive.net/wp-content/uploads/CMB-AML_drs_metadata_manifest.csv",
                path,
            )
        ],
        conditions=conditions("controlled"),
        usage_info=usage_info("controlled", TCIA_CONTROLLED, "phs002192"),
        constant_fields={
            "accessLevel": "controlled",
            "retrievalRoute": "GA4GH DRS identifier",
            "authorizationAuthority": "dbGaP phs002192",
        },
        additional_properties=[
            property_value("GA4GH DRS specification", GA4GH_DRS),
            property_value("NIH RAS GA4GH documentation", NIH_RAS),
            property_value(
                "GA4GH authentication boundary",
                "NIH RAS and dbGaP support GA4GH Passport-based interoperability in documented NIH/NCBI workflows. "
                "This draft does not claim that the TCIA CTDC route accepts an NIH RAS Passport.",
            ),
        ],
        distributions=[],
    )


def make_saros_assets_draft(public_db: Path) -> RecordSetDraft:
    raw = sqlite_rows(
        public_db,
        "SELECT a.asset_id, a.subject_id, a.subject_id_namespace, a.participant_link_status, "
        "a.asset_granularity, a.asset_name, a.file_name, a.package_path, a.file_format, a.container_format, "
        "a.media_kind, a.spatial_dimensionality, a.temporal_dimensionality, a.imaging_domain, a.modality, "
        "a.object_role, a.represented_file_count, a.size_bytes, a.checksum, a.checksum_algorithm, "
        "a.representation_provenance_class, a.source_system, a.source_record_id, a.source_url, "
        "a.raw_values_json, a.provenance_json, a.quality_flag_json, m.metadata_json, "
        "m.field_source_ids_json, m.field_provenance_json, m.conflicting_values_json, "
        "m.populated_field_count, m.conflict_field_count "
        "FROM public_non_dicom_assets a LEFT JOIN public_non_dicom_image_metadata m ON m.asset_id=a.asset_id "
        "WHERE a.short_title='SAROS' AND a.asset_granularity='file' ORDER BY a.package_path, a.asset_id",
        (),
    )
    rows, source_names = canonicalize_rows(raw)
    descriptions = {
        "asset_id": "Stable TCIA V2 logical-asset identifier and record key.",
        "package_path": "Exact member path within the published SAROS ZIP archive.",
        "PatientID": "Dataset-scoped participant identifier supported by the source inventory.",
        "representation_provenance_class": "Relationship of this logical asset to the representation supplied by the source.",
    }
    archive_url = "https://www.cancerimagingarchive.net/wp-content/uploads/SAROS-Collection-NIfTI-files-v2_03-70-2024.zip"
    return RecordSetDraft(
        dataset_short_title="SAROS",
        slug="saros",
        download_id="46289",
        filename="46289-segmentation-files.csv",
        name="SAROS segmentation archive members",
        description="One CSV row per NIfTI segmentation member in the published SAROS ZIP, retaining V2 asset metadata and provenance.",
        record_grain="archive member",
        retrieval_key="asset_id",
        access_level="open",
        license_value="https://creativecommons.org/licenses/by/4.0/",
        rows=rows,
        fields=field_specs(rows, source_names, descriptions),
        sources=[Source("TCIA V2 public non-DICOM metadata", "https://github.com/kirbyju/tcia-query-skill/releases/tag/tcia-metadata-v2-latest", public_db)],
        conditions=conditions("open"),
        usage_info=usage_info("open", "https://creativecommons.org/licenses/by/4.0/"),
        constant_fields={"accessLevel": "open", "retrievalRoute": "ZIP archive member", "packageUrl": archive_url},
        additional_properties=[],
        distributions=[
            {
                "@type": "cr:FileObject",
                "@id": "recordsets/46289/archive",
                "name": "SAROS segmentation ZIP archive",
                "contentUrl": archive_url,
                "encodingFormat": "application/zip",
                "license": "https://creativecommons.org/licenses/by/4.0/",
            }
        ],
    )


def make_csv_draft(
    *,
    short_title: str,
    slug: str,
    download_id: str,
    name: str,
    path: Path,
    url: str,
    license_value: str,
    key_candidates: list[str],
) -> RecordSetDraft:
    rows, source_names = csv_rows(path)
    key = next((candidate for candidate in key_candidates if all(row.get(candidate) for row in rows)), "")
    if not key:
        raise ValueError(f"No complete key found in {path}; candidates={key_candidates}")
    return RecordSetDraft(
        dataset_short_title=short_title,
        slug=slug,
        download_id=download_id,
        filename=f"{download_id}-data-records.csv",
        name=name,
        description="One generated CSV row per source CSV row, retaining all published columns.",
        record_grain="source CSV row",
        retrieval_key=key,
        access_level="open",
        license_value=license_value,
        rows=rows,
        fields=field_specs(rows, source_names),
        sources=[Source(name, url, path)],
        conditions=conditions("open"),
        usage_info=usage_info("open", license_value),
        constant_fields={"accessLevel": "open", "retrievalRoute": "direct CSV"},
        additional_properties=[],
        distributions=[],
    )


def make_cmb_aspera_draft(public_db: Path) -> RecordSetDraft:
    raw = sqlite_rows(
        public_db,
        "SELECT asset_id, subject_id, subject_id_namespace, participant_link_status, asset_name, file_name, "
        "package_path, file_format, container_format, media_kind, spatial_dimensionality, temporal_dimensionality, "
        "imaging_domain, modality, object_role, represented_file_count, size_bytes, checksum, checksum_algorithm, "
        "representation_provenance_class, source_system, source_record_id, source_url, raw_values_json, "
        "provenance_json, quality_flag_json FROM public_non_dicom_assets "
        "WHERE short_title='CMB-AML' AND download_id='41647' AND asset_granularity='file' "
        "AND source_system='tcia_aspera' ORDER BY package_path, asset_id",
        (),
    )
    rows, source_names = canonicalize_rows(raw)
    handoff = (
        "https://faspex.cancerimagingarchive.net/?context=eyJyZXNvdXJjZSI6InBhY2thZ2VzIiwidHlwZSI6"
        "ImV4dGVybmFsX2Rvd25sb2FkX3BhY2thZ2UiLCJpZCI6IjEzMDYiLCJwYXNzY29kZSI6IjRlNTc0MWUxNzI3"
        "OTA1OTUwMmM1ZWRjOTZmN2EyNTAwNmRjNDJhOGUiLCJwYWNrYWdlX2lkIjoiMTMwNiIsImVtYWlsIjoiaGVsc"
        "EBjYW5jZXJpbWFnaW5nYXJjaGl2ZS5uZXQifQ=="
    )
    return RecordSetDraft(
        dataset_short_title="CMB-AML",
        slug="cmb-aml",
        download_id="41647",
        filename="41647-aspera-pathology-files.csv",
        name="Original pathology package inventory",
        description="Inventoried submitted-original pathology files delivered through the TCIA Aspera package. PathDB representations are intentionally not substituted or asserted byte-equivalent.",
        record_grain="submitted-original package member",
        retrieval_key="asset_id",
        access_level="open",
        license_value="https://creativecommons.org/licenses/by/4.0/",
        rows=rows,
        fields=field_specs(rows, source_names),
        sources=[Source("TCIA V2 public non-DICOM metadata", "https://github.com/kirbyju/tcia-query-skill/releases/tag/tcia-metadata-v2-latest", public_db)],
        conditions=conditions("open"),
        usage_info=usage_info("open", "https://creativecommons.org/licenses/by/4.0/"),
        constant_fields={"accessLevel": "open", "retrievalRoute": "Aspera package", "transferHandoffUrl": handoff},
        additional_properties=[
            property_value("WordPress reported images", 67),
            property_value("File-grain submitted-original inventory rows", len(rows)),
            property_value("Coverage status", "partial inventory; do not infer missing rows or substitute PathDB representations"),
        ],
        distributions=[],
    )


def write_json(path: Path, value: Any) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    body = json.dumps(value, indent=2, ensure_ascii=False, sort_keys=False) + "\n"
    path.write_text(body, encoding="utf-8")
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def csv_cell(value: Any) -> Any:
    if value is None:
        return ""
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return value


def write_recordset_csv(path: Path, draft: RecordSetDraft) -> dict[str, Any]:
    path.parent.mkdir(parents=True, exist_ok=True)
    field_names = [str(spec["name"]) for spec in draft.fields] + list(draft.constant_fields)
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=field_names, lineterminator="\n")
        writer.writeheader()
        for row in draft.rows:
            complete_row = {name: csv_cell(row.get(name)) for name in field_names}
            complete_row.update({name: csv_cell(value) for name, value in draft.constant_fields.items()})
            writer.writerow(complete_row)
    return {"sha256": sha256_path(path), "bytes": path.stat().st_size}


def write_dataset_group(
    out: Path,
    snapshot_db: Path,
    short_title: str,
    drafts: list[RecordSetDraft],
    summary: dict[str, Any],
) -> None:
    dataset = dataset_metadata(snapshot_db, short_title)
    release_date = first_release_date(snapshot_db, short_title)
    group = out / ("analysis-results" if dataset["dataset_type"] == "Analysis Result" else "collections") / str(dataset["slug"])
    csv_files: dict[str, dict[str, Any]] = {}
    for draft in drafts:
        path = group / "recordsets" / draft.filename
        csv_metadata = write_recordset_csv(path, draft)
        csv_files[draft.download_id] = csv_metadata
        summary["files"][str(path.relative_to(out))] = {
            **csv_metadata,
            "recordsets": 1,
            "records": len(draft.rows),
            "role": "recordset_csv",
            "retrieval_key": draft.retrieval_key,
        }
    document = dataset_document(dataset, drafts, release_date=release_date, csv_files=csv_files)
    path = group / "croissant.jsonld"
    file_digest = write_json(path, document)
    summary["files"][str(path.relative_to(out))] = {
        "sha256": file_digest,
        "recordsets": len(drafts),
        "records": sum(len(draft.rows) for draft in drafts),
        "role": "dataset_croissant",
    }


def build(args: argparse.Namespace) -> dict[str, Any]:
    snapshot_db = args.snapshot_db.resolve()
    public_db = args.public_non_dicom_db.resolve()
    out = args.out.resolve()
    if out.exists() and any(out.iterdir()):
        raise ValueError(f"Output directory must be empty or absent: {out}")

    four_d = make_excel_dicom_draft(
        short_title="4D-Lung",
        slug="4d-lung",
        download_id="42107",
        name="Images and Radiation Therapy Structures",
        manifest_path=args.four_d_lung_manifest.resolve(),
        metadata_path=args.four_d_lung_metadata.resolve(),
        manifest_url="https://www.cancerimagingarchive.net/wp-content/uploads/doiJNLP-Y71kLpdQ.tcia",
        metadata_url="https://www.cancerimagingarchive.net/wp-content/uploads/doiJNLP-Y71kLpdQ-nbia-digest.xlsx",
        license_value="https://creativecommons.org/licenses/by/3.0/",
    )
    cmb_open = make_excel_dicom_draft(
        short_title="CMB-AML",
        slug="cmb-aml",
        download_id="48105",
        name="Public radiology images",
        manifest_path=args.cmb_public_manifest.resolve(),
        metadata_path=args.cmb_public_metadata.resolve(),
        manifest_url="https://www.cancerimagingarchive.net/wp-content/uploads/CMB-AML_v09_20260702.tcia",
        metadata_url="https://www.cancerimagingarchive.net/wp-content/uploads/CMB-AML_v09_20260702-nbia-digest.xlsx",
        license_value="https://creativecommons.org/licenses/by/4.0/",
    )
    controlled = make_controlled_draft(args.cmb_controlled_manifest.resolve())
    cmb_aspera = make_cmb_aspera_draft(public_db)
    pathdb = make_pathdb_draft(snapshot_db)
    saros_assets = make_saros_assets_draft(public_db)
    saros_info = make_csv_draft(
        short_title="SAROS",
        slug="saros",
        download_id="46291",
        name="SAROS segmentation information",
        path=args.saros_info.resolve(),
        url="https://www.cancerimagingarchive.net/wp-content/uploads/Segmentation-Info_09-29-2023.csv",
        license_value="https://creativecommons.org/licenses/by/4.0/",
        key_candidates=["id", "tcia_series_instance_uid"],
    )

    snapshot_hash, snapshot_generated = snapshot_provenance(snapshot_db)
    summary: dict[str, Any] = {
        "generator": "generate_recordset_examples.py",
        "generator_version": "0.3.0-draft",
        "generated_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "croissant_conforms_to": CROISSANT_11,
        "record_storage": "external_csv_fileobjects",
        "record_storage_note": EXTERNAL_CSV_NOTE,
        "source_snapshot": {
            "path": snapshot_db.name,
            "content_sha256": snapshot_hash,
            "generated_at_utc": snapshot_generated,
        },
        "source_artifacts": {},
        "files": {},
    }
    for path in (
        args.four_d_lung_manifest,
        args.four_d_lung_metadata,
        args.cmb_public_manifest,
        args.cmb_public_metadata,
        args.cmb_controlled_manifest,
        args.saros_info,
        public_db,
    ):
        resolved = path.resolve()
        summary["source_artifacts"][resolved.name] = {"sha256": sha256_path(resolved), "bytes": resolved.stat().st_size}

    write_dataset_group(out, snapshot_db, "4D-Lung", [four_d], summary)
    write_dataset_group(out, snapshot_db, "HNSCC-mIF-mIHC-comparison", [pathdb], summary)
    write_dataset_group(out, snapshot_db, "CMB-AML", [cmb_open, controlled, cmb_aspera], summary)
    write_dataset_group(out, snapshot_db, "SAROS", [saros_assets, saros_info], summary)
    write_json(out / "generation-summary.json", summary)
    return summary


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(description=__doc__)
    value.add_argument("--snapshot-db", type=Path, required=True)
    value.add_argument("--public-non-dicom-db", type=Path, required=True)
    value.add_argument("--four-d-lung-manifest", type=Path, required=True)
    value.add_argument("--four-d-lung-metadata", type=Path, required=True)
    value.add_argument("--cmb-public-manifest", type=Path, required=True)
    value.add_argument("--cmb-public-metadata", type=Path, required=True)
    value.add_argument("--cmb-controlled-manifest", type=Path, required=True)
    value.add_argument("--saros-info", type=Path, required=True)
    value.add_argument("--out", type=Path, default=Path("examples/recordset-manifests"))
    return value


def main() -> int:
    args = parser().parse_args()
    summary = build(args)
    print(json.dumps({"files": len(summary["files"]), "out": str(args.out.resolve())}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
