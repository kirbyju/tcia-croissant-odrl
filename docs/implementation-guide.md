# TCIA Croissant implementation guide

Updated: November 12, 2026.

This is the current implementation guidance for the TCIA development team.
Use it for implementation priorities and rollout requirements. The other design
notes supply supporting background; this guide takes precedence where their
recommendations differ. This is a proposed implementation plan, not a claim
that WordPress or a released Data Retriever already implements it.

## 1. Agree on the publication format and verify TDR compatibility

Review the [examples](../examples/README.md). There are two formats:

| Format | Location | Compatibility |
| --- | --- | --- |
| Download summaries | Top-level `examples/*.croissant.jsonld` | Describe WordPress download rows and link to existing files, manifests, or transfer handoffs. The local TDR implementation inspected for this guide handles direct files and expands supported nested manifests marked for TDR. Aspera transfer packages are skipped with warnings. |
| External CSV recordsets | [`examples/recordset-manifests/`](../examples/recordset-manifests/README.md) | One dataset Croissant document plus one CSV inventory per modeled download record, with fields mapped to source CSV columns. The inspected TDR implementation does not implement general Croissant field-source resolution for this format. |

Use the external CSV recordset model as the target architecture, subject to
agreement on its retrieval contract and implementation of the necessary TDR
support. The original summaries can support an earlier rollout after testing
against the intended released TDR version. The formats are not interchangeable;
successful Croissant validation does not prove TDR download support.

Define stable RecordSet IDs, record grains and keys, and route selection.
A dataset download selects all supported RecordSets; an individual download
selects explicit RecordSet IDs. WordPress and TDR must agree on how selection
is passed. See the [recordset design](recordset-manifest-design.md).

## 2. Adapt the existing generation scripts

Two prototype generators are already available:

- [`generate_tcia_croissant.py`](../scripts/generate_tcia_croissant.py) generates
  download summaries from a SQLite snapshot containing WordPress records, with
  DataCite enrichment. It excludes hidden records by default and writes beneath
  `collections/<slug>/` or `analysis-results/<slug>/`.
- [`generate_recordset_examples.py`](../scripts/generate_recordset_examples.py)
  generates the external CSV examples using additional manifests, metadata
  workbooks, and non-DICOM inventories. It preserves source columns, records
  hashes, rejects duplicate retrieval keys, and reconciles public DICOM manifest
  UID sets against metadata workbook UID sets.

Example invocation of the summary exporter:

```bash
python3 scripts/generate_tcia_croissant.py \
  --db /path/to/tcia_snapshot.sqlite \
  --out croissant-output
```

These are implementation references, not an installed WordPress plugin.
Reuse or port the mappings and validation logic, adapting the input layer to
WordPress. The recordset generator is a dataset-specific pilot that needs
generalization for production; its inputs are documented by `--help`.

WordPress download metadata alone does not supply all payload inventory rows.
Define the authoritative inventory source and refresh mechanism for each route.
Generate page metadata and Croissant from shared source facts to prevent drift.
Preserve raw source values and provenance; do not invent missing inventory rows.

## 3. Generate and publish automatically

Publish one Croissant document per public Collection or Analysis Result, and,
for the target model, one CSV per modeled WordPress download RecordSet.

Regenerate the affected dataset when:

- A download record is added, edited, deleted, or reassigned. Reassignment must
  regenerate both the previous and new parent dataset.
- Relevant dataset metadata changes: title, DOI, version, dates, visibility,
  access conditions, licenses, or provenance.
- An associated manifest, inventory, metadata attachment, or shared policy
  changes, including replacement of an attachment at an unchanged URL.

Queue generation after the underlying changes are saved. Coalesce repeated
events and prevent older jobs from overwriting newer results.

Choose stable TCIA-hosted URLs. These are proposed patterns, not deployed URLs:

```text
/collection/cmb-aml/croissant.jsonld
/collection/cmb-aml/recordsets/48105-public-dicom-series.csv
/analysis-results/saros/croissant.jsonld
```

Public URLs can differ from the generators' filesystem layout. Use WordPress
record IDs for stable recordset identity; define redirects for slug changes.

Validate the complete generation before publication. Publish JSON-LD and its
referenced CSVs as a consistent version, with matching hashes and byte sizes.
Versioned immutable CSV URLs behind a stable JSON-LD URL are one option.
Serve JSON-LD as `application/ld+json` and CSVs as `text/csv`; configure cache
invalidation or revalidation. Configure CORS if cross-origin browser access is
required.

Record generation time, source versions/hashes, output hashes, and errors.
Provide administrator-visible failures and retry controls. Ordinary generation
failures should retain the last valid version with an administrator-visible
stale status. Withdrawals, hidden datasets, and removed or restricted downloads
require explicit invalidation so obsolete access information is not kept public.
Remove obsolete artifacts and page links as appropriate.

