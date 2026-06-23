# TCIA Croissant Metadata Prototype

This repository is a small prototype for publishing TCIA dataset metadata as
Croissant JSON-LD while preserving TCIA's existing website, DOI, policy, and
download-tool workflows.

The current scope is intentionally conservative: Croissant describes TCIA
datasets and their download/access rows. It does not try to make all TCIA
imaging payloads directly importable through `mlcroissant`.

## What Is Included

```text
docs/prototype-developer-notes.md
docs/website-integration-recommendations.md
scripts/generate_tcia_croissant.py
examples/*.croissant.jsonld
examples/validation-summary.json
requirements.txt
```

The example Croissant files are representative samples only. They illustrate
five important TCIA edge cases: public DICOM routed through IDC, controlled
access routed through CTDC, noncommercial licensing, mixed access routed through
General Commons, and an Analysis Result with NIfTI segmentations derived from
source image collections with mixed access and licensing.

## What Is Not Included

This repo does not include:

- a TCIA SQLite snapshot
- a full generated Croissant corpus
- TCIA Data Retriever logic
- Aspera download automation
- IDC, General Commons, or DICOM download code
- production TCIA website integration

Those pieces should remain in the appropriate TCIA systems and tools.

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

The exporter uses Python's standard library and expects a TCIA metadata SQLite
snapshot with WordPress records.

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

## Validate Examples

Install the official validator:

```bash
python3 -m pip install -r requirements.txt
```

Validate one file:

```bash
mlcroissant validate --jsonld examples/4d-lung.open-manifest.croissant.jsonld
```

Validate all examples:

```bash
python3 - <<'PY'
from pathlib import Path
import mlcroissant as mlc

for path in sorted(Path("examples").glob("*.croissant.jsonld")):
    mlc.Dataset(str(path))
    print(f"ok {path}")
PY
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

## Licensing

Before publishing this folder as a public GitHub repository, choose and add an
appropriate repository license. Do not assume this prototype's code and examples
inherit the licenses of the referenced TCIA datasets.
