# Website Integration Recommendations

This note describes how the Croissant prototype could fit into TCIA dataset
pages, DataCite DOI records, and ODRL policy metadata.

It is based on a review of a current TCIA collection page pattern, using
`https://www.cancerimagingarchive.net/collection/cmb-aml/` as an example. The
recommendations apply generally to TCIA Collection and Analysis Result pages.

## Recommended Architecture

Use three linked layers instead of trying to put everything into one HTML
`script` block:

| Layer | Location | Purpose |
| --- | --- | --- |
| Schema.org Dataset | Embedded in the dataset page HTML. | Supports web discovery, search engines, data catalogs, and general JSON-LD consumers. |
| Croissant | Stable TCIA-hosted JSON-LD URL linked from the page. | Gives tools a richer, validated dataset metadata document with download/access rows. |
| ODRL | Reusable TCIA-hosted policy JSON-LD URLs or nodes linked from Schema.org/Croissant. | Makes access and reuse policy statements machine-readable while preserving the human-readable TCIA policy pages. |

DataCite remains the DOI and citation registration layer. Once Croissant URLs
are stable, DataCite should point to those URLs as related metadata.

## Search Versus Download Functions

TCIA often exposes both a search/browse button and a download button for the
same row. The metadata should preserve that distinction everywhere:

| Function | Typical TCIA target | Recommended metadata treatment |
| --- | --- | --- |
| Search/browse | NBIA Search, PathDB, CTDC, General Commons, or another web page where users inspect/filter data. | Represent as `search_url` plus `search_system`, or as a Schema.org action/entry point if the website layer supports that. |
| Download | Direct file URL, Data Retriever manifest, or Aspera/Faspex package URL. | Represent as `contentUrl`/`download_url`, with `download_artifact_role` and `access_mechanism`. |

It is appropriate for Croissant to describe the search/browse interface as
machine-readable access metadata. It is not appropriate to treat a search page
as the downloadable dataset payload. In practical terms, the search URL should
not become the `contentUrl` of a Croissant `FileObject`; the download URL should.

## Current TCIA Page Pattern

The reviewed page currently emits two JSON-LD blocks:

1. A Yoast-generated Schema.org graph for `WebPage`, `CollectionPage`,
   `ImageObject`, `BreadcrumbList`, `WebSite`, and `Organization`.
2. A TCIA-generated Schema.org `Dataset` block for the collection metadata.

That is a good starting point. The TCIA-generated `Dataset` block already
contains useful fields such as:

- `name`
- `alternateName`
- `description`
- `url`
- `sameAs`
- `identifier`
- `creator`
- `funder`
- `version`
- `distribution`
- `license`

The recommended changes are mostly about making those fields more precise and
connecting them to Croissant and ODRL.

## Schema.org Dataset Changes

### 1. Give the Dataset a stable identifier

Add an `@id` to the Dataset node. Prefer the DOI URL when present; otherwise
use the page URL plus `#dataset`.

```json
{
  "@context": "https://schema.org/",
  "@type": "Dataset",
  "@id": "https://doi.org/10.7937/PCTE-6M66",
  "url": "https://www.cancerimagingarchive.net/collection/cmb-aml/"
}
```

Also connect the page-level JSON-LD graph to the Dataset with `mainEntity`:

```json
{
  "@type": ["WebPage", "CollectionPage"],
  "@id": "https://www.cancerimagingarchive.net/collection/cmb-aml/",
  "mainEntity": {
    "@id": "https://doi.org/10.7937/PCTE-6M66"
  }
}
```

This lets machines understand that the page describes the dataset, not just a
generic webpage.

### 2. Use clean text for descriptions

The current Dataset description can contain escaped HTML. It is valid JSON, but
downstream tools get markup instead of plain text. Prefer a cleaned summary:

```json
{
  "description": "This collection contains de-identified radiology and histopathology imaging procured from subjects in NCI's Cancer Moonshot Biobank - Acute Myeloid Leukemia Cancer cohort."
}
```

### 3. Treat the dataset DOI as an identifier, not as `citation`

Use the dataset DOI in `identifier` and `sameAs`.

```json
{
  "identifier": [
    {
      "@type": "PropertyValue",
      "propertyID": "DOI",
      "value": "10.7937/PCTE-6M66",
      "url": "https://doi.org/10.7937/PCTE-6M66"
    }
  ],
  "sameAs": "https://doi.org/10.7937/PCTE-6M66"
}
```

Do not use `citation` for the dataset's own DOI. In Schema.org Dataset guidance,
`citation` is better reserved for related papers that should be cited in
addition to the dataset itself. If no related paper DOI is known, omit
`citation`.

### 4. Separate dataset-level and download-row access

Mixed-access datasets should not rely on a single blunt dataset-level
`isAccessibleForFree` value. Instead:

- put dataset-level `conditionsOfAccess` on the Dataset
- put specific `license`, `conditionsOfAccess`, and `additionalProperty` values
  on each `DataDownload`
- make controlled rows unambiguous

Example:

