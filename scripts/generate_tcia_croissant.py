#!/usr/bin/env python3
"""Generate prototype Croissant JSON-LD files from a TCIA snapshot SQLite DB."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import html
import json
import re
import sqlite3
import sys
import urllib.parse
import zipfile
from html.parser import HTMLParser
from pathlib import Path
from typing import Any


DEFAULT_DB = Path("cache/tcia_snapshot.sqlite")
DEFAULT_OUT = Path("croissant-output")
TCIA_DATA_USAGE_POLICY_URL = "https://www.cancerimagingarchive.net/data-usage-policies-and-restrictions/"
TCIA_CONTROLLED_ACCESS_POLICY_URL = "https://www.cancerimagingarchive.net/nih-controlled-data-access-policy/"
TCIA_ORG_URL = "https://www.cancerimagingarchive.net/"
CROISSANT_CONFORMS_TO = "http://mlcommons.org/croissant/1.1"
GENERATOR_VERSION = "tcia-croissant-prototype/0.1.0"


class _HTMLTextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        if data:
            self.parts.append(data)

    def text(self) -> str:
        return " ".join(self.parts)


def clean_text(value: Any) -> str:
    if value is None or value is False:
        return ""
    if isinstance(value, (list, tuple)):
        return "; ".join(clean_text(item) for item in value if clean_text(item))
    if isinstance(value, dict):
        return clean_text(value.get("text") or value.get("label") or value.get("url") or "")
    text = html.unescape(str(value))
    if "<" in text and ">" in text:
        parser = _HTMLTextExtractor()
        parser.feed(text)
        text = parser.text()
    return re.sub(r"\s+", " ", text).strip()


def as_list(value: Any) -> list[str]:
    if value in (None, False, ""):
        return []
    if isinstance(value, str):
        if value.startswith("["):
            try:
                return as_list(json.loads(value))
            except json.JSONDecodeError:
                pass
        parts = [part.strip() for part in re.split(r";|\|", value) if part.strip()]
        return parts or [value.strip()]
    if isinstance(value, dict):
        label = clean_text(value.get("label") or value.get("name") or value.get("url"))
        return [label] if label else []
    if isinstance(value, (list, tuple, set)):
        items: list[str] = []
        for item in value:
            if item in (None, False, ""):
                continue
            items.extend(as_list(item))
        return dedupe(items)
    return [clean_text(value)]


def dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    output: list[str] = []
    for value in values:
        cleaned = clean_text(value)
        key = cleaned.casefold()
        if cleaned and key not in seen:
            seen.add(key)
            output.append(cleaned)
    return output


def doi_url(doi: str) -> str:
    cleaned = doi.strip()
    if not cleaned:
        return ""
    if cleaned.lower().startswith("https://doi.org/"):
        return cleaned
    return f"https://doi.org/{cleaned}"


def slugify(value: str, fallback: str = "dataset") -> str:
    slug = re.sub(r"[^A-Za-z0-9._-]+", "-", value.strip()).strip("-._")
    return slug or fallback


def lower_text(*values: Any) -> str:
    return " ".join(clean_text(value) for value in values).casefold()


def license_url_from_label(label: str) -> str:
    text = label.casefold()
    if "cc by-nc-sa" in text or "cc-by-nc-sa" in text:
        return "https://creativecommons.org/licenses/by-nc-sa/4.0/"
    if "cc by-nc" in text or "cc-by-nc" in text or "noncommercial" in text:
        return "https://creativecommons.org/licenses/by-nc/4.0/"
    if "cc by 4.0" in text or "cc-by-4.0" in text:
        return "https://creativecommons.org/licenses/by/4.0/"
    if "cc by 3.0" in text or "cc-by-3.0" in text:
        return "https://creativecommons.org/licenses/by/3.0/"
    if "nih controlled" in text or "controlled data access" in text:
        return TCIA_CONTROLLED_ACCESS_POLICY_URL
    return ""


def normalize_license(value: Any) -> tuple[str, str]:
    if isinstance(value, dict):
        label = clean_text(value.get("label") or value.get("name") or value.get("text"))
        url = clean_text(value.get("url") or value.get("@id"))
        return label, url or license_url_from_label(label)
    label = clean_text(value)
    return label, license_url_from_label(label)


def access_level_for_download(download: dict[str, Any], label: str, url: str) -> str:
    text = lower_text(label, url, download.get("requirements"), download.get("download requirements"))
    if download.get("controlled_access") is True:
        return "controlled"
    if any(term in text for term in ["nih controlled", "controlled data access", "restricted", "dbgap"]):
        return "controlled"
    if any(term in text for term in ["noncommercial", "by-nc", "by nc"]):
        return "open_noncommercial"
    if any(term in text for term in ["creative commons", "cc by", "cc-by"]):
        return "open"
    if not label and not url:
        return "unknown"
    return "review_needed"


def get_first(record: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in record and record[key] not in (None, ""):
            return record[key]
    return ""


def normalize_download(download: dict[str, Any], index: int) -> dict[str, Any]:
    license_label, license_url = normalize_license(get_first(download, "license", "license_label"))
    requirements = get_first(download, "download requirements", "requirements", "download_requirements")
    req_label = ""
    req_url = ""
    req_text = ""
    if isinstance(requirements, dict):
        req_label = clean_text(requirements.get("label"))
        req_url = clean_text(requirements.get("url"))
        req_text = clean_text(requirements.get("text"))
    else:
        req_text = clean_text(requirements)

    download_id = clean_text(get_first(download, "id", "download_id")) or f"row-{index + 1}"
    url = clean_text(get_first(download, "download url", "download_url", "url"))
    title = clean_text(get_first(download, "title", "download title", "download_title"))
    metadata_url = clean_text(get_first(download, "download metadata", "download_metadata"))
    size = clean_text(get_first(download, "download size", "download_size"))
    size_unit = clean_text(get_first(download, "download size unit", "download_size_unit"))
    data_types = as_list(get_first(download, "data type", "data_types"))
    file_types = as_list(get_first(download, "file type", "file_types"))
    download_types = as_list(get_first(download, "download type", "download_types"))
    external_resources = as_list(get_first(download, "external_resources", "external resources"))
    description = clean_text(get_first(download, "description"))
    access_level = access_level_for_download(download, license_label, license_url)

    return {
        "id": download_id,
        "title": title,
        "url": url,
        "metadata_url": metadata_url,
        "description": description,
        "license_label": license_label,
        "license_url": license_url,
        "requirements_label": req_label,
        "requirements_url": req_url,
        "requirements_text": req_text,
        "download_size": size,
        "download_size_unit": size_unit,
        "download_types": download_types,
        "data_types": data_types,
        "file_types": file_types,
        "external_resources": external_resources,
        "subjects": clean_text(get_first(download, "subjects")),
        "studies": clean_text(get_first(download, "studies")),
        "series": clean_text(get_first(download, "series")),
        "images": clean_text(get_first(download, "images")),
        "collection_status": clean_text(get_first(download, "collection status", "collection_status")),
        "date_updated": clean_text(get_first(download, "date updated", "date_updated")),
        "access_level": access_level,
        "raw": download,
    }


def parse_json(text: str | None, default: Any) -> Any:
    if not text:
        return default
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return default


def load_meta(conn: sqlite3.Connection) -> dict[str, Any]:
    meta: dict[str, Any] = {}
    for row in conn.execute("SELECT key, value FROM snapshot_meta ORDER BY key"):
        meta[row["key"]] = parse_json(row["value"], row["value"])
    return meta


def load_datacite(conn: sqlite3.Connection) -> dict[str, dict[str, Any]]:
    datacite: dict[str, dict[str, Any]] = {}
    try:
        rows = conn.execute(
            "SELECT doi, tcia_short_name, title, publisher, publication_year, version, created, url, normalized_json "
            "FROM datacite_dois"
        )
    except sqlite3.OperationalError:
        return datacite
    for row in rows:
        normalized = parse_json(row["normalized_json"], {})
        record = {
            "doi": row["doi"] or normalized.get("doi", ""),
            "tcia_short_name": row["tcia_short_name"] or normalized.get("tcia_short_name", ""),
            "title": row["title"] or normalized.get("title", ""),
            "publisher": row["publisher"] or normalized.get("publisher", ""),
            "publication_year": row["publication_year"] or normalized.get("publication_year", ""),
            "version": row["version"] or normalized.get("version", ""),
            "created": row["created"] or normalized.get("created", ""),
            "url": row["url"] or normalized.get("url", ""),
            "normalized": normalized,
        }
        short_name = clean_text(record["tcia_short_name"])
        if short_name:
            datacite[short_name.casefold()] = record
    return datacite


def download_key_for_source(source: str) -> str:
    return "collection_downloads" if source == "collections" else "result_downloads"


def dataset_type_for_source(source: str) -> str:
    if source == "collections":
        return "Collection"
    if source == "analysis-results":
        return "Analysis Result"
    return source


def short_description(normalized: dict[str, Any], raw: dict[str, Any], title: str) -> str:
    for key in ("summary", "abstract", "detailed_description", "description"):
        text = clean_text(normalized.get(key) or raw.get(key))
        if text:
            return text
    return f"TCIA metadata record for {title}."


def citation_text(raw: dict[str, Any], datacite: dict[str, Any], title: str, doi: str) -> str:
    for citation in raw.get("citations") or []:
        if clean_text(citation.get("type")).casefold() == "data citation":
            text = clean_text(citation.get("statement") or citation.get("html"))
            if text:
                return text
    year = clean_text(datacite.get("publication_year")) or "n.d."
    url = doi_url(doi)
    if url:
        return f"{title}. The Cancer Imaging Archive. {year}. {url}"
    return f"{title}. The Cancer Imaging Archive. {year}."


def publication_citations(raw: dict[str, Any]) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for citation in raw.get("citations") or []:
        citation_type = clean_text(citation.get("type"))
        if citation_type == "Data Citation":
            continue
        doi = clean_text(citation.get("doi"))
        text = clean_text(citation.get("statement") or citation.get("html"))
        item: dict[str, Any] = {"@type": "CreativeWork"}
        if text:
            item["name"] = text
        if doi:
            item["identifier"] = doi
            item["url"] = doi_url(doi)
        if item.keys() != {"@type"}:
            output.append(item)
    return output


def context() -> dict[str, Any]:
    return {
        "@language": "en",
        "@vocab": "https://schema.org/",
        "arrayShape": "cr:arrayShape",
        "citeAs": "cr:citeAs",
        "column": "cr:column",
        "conformsTo": "dct:conformsTo",
        "containedIn": "cr:containedIn",
        "cr": "http://mlcommons.org/croissant/",
        "rai": "http://mlcommons.org/croissant/RAI/",
        "data": {"@id": "cr:data", "@type": "@json"},
        "dataType": {"@id": "cr:dataType", "@type": "@vocab"},
        "dct": "http://purl.org/dc/terms/",
        "description": {"@container": "@language"},
        "equivalentProperty": "cr:equivalentProperty",
        "examples": {"@id": "cr:examples", "@type": "@json"},
        "extract": "cr:extract",
        "field": "cr:field",
        "fileProperty": "cr:fileProperty",
        "fileObject": "cr:fileObject",
        "fileSet": "cr:fileSet",
        "format": "cr:format",
        "includes": "cr:includes",
        "isArray": "cr:isArray",
        "isLiveDataset": "cr:isLiveDataset",
        "jsonPath": "cr:jsonPath",
        "key": "cr:key",
        "md5": "cr:md5",
        "name": {"@container": "@language"},
        "parentField": "cr:parentField",
        "path": "cr:path",
        "recordSet": "cr:recordSet",
        "references": "cr:references",
        "regex": "cr:regex",
        "repeated": "cr:repeated",
        "replace": "cr:replace",
        "samplingRate": "cr:samplingRate",
        "sc": "https://schema.org/",
        "separator": "cr:separator",
        "source": "cr:source",
        "subField": "cr:subField",
        "transform": "cr:transform",
        "odrl": "http://www.w3.org/ns/odrl/2/",
        "sdVersion": "cr:sdVersion",
    }


def organization() -> dict[str, str]:
    return {"@type": "Organization", "name": "The Cancer Imaging Archive", "url": TCIA_ORG_URL}


def policy_usage_info(access_level: str, license_label: str = "", license_url: str = "") -> list[dict[str, Any]]:
    usage: list[dict[str, Any]] = [
        {
            "@type": "CreativeWork",
            "@id": TCIA_DATA_USAGE_POLICY_URL,
            "name": "TCIA Data Usage Policies and Restrictions",
            "url": TCIA_DATA_USAGE_POLICY_URL,
        }
    ]
    if access_level == "controlled":
        usage.append(
            {
                "@type": ["CreativeWork", "odrl:Offer"],
                "@id": TCIA_CONTROLLED_ACCESS_POLICY_URL,
                "name": "TCIA NIH Controlled Data Access Policy",
                "url": TCIA_CONTROLLED_ACCESS_POLICY_URL,
                "description": "Access requires authorization under the TCIA NIH Controlled Data Access Policy.",
                "odrl:permission": {
                    "@type": "odrl:Permission",
                    "odrl:action": {"@id": "odrl:use", "name": "Use"},
                    "odrl:duty": {
                        "@type": "odrl:Duty",
                        "odrl:action": {"@id": "odrl:obtainConsent", "name": "Obtain required access approval"},
                    },
                },
            }
        )
    elif access_level == "open_noncommercial":
        usage.append(
            {
                "@type": ["CreativeWork", "odrl:Offer"],
                "name": "Noncommercial use condition",
                "description": f"{license_label or 'This license'} includes a noncommercial-use condition.",
                "odrl:permission": {
                    "@type": "odrl:Permission",
                    "odrl:action": {"@id": "odrl:use", "name": "Use"},
                    "odrl:constraint": {
                        "@type": "odrl:Constraint",
                        "name": "Non-commercial use only",
                        "odrl:operator": {"@id": "odrl:eq"},
                        "odrl:rightOperand": "noncommercial",
                    },
                },
            }
        )
    if license_url:
        usage.append({"@type": "CreativeWork", "@id": license_url, "name": license_label or license_url, "url": license_url})
    return usage


def file_name_from_url(url: str, fallback: str) -> str:
    if not url:
        return fallback
    parsed = urllib.parse.urlparse(url)
    name = urllib.parse.unquote(Path(parsed.path).name)
    return name or fallback


def encoding_formats(url: str, file_types: list[str]) -> list[str]:
    suffix = Path(urllib.parse.urlparse(url).path).suffix.casefold()
    by_suffix = {
        ".csv": ["text/csv"],
        ".tsv": ["text/tab-separated-values"],
        ".xlsx": ["application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"],
        ".xls": ["application/vnd.ms-excel"],
        ".zip": ["application/zip"],
        ".json": ["application/json"],
        ".pdf": ["application/pdf"],
        ".tcia": ["text/plain", "application/vnd.tcia.manifest"],
        ".nii": ["application/vnd.nifti"],
        ".gz": ["application/gzip"],
        ".svs": ["image/tiff"],
        ".tif": ["image/tiff"],
        ".tiff": ["image/tiff"],
        ".dcm": ["application/dicom"],
    }
    formats = list(by_suffix.get(suffix, []))
    if formats:
        return dedupe(formats)
    for file_type in file_types:
        key = file_type.casefold()
        if key == "dicom":
            formats.append("application/dicom")
        elif key == "csv":
            formats.append("text/csv")
        elif key == "tsv":
            formats.append("text/tab-separated-values")
        elif key == "xlsx":
            formats.append("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        elif key == "zip":
            formats.append("application/zip")
        elif key == "json":
            formats.append("application/json")
        elif key == "pdf":
            formats.append("application/pdf")
        elif key in {"svs", "tiff", "tif"}:
            formats.append("image/tiff")
        elif key == "nifti":
            formats.append("application/vnd.nifti")
    return dedupe(formats) or ["application/octet-stream"]


def access_mechanism(download: dict[str, Any]) -> str:
    text = lower_text(
        download.get("requirements_label"),
        download.get("requirements_text"),
        download.get("requirements_url"),
    )
    if "aspera" in text or "faspex" in text:
        return "Aspera"
    if "data retriever" in text:
        return "TCIA Data Retriever"
    if not download.get("url"):
        return "metadata only"
    return "direct download"


def download_artifact_role(download: dict[str, Any]) -> str:
    mechanism = access_mechanism(download)
    url = download.get("url", "")
    if not url:
        return "metadata only"
    if mechanism == "TCIA Data Retriever":
        return "manifest"
    if mechanism == "Aspera":
        return "transfer package"
    return "data file"


def content_size(download: dict[str, Any]) -> str:
    size = download.get("download_size", "")
    unit = download.get("download_size_unit", "")
    if not size:
        return ""
    return f"{size} {unit.upper()}".strip()


def property_value(name: str, value: Any) -> dict[str, Any] | None:
    if value in (None, "", [], {}):
        return None
    return {"@type": "PropertyValue", "name": name, "value": value}


def add_if_present(target: dict[str, Any], key: str, value: Any) -> None:
    if value not in (None, "", [], {}):
        target[key] = value


def file_object(download: dict[str, Any], file_id: str, fallback_name: str) -> dict[str, Any]:
    license_value = download["license_url"] or download["license_label"]
    name = download["title"] or file_name_from_url(download["url"], fallback_name)
    item: dict[str, Any] = {
        "@type": "cr:FileObject",
        "@id": file_id,
        "name": name,
        "contentUrl": download["url"],
        "encodingFormat": encoding_formats(download["url"], download["file_types"]),
        "usageInfo": policy_usage_info(download["access_level"], download["license_label"], download["license_url"]),
    }
    add_if_present(item, "description", download["description"])
    add_if_present(item, "contentSize", content_size(download))
    add_if_present(item, "license", license_value)
    add_if_present(item, "dateModified", download["date_updated"])
    additional = [
        property_value("TCIA download id", download["id"]),
        property_value("TCIA access level", download["access_level"]),
        property_value("TCIA download types", download["download_types"]),
        property_value("TCIA data types", download["data_types"]),
        property_value("TCIA file types", download["file_types"]),
        property_value("TCIA download artifact role", download_artifact_role(download)),
        property_value("TCIA access mechanism", access_mechanism(download)),
        property_value("TCIA download metadata", download["metadata_url"]),
        property_value("TCIA download requirements", download["requirements_text"] or download["requirements_label"]),
    ]
    properties = [entry for entry in additional if entry]
    if properties:
        item["additionalProperty"] = properties
    return item


def field(recordset_id: str, name: str, data_type: str, is_array: bool = False) -> dict[str, Any]:
    item: dict[str, Any] = {"@type": "cr:Field", "@id": f"{recordset_id}/{name}", "dataType": data_type}
    if is_array:
        item["isArray"] = True
    return item


def int_value(value: str) -> int | None:
    if not value:
        return None
    try:
        return int(float(value.replace(",", "")))
    except ValueError:
        return None


def recordset(download: dict[str, Any], recordset_id: str, file_id: str | None, dataset_short_title: str) -> dict[str, Any]:
    name_parts = [
        download["title"],
        "; ".join(download["download_types"]),
        "; ".join(download["data_types"]),
        "; ".join(download["file_types"]),
    ]
    name = next((part for part in name_parts if part), f"Download {download['id']}")
    fields: list[dict[str, Any]] = []
    inline_record: dict[str, Any] = {}

    def add_field(name: str, data_type: str, value: Any, is_array: bool = False) -> None:
        fields.append(field(recordset_id, name, data_type, is_array=is_array))
        inline_record[f"{recordset_id}/{name}"] = value

    add_field("download_id", "sc:Text", download["id"])
    if download["url"]:
        add_field("download_url", "sc:URL", download["url"])
    if file_id:
        add_field("file_object_id", "sc:Text", file_id)
    add_field("download_types", "sc:Text", download["download_types"], is_array=True)
    add_field("data_types", "sc:Text", download["data_types"], is_array=True)
    add_field("file_types", "sc:Text", download["file_types"], is_array=True)
    add_field("download_artifact_role", "sc:Text", download_artifact_role(download))
    add_field("access_mechanism", "sc:Text", access_mechanism(download))
    add_field("access_level", "sc:Text", download["access_level"])
    add_field("license_label", "sc:Text", download["license_label"])
    if download["license_url"]:
        add_field("license_url", "sc:URL", download["license_url"])
    for name_key in ("subjects", "studies", "series", "images"):
        integer = int_value(download[name_key])
        if integer is not None:
            add_field(name_key, "sc:Integer", integer)
    if download["metadata_url"]:
        add_field("download_metadata", "sc:URL", download["metadata_url"])
    if download["requirements_text"] or download["requirements_label"]:
        add_field("download_requirements", "sc:Text", download["requirements_text"] or download["requirements_label"])

    item: dict[str, Any] = {
        "@type": "cr:RecordSet",
        "@id": recordset_id,
        "name": name,
        "description": f"TCIA current download record {download['id']} for {dataset_short_title}.",
        "dataType": "sc:DataDownload",
        "key": {"@id": f"{recordset_id}/download_id"},
        "field": fields,
        "data": [inline_record],
        "usageInfo": policy_usage_info(download["access_level"], download["license_label"], download["license_url"]),
    }
    return item


def dataset_keywords(normalized: dict[str, Any], raw: dict[str, Any], source: str, short_title: str) -> list[str]:
    values: list[str] = [short_title, dataset_type_for_source(source)]
    for key in ("data_types", "cancer_types", "cancer_locations", "species"):
        values.extend(as_list(normalized.get(key) or raw.get(key)))
    return dedupe(values)


def dataset_access_level(normalized: dict[str, Any], downloads: list[dict[str, Any]]) -> str:
    levels = {download["access_level"] for download in downloads}
    if "controlled" in levels and len(levels - {"controlled"}) > 0:
        return "mixed"
    if "controlled" in levels:
        return "controlled"
    if "open_noncommercial" in levels:
        return "open_noncommercial"
    if levels == {"open"}:
        return "open"
    if clean_text(normalized.get("license_status")).casefold() == "open (creative commons)":
        return "open"
    return clean_text(normalized.get("license_status")) or "unknown"


def dataset_licenses(normalized: dict[str, Any], downloads: list[dict[str, Any]]) -> list[str]:
    values: list[str] = []
    for download in downloads:
        values.append(download["license_url"] or download["license_label"])
    if not values:
        for label in as_list(normalized.get("licenses")):
            values.append(license_url_from_label(label) or label)
    return dedupe(values)


def build_document(row: sqlite3.Row, datacite_by_short_title: dict[str, dict[str, Any]]) -> tuple[dict[str, Any], dict[str, Any]]:
    source = row["source"]
    raw = parse_json(row["raw_json"], {})
    normalized = parse_json(row["normalized_json"], {})
    short_title = clean_text(row["short_title"] or normalized.get("short_title") or raw.get("collection_short_title") or raw.get("result_short_title"))
    title = clean_text(row["title"] or normalized.get("title") or raw.get("title") or short_title)
    doi = clean_text(row["doi"] or normalized.get("doi"))
    link = clean_text(row["link"] or normalized.get("link") or raw.get("link"))
    datacite = datacite_by_short_title.get(short_title.casefold(), {})
    downloads = [
        normalize_download(download, index)
        for index, download in enumerate(raw.get(download_key_for_source(source)) or normalized.get("current_downloads") or [])
    ]
    access_level = dataset_access_level(normalized, downloads)
    licenses = dataset_licenses(normalized, downloads)
    distribution: list[dict[str, Any]] = []
    recordsets: list[dict[str, Any]] = []
    for index, download in enumerate(downloads):
        base = slugify(download["id"], f"download-{index + 1}")
        recordset_id = f"download-{base}"
        file_id = None
        if download["url"]:
            file_id = f"file-{base}"
            distribution.append(file_object(download, file_id, f"{short_title}-download-{index + 1}"))
        recordsets.append(recordset(download, recordset_id, file_id, short_title))

    doc: dict[str, Any] = {
        "@context": context(),
        "@type": "sc:Dataset",
        "@id": doi_url(doi) or f"{link.rstrip('/')}/#dataset",
        "conformsTo": CROISSANT_CONFORMS_TO,
        "name": title,
        "description": short_description(normalized, raw, title),
        "url": link,
        "creator": organization(),
        "publisher": organization(),
        "license": licenses or [TCIA_DATA_USAGE_POLICY_URL],
        "citeAs": citation_text(raw, datacite, title, doi),
        "keywords": dataset_keywords(normalized, raw, source, short_title),
        "sdPublisher": organization(),
        "sdVersion": "0.1.0",
        "isLiveDataset": True,
        "usageInfo": policy_usage_info(access_level),
        "distribution": distribution,
        "recordSet": recordsets,
    }
    identifiers = [
        property_value("TCIA short title", short_title),
        property_value("TCIA dataset type", dataset_type_for_source(source)),
    ]
    if doi:
        identifiers.append(property_value("DOI", doi))
        doc["sameAs"] = [doi_url(doi)]
    doc["identifier"] = [entry for entry in identifiers if entry]
    add_if_present(doc, "dateModified", clean_text(row["date_updated"] or normalized.get("date_updated")))
    created = clean_text(datacite.get("created"))
    if created:
        add_if_present(doc, "datePublished", created[:10])
    else:
        add_if_present(doc, "datePublished", clean_text(datacite.get("publication_year")))
    add_if_present(doc, "version", clean_text(datacite.get("version")))
    add_if_present(doc, "citation", publication_citations(raw))
    additional = [
        property_value("TCIA access level", access_level),
        property_value("TCIA license status", normalized.get("license_status")),
        property_value("TCIA subjects", normalized.get("subjects")),
        property_value("TCIA program", normalized.get("program")),
        property_value("Croissant generator", GENERATOR_VERSION),
        property_value("TCIA snapshot schema version", row["schema_version"]),
    ]
    doc["additionalProperty"] = [entry for entry in additional if entry]

    index_entry = {
        "short_title": short_title,
        "dataset_type": dataset_type_for_source(source),
        "title": title,
        "doi": doi,
        "url": link,
        "access_level": access_level,
        "licenses": licenses,
        "download_recordsets": len(recordsets),
    }
    return doc, index_entry


def json_bytes(data: Any) -> bytes:
    return (json.dumps(data, indent=2, ensure_ascii=True) + "\n").encode("utf-8")


def write_json(path: Path, data: Any) -> str:
    payload = json_bytes(data)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)
    return hashlib.sha256(payload).hexdigest()


def create_zip(output_dir: Path, zip_path: Path) -> None:
    files = sorted(path for path in output_dir.rglob("*") if path.is_file() and path != zip_path)
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in files:
            archive.write(path, path.relative_to(output_dir).as_posix())


def generate(db_path: Path, output_dir: Path, include_hidden: bool = False, limit: int | None = None) -> dict[str, Any]:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        meta = load_meta(conn)
        datacite_by_short_title = load_datacite(conn)
        rows = list(
            conn.execute(
                """
                SELECT source, id, slug, short_title, doi, title, link, date_updated, hidden,
                       normalized_json, raw_json, ? AS schema_version
                FROM wordpress_records
                WHERE source IN ('collections', 'analysis-results')
                ORDER BY lower(short_title)
                """,
                (str(meta.get("schema_version", "")),),
            )
        )
    finally:
        conn.close()

    output_dir.mkdir(parents=True, exist_ok=True)
    index_entries: list[dict[str, Any]] = []
    file_entries: list[dict[str, Any]] = []
    written = 0
    for row in rows:
        if row["hidden"] and not include_hidden:
            continue
        doc, index_entry = build_document(row, datacite_by_short_title)
        source_dir = "collections" if row["source"] == "collections" else "analysis-results"
        slug = slugify(row["slug"] or index_entry["short_title"])
        relative = Path(source_dir) / slug / "croissant.jsonld"
        sha256 = write_json(output_dir / relative, doc)
        index_entry["path"] = relative.as_posix()
        index_entry["sha256"] = sha256
        index_entries.append(index_entry)
        file_entries.append({"path": relative.as_posix(), "sha256": sha256})
        written += 1
        if limit is not None and written >= limit:
            break

    manifest = {
        "generated_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "generator": GENERATOR_VERSION,
        "source_sqlite": str(db_path),
        "source_snapshot_meta": meta,
        "include_hidden": include_hidden,
        "dataset_count": len(index_entries),
        "download_recordset_count": sum(entry["download_recordsets"] for entry in index_entries),
        "files": file_entries,
    }
    index = {
        "generated_at_utc": manifest["generated_at_utc"],
        "generator": GENERATOR_VERSION,
        "dataset_count": manifest["dataset_count"],
        "download_recordset_count": manifest["download_recordset_count"],
        "datasets": index_entries,
    }
    write_json(output_dir / "tcia_croissant_index.json", index)
    write_json(output_dir / "tcia_croissant_manifest.json", manifest)
    (output_dir / "README.md").write_text(
        "\n".join(
            [
                "# TCIA Croissant Prototype",
                "",
                "Generated locally from a TCIA query skill SQLite snapshot.",
                "",
                "Mapping notes:",
                "",
                "- One Croissant `sc:Dataset` file is generated for each visible TCIA Collection or Analysis Result.",
                "- Each current TCIA download row is represented as both a `cr:FileObject` in `distribution` and a child `cr:RecordSet` in `recordSet`.",
                "- `encodingFormat` describes the linked download artifact itself. TCIA payload labels such as DICOM are retained separately as `TCIA file types`.",
                "- Manifest/application handoffs are identified with `TCIA download artifact role` and `TCIA access mechanism` metadata.",
                "- Dataset and download-level `usageInfo` include TCIA policy links and lightweight ODRL stubs for controlled or noncommercial access conditions.",
                "- `isLiveDataset` is set to `true` because the snapshot does not contain real file checksums; production TCIA Croissant should prefer stable file SHA-256 values where available.",
                "- The files are a prototype. They are not official TCIA website metadata, DataCite metadata, or legal guidance.",
                "",
                "Start with `tcia_croissant_index.json`, then inspect individual `croissant.jsonld` files under `collections/` or `analysis-results/`.",
                "",
            ]
        ),
        encoding="utf-8",
    )
    create_zip(output_dir, output_dir / "tcia_croissant_jsonld.zip")
    manifest["zip_path"] = "tcia_croissant_jsonld.zip"
    manifest["zip_sha256"] = hashlib.sha256((output_dir / "tcia_croissant_jsonld.zip").read_bytes()).hexdigest()
    write_json(output_dir / "tcia_croissant_manifest.json", manifest)
    return manifest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=DEFAULT_DB, help="Path to tcia_snapshot.sqlite.")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT, help="Output directory for generated Croissant files.")
    parser.add_argument("--include-hidden", action="store_true", help="Include hidden/staged/retired WordPress records.")
    parser.add_argument("--limit", type=int, help="Generate only the first N datasets for testing.")
    args = parser.parse_args(argv)

    if not args.db.exists():
        parser.error(f"SQLite snapshot not found: {args.db}")
    manifest = generate(args.db, args.out, include_hidden=args.include_hidden, limit=args.limit)
    print(
        json.dumps(
            {
                "output_dir": str(args.out.resolve()),
                "dataset_count": manifest["dataset_count"],
                "download_recordset_count": manifest["download_recordset_count"],
                "zip_path": manifest["zip_path"],
                "zip_sha256": manifest["zip_sha256"],
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
