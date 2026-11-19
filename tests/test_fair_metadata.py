import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from fair_metadata import add_metadata_provenance, dataset_keywords


class FairMetadataTest(unittest.TestCase):
    def test_keyword_mapping_accepts_snapshot_json_without_inventing_terms(self):
        value = dataset_keywords({"short_title": "Example", "dataset_type": "Collection",
                                  "cancer_types": '["Lung Cancer"]',
                                  "normalized_json": '{"species":["Human"],"data_categories":["Radiology Imaging"]}'})
        self.assertEqual(value, ["Example", "Collection", "Lung Cancer", "Human", "Radiology Imaging"])

    def test_exporter_activity_describes_metadata_and_recordsets(self):
        for path in (ROOT / "examples").rglob("*.jsonld"):
            with self.subTest(path=path):
                doc = json.loads(path.read_text())
                self.assertNotIn("prov:wasGeneratedBy", doc)
                metadata = next(x for x in doc["subjectOf"] if x["@id"].endswith("croissant.jsonld"))
                self.assertIn("prov:wasDerivedFrom", metadata)
                activity = metadata["prov:wasGeneratedBy"]
                self.assertIn("prov:used", activity)
                for recordset in doc["recordSet"]:
                    self.assertEqual(recordset["prov:wasGeneratedBy"]["@id"], activity["@id"])
                self.assertTrue(doc["keywords"])

    def test_manifest_sizes_are_not_payload_sizes(self):
        for path in (ROOT / "examples").glob("*.jsonld"):
            doc = json.loads(path.read_text())
            for item in doc.get("distribution", []) + doc.get("isBasedOn", []):
                properties = {x.get("name"): x.get("value") for x in item.get("additionalProperty", [])}
                if properties.get("TCIA download artifact role") in ("manifest", "transfer package"):
                    self.assertNotIn("contentSize", item)
                self.assertNotIn("application/vnd.tcia.manifest", item.get("encodingFormat", []))
                self.assertNotIn("application/vnd.nifti", item.get("encodingFormat", []))

    def test_provenance_mapping_is_idempotent_and_preserves_other_links(self):
        document = {"@context": {}, "@id": "https://doi.org/10.1234/test", "name": "Test",
                    "url": "https://example.org/data/", "subjectOf": {"@id": "https://example.org/paper"}}
        add_metadata_provenance(document)
        first = json.dumps(document, sort_keys=True)
        add_metadata_provenance(document)
        self.assertEqual(first, json.dumps(document, sort_keys=True))
        self.assertEqual(document["subjectOf"][0]["@id"], "https://example.org/paper")


if __name__ == "__main__":
    unittest.main()