```json
{
  "@type": "Dataset",
  "conditionsOfAccess": "Mixed open and controlled access. Review each download row for its license, access mechanism, and controlled-access requirements.",
  "license": [
    "https://creativecommons.org/licenses/by/4.0/",
    "https://www.cancerimagingarchive.net/nih-controlled-data-access-policy/"
  ]
}
```

### 5. Model manifest links as access artifacts

For Data Retriever rows, the URL points to a manifest or application handoff,
not directly to DICOM payload bytes. The Schema.org `DataDownload` should make
that clear:

```json
{
  "@type": "DataDownload",
  "name": "Images of the head (see Restricted License)",
  "contentUrl": "https://www.cancerimagingarchive.net/wp-content/uploads/CMB-AML_drs_metadata_manifest.csv",
  "encodingFormat": "text/csv",
  "license": "https://www.cancerimagingarchive.net/nih-controlled-data-access-policy/",
  "conditionsOfAccess": "Controlled-access TCIA data. Users must obtain authorization before download.",
  "additionalProperty": [
    {
      "@type": "PropertyValue",
      "name": "TCIA download artifact role",
      "value": "manifest"
    },
    {
      "@type": "PropertyValue",
      "name": "TCIA access mechanism",
      "value": "TCIA Data Retriever"
    },
    {
      "@type": "PropertyValue",
      "name": "TCIA search system",
      "value": "Clinical Translational Data Commons (CTDC)"
    },
    {
      "@type": "PropertyValue",
      "name": "TCIA payload data types",
      "value": ["CT", "MR", "PT"]
    },
    {
      "@type": "PropertyValue",
      "name": "TCIA payload file types",
      "value": ["DICOM"]
    }
  ]
}
```

This distinction matters because CSV can be either a regular data file or a
manifest. TCIA's helper metadata, such as "requires TCIA Data Retriever" or
"requires Aspera", should determine the role. File extension alone is not
reliable.

For rows with separate browse/search and download workflows, preserve both. For
example, the CMB-AML pathology row uses PathDB as the search/browse interface
but Aspera as the download handoff. Those should be modeled as separate
properties rather than collapsed into one access label.

If TCIA wants the page-level Schema.org to express this with standard actions,
one option is to attach a `SearchAction` or `ViewAction` to the `DataDownload`
or dataset page while still keeping the download artifact in `contentUrl`.
Croissant can carry the same distinction more simply as row-level fields:
`search_url`, `search_system`, `download_url`, `download_artifact_role`, and
`access_mechanism`.

### 6. Remove placeholder distributions

Do not emit `DataDownload` entries for placeholders such as:

```json
{
  "encodingFormat": "N/A",
  "contentUrl": "https://www.cancerimagingarchive.net"
}
```

If the row does not expose a real downloadable artifact, omit it from
`distribution` or represent it only as metadata in Croissant.

### 7. Use dates precisely

Use `dateModified` for TCIA collection update dates.

Use `datePublished` for first publication dates when known.

Use `temporalCoverage` only when describing the time span covered by the data
itself. A single TCIA update date should not be placed in `temporalCoverage`.

### 8. Add catalog and discovery fields

Add fields that help crawlers and data catalogs:

```json
{
  "includedInDataCatalog": {
    "@type": "DataCatalog",
    "@id": "https://www.cancerimagingarchive.net/#catalog",
    "name": "The Cancer Imaging Archive",
    "url": "https://www.cancerimagingarchive.net/"
  },
  "keywords": ["CMB-AML", "Acute Myeloid Leukemia", "CT", "MR", "PT", "Histopathology"],
  "publisher": {
    "@type": "Organization",
    "name": "The Cancer Imaging Archive",
    "url": "https://www.cancerimagingarchive.net/"
  }
}
```

### 9. Represent Analysis Result provenance

For Analysis Result pages, use Schema.org `isBasedOn` to connect derived outputs
to source datasets or source-image access rows when that metadata is available.
This should not turn the source images into the Analysis Result's own download
payloads; it simply preserves the provenance and policy context.

Minimal SAROS-style pattern:

```json
{
  "@type": "Dataset",
  "@id": "https://doi.org/10.25737/SZ96-ZG60",
  "name": "SAROS - A large, heterogeneous, and sparsely annotated segmentation dataset on CT imaging data",
  "distribution": [
    {
      "@type": "DataDownload",
      "name": "SAROS Segmentations",
      "encodingFormat": ["application/zip"],
      "contentUrl": "https://www.cancerimagingarchive.net/wp-content/uploads/SAROS-Collection-NIfTI-files-v2_03-70-2024.zip"
    }
  ],
  "isBasedOn": [
    {
      "@type": "Dataset",
      "name": "HNSCC"
    },
    {
      "@type": "DataDownload",
      "name": "GC_manifest_SAROS_SourceImages_TCIARestricted_9-12-2023.csv",
      "encodingFormat": "text/csv",
      "license": "https://www.cancerimagingarchive.net/nih-controlled-data-access-policy/",
      "conditionsOfAccess": "Controlled-access source image manifest used for SAROS provenance."
    }
  ]
}
```

