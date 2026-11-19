# FAIR feedback review and proposed Croissant changes

November 19, 2026. Repository metadata revision; production deployment remains pending.

## Recommendation

Address the feedback through the existing Croissant and WordPress rollout.
Publish complete core Dataset metadata in WordPress, with discoverable linked
Croissant for inventories and detailed provenance. Do not add Bioschemas or
clinical ontology identifiers merely to change an automated score.

The [revised implementation guide](implementation-guide.md) contains the proposed
requirements. All nine example JSON-LD files and both exporters have a local
proposal. Seven inventory CSVs remain byte-for-byte unchanged.

## Feedback and proposed response

| Feedback | Proposed response |
| --- | --- |
| Missing keywords (F2) | Add keywords and TCIA publisher metadata to the four recordset examples; keep existing summary keywords. Generate keywords from existing source labels and include them in the WordPress Dataset block. |
| Missing vocabulary (I2) | Use PROV-O on the generated metadata document and RecordSets. This complements existing ODRL and source-provenance statements. No unreviewed LOINC/MeSH mappings. |
| Distribution size/type (R1) | Describe the actual downloadable artifact. Remove unsupported vendor MIME names; retain payload labels separately. Move aggregate manifest/package payload sizes out of `contentSize` into `TCIA represented payload size`. Generated inventory CSVs retain exact byte counts and hashes. |
| Formal provenance (R1.2) | Attach the export activity to the metadata `CreativeWork` and generated RecordSets. Preserve inventory source URLs and hashes. Do not imply the Croissant exporter acquired the original images or performed scientific annotations. |
| Disciplinary standard (R1.3) | Retain actual Croissant 1.1 conformance. The tested F-UJI registry already recognizes Croissant as disciplinary metadata. Add Bioschemas only as separately validated conformance work if desired. |

Also change the guide's HTML discovery links to parameter-free
`type="application/ld+json"` and add `rel="describedby"`. The original link's
profile parameter fails the tested F-UJI linked-RDF media-type filter; the new
links pass its parser/filter. This is a local link-parser test, not an HTTP
discovery or endpoint-availability test.

## What was actually tested

