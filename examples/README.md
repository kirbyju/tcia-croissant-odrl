# Example Croissant Files

These examples are representative samples generated from a TCIA metadata
snapshot. They are included to show the metadata shape and access-row modeling,
not to provide a complete TCIA Croissant corpus.

| File | Demonstrates |
| --- | --- |
| `4d-lung.open-manifest.croissant.jsonld` | Open dataset with a TCIA Data Retriever manifest. |
| `a091105.controlled-manifest.croissant.jsonld` | Controlled-access dataset with a Data Retriever manifest. |
| `a091105-tumor-annotations.manifest-and-direct-csv.croissant.jsonld` | Analysis Result with both a DICOM manifest row and a direct CSV row. |
| `hnscc.mixed-access.croissant.jsonld` | Mixed open/controlled metadata and multiple download rows. |
| `breast-cancer-screening-dbt.noncommercial.croissant.jsonld` | Open noncommercial licensing and multiple access rows. |

Important: `mlcroissant.Dataset(...).records("download-...")` returns metadata
about a TCIA download/access row. For manifest rows, it does not return the
payload files behind the manifest.
