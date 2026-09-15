# TCIA Croissant Metadata Prototype

This repository is a small prototype for publishing TCIA dataset metadata as
Croissant JSON-LD while preserving TCIA's existing website, DOI, policy, and
download-tool workflows.

The repository demonstrates a recordset publication model with one Croissant
document per dataset and one human-readable CSV `FileObject` per WordPress
download recordset. Croissant formally defines the CSV fields, keys, access
conditions, and provenance; the CSV supplies the retrieval inventory and
detailed metadata.

## What Is Included

```text
docs/prototype-developer-notes.md
docs/website-integration-recommendations.md
docs/recordset-manifest-design.md
scripts/generate_tcia_croissant.py
scripts/generate_recordset_examples.py
examples/*.croissant.jsonld
examples/validation-summary.json
examples/recordset-manifests/**
requirements.txt
```

The example Croissant files are representative samples only. They cover public
DICOM series, controlled DRS objects, NIfTI segmentations and related tabular
data, and two digital pathology workflows:

- **HNSCC-mIF-mIHC-comparison** describes 3,212 directly downloadable PathDB
  image records for an AI-ready computational pathology collection with
  multiplex immunofluorescence and immunohistochemistry imagery.
- **CMB-AML** describes a histopathology transfer inventory alongside public
  and controlled radiology recordsets, demonstrating how one multimodal dataset
  can expose different retrieval routes without losing record-level metadata.

The files under `examples/recordset-manifests/` cover 4D-Lung,
HNSCC-mIF-mIHC-comparison, CMB-AML, and SAROS. Each dataset has one Croissant
document whose RecordSets source their rows from route-specific CSV files. See
[the recordset design note](docs/recordset-manifest-design.md) for the proposed
WordPress and Data Retriever contract.

## Recommended Mental Model

```text
DataCite identifies and cites the dataset.
Schema.org makes the dataset understandable on the web.
Croissant packages the dataset metadata for machine use and validation.
ODRL expresses usage policy details that are more complex than a license URL.
```

The same TCIA source metadata should generate all of these standards views.
Avoid maintaining separate hand-authored facts in WordPress, DataCite,
Croissant, and ODRL.

## Download Rows Versus Payloads

TCIA download rows can point to different kinds of linked artifacts:

| Helper metadata | Prototype role | Meaning |
| --- | --- | --- |
| no Data Retriever or Aspera requirement | `data file` | The linked URL is treated as the downloadable artifact itself. |
| requires TCIA Data Retriever | `manifest` | The linked URL is an application handoff/inventory, not the payload. |
| requires Aspera/Faspex | `transfer package` | The linked URL is a transfer workflow handoff. |

This role is based on TCIA's download-requirements helper metadata, not file
extension. CSV files can be either ordinary data files or Data Retriever
manifests.

Many TCIA rows also have a separate search or browse button. The prototype keeps
that distinct from the download artifact:

- `download_url` / `contentUrl` is the downloadable file, manifest, or transfer
  handoff.
- `search_url` is the web interface used to inspect, search, or preview the
  row before downloading.
- `search_system` names that interface, such as NBIA Search, PathDB, CTDC, or
  General Commons.

Those search pages are useful machine-readable access metadata, but they are not
modeled as Croissant `FileObject` payloads.

## Generate Croissant From A Snapshot

The original access-summary exporter uses Python's standard library and expects
a TCIA metadata SQLite snapshot with WordPress records. The recordset generator
also reads CSV and XLSX source metadata using the dependencies in
`requirements.txt`.

This repository does not bundle the snapshot. For local experiments, get the
latest published snapshot from the `tcia-query-skill` repository and point the
exporter at the downloaded `tcia_snapshot.sqlite` file. If you have the
`tcia-query-skill` repo checked out, the normal refresh command is:

```bash
python3 scripts/tcia_snapshot.py ensure
```

That command populates the skill's local cache with:

```text
cache/tcia_snapshot.sqlite
```

Alternatively, download the latest release assets from the TCIA query skill
repository and decompress `tcia_snapshot.sqlite.gz`.

```bash
python3 scripts/generate_tcia_croissant.py \
  --db path/to/tcia_snapshot.sqlite \
  --out croissant-output
```

The recordset pilot additionally requires the official `.tcia`, CSV, and XLSX
source artifacts named by the generator's `--help` output, plus the query-skill
public non-DICOM SQLite artifact. Generation records source hashes and refuses
UID mismatches or duplicate retrieval keys:

```bash
python3 scripts/generate_recordset_examples.py \
  --snapshot-db path/to/tcia_snapshot.sqlite \
  --public-non-dicom-db path/to/public_non_dicom_metadata.sqlite \
  --four-d-lung-manifest path/to/4d-lung.tcia \
  --four-d-lung-metadata path/to/4d-lung-metadata.xlsx \
  --cmb-public-manifest path/to/cmb-aml-public.tcia \
  --cmb-public-metadata path/to/cmb-aml-public-metadata.xlsx \
  --cmb-controlled-manifest path/to/cmb-aml-controlled.csv \
  --saros-info path/to/saros-segmentation-info.csv \
  --out recordset-output
```

## Validate Examples

Install the official validator:

```bash
python3 -m pip install -r requirements.txt
```

Validate one file:

```bash
mlcroissant validate --jsonld examples/4d-lung.open-manifest.croissant.jsonld
```

For the external-CSV pilot:

```bash
mlcroissant validate \
  --jsonld=examples/recordset-manifests/collections/cmb-aml/croissant.jsonld
```

Validate all examples:

```bash
python3 - <<'PY'
from pathlib import Path
import mlcroissant as mlc

for path in sorted(Path("examples").glob("**/*.jsonld")):
    mlc.Dataset(str(path))
    print(f"ok {path}")
PY
```

Run the recordset invariants:

```bash
python3 -m unittest discover -s tests
```

## More Detail

See [docs/prototype-developer-notes.md](docs/prototype-developer-notes.md) for
the design rationale, standards strategy, mapping details, and production
questions for TCIA developers.

See
[docs/website-integration-recommendations.md](docs/website-integration-recommendations.md)
for recommendations on updating TCIA dataset page Schema.org JSON-LD, linking
Croissant files from HTML, introducing reusable ODRL policies, and connecting
stable Croissant URLs back to DataCite DOI records.
