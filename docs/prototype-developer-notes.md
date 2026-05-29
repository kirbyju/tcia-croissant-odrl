# TCIA Croissant Metadata Prototype

Date: 2026-05-29

This note summarizes a local prototype for publishing TCIA dataset metadata in
Croissant JSON-LD. The goal is to help TCIA developers evaluate how Croissant
could fit into the website, Collection Manager, DataCite workflows, and download
tools without changing production systems yet.

## Goal

TCIA already has authoritative human-readable dataset pages, per-download
license metadata, data usage policies, DOI metadata in DataCite, and separate
download tools such as TCIA Data Retriever and Aspera.

The Croissant prototype is intended to add a machine-readable metadata view over
that same information. It should help automated tools answer questions like:

- What is this TCIA dataset?
- What is the DOI and recommended citation?
- What download/access rows are available?
- Which rows are direct files, manifests, or transfer-package handoffs?
- Which license, policy, and access requirements apply to each row?
- Which application or workflow is needed to access the linked artifact?

The prototype is not intended to make every TCIA imaging dataset directly
loadable as Python records.

## Standards Strategy

The broader goal is not to replace TCIA's existing dataset pages, licenses,
download tools, or DOI registration workflow. The goal is to publish the same
information in standards-based forms that humans, search engines, data catalogs,
AI tools, and research software can interpret more consistently.

These standards are complementary:

| Standard | TCIA role | Why it helps |
| --- | --- | --- |
| Schema.org | Common web vocabulary for dataset pages, downloadable distributions, citations, licenses, publishers, dates, and identifiers. | Makes TCIA metadata recognizable to search engines, general web crawlers, knowledge graphs, and JSON-LD-aware tools. |
| Croissant | A dataset metadata profile built on JSON-LD and Schema.org, with stronger structure for files, record sets, fields, ML/AI data use, and validation. | Gives TCIA a testable machine-readable dataset document that goes beyond generic page markup. |
| ODRL | Policy vocabulary for expressing permissions, prohibitions, duties, constraints, and inherited usage policies. | Lets TCIA describe access and reuse conditions in a structured way while still pointing back to authoritative human-readable policies. |
| DataCite | Persistent identifier, citation, version, creator, publisher, rights, and related-metadata registration for TCIA DOIs. | Keeps DOI landing, citation, and scholarly metadata stable while linking out to richer TCIA-hosted metadata documents. |

One useful mental model is:

```text
DataCite identifies and cites the dataset.
Schema.org makes the dataset understandable on the web.
Croissant packages the dataset metadata for machine use and validation.
ODRL expresses usage policy details that are more complex than a license URL.
```

In practice, the same TCIA source metadata should generate all of these views.
Developers should avoid maintaining separate hand-authored versions of the same
facts in WordPress, DataCite, Croissant, and ODRL. The Collection Manager and
normalized TCIA metadata snapshot should remain the source inputs; standards
documents should be generated projections.

## Human And Machine Benefits

Humans still need clear TCIA pages that explain the dataset, citation, license,
data access steps, controlled-access requirements, and download tooling in plain
language. Standards-based metadata does not replace that experience.

The standards help humans indirectly by making the same information easier to
check, reuse, and display consistently across TCIA pages, APIs, catalogs, DOI
records, and downstream tools. For example, a developer can build a UI that
knows whether a row is a direct CSV, a Data Retriever manifest, an Aspera
package, or a controlled-access handoff without re-scraping page text.

The standards help machines directly by turning TCIA's publication metadata into
structured statements:

- crawlers can identify TCIA pages as datasets, not just web pages
- data catalogs can ingest dataset titles, descriptions, DOIs, licenses, and
  distributions
- DOI clients can follow DataCite relationships to richer metadata
- AI agents can distinguish direct files from manifests and controlled-access
  rows
- validation tools can catch missing or inconsistent metadata earlier
- policy-aware tools can see that a Creative Commons license, TCIA usage policy,
  and controlled-access requirement are related but distinct layers

This should make TCIA datasets easier to find, cite, evaluate, and route to the
right access workflow, even when the actual imaging payloads still require TCIA
Data Retriever, IDC/idc-index, General Commons, or Aspera.

## Important Scope Decision

For now, TCIA Croissant should model **download/access metadata**, not the full
payload behind every download row.

This is especially important for TCIA because many download rows do not point
directly to the actual imaging files. They point to an artifact that must be
opened by another system:

| TCIA row type | Croissant role in this prototype | What it means |
| --- | --- | --- |
| No Data Retriever or Aspera requirement | `data file` | The linked URL is treated as the downloadable artifact itself. |
| `download requirements` says TCIA Data Retriever | `manifest` | The linked URL is an inventory or application handoff, not the payload. |
| `download requirements` says Aspera/Faspex | `transfer package` | The linked URL is a transfer workflow handoff. |

Croissant can describe those artifacts, but TCIA-specific downloading remains
outside Croissant. That means the prototype does not ask `mlcroissant` to parse
`.tcia` manifests, launch Data Retriever, call IDC, authenticate to General
Commons, or use Aspera.

