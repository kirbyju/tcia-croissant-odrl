import csv
import hashlib
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = ROOT / "examples" / "recordset-manifests"

EXPECTED_CSV = {
    "collections/4d-lung/recordsets/42107-public-dicom-series.csv": (6690, "SeriesInstanceUID"),
    "collections/hnscc-mif-mihc-comparison/recordsets/pathdb-images.csv": (3212, "imageUrl"),
    "collections/cmb-aml/recordsets/48105-public-dicom-series.csv": (52, "SeriesInstanceUID"),
    "collections/cmb-aml/recordsets/48107-controlled-drs-files.csv": (65, "drs_uri"),
    "collections/cmb-aml/recordsets/41647-aspera-pathology-files.csv": (62, "asset_id"),
    "analysis-results/saros/recordsets/46289-segmentation-files.csv": (1709, "asset_id"),
    "analysis-results/saros/recordsets/46291-data-records.csv": (900, "id"),
}

DATASET_DOCUMENTS = [
    "collections/4d-lung/croissant.jsonld",
    "collections/hnscc-mif-mihc-comparison/croissant.jsonld",
    "collections/cmb-aml/croissant.jsonld",
    "analysis-results/saros/croissant.jsonld",
]


def load_json(relative_path: str) -> dict:
    return json.loads((EXAMPLES / relative_path).read_text(encoding="utf-8"))


class RecordsetExamplesTest(unittest.TestCase):
    def test_csv_inventories_have_expected_counts_and_unique_keys(self) -> None:
        for path, (expected_count, key) in EXPECTED_CSV.items():
            with self.subTest(path=path):
                with (EXAMPLES / path).open("r", encoding="utf-8", newline="") as stream:
                    reader = csv.DictReader(stream)
                    rows = list(reader)
                self.assertEqual(len(rows), expected_count)
                self.assertIn(key, reader.fieldnames or [])
                keys = [row[key] for row in rows]
                self.assertNotIn("", keys)
                self.assertEqual(len(keys), len(set(keys)))
                route_headers = {"SeriesInstanceUID", "imageUrl", "drs_uri"}.intersection(
                    reader.fieldnames or []
                )
                self.assertLessEqual(len(route_headers), 1)

    def test_croissant_fields_are_sourced_from_csv_fileobjects(self) -> None:
        seen_csv = set()
        for path in DATASET_DOCUMENTS:
            document = load_json(path)
            self.assertEqual(document["conformsTo"], "http://mlcommons.org/croissant/1.1")
            distributions = {item["@id"]: item for item in document["distribution"]}
            for recordset in document["recordSet"]:
                self.assertNotIn("data", recordset)
                source_ids = set()
                for field in recordset["field"]:
                    source = field["source"]
                    source_id = source["fileObject"]["@id"]
                    source_ids.add(source_id)
                    self.assertEqual(source["extract"]["column"], field["name"])
                self.assertEqual(len(source_ids), 1)
                source_id = source_ids.pop()
                distribution = distributions[source_id]
                self.assertEqual(distribution["@type"], "cr:FileObject")
                self.assertEqual(distribution["encodingFormat"], "text/csv")
                relative_csv = source_id.split("/croissant/", 1)[1]
                local_csv = (EXAMPLES / Path(path).parent / relative_csv).resolve()
                self.assertTrue(local_csv.is_file())
                self.assertEqual(distribution["sha256"], hashlib.sha256(local_csv.read_bytes()).hexdigest())
                self.assertEqual(distribution["contentSize"], f"{local_csv.stat().st_size} B")
                seen_csv.add(str(local_csv.relative_to(EXAMPLES.resolve())))
        self.assertEqual(seen_csv, set(EXPECTED_CSV))

    def test_controlled_csv_contains_identifiers_not_credentials(self) -> None:
        path = EXAMPLES / "collections/cmb-aml/recordsets/48107-controlled-drs-files.csv"
        with path.open("r", encoding="utf-8", newline="") as stream:
            rows = list(csv.DictReader(stream))
        self.assertEqual({row["dbGaPStudyAccession"] for row in rows}, {"phs002192"})
        self.assertTrue(all(row["drs_uri"].startswith("drs://") for row in rows))
        serialized = path.read_text(encoding="utf-8").casefold()
        for forbidden in ("access_token", "refresh_token", "authorization: bearer", "signedurl"):
            self.assertNotIn(forbidden, serialized)

    def test_generation_summary_matches_all_generated_files(self) -> None:
        summary = load_json("generation-summary.json")
        self.assertEqual(len(summary["files"]), 11)
        self.assertEqual(summary["record_storage"], "external_csv_fileobjects")
        for path, metadata in summary["files"].items():
            with self.subTest(path=path):
                body = (EXAMPLES / path).read_bytes()
                self.assertEqual(hashlib.sha256(body).hexdigest(), metadata["sha256"])


if __name__ == "__main__":
    unittest.main()
