# External CSV recordset examples

Each dataset directory contains one `croissant.jsonld`. Its `recordsets/`
directory contains one human-readable CSV for each modeled WordPress download.

| Dataset | Croissant RecordSets | CSV rows |
| --- | ---: | ---: |
| 4D-Lung | 1 | 6,690 |
| HNSCC-mIF-mIHC-comparison | 1 | 3,212 |
| CMB-AML | 3 | 179 |
| SAROS | 2 | 2,609 |

There are four Croissant documents and seven CSV files containing 12,690 rows.
Every Croissant field identifies its source CSV and column. The generated
`FileObject` also records the CSV byte size and SHA-256 checksum.

Suggested review order:

1. `collections/cmb-aml/croissant.jsonld` shows three recordsets with public
   DICOM, controlled DRS, and Aspera package routes.
2. Its `recordsets/` directory shows the corresponding CSV inventories.
3. `collections/4d-lung/` shows the larger DICOM-series example with the former
   metadata workbook merged into the recordset CSV.
4. `analysis-results/saros/` shows an Analysis Result with two recordsets.

See [the design explanation](../../docs/recordset-manifest-design.md) for the
publication model, terminology, Data Retriever flow, controlled-access
boundary, provenance, and questions for reviewers.

`generation-summary.json` records the source and output hashes.
`validation-summary.json` records the Croissant and CSV verification results.

These are design-review examples, not production download contracts.
