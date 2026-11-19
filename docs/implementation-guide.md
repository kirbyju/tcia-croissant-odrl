# TCIA Croissant implementation guide

Updated: November 19, 2026.

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
    "encodingFormat": "application/ld+json"
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
  type="application/ld+json"
  href="https://www.cancerimagingarchive.net/collection/cmb-aml/croissant.jsonld">
```

Also expose an explicit metadata relationship, using the same URL:

```html
<link
  rel="describedby"
  type="application/ld+json"
  href="https://www.cancerimagingarchive.net/collection/cmb-aml/croissant.jsonld">
```

The endpoint's HTTP `Content-Type` must be `application/ld+json`. Keeping the
HTML link's `type` parameter-free supports harvesters that compare media types
literally. The JSON-LD `conformsTo` value identifies Croissant 1.1. An equivalent
HTTP `Link` header with `rel="describedby"` can support non-HTML clients.
`subjectOf` and a visible download button alone are not discovery acceptance
tests: verify that the assessor actually follows the advertised link.

Advertise the link only after the endpoint is valid and available. These URLs
are proposed. The live CMB-AML page could not be retrieved during preparation,
so this is not an exact diff against current production markup.

Generate accurate per-download access and license metadata for mixed-access
datasets. Distinguish manifest URLs, payload formats, and search/viewer URLs.
The [website integration note](website-integration-recommendations.md) contains
additional Schema.org cleanup recommendations.

### FAIR metadata requirements shared by WordPress and Croissant

The supplied [FAIR feedback](https://docs.google.com/document/d/1LEzXiZO_XMIkQpnEIsPyVmyk1KBs3Dn9A-VvF9V1h9s/edit)
reports 84% overall and five incomplete metrics. It supplies one example DOI,
but not the second DOI, raw assessment JSON, assessment date, or F-UJI and
metrics versions. Treat its reasons as hypotheses to verify, not a reproducible
baseline or a guarantee of a particular improvement.

Generate the core Dataset properties in the page and Croissant from shared
source facts. Keep the page-level Dataset complete even when the richer
RecordSets and provenance live in linked Croissant. Preserve authors and
publication dates already present; TCIA as publisher does not establish TCIA
as the scientific dataset's creator. Missing creators in the recordset pilot
must be sourced from the dataset citation or curated DOI metadata before release.
The older summary exporter currently hardcodes TCIA as `creator`; replace that
fallback with reviewed dataset authors rather than treating its passing F2
result as evidence of correct attribution. Its use of DataCite record `created`
as `datePublished` also needs replacement with the actual dataset release date;
DOI registration and dataset publication can occur on different dates.

| Feedback | Implementation requirement | Validation and limits |
| --- | --- | --- |
| F2: missing keywords | Populate `keywords` from existing disease, anatomical location, species and Data Category labels; retain useful existing keywords. Include these in both page and Croissant Dataset objects. | Assert nonempty keywords and check F-UJI's harvested core metadata. Plain keywords improve discovery but do not become ontology identifiers. |
| I2: registered vocabulary | Declare `prov: http://www.w3.org/ns/prov#` and use real PROV-O statements on metadata documents and generated inventories. Existing ODRL statements may also be recognized. | Expand the JSON-LD and verify actual predicates/types, then inspect the registered namespaces reported by the pinned assessor. A declaration alone is insufficient evidence of meaningful vocabulary use. |
| R1: content descriptors | `encodingFormat` and `contentSize` describe the artifact at that object's `contentUrl`. A CSV inventory is `text/csv`; a plain-text `.tcia` manifest is `text/plain`; a ZIP is `application/zip`. Describe DICOM payloads as `application/dicom` only on DICOM objects. | Generated CSVs have exact byte counts and hashes. Use source-supported file sizes for direct artifacts, preserving source precision; verify bytes where possible. A manifest's represented payload size belongs in a separately named property. Leave unknown artifact sizes absent and report the gap. Search, viewer and transfer-service pages are not payload files. |
| R1.2: provenance | Separate scientific data provenance from metadata-generation provenance. Use `prov:wasDerivedFrom` for evidenced inventory sources and `prov:wasGeneratedBy` for the metadata/inventory generation activity. Add scientific acquisition, annotation or derivation activities only when supported by reviewed descriptions. | The current examples scope exporter provenance to the linked metadata document and generated RecordSets. Passing a namespace-based provenance check does not establish complete scientific provenance. |
| R1.3: disciplinary profile | Retain Croissant 1.1 `conformsTo` and use actual Croissant terms. Current F-UJI includes Croissant in its disciplinary standards registry. | Test recognition with the pinned version. Bioschemas is optional additional conformance work, not an automatic fix. Declare its versioned Dataset profile only after checking required properties, expected types and cardinalities. |

Do not emit invented media types such as `application/vnd.tcia.manifest` or
`application/vnd.nifti`. For an unregistered format, use a documented format URL
where supported, or an accurately identified generic media type, retaining the
specific format label separately. Schema.org permits format URLs as well as MIME
strings; F-UJI's recognition can differ. See the [IANA registry](https://www.iana.org/assignments/media-types/media-types.xhtml)
and [Schema.org encodingFormat](https://schema.org/encodingFormat).

The shared prototype helper [`fair_metadata.py`](../scripts/fair_metadata.py)
adds a `subjectOf` metadata `CreativeWork` identified by the proposed Croissant
URL, linked from the Dataset DOI by `subjectOf`. Its `prov:wasDerivedFrom` identifies
the supplied source records/inventories; and its `prov:wasGeneratedBy` describes
the exporter. RecordSets reference that activity. In production, also record
immutable source snapshot/version identifiers and generation timestamps. These
proposed metadata URLs are not assertions of live endpoints.

Do not copy the feedback's example LOINC/MeSH mapping without checking it.
`variableMeasured` should describe actual measured variables with accurate
identifiers; disease topics can instead use reviewed `about`/`DefinedTerm`
metadata. Neither arbitrary ontology URLs nor generic modality labels establish
what was measured. No clinical ontology mappings are introduced by this proposal.

The proposed example revision preserves historical source evidence and CSVs.
It corrects exporter provenance and manifest-size semantics and adds missing
recordset keywords and publisher metadata. It is not a fresh inventory export.
See the [review and test results](fair-feedback-review.md).

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
- Run a pinned F-UJI version and metrics configuration before and after rollout
  using the same DOI inputs, settings and evidence window. Keep raw results,
  harvested metadata, namespace and standards outputs, logs, timestamps and
  assessment input URLs. Record external-service failures separately from
  metadata defects. Confirm that existing passing metrics do not regress.
- Test both the WordPress Dataset block and the discoverable linked document.
  Inspect which subject F-UJI selects as its main entity: current collector
  heuristics can select a large RecordSet instead of the Dataset. The current
  recordset pilot also lacks dataset creators. These gaps must not be hidden
  by an aggregate score or by removing useful RecordSet metadata.
- Verify nonempty harvested keywords, recognized PROV-O/other used vocabularies,
  formal provenance recognition, artifact-specific type/size descriptors and
  recognition of Croissant as a community standard. Validate the semantics as
  well as the score. Unknown sizes and unverified profiles must remain explicit.
- Use [`assess_fuji_metadata.py`](../scripts/assess_fuji_metadata.py) for a quick,
  offline collector/evaluator comparison. It deliberately performs no DOI
  resolution, page discovery, repository lookups or data downloads and cannot
  establish an overall FAIR score. Full DOI/page assessment remains a release gate.
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