## Why This Boundary Matters

The Croissant spec is designed to describe datasets, resources, and record sets
in a standardized JSON-LD form. It can support loadable ML datasets when the
underlying resources are directly accessible and modeled in enough detail.

TCIA has an extra domain-specific access layer:

```text
Croissant Dataset
  -> TCIA download/access row
    -> direct file OR manifest OR transfer handoff
      -> actual data files, series, or controlled-access objects
```

This prototype intentionally stops at the TCIA download/access row. Actual data
download behavior should remain in TCIA tooling such as TCIA Data Retriever,
IDC/idc-index workflows, General Commons controlled-access workflows, and Aspera.

## Current Prototype Output

The proof of concept generates a directory with this shape:

```text
croissant-output/
```

Key files:

```text
tcia_croissant_index.json
tcia_croissant_manifest.json
tcia_croissant_jsonld.zip
collections/<slug>/croissant.jsonld
analysis-results/<slug>/croissant.jsonld
```

Exporter script:

```text
generate_tcia_croissant.py
```

Source SQLite snapshot:

```text
cache/tcia_snapshot.sqlite
```

Current output summary:

| Metric | Value |
| --- | ---: |
| Visible datasets generated | 289 |
| Download-row RecordSets generated | 698 |
| Open datasets | 215 |
| Controlled datasets | 24 |
| Mixed open/controlled datasets | 41 |
| Open noncommercial datasets | 9 |
| Direct data-file download rows | 338 |
| Data Retriever manifest download rows | 252 |
| Aspera transfer-package artifacts | 101 |
| Metadata-only download rows without a URL | 7 |

Current zip SHA-256:

```text
b797bf44d8968f49cba776a8a8a3306128be11fc51d38527e575c7ae4f6b7b6c
```

The generated JSON-LD files were validated with `mlcroissant` 1.1.0:

```text
Files checked: 289
Validation failures: 0
```

## Mapping

Each visible TCIA WordPress Collection or Analysis Result becomes one Croissant
`sc:Dataset`.

Each current TCIA download row becomes one child `cr:RecordSet`. The RecordSet
contains one inline metadata record describing the TCIA access row. It is not a
record set of the payload files.

Each download row with a URL also becomes one `cr:FileObject` in `distribution`.
That `FileObject` describes the linked artifact itself.

Important fields:

| Field | Meaning |
| --- | --- |
| `@type: sc:Dataset` | Croissant dataset root for a TCIA Collection or Analysis Result. |
| `distribution` | Linked artifacts exposed by TCIA download rows. |
| `recordSet` | One RecordSet per TCIA download/access row. |
| `download_artifact_role` | `data file`, `manifest`, or `transfer package`. |
| `access_mechanism` | `direct download`, `TCIA Data Retriever`, or `Aspera`. |
| `file_types` | TCIA payload labels, such as DICOM, CSV, XLSX, ZIP, NIfTI. |
| `encodingFormat` | The format of the linked artifact at `contentUrl`, not necessarily the payload behind a manifest. |
| `usageInfo` | Links to TCIA policy/licensing information, with lightweight ODRL-compatible structure. |

The artifact role is based on TCIA's download-requirements helper metadata, not
on file extension. This matters because CSV files can be either ordinary data
files or newer/richer Data Retriever manifests. In the local SQLite snapshot used
for this prototype, the helper metadata is available inside each raw WordPress
download record as `download requirements`. Newer snapshot schemas also expose
the same information in normalized download columns.

Example: A091105-Tumor-Annotations has two download rows:

| Download row | Linked artifact | Artifact role | Access mechanism | Payload label |
| --- | --- | --- | --- | --- |
| `46387` | `.tcia` manifest | `manifest` | `TCIA Data Retriever` | DICOM |
| `46389` | CSV file | `data file` | `direct download` | CSV |

In Python, `mlcroissant.Dataset(...).records("download-46387")` returns the
metadata record for the Data Retriever manifest. It does not return DICOM
instances.

## Direct Files Versus Manifests

For a direct CSV row, the prototype currently describes the row and the linked
CSV file. It does not yet infer the CSV's internal columns.

For a Data Retriever manifest row, whether the manifest URL ends in `.tcia` or
`.csv`, the prototype describes the manifest as the linked artifact and records
the payload labels such as DICOM. It does not parse the manifest into Series
Instance UIDs, DRS URIs, or richer row-level inventory records, and it does not
download images.

For an Aspera row, the prototype describes the row as a transfer-package handoff.
It does not reconstruct or automate the Aspera package download.

This conservative behavior is intentional. TCIA can add richer record sets later
for selected direct CSV or spreadsheet files, but that should be a second phase.

## Policy And Licensing

Dataset-level and row-level Croissant metadata include:

- dataset DOI and citation where available
- TCIA landing page URL
- license URL or label
- controlled/open/mixed access indicators
- TCIA data usage policy link
- TCIA controlled-access policy link where applicable

ODRL is useful as a structured way to express usage policy, but it should not
replace TCIA's human-readable policies or licenses. In this prototype, `usageInfo`
is a place to expose policy links and lightweight ODRL-compatible statements.

