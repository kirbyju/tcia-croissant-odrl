#!/usr/bin/env python3
"""Run F-UJI's RDF collector and four metadata evaluators without fetching data.

This is a component comparison, not an end-to-end FAIR assessment. Install a
pinned official F-UJI checkout separately; pass it on PYTHONPATH if necessary.
No DOI resolution, landing-page discovery, repository lookup or data downloads
are performed. Network requests are rejected to keep that boundary explicit.
"""
import argparse
import asyncio
import contextlib
import datetime as dt
import hashlib
import io
import json
import logging
import re
import socket
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import fuji_server
import lxml.html  # Also imported by F-UJI's full metadata harvester.
from fuji_server.helper.preprocessor import Preprocessor
from fuji_server.helper.metadata_collector_rdf import MetaDataCollectorRdf
from fuji_server.helper.metadata_collector import MetadataOfferingMethods
from fuji_server.helper.metric_helper import MetricHelper
from fuji_server.evaluators.fair_evaluator_minimal_metadata import FAIREvaluatorCoreMetadata
from fuji_server.evaluators.fair_evaluator_semantic_vocabulary import FAIREvaluatorSemanticVocabulary
from fuji_server.evaluators.fair_evaluator_data_provenance import FAIREvaluatorDataProvenance
from fuji_server.evaluators.fair_evaluator_community_metadata import FAIREvaluatorCommunityMetadata
from fuji_server.evaluators.fair_evaluator_data_content_metadata import FAIREvaluatorDataContentMetadata
from fuji_server.helper.signposting_helper import SignpostingHelper


class RecordingCollector(MetaDataCollectorRdf):
    def get_main_entity(self, graph):
        result = super().get_main_entity(graph)
        self.selected_entity = {"id": str(result[0]), "types": result[1]}
        return result


def reject_network(*args, **kwargs):
    raise RuntimeError("Network disabled: metadata component assessment only")


async def assess(path, document=None):
    if document is None:
        document = json.loads(path.read_text())
    logger = logging.getLogger(str(path))
    logger.addHandler(logging.NullHandler())
    logger.setLevel(logging.CRITICAL)
    collector = RecordingCollector(logger, json_ld_content=document)
    source, metadata = await collector.parse_metadata()
    helper = MetricHelper("metrics_v0.8", logger)
    fuji = SimpleNamespace(
        isDebug=False, count=0, logger=logger, metadata_merged=metadata,
        metadata_sources=[(source, MetadataOfferingMethods.JSON_IN_HTML)],
        namespace_uri=list(collector.namespaces),
        linked_namespace_uri=collector.linked_namespaces,
        LINKED_VOCAB_INDEX=Preprocessor.get_linked_vocab_index(),
        DEFAULT_NAMESPACES=Preprocessor.getDefaultNamespaces(),
        LOG_SUCCESS=25, LOG_FAILURE=35, metric_helper=helper,
        METRICS=helper.get_custom_metrics(["metric_name", "total_score", "metric_tests", "metric_number"]),
        metadata_service_url=None, landing_url=document.get("url"),
        sparql_endpoint=None, csw_endpoint=None, oaipmh_endpoint=None,
        community_standards=[], community_standards_uri={}, repo_helper=None,
    )
    result = {"sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
              "harvested": metadata, "namespaces": sorted(set(collector.namespaces)),
              "selected_entity": getattr(collector, "selected_entity", None), "metrics": {}}
    for evaluator in (FAIREvaluatorCoreMetadata, FAIREvaluatorSemanticVocabulary,
                      FAIREvaluatorDataProvenance, FAIREvaluatorCommunityMetadata):
        # I2 normalizes namespaces in place; isolate the input to every metric.
        fuji.namespace_uri = list(collector.namespaces)
        fuji.linked_namespace_uri = dict(collector.linked_namespaces)
        evaluation = await evaluator(fuji).getResult()
        result["metrics"][evaluation["metric_identifier"]] = evaluation
    result["distribution_descriptors"] = metadata.get("object_content_identifier", [])
    fuji.content_identifier = {}
    for descriptor in result["distribution_descriptors"]:
        fuji.content_identifier[descriptor["url"]] = {
            "claimed_type": descriptor.get("type") if descriptor.get("type") not in (None, "None", "") else None,
            "claimed_size": descriptor.get("size") if descriptor.get("size") not in (None, "None", "") else None,
        }
    descriptor_evaluator = FAIREvaluatorDataContentMetadata(fuji)
    result["R1_descriptor_presence_subtest_only"] = {
        url: descriptor_evaluator.subtestDataTypeAndSizeGiven(url)
        for url in fuji.content_identifier
    }
    return result


async def main(args):
    Preprocessor.set_metric_yaml_path(Preprocessor.fuji_server_dir / "yaml")
    results = {"scope": "Offline F-UJI RDF collector plus F2, I2, R1.2 and R1.3 evaluators; not an overall FAIR score",
               "fuji_version": getattr(fuji_server, "__version__", "unknown"),
               "fuji_commit": args.fuji_commit,
               "assessed_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
               "metrics_version": "0.8", "examples": {}}
    for path in sorted(args.examples.rglob("*.jsonld")):
        results["examples"][str(path.relative_to(args.examples))] = await assess(path)
    # Isolate the keyword recommendation using an otherwise identical existing
    # Dataset. This ablation is not a reconstruction of either assessed DOI.
    keyword_path = args.examples / "4d-lung.open-manifest.croissant.jsonld"
    if keyword_path.exists():
        without_keywords = json.loads(keyword_path.read_text())
        without_keywords.pop("keywords", None)
        results["keyword_ablation"] = await assess(keyword_path, without_keywords)
    guide = args.examples.parent / "docs/implementation-guide.md"
    if guide.exists():
        blocks = re.findall(r"```html\n(.*?)```", guide.read_text(), re.S)
        html = "<html><head>" + "\n".join(blocks) + "</head><body></body></html>"
        helper = SignpostingHelper(metric_version=0.8)
        await helper.set_all_typed_and_signposting_links(
            "https://www.cancerimagingarchive.net/collection/cmb-aml/", None, html, {})
        results["guide_head_link_parser_test"] = helper.get_links(["alternate", "describedby"], "content")
        for link in results["guide_head_link_parser_test"]:
            # Same media-type filter as this pinned F-UJI harvester's linked-RDF path.
            link["passes_linked_rdf_media_type_filter"] = bool(re.search(
                r"[\/+](rdf(\+xml)?|(?:x-)?turtle|ttl|n3|n-triples|ld\+json)+$", str(link["type"])))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(results, indent=2, default=str) + "\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--examples", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--fuji-commit", help="Pinned checkout revision, recorded for reproducibility")
    args = parser.parse_args()
    # F-UJI writes diagnostics to stdout. Keep JSON in the requested output file.
    with patch.object(socket.socket, "connect", reject_network), contextlib.redirect_stdout(io.StringIO()):
        logging.getLogger("tldextract").setLevel(logging.CRITICAL)
        asyncio.run(main(args))
