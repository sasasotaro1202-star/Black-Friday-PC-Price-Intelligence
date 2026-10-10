import json
import pathlib
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import discover


class DiscoveryTests(unittest.TestCase):
    def test_curated_skus_sharing_a_family_page_are_not_dropped(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            (root / "config").mkdir()
            (root / "data").mkdir()
            shared_url = "https://store.asus.com/jp/rog-strix-g16-g614.html"
            (root / "config" / "targets.json").write_text(json.dumps({
                "allowed_domains": ["store.asus.com"],
                "queries": [],
            }), encoding="utf-8")
            (root / "config" / "candidate_catalog.json").write_text(json.dumps({
                "candidates": [
                    {"id": "variant-a", "name": "Variant A", "url": shared_url,
                     "url_is_exact": False, "aliases": ["MODEL-A"]},
                    {"id": "variant-b", "name": "Variant B", "url": shared_url,
                     "url_is_exact": False, "aliases": ["MODEL-B"]},
                ]
            }), encoding="utf-8")
            (root / "data" / "watchlist.json").write_text(json.dumps({
                "generated_at": "2026-10-01T00:00:00+09:00",
                "urls": [
                    {"id": "variant-a", "url": shared_url,
                     "query": "MODEL-A", "priority": "critical"}
                ],
            }), encoding="utf-8")

            with patch.object(discover, "ROOT", str(root)), patch.object(discover, "search", return_value=[]):
                discover.main()

            result = json.loads((root / "data" / "watchlist.json").read_text(encoding="utf-8"))
            ids = {x["id"] for x in result["urls"]}
            shared_entries = [x for x in result["urls"] if x["url"] == shared_url]
            self.assertEqual(ids, {"variant-a", "variant-b"})
            self.assertEqual(len(shared_entries), 2)
            self.assertEqual(result["discovery_stats"]["newly_discovered_count"], 1)

    def test_missing_curated_candidate_is_restored(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            (root / "config").mkdir()
            (root / "data").mkdir()
            (root / "config" / "targets.json").write_text(json.dumps({
                "allowed_domains": ["example.com"],
                "queries": [],
            }), encoding="utf-8")
            (root / "config" / "candidate_catalog.json").write_text(json.dumps({
                "candidates": [
                    {"id": "curated-pc", "name": "Curated PC",
                     "url": "https://example.com/pc", "url_is_exact": True}
                ]
            }), encoding="utf-8")
            (root / "data" / "watchlist.json").write_text(json.dumps({
                "generated_at": "2026-10-10T10:00:00+09:00",
                "urls": [],
            }), encoding="utf-8")
            with patch.object(discover, "ROOT", str(root)), patch.object(discover, "search", return_value=[]):
                discover.main()
            result = json.loads((root / "data" / "watchlist.json").read_text(encoding="utf-8"))
            self.assertEqual([x["id"] for x in result["urls"]], ["curated-pc"])


if __name__ == "__main__":
    unittest.main()
