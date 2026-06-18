from collections import Counter, defaultdict
from datetime import datetime
import math

from constants import (
    DEFAULT_TENDENCIES,
    RWR_ALPHA,
    RWR_ITERATIONS,
    RWR_CONVERGENCE,
    LOC_SIM_THRESHOLD,
    LOC_SIM_DECAY,
    LOC_TEMPORAL_WEIGHT,
    LOC_TEMPORAL_BASE,
    RECENCY_HALFLIFE_DAYS,
    DOW_WEIGHTS,
    DOW_OTHER,
    HOUR_SIGMA_SQ,
    RELATED_SCORE_THRESHOLD,
)
from utils import fuzzy_match, parse_dt


def get_default_tendencies(query):
    for name, places in DEFAULT_TENDENCIES.items():
        if fuzzy_match(query, name):
            total = len(places)
            return [(p, 1, 100 / total, i == 0) for i, p in enumerate(places)]
    return None


def build_name_to_category(records):
    name_to_cat = {}
    cat_counts = defaultdict(Counter)
    for r in records:
        name = r.get("name", "")
        cat = r.get("category", "")
        if name and cat:
            cat_counts[name][cat] += 1
    for name, counts in cat_counts.items():
        name_to_cat[name] = counts.most_common(1)[0][0]
    return name_to_cat


def build_item_loc_graph(records_slice):
    item_to_loc = defaultdict(Counter)
    loc_to_item = defaultdict(Counter)
    for r in records_slice:
        name = r.get("name", "")
        loc = r.get("location", "")
        if name and loc:
            item_to_loc[name][loc] += 1
            loc_to_item[loc][name] += 1
    return item_to_loc, loc_to_item


def build_loc_sim_graph(records_slice):
    loc_items = defaultdict(set)
    for r in records_slice:
        loc = r.get("location", "")
        name = r.get("name", "")
        if loc and name:
            loc_items[loc].add(name)
    locs = list(loc_items.keys())
    graph = defaultdict(dict)
    for i, l1 in enumerate(locs):
        for l2 in locs[i + 1 :]:
            inter = loc_items[l1] & loc_items[l2]
            union = loc_items[l1] | loc_items[l2]
            j = len(inter) / len(union) if union else 0
            if j >= LOC_SIM_THRESHOLD:
                graph[l1][l2] = j
                graph[l2][l1] = j
    return graph


def unified_predict(query_name, records, search_cat):
    if not query_name:
        return None, ""

    pool = records if not search_cat else [r for r in records if r.get("category", "") == search_cat]
    item_to_loc, loc_to_item = build_item_loc_graph(pool)
    loc_sim = build_loc_sim_graph(pool)

    if not item_to_loc:
        defaults = get_default_tendencies(query_name)
        if defaults:
            return defaults, "一般的な傾向から予測（まだ記録がありません）"
        return [], ""

    matched = [n for n in item_to_loc if fuzzy_match(query_name, n)]
    seeds = matched[:]
    if not seeds:
        ntc = build_name_to_category(pool)
        q_cat = None
        for n, c in ntc.items():
            if fuzzy_match(query_name, n):
                q_cat = c
                break
        if q_cat:
            seeds = [n for n in item_to_loc if ntc.get(n) == q_cat]
    has_direct = bool(matched)
    if not seeds:
        defaults = get_default_tendencies(query_name)
        if defaults:
            return defaults, "一般的な傾向から予測（まだ記録がありません）"
        return [], ""

    item_scores = defaultdict(float)
    for s in seeds:
        item_scores[s] = 1.0 / len(seeds)
    location_scores = defaultdict(float)

    for _ in range(RWR_ITERATIONS):
        nls = defaultdict(float)
        for item, sc in item_scores.items():
            if sc == 0:
                continue
            nbrs = item_to_loc.get(item, {})
            total = sum(nbrs.values())
            if total > 0:
                for loc, w in nbrs.items():
                    nls[loc] += sc * w / total
        for loc, sc in list(nls.items()):
            for sl, sj in loc_sim.get(loc, {}).items():
                nls[sl] += sc * sj * LOC_SIM_DECAY
        nis = defaultdict(float)
        for loc, sc in nls.items():
            nbrs = loc_to_item.get(loc, {})
            total = sum(nbrs.values())
            if total > 0:
                for item, w in nbrs.items():
                    nis[item] += sc * w / total
        for item in list(item_scores.keys()) + list(nis.keys()):
            nis[item] = (1 - RWR_ALPHA) * nis.get(item, 0)
        for s in seeds:
            nis[s] += RWR_ALPHA / len(seeds)
        diff = sum(abs(nis.get(k, 0) - v) for k, v in item_scores.items())
        item_scores = nis
        location_scores = nls
        if diff < RWR_CONVERGENCE:
            break

    if not location_scores:
        defaults = get_default_tendencies(query_name)
        if defaults:
            return defaults, "一般的な傾向から予測（まだ記録がありません）"
        return [], ""

    now = datetime.now()
    cdow = now.weekday()
    chour = now.hour
    loc_temporal = Counter()
    for r in pool:
        loc = r.get("location", "")
        if loc not in location_scores:
            continue
        fd = r.get("found_date", "")
        dt = parse_dt(fd)
        if not dt:
            continue
        dw = DOW_WEIGHTS.get(abs(dt.weekday() - cdow), DOW_OTHER)
        hw = math.exp(-abs(dt.hour - chour) ** 2 / HOUR_SIGMA_SQ)
        rw = 0.5 ** ((now - dt).days / RECENCY_HALFLIFE_DAYS)
        loc_temporal[loc] += dw * hw * rw

    t_total = sum(loc_temporal.values()) or 1
    combined = {}
    for loc, gs in location_scores.items():
        tw = loc_temporal.get(loc, 0.5) / t_total * len(loc_temporal)
        combined[loc] = gs * (LOC_TEMPORAL_BASE + LOC_TEMPORAL_WEIGHT * min(tw, 3) / 3)

    total = sum(combined.values())
    if total == 0:
        defaults = get_default_tendencies(query_name)
        if defaults:
            return defaults, "一般的な傾向から予測（まだ記録がありません）"
        return [], ""

    results_list = []
    for loc, sc in sorted(combined.items(), key=lambda x: -x[1]):
        pct = sc / total * 100
        results_list.append((loc, round(sc, 1), pct, False))
    if results_list:
        mp = max(r[2] for r in results_list)
        results_list = [(l, w, p, p == mp) for l, w, p, _ in results_list]

    n_related = len(
        [n for n, sc in item_scores.items() if n not in seeds and sc > RELATED_SCORE_THRESHOLD]
    )
    kind = "同カテゴリ" if not has_direct else "直接一致"
    ctx = f"グラフ伝搬（{kind}）: 起点{len(seeds)} + 関連{n_related}"
    return results_list, ctx