## DataCite And HTML Integration Later

The local prototype should not be registered in DataCite yet because the JSON-LD
files are not hosted at stable TCIA-owned URLs.

Once production URLs exist, TCIA could:

1. Host each Croissant file at a stable URL, such as:

   ```text
   https://www.cancerimagingarchive.net/collection/<slug>/croissant.jsonld
   https://www.cancerimagingarchive.net/analysis-result/<slug>/croissant.jsonld
   ```

2. Add a discovery link in the dataset page HTML:

   ```html
   <link rel="alternate"
         type='application/ld+json; profile="http://mlcommons.org/croissant/1.1"'
         href="https://www.cancerimagingarchive.net/collection/<slug>/croissant.jsonld">
   ```

3. Add a DataCite `relatedIdentifier` from the DOI record to the Croissant file,
   likely using `HasMetadata`, after TCIA decides on final URL patterns.

4. Optionally include the Croissant URL in TCIA APIs so downstream tools do not
   have to scrape HTML.

## Current Validation Behavior

The prototype sets:

```json
"isLiveDataset": true
```

This is currently needed because the SQLite snapshot does not contain stable
SHA-256 checksums for all linked files. The official `mlcroissant` validator
requires `sha256` or `md5` for non-live `FileObject`s.

For production, TCIA should decide whether to:

- keep `isLiveDataset: true`, which is reasonable for remote, evolving access
  workflows, or
- add stable SHA-256 values for linked artifacts where TCIA can guarantee them.

Adding hashes would improve reproducibility, but it may not be practical for all
legacy manifests, controlled-access handoffs, or Aspera packages.

## Regeneration

Current prototype command:

This prototype expects a TCIA metadata SQLite snapshot. The snapshot is not
included in this share folder. For local experiments, get the latest published
snapshot from the `tcia-query-skill` repository. If that repo is checked out,
run:

```bash
python3 scripts/tcia_snapshot.py ensure
```

That creates or updates:

```text
cache/tcia_snapshot.sqlite
```

Developers can also download the latest release asset
`tcia_snapshot.sqlite.gz` from the TCIA query skill repository and decompress it
before running the Croissant exporter.

```bash
python3 generate_tcia_croissant.py \
  --db path/to/tcia_snapshot.sqlite \
  --out path/to/croissant-output
```

Validation command pattern:

```bash
python3 -m pip install mlcroissant
mlcroissant validate --jsonld /path/to/croissant.jsonld
```

For bulk validation, use the same Python API the CLI uses:

```python
from pathlib import Path
import mlcroissant as mlc

root = Path("/path/to/generated/croissant")
for path in root.glob("**/croissant.jsonld"):
    mlc.Dataset(str(path))
```

## Production Questions For Developers

Recommended decisions before production integration:

1. Official URL pattern for Croissant files.
2. Whether Croissant is generated on demand from Collection Manager or prebuilt
   during metadata publication.
3. Whether hidden/staged/retired records should ever have internal Croissant
   outputs.
4. Whether to include Croissant URLs in DataCite immediately or only after a
   public beta period.
5. Whether direct CSV/spreadsheet files should eventually get deeper loadable
   RecordSets.
6. Whether TCIA can publish stable checksums for linked artifacts.
7. How to expose the same artifact-role/access-mechanism fields in TCIA APIs.
8. How controlled-access rows should be represented so tools never mistake them
   for public direct downloads.

## Proposed Phase Plan

Phase 1: Access metadata only

- Generate one Croissant file per visible TCIA dataset.
- Represent each current download row as access metadata.
- Distinguish direct file, manifest, and transfer-package handoff.
- Validate with `mlcroissant`.
- Share internally with developers for review.

Phase 2: Website/API integration

- Host stable JSON-LD URLs on TCIA infrastructure.
- Add HTML discovery links.
- Expose Croissant URLs in APIs.
- Add DataCite `HasMetadata` links once URL patterns are stable.

Phase 3: Optional richer file modeling

- Add deeper schemas for selected direct CSV/spreadsheet files.
- Consider parsed manifest inventories as separate TCIA-generated metadata files,
  not as core Croissant download behavior.
- Keep actual downloads in TCIA Data Retriever, IDC/idc-index, General Commons,
  and Aspera tooling.

## References

- Schema.org Dataset: https://schema.org/Dataset
- Croissant 1.1 specification: https://docs.mlcommons.org/croissant/docs/croissant-spec-1.1.html
- Croissant 1.0 specification landing page: https://docs.mlcommons.org/croissant/docs/croissant-spec.html
- DataCite Metadata Schema 4.7: https://schema.datacite.org/meta/kernel-4.7/
- W3C ODRL Information Model: https://www.w3.org/TR/odrl-model/
- TCIA Data Usage Policies and Restrictions: https://www.cancerimagingarchive.net/data-usage-policies-and-restrictions/
- TCIA NIH Controlled Data Access Policy: https://www.cancerimagingarchive.net/nih-controlled-data-access-policy/