The linked Croissant file can carry the richer version of this pattern: inferred
source collections, source-image access levels, source-image licenses, and the
downstream access systems used for source images. That keeps the page-level
Schema.org concise while giving tools a more complete machine-readable path.

## Croissant Link From HTML

Do not embed the whole Croissant file in the page header. Link to it as an
alternate machine-readable representation:

```html
<link rel="alternate"
      type='application/ld+json; profile="http://mlcommons.org/croissant/1.1"'
      href="https://www.cancerimagingarchive.net/collection/cmb-aml/croissant.jsonld">
```

The linked Croissant file should keep the prototype's conservative boundary:

- one `sc:Dataset` per TCIA Collection or Analysis Result
- one `cr:RecordSet` per current TCIA download/access row
- one `cr:FileObject` per linked artifact when a row has a URL
- `encodingFormat` describes the linked artifact, such as `.tcia`, CSV, ZIP, or
  Aspera handoff
- TCIA payload labels stay in explicit fields such as `file_types`,
  `data_types`, and `download_artifact_role`
- Croissant does not launch TCIA Data Retriever, parse every manifest, download
  DICOM, or automate Aspera
- rows with search/browse URLs expose separate `search_url` and `search_system`
  values, such as NBIA Search, CTDC, General Commons, or PathDB
- Analysis Results can use `isBasedOn` to describe source collections and
  source-image access rows without mixing those rows into the result payload

## ODRL Policy Layer

ODRL should be treated as a policy description layer, not as a replacement for
TCIA's human-readable policies or dataset licenses.

Recommended first step:

- publish a small set of reusable TCIA policy JSON-LD documents
- link them from Schema.org `license`, Schema.org `usageInfo` when used, and
  Croissant `usageInfo`
- keep the policy documents grounded in the official TCIA policy pages

Potential reusable policies:

| Policy | Applies to |
| --- | --- |
| TCIA data usage and citation policy | All TCIA datasets and download rows. |
| CC BY attribution policy | Open Creative Commons rows. |
| CC BY-NC noncommercial policy | Open noncommercial rows. |
| NIH controlled data access policy | Controlled or restricted rows. |

An ODRL policy document should state permissions, prohibitions, and duties in
machine-readable form while linking to the authoritative human-readable TCIA
policy page.

Minimal example:

```json
{
  "@context": {
    "odrl": "http://www.w3.org/ns/odrl/2/",
    "schema": "https://schema.org/"
  },
  "@type": "odrl:Set",
  "@id": "https://www.cancerimagingarchive.net/policies/odrl/tcia-data-usage",
  "schema:name": "TCIA Data Usage Policies and Restrictions",
  "schema:url": "https://www.cancerimagingarchive.net/data-usage-policies-and-restrictions/",
  "odrl:permission": [
    {
      "odrl:action": {"@id": "odrl:use"},
      "odrl:duty": [
        {"odrl:action": {"@id": "odrl:attribute"}}
      ]
    }
  ]
}
```

For controlled data, include a duty to obtain required authorization and link
the human-readable NIH Controlled Data Access Policy.

## DataCite Integration

Do not update DataCite until Croissant URLs are stable and hosted by TCIA.

Once stable, add a DataCite `relatedIdentifier` from the dataset DOI record to
the Croissant file:

```json
{
  "relationType": "HasMetadata",
  "relatedIdentifier": "https://www.cancerimagingarchive.net/collection/cmb-aml/croissant.jsonld",
  "relatedIdentifierType": "URL",
  "relatedMetadataScheme": "Croissant",
  "schemeUri": "http://mlcommons.org/croissant/1.1",
  "schemeType": "JSON-LD"
}
```

The DOI remains the citation and landing-page anchor. Croissant becomes a
related metadata document, not a replacement DOI record.

## Implementation Checklist

Recommended production sequence:

1. Keep the existing Yoast `WebPage` graph.
2. Generate a cleaner TCIA `Dataset` node from the same source metadata used by
   the dataset page.
3. Add `@id` and connect the page graph to the Dataset with `mainEntity`.
4. Fix DOI/citation/date fields.
5. Make distribution rows reflect linked artifacts and helper metadata.
6. Host Croissant files at stable TCIA URLs.
7. Add `rel="alternate"` Croissant links to dataset pages.
8. Publish reusable ODRL policy JSON-LD documents or nodes.
9. Link stable Croissant URLs from DataCite using `HasMetadata`.
10. Validate with Schema.org tooling, Google Rich Results testing, and
    `mlcroissant`.

## Anti-Patterns To Avoid

- Do not hand-author independent facts in WordPress, DataCite, Schema.org,
  Croissant, and ODRL.
- Do not infer manifest status from file extension.
- Do not label a manifest URL as if it directly downloads DICOM payload bytes.
- Do not represent controlled-access rows as public direct downloads.
- Do not use `citation` for the dataset's own DOI.
- Do not put page update dates in `temporalCoverage`.
- Do not register Croissant URLs in DataCite before TCIA has stable public URL
  patterns.
