# Croissant with external recordset CSV files

## Proposed publication model

Publish one Croissant 1.1 document for each TCIA Collection or Analysis Result.
Model each current WordPress download as a Croissant `RecordSet`, with one
human-readable CSV `FileObject` containing the recordset inventory and metadata.

```text
TCIA dataset Croissant
├── RecordSet: WordPress download A
│   └── fields source columns from download-a.csv FileObject
├── RecordSet: WordPress download B
│   └── fields source columns from download-b.csv FileObject
└── distribution
    ├── download-a.csv
    └── download-b.csv
```

This replaces the earlier inline `RecordSet.data` experiment. The repository
now presents one approach for expert review: externally stored CSV records,
formally described by Croissant.

## Why the CSV is a FileObject

In Croissant, a `FileObject` represents one file that is part of a dataset. A
`FileSet` represents a homogeneous set of actual files, such as every `.nii.gz`
member inside an archive. Therefore, the tabular recordset inventory is a
`FileObject`, not a `FileSet`.

Each Croissant `Field` contains a `source` that identifies:

- the CSV `FileObject`; and
- the CSV column to extract.

For example:

```json
{
  "@type": "cr:Field",
  "@id": ".../records/SeriesInstanceUID",
  "name": "SeriesInstanceUID",
  "dataType": "sc:Text",
  "source": {
    "fileObject": {"@id": ".../42107-public-dicom-series.csv"},
    "extract": {"column": "SeriesInstanceUID"}
  }
}
```

The CSV is readable without a Croissant library. The Croissant document adds
the stable recordset identity, key, field types and meanings, access policy,
source provenance, checksum, and exact relationship between the CSV and the
published dataset.

## WordPress and Data Retriever behavior

The intended publication contract is:

1. A dataset page publishes one stable Croissant URL.
2. Each WordPress download record corresponds to one Croissant `RecordSet` and
   its CSV `FileObject`.
3. A recordset download supplies the Croissant URL and selected RecordSet ID.
4. A full-dataset download supplies the Croissant URL without restricting the
   RecordSet IDs.
5. Data Retriever loads the selected CSV files and dispatches on the retrieval
   field declared by each RecordSet.

The CSV files remain route-specific. A CSV contains no more than one Data
Retriever route header:

- `SeriesInstanceUID` for public DICOM series;
- `imageUrl` for direct public files; or
- `drs_uri` for controlled objects.

Other recordsets, such as archive inventories, retain their native key and
explicit route description. A viewer URL remains distinct from a payload URL.
An Aspera inventory is not asserted to be byte-equivalent to PathDB content.

## Examples

| Dataset | WordPress-style recordset | CSV rows | Key |
| --- | --- | ---: | --- |
| 4D-Lung | Public DICOM imaging | 6,690 | `SeriesInstanceUID` |
| HNSCC-mIF-mIHC-comparison | PathDB public images | 3,212 | `imageUrl` |
| CMB-AML | Public DICOM imaging | 52 | `SeriesInstanceUID` |
| CMB-AML | Controlled imaging | 65 | `drs_uri` |
| CMB-AML | Original pathology transfer | 62 | `asset_id` |
| SAROS | Segmentation archive inventory | 1,709 | `asset_id` |
| SAROS | Segmentation information | 900 | `id` |

There are four Croissant documents and seven recordset CSV files. The examples
contain 12,690 rows in total.

## Metadata preservation

Patient ID, Study Date, Study Description, Series Description, modality, file
size, and other available fields are CSV columns described by Croissant fields.
This allows TCIA to retire a separate WordPress “metadata” attachment after the
recordset CSV becomes the authoritative combined inventory and metadata table.

The generator preserves every source column, records renamed source headers in
`alternateName`, keeps blank source cells blank, and adds only explicit
recordset constants such as access level and retrieval route. It fails on
duplicate retrieval keys. For the 4D-Lung and CMB-AML public DICOM examples, it
also requires the `.tcia` UID set to exactly match the metadata workbook UID
set.

## Controlled access and GA4GH

The CMB-AML controlled CSV contains public metadata, published CRDC `drs_uri`
values, and dbGaP study accession `phs002192`. It contains no credentials,
tokens, passports, access URLs, or transient signed URLs. A manifest identifies
data but does not grant access.

NIH Researcher Auth Service supports GA4GH Passports and Visas, and NCBI
documents an RAS Passport flow for dbGaP-authorized use of NCBI DRS. That does
not establish that the current TCIA CTDC route accepts an NIH RAS Passport. The
example records the relationship as explanatory metadata without claiming
runtime interoperability.

Data Use Ontology or detailed ODRL assertions should be added only when the
exact data-use limitation has an authoritative source or curator-reviewed
mapping. The generator does not infer DUO terms from a dbGaP accession or
disease label.

## Provenance and current limitations

Each generated CSV is represented by a `FileObject` with its byte size and
SHA-256 checksum. The generation summary also records the input artifact hashes
and TCIA snapshot timestamp.

The examples use current official manifests where available and dated local
TCIA query-skill artifacts for enriched metadata. Installation of the current
published V2 bundle failed its manifest-asset validation during this work, so
these are reproducible design examples rather than a claim of a verified-current
V2 release export.

The CMB-AML pathology inventory is explicitly partial: WordPress reports 67
images while the available submitted-original inventory has 62 file rows. The
generator preserves that discrepancy rather than inventing records or
substituting PathDB representations.

## Review questions

- Is one dataset Croissant plus one CSV per WordPress recordset the desired
  publication unit?
- Is a RecordSet ID sufficient for WordPress and Data Retriever selection, or
  should WordPress store a separate stable selector?
- Are the proposed record grains and retrieval keys correct for every route?
- Which field names should become a stable TCIA manifest profile?
- When should an actual payload collection also be modeled as a `FileSet`?
- What publication event and version change should regenerate the Croissant and
  CSV checksums?

## References

- [Croissant 1.1 specification](https://docs.mlcommons.org/croissant/docs/croissant-spec-1.1.html)
- [Croissant RAI specification](https://docs.mlcommons.org/croissant/docs/croissant-rai-spec.html)
- [NIH Researcher Auth Service](https://auth.nih.gov/docs/RAS/)
- [NIH RAS service offerings](https://auth.nih.gov/docs/RAS/serviceofferings.html)
- [NCBI dbGaP Power User Portal](https://www.ncbi.nlm.nih.gov/gap/power-user-portal/)
- [General Commons user guide](https://datacommons.cancer.gov/repository/general-commons)