The supplied [feedback document](https://docs.google.com/document/d/1LEzXiZO_XMIkQpnEIsPyVmyk1KBs3Dn9A-VvF9V1h9s/edit)
reports 84% for two DOI assessments, but names only LIDC-IDRI
(`10.7937/K9/TCIA.2015.LO9QL9SX`) and supplies no raw results, run date, version
or settings. LIDC-IDRI is not among this repository's nine examples. These tests
therefore do **not** reproduce that 84% or establish a new overall TCIA score.

I ran the official F-UJI RDF collector and F2, I2, R1.2 and R1.3 evaluators on
all nine committed examples and their nine revised counterparts. F-UJI was
pinned to commit `88085ba498f98583ef4523bda651e9d1a7c2f64f` (4.0.1), with
`metrics_v0.8.yaml` and its bundled vocabulary/standards registries. The TCIA
baseline is `a3d5b317812ecb7e7b35d4ccbfd5db79a8b6d7f3`, verified as current
GitHub main during this review.

| Check | Observed result |
| --- | --- |
| I2, older 4D-Lung summary | **0/2 → 2/2**, maturity 0 → 3. The other eight examples retain 2/2. |
| R1.2, all five older summaries | Formal-provenance subtest changes **fail → pass**; maturity **2 → 3**. Overall metric points stay **1/1**, because this configuration already awarded that score for descriptive provenance. The four recordset examples already had formal PROV and retain their result. |
| R1.3, all nine examples | **1/1 before and after**; Croissant is recognized without a Bioschemas declaration. |
| F2, controlled keyword ablation | Removing only keywords from the existing 4D-Lung summary yields **1/2**; restoring them yields **2/2**. This isolates the recommendation; it is not a production before/after result. |
| F2, actual recordset examples | Remains **0/2** in these standalone component runs. F-UJI selects a RecordSet instead of the Dataset in all four originals and three revised documents. The revised SAROS document is selected correctly but still lacks a creator. |
| R1 descriptor-presence subtest | Revised SAROS inventories expose type and size for both generated CSVs when F-UJI selects its Dataset. Its ZIP size remains unknown. No full R1 score or remote byte/type verification was attempted. Removing an inaccurate manifest size makes its presence subtest fail; keeping a false value to retain a score would be incorrect. |
| Croissant validation | **9/9 pass** with `mlcroissant==1.1.0`; the older SAROS summary retains warnings for missing recommended publication date and version. |
| Local consistency tests | **8 pass**, including CSV counts/keys/hashes, metadata provenance, keyword mapping and manifest-size separation. |
| Media types | All emitted `encodingFormat` values checked against the relevant live IANA registry CSVs are registered. This does not verify remote server response headers or file bytes. |

These are metadata component tests with network connections disabled during
assessment. There was no DOI resolution, WordPress fetching, DataCite lookup,
repository lookup, data transfer, or live FAIR assessment. The metadata document
URLs in the examples remain proposed URLs. No public test service received the
local examples.

## Remaining release requirements

1. Source real dataset authors and release dates. The recordset pilot omits
   creators; the older exporter hardcodes TCIA as creator and uses DOI record
   creation time as publication time. Passing F2 does not validate those facts.
   The older SAROS summary lacks publication date and version. These gaps are
   documented rather than filled with invented values in this proposal.
2. Publish and test the linked metadata from staging dataset pages, retaining
   complete core Dataset metadata in the HTML. Inspect F-UJI's selected subject
   and harvested values. Preserve useful RecordSet detail; investigate the
   harvester's selection behavior if it still chooses the wrong subject.
3. Rerun the same DOI assessments before and after deployment using a pinned
   evaluator/configuration. Keep raw JSON and diagnostics. Verify actual file
   sizes/types using authorized samples; preserve controlled-access boundaries.
   An expected score improvement is not a substitute for those checks.

## Reproducing the component test

Use Python 3.13 and a separate checkout of the official F-UJI repository pinned
to the commit above. Install it and this repository's `requirements.txt` in an
isolated environment. No browser installation or Tika service is needed for
these metadata-only checks.

```bash
PYTHONPATH=/path/to/pinned-fuji python scripts/assess_fuji_metadata.py \
  --examples examples \
  --out /tmp/fuji-metadata.json \
  --fuji-commit 88085ba498f98583ef4523bda651e9d1a7c2f64f
python -m unittest discover -s tests -v
```

The harness records the selected RDF subject, harvested metadata, namespaces,
individual tests, maturity, score, and artifact type/size-presence checks.
The tiny keyword ablation and guide-link parser exercise are labeled separately.
It never computes an overall FAIR score.

## Evidence and scope of example edits

- [Environment and pinned metric hash](fair-review-evidence/environment.json)
- [Raw baseline results](fair-review-evidence/fuji-before.json) and
  [raw revised results](fair-review-evidence/fuji-after.json)
- [Example hashes and keyword sources](fair-review-evidence/example-revisions.json)
- [Croissant validation](fair-review-evidence/mlcroissant.json),
  [local tests](fair-review-evidence/test-results.txt), and
  [IANA checks](fair-review-evidence/iana-media-types.json)

For three recordset examples, keywords were copied from an existing summary
with the same DOI. For HNSCC-mIF-mIHC-comparison, labels came from the existing
PathDB inventory's CancerType, CancerLocation and species columns. Those values
are preserved as source labels, not asserted as standardized ontology mappings.
The generator uses labels from its supplied WordPress snapshot for future runs.

`generation-summary.json` retains the historical inventory sources and generation
timestamp, updates only changed JSON-LD output hashes, and marks this metadata
revision separately. `validation-summary.json` retains its historical checks
and adds the current metadata-validation result. No source-inventory refresh
or WordPress/DataCite write was performed. Publishing these repository changes
does not deploy those systems.

Primary references: [F-UJI source at the tested revision](https://github.com/pangaea-data-publisher/fuji/tree/88085ba498f98583ef4523bda651e9d1a7c2f64f),
[F-UJI standards registry](https://github.com/pangaea-data-publisher/fuji/blob/88085ba498f98583ef4523bda651e9d1a7c2f64f/fuji_server/data/metadata_standards.yaml),
[PROV-O](https://www.w3.org/TR/prov-o/),
[Schema.org encodingFormat](https://schema.org/encodingFormat),
[IANA media types](https://www.iana.org/assignments/media-types/media-types.xhtml),
[Bioschemas Dataset profile](https://bioschemas.org/profiles/Dataset/1.0-RELEASE).