Never publish credentials, tokens, or signed access URLs. Controlled manifests
identify data; the relevant service still enforces authorization. Preserve
per-recordset licenses, conditions, search URLs, and download routes. Keep
Aspera handoffs distinct from direct public files and viewer URLs.

## 4. Link Croissant from Schema.org and HTML

Keep the existing page-level Schema.org graph and Dataset metadata. Link the
Dataset to its Croissant metadata document and add an HTML discovery link.

For CMB-AML, merge these fields into the existing `Dataset` object. This is an
additive example, not a replacement for the full object:

```json
{
  "@id": "https://doi.org/10.7937/PCTE-6M66",
  "subjectOf": {
    "@type": "CreativeWork",
    "@id": "https://www.cancerimagingarchive.net/collection/cmb-aml/croissant.jsonld",
    "name": "CMB-AML Croissant metadata",
    "url": "https://www.cancerimagingarchive.net/collection/cmb-aml/croissant.jsonld",
    "encodingFormat": "application/ld+json",
    "about": {
      "@id": "https://doi.org/10.7937/PCTE-6M66"
    }
  }
}
```

This guide recommends [`subjectOf`](https://schema.org/subjectOf), which links
a thing to a work about it. Describe the metadata document as a
[`CreativeWork`](https://schema.org/CreativeWork). Keep the existing `@context`
and `@type: Dataset`. Preserve existing `subjectOf` entries by appending to an
array. Use the same Dataset identifier in Croissant and any page-graph
`mainEntity` reference.

Add this discovery link to the HTML `<head>`:

```html
<link
  rel="alternate"
  type='application/ld+json; profile="http://mlcommons.org/croissant/1.1"'
  href="https://www.cancerimagingarchive.net/collection/cmb-aml/croissant.jsonld">
```

Advertise the link only after the endpoint is valid and available. These URLs
are proposed. The live CMB-AML page could not be retrieved during preparation,
so this is not an exact diff against current production markup.

Generate accurate per-download access and license metadata for mixed-access
datasets. Distinguish manifest URLs, payload formats, and search/viewer URLs.
The [website integration note](website-integration-recommendations.md) contains
additional Schema.org cleanup recommendations.

## 5. Add the download interface

Add a dataset-level button linking to the published Croissant URL. Suggested
label: **Download all with TCIA Data Retriever**. Include nearby instructions
for opening the downloaded manifest in TDR and a TDR installation link. A
normal JSON-LD link does not launch the desktop application; automatic launch
requires a separately implemented application handoff.

For mixed-route datasets, explain what TDR supports and which records require
authorization or another tool. If TDR cannot retrieve every recordset, qualify
the label or adjacent description and provide the remaining routes. CMB-AML's
Aspera pathology handoff is skipped by the inspected TDR implementation; do not
imply that this produces a complete dataset download.

If individual row buttons use Croissant, implement and test explicit RecordSet
selection. Keep existing download routes available during the transition.

## 6. Backfill and verify before rollout

Backfill all public Collections and Analysis Results. Provide an administrator
command to regenerate one dataset or the full corpus.

Acceptance checks:

- Validate documents with `mlcroissant` and page markup with Schema.org tooling.
  Check CSV availability, hashes, keys, field mappings, and reconciliation with
  authoritative source inventories.
- Test the intended released TDR version against public DICOM, controlled DRS,
  direct files, unsupported Aspera handoffs, and Analysis Result outputs.
  Verify payload retrieval rather than merely saving inventory CSVs. Use small,
  authorized samples for transfer tests.
- Verify full-dataset and selected-recordset flows. Clearly report skipped or
  failed records; partial success must not be presented as complete.
- Exercise add/change/delete/reassignment, inventory replacement, policy changes,
  visibility changes, generation failure, and cache refresh behavior.
- Confirm that page metadata, buttons, and artifacts agree after updates and
  that no unpublished records or credentials are exposed.

The CMB-AML CSV pilot documents an incomplete pathology inventory: 62 inventory
rows versus 67 images reported by WordPress in its source evidence. Resolve or
clearly disclose the discrepancy before demonstrating a complete download.
Recheck current sources during implementation.

## Follow-up after stable hosting

Link stable Croissant URLs from DataCite using `HasMetadata`; the
[integration note](website-integration-recommendations.md#datacite-integration)
provides an example. Publish reusable ODRL policy documents if that layer is
adopted, using authoritative, reviewed mappings. Do not infer detailed DUO or
ODRL restrictions from disease labels or dbGaP accessions. Policy metadata and
manifests do not grant access or replace access enforcement.
