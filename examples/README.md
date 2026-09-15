# Example Croissant Files

These examples are representative samples generated from a TCIA metadata
snapshot. They are included to show the metadata shape and access-row modeling,
not to provide a complete TCIA Croissant corpus.

| File | Demonstrates |
| --- | --- |
| `4d-lung.open-manifest.croissant.jsonld` | Public DICOM dataset with a TCIA Data Retriever manifest and IDC as the downstream storage/access route. |
| `cmb-aml.radiology-pathology-external-clinical.croissant.jsonld` | Controlled-access CTDC radiology manifest, open radiology manifest, Aspera pathology package, PathDB pathology search URL, and external clinical-resource signal. |
| `breast-cancer-screening-dbt.noncommercial.croissant.jsonld` | Open dataset with noncommercial licensing, useful for testing CC BY-NC policy handling. |
| `hnscc.mixed-access.croissant.jsonld` | Mixed open/controlled dataset with controlled DICOM manifests routed through General Commons plus direct open clinical files. |
| `saros.analysis-result-nifti-derived.croissant.jsonld` | Analysis Result example with open NIfTI/ZIP segmentation outputs and source-image context derived from controlled, CC BY, and CC BY-NC source image manifests. |

Important: `mlcroissant.Dataset(...).records("download-...")` returns metadata
about a TCIA download/access row. For manifest rows, it does not return the
payload files behind the manifest.

The examples also include Schema.org-aligned fields that support website
integration, including `alternateName`, `includedInDataCatalog`, and
`conditionsOfAccess`. These are intended to mirror the page-level Schema.org
recommendations while keeping Croissant as the richer linked metadata document.

SAROS is intentionally different from the Collection examples. Its current
Analysis Result downloads are the derived segmentation artifacts, while its
`isBasedOn` metadata points back to source collections and source-image access
rows so downstream tools can see the derivation context without treating source
images as SAROS result payloads.

A091105 examples are intentionally not included because that dataset is
currently offline while it waits for migration into CTDC.

The external-CSV recordset pilot is separate from these access-summary files.
See [`recordset-manifests/`](recordset-manifests/) for four dataset Croissant
documents, seven recordset CSV files, generation evidence, and review notes.
