import unittest

from constants import DEFAULT_TENDENCIES, LOC_SIM_THRESHOLD
from predict import (
    get_default_tendencies,
    build_name_to_category,
    build_item_loc_graph,
    build_loc_sim_graph,
    unified_predict,
)


def make_record(name, location, category="その他", found_date="2026-11-20"):
    return {
        "id": "test-id",
        "name": name,
        "location": location,
        "category": category,
        "found_date": found_date,
        "resolved": False,
    }


class TestGetDefaultTendencies(unittest.TestCase):
    def test_known_item_returns_default_places(self):
        result = get_default_tendencies("財布")
        self.assertIsNotNone(result)
        expected = DEFAULT_TENDENCIES["財布"]
        self.assertEqual(len(result), len(expected))
        for (loc, weight, pct, top), exp_loc in zip(result, expected):
            self.assertEqual(loc, exp_loc)
            self.assertEqual(weight, 1)
            self.assertEqual(pct, 100 / len(expected))
            self.assertEqual(top, exp_loc == expected[0])

    def test_unknown_item_returns_none(self):
        self.assertIsNone(get_default_tendencies("存在しない物"))


class TestBuildNameToCategory(unittest.TestCase):
    def test_most_frequent_category_wins(self):
        records = [
            {"name": "ポケットカバン", "category": "カバン"},
            {"name": "ポケットカバン", "category": "カバン"},
            {"name": "ポケットカバン", "category": "財布"},
        ]
        self.assertEqual(build_name_to_category(records)["ポケットカバン"], "カバン")


class TestBuildItemLocGraph(unittest.TestCase):
    def test_builds_item_to_loc_and_loc_to_item(self):
        records = [make_record("財布", "机の上"), make_record("財布", "カバンの中")]
        item_to_loc, loc_to_item = build_item_loc_graph(records)
        self.assertEqual(dict(item_to_loc["財布"]), {"机の上": 1, "カバンの中": 1})
        self.assertEqual(dict(loc_to_item["机の上"]), {"財布": 1})


class TestBuildLocSimGraph(unittest.TestCase):
    def test_similar_locations_are_linked(self):
        records = [make_record("財布", "机の上"), make_record("財布", "ソファ")]
        graph = build_loc_sim_graph(records)
        self.assertIn("机の上", graph)
        self.assertIn("ソファ", graph["机の上"])
        self.assertGreaterEqual(graph["机の上"]["ソファ"], LOC_SIM_THRESHOLD)

    def test_disjoint_locations_are_not_linked(self):
        records = [make_record("財布", "机の上"), make_record("鍵", "ソファ")]
        graph = build_loc_sim_graph(records)
        self.assertNotIn("ソファ", graph.get("机の上", {}))


class TestUnifiedPredict(unittest.TestCase):
    def test_empty_query_returns_none(self):
        results, ctx = unified_predict("", [make_record("財布", "机の上")], None)
        self.assertIsNone(results)
        self.assertEqual(ctx, "")

    def test_no_records_falls_back_to_default_tendencies(self):
        results, ctx = unified_predict("財布", [], None)
        self.assertEqual(len(results), len(DEFAULT_TENDENCIES["財布"]))
        self.assertIn("一般的な傾向", ctx)

    def test_no_records_no_default_returns_empty(self):
        results, ctx = unified_predict("存在しない物", [], None)
        self.assertEqual(results, [])
        self.assertEqual(ctx, "")

    def test_unified_predict_uses_injected_fallback(self):
        fallback = [("車の中", 1, 100.0, True)]
        results, ctx = unified_predict("財布", [], None, fallback=fallback)
        self.assertEqual(results, [fallback[0]])
        self.assertIn("一般的な傾向", ctx)

    def test_unified_predict_multiple_seeds(self):
        records = [
            make_record("財布", "机の上", "財布"),
            make_record("財布ケース", "カバンの中", "財布"),
        ]
        results, ctx = unified_predict("財布", records, None)
        self.assertEqual(len(results), 2)
        self.assertIn("起点2", ctx)
        self.assertIn("直接一致", ctx)
        top_count = sum(1 for r in results if r[3])
        self.assertEqual(top_count, 1)

    def test_no_fuzzy_match_falls_back_to_default_tendencies(self):
        results, ctx = unified_predict("財布", [make_record("鍵", "玄関", "鍵")], None)
        self.assertEqual(len(results), len(DEFAULT_TENDENCIES["財布"]))
        self.assertIn("一般的な傾向", ctx)

    def test_single_record_direct_result(self):
        results, ctx = unified_predict("財布", [make_record("財布", "机の上", "財布")], None)
        self.assertEqual(len(results), 1)
        loc, weight, pct, top = results[0]
        self.assertEqual(loc, "机の上")
        self.assertEqual(pct, 100.0)
        self.assertTrue(top)
        self.assertIn("直接一致", ctx)

    def test_top_location_marked_once(self):
        records = [
            make_record("財布", "机の上", "財布"),
            make_record("財布", "カバンの中", "財布"),
        ]
        results, ctx = unified_predict("財布", records, None)
        self.assertEqual(len(results), 2)
        top_count = sum(1 for r in results if r[3])
        self.assertEqual(top_count, 1)
        pcts = [r[2] for r in results]
        self.assertEqual(pcts, sorted(pcts, reverse=True))

    def test_category_filter_is_applied(self):
        records = [
            make_record("財布", "机の上", "財布"),
            make_record("鍵", "玄関", "鍵"),
        ]
        results, ctx = unified_predict("財布", records, "財布")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0][0], "机の上")
        self.assertIn("直接一致", ctx)


if __name__ == "__main__":
    unittest.main()
