"""Shared semantic metadata mappings for the two prototype exporters."""
import json


def dataset_keywords(dataset):
    """Use supplied labels, never guess ontology identifiers or measured variables."""
    sources = [dataset]
    for key in ("normalized_json", "raw_json"):
        value = dataset.get(key)
        if isinstance(value, str):
            value = json.loads(value)
        if isinstance(value, dict):
            sources.append(value)
    values = [dataset.get("short_title"), dataset.get("dataset_type")]
    for source in sources:
        for key in ("keywords", "cancer_types", "cancer_locations", "species", "data_categories"):
            value = source.get(key)
            if isinstance(value, str):
                if value.startswith("["):
                    value = json.loads(value)
                else:
                    value = [value]
            if isinstance(value, list):
                values.extend(v for v in value if isinstance(v, str))
    return list(dict.fromkeys(v.strip() for v in values if isinstance(v, str) and v.strip()))


def add_metadata_provenance(document):
    """Describe generation of the metadata document, separately from the data."""
    document["@context"]["prov"] = "http://www.w3.org/ns/prov#"
    metadata_url = document["url"].rstrip("/") + "/croissant.jsonld"
    activity_id = metadata_url + "#metadata-generation"
    sources = {}
    for recordset in document.get("recordSet", []):
        for source in recordset.get("prov:wasDerivedFrom", []):
            sources[source["@id"]] = source
        # Recordsets describe generated inventories, rather than scientific data acquisition.
        recordset["prov:wasGeneratedBy"] = {"@id": activity_id}
    sources[document["url"]] = {
        "@id": document["url"], "@type": "prov:Entity",
        "description": "TCIA WordPress metadata record represented in the supplied source snapshot; not a fresh page retrieval.",
    }
    metadata = {
        "@id": metadata_url,
        "@type": ["sc:CreativeWork", "prov:Entity"],
        "name": document.get("alternateName", document["name"]) + " Croissant metadata",
        "url": metadata_url,
        "encodingFormat": "application/ld+json",
        "prov:wasDerivedFrom": list(sources.values()),
        "prov:wasGeneratedBy": {
            "@id": activity_id, "@type": "prov:Activity",
            "name": "TCIA Croissant metadata generation",
            "description": "Projection of supplied TCIA metadata and inventory sources into Croissant. This activity does not describe acquisition or annotation of the original research data.",
            "prov:used": [{"@id": key} for key in sources],
        },
    }
    existing = document.get("subjectOf", [])
    if not isinstance(existing, list):
        existing = [existing]
    document["subjectOf"] = [item for item in existing if not isinstance(item, dict) or item.get("@id") != metadata_url] + [metadata]
