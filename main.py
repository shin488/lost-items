from datetime import datetime
from collections import Counter, defaultdict
import json
import unicodedata
import calendar
import math
import uuid
import random

import flet as ft

STORAGE_KEY = "lost_items_v4"
CATEGORIES_KEY = "lost_items_categories_v1"
FLOORPLAN_KEY = "lost_items_floorplan_v1"
MAX_GRID = 30
DEFAULT_CATEGORIES = ["財布", "鍵", "スマホ", "イヤホン", "傘", "本", "文房具", "衣類", "カバン", "その他"]
WEEKDAYS_JP = ["月曜", "火曜", "水曜", "木曜", "金曜", "土曜", "日曜"]

DEFAULT_TENDENCIES = {
    "財布": ["ズボンのポケット", "カバンの中", "机の上", "ベッドの上"],
    "鍵": ["玄関の鍵穴", "カバンの中", "机の上", "ポケット"],
    "スマホ": ["布団の隙間", "ソファの隙間", "机の上", "ベッドの上"],
    "イヤホン": ["ポケット", "カバンの中", "机の上", "ベッドの上"],
    "傘": ["玄関", "会社/学校", "電車の中", "駐輪場"],
    "本": ["机の上", "カバンの中", "ベッドの上", "リビング"],
    "文房具": ["机の上", "カバンの中", "引き出しの中"],
    "衣類": ["洗濯機", "クローゼット", "ハンガー"],
    "カバン": ["玄関", "机の上", "車の中", "会社/学校"],
    "その他": ["ポケット", "カバンの中", "机の上", "ソファの隙間"],
}

# グラフ伝搬定数
RWR_ALPHA = 0.3
RWR_ITERATIONS = 20
RWR_CONVERGENCE = 1e-8
LOC_SIM_THRESHOLD = 0.15
LOC_SIM_DECAY = 0.3
LOC_TEMPORAL_WEIGHT = 0.4
LOC_TEMPORAL_BASE = 0.6
RECENCY_HALFLIFE_DAYS = 30
DOW_WEIGHTS = {0: 1.0, 1: 0.5, 6: 0.5}
DOW_OTHER = 0.2
HOUR_SIGMA_SQ = 18
RELATED_SCORE_THRESHOLD = 0.01

_js_window = None
try:
    from js import window as _js_window
except Exception:
    pass


def fuzzy_match(query: str, text: str) -> bool:
    q = unicodedata.normalize("NFKC", query.strip().lower())
    t = unicodedata.normalize("NFKC", text.strip().lower())
    return bool(q) and (q in t)


def parse_weekday(d: str):
    for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d", "%Y/%m/%d", "%m-%d", "%m/%d"):
        try:
            return datetime.strptime(d, fmt).weekday()
        except ValueError:
            pass
    return None


def parse_dt(s):
    for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            pass
    return None


def _ls_get(key):
    if _js_window is not None:
        try:
            return _js_window.localStorage.getItem(key)
        except Exception:
            pass
    return None


def _ls_set(key, val):
    if _js_window is not None:
        try:
            _js_window.localStorage.setItem(key, val)
            return True
        except Exception:
            pass
    return False


def load_categories():
    raw = _ls_get(CATEGORIES_KEY)
    if raw:
        try:
            cats = json.loads(raw)
            if isinstance(cats, list) and len(cats) > 0:
                return cats
        except Exception:
            pass
    return DEFAULT_CATEGORIES[:]


def save_categories(cats):
    _ls_set(CATEGORIES_KEY, json.dumps(cats, ensure_ascii=False))


def load_floorplan():
    raw = _ls_get(FLOORPLAN_KEY)
    if raw:
        try:
            fp = json.loads(raw)
            if isinstance(fp, dict) and "rows" in fp and "cols" in fp:
                return fp
        except Exception:
            pass
    return {"name": "マイ間取り", "rows": 3, "cols": 3, "cell_size": 80, "cells": []}


def save_floorplan(fp):
    _ls_set(FLOORPLAN_KEY, json.dumps(fp, ensure_ascii=False))


def migrate_floorplan_cells(cells):
    changed = False
    for cell in cells:
        if "spots" in cell and "furniture" not in cell:
            old = cell.pop("spots", "")
            cell["furniture"] = [{"name": "その他", "spots": [s.strip() for s in old.split(",") if s.strip()]}] if old.strip() else []
            changed = True
        cell.setdefault("furniture", [])
    return changed


def main(page: ft.Page):
    page.title = "なくしもの探知機"

    page.theme = ft.Theme(
        color_scheme=ft.ColorScheme(
            primary=ft.Colors.TEAL_800,
            primary_container=ft.Colors.TEAL_100,
            secondary=ft.Colors.BROWN_700,
            secondary_container=ft.Colors.AMBER_50,
            surface=ft.Colors.WHITE,
            surface_container=ft.Colors.AMBER_50,
        ),
        use_material3=True,
    )

    records = []
    categories = load_categories()
    floorplan = load_floorplan()
    floorplan.setdefault("cell_size", 80)
    if migrate_floorplan_cells(floorplan.get("cells", [])):
        save_floorplan(floorplan)
    search_val = ""
    search_cat = ""
    results = None
    search_context_info = ""
    search_loading = False

    cal_year = datetime.now().year
    cal_month = datetime.now().month

    search_ref = ft.Ref[ft.TextField]()
    name_ref = ft.Ref[ft.TextField]()
    date_ref = ft.Ref[ft.TextField]()
    location_ref = ft.Ref[ft.TextField]()
    category_ref = ft.Ref[ft.Dropdown]()
    search_dropdown_ref = ft.Ref[ft.Dropdown]()

    chips_container = ft.Column(spacing=4)
    location_chips_container = ft.Column(spacing=4)
    results_container = ft.Column(spacing=6)
    simulation_container = ft.Column(spacing=4)
    history_container = ft.Column(spacing=4)
    ranking_container = ft.Column(spacing=8)
    analysis_container = ft.Column(spacing=8)
    analysis_progress = ft.ProgressBar(visible=False, color=ft.Colors.TEAL_600)
    floorplan_grid_container = ft.Column(spacing=2, horizontal_alignment=ft.CrossAxisAlignment.CENTER)

    def load_from_storage():
        nonlocal records
        raw = _ls_get(STORAGE_KEY)
        if raw is not None:
            try:
                data = json.loads(raw)
                if isinstance(data, list):
                    records = data
                    return
            except Exception:
                pass
        try:
            raw = page.client_storage.get(STORAGE_KEY)
            if raw and isinstance(raw, list):
                records = raw
        except Exception:
            pass

    def ensure_record_ids():
        nonlocal records
        changed = False
        for r in records:
            if "id" not in r:
                r["id"] = str(uuid.uuid4())
                changed = True
        if changed:
            save()

    def save():
        raw = json.dumps(records, ensure_ascii=False)
        if _ls_set(STORAGE_KEY, raw):
            return True
        try:
            page.client_storage.set(STORAGE_KEY, records)
            return True
        except Exception:
            return False

    def get_filtered():
        nonlocal search_cat
        if not search_cat:
            return records
        return [r for r in records if r.get("category", "") == search_cat]

    def get_default_tendencies(query):
        for name, places in DEFAULT_TENDENCIES.items():
            if fuzzy_match(query, name):
                total = len(places)
                return [(p, 1, 100 / total, i == 0) for i, p in enumerate(places)]
        return None

    def build_name_to_category():
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
            for l2 in locs[i+1:]:
                inter = loc_items[l1] & loc_items[l2]
                union = loc_items[l1] | loc_items[l2]
                j = len(inter) / len(union) if union else 0
                if j >= LOC_SIM_THRESHOLD:
                    graph[l1][l2] = j
                    graph[l2][l1] = j
        return graph

    def unified_predict(query_name):
        if not query_name:
            return None, ""
        pool = get_filtered()
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
            ntc = build_name_to_category()
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

        n_related = len([n for n, sc in item_scores.items() if n not in seeds and sc > RELATED_SCORE_THRESHOLD])
        kind = "同カテゴリ" if not has_direct else "直接一致"
        ctx = f"グラフ伝搬（{kind}）: 起点{len(seeds)} + 関連{n_related}"
        return results_list, ctx

    def search_from_history(name):
        nonlocal search_val, results, search_context_info, search_loading
        search_val = name
        search_ref.current.value = name
        search_ref.current.update()
        search_loading = True
        refresh()
        results, search_context_info = unified_predict(name)
        search_loading = False
        tabs.selected_index = 0
        tabs.update()
        refresh()

    def on_search_click(e):
        nonlocal search_val, results, search_context_info, search_loading
        q = search_ref.current.value.strip()
        if not q:
            e.page.show_snack_bar(ft.SnackBar(content=ft.Text("なくした物を入力してください")))
            results = []
            refresh()
            return
        search_val = q
        search_loading = True
        refresh()
        results, search_context_info = unified_predict(q)
        search_loading = False
        refresh()

    def on_search_cat_change(e):
        nonlocal search_cat, results
        search_cat = e.control.value
        results = None
        refresh()

    def on_add_record(e):
        nonlocal records
        name = name_ref.current.value.strip()
        location = location_ref.current.value.strip()
        if not name:
            e.page.show_snack_bar(ft.SnackBar(
                content=ft.Text("「なくした物」を入力してください"), bgcolor=ft.Colors.RED_400))
            return
        if not location:
            e.page.show_snack_bar(ft.SnackBar(
                content=ft.Text("「見つかった場所」を入力してください"), bgcolor=ft.Colors.RED_400))
            return
        parts = location.split(" > ")
        location_parts = {}
        if len(parts) >= 1:
            location_parts["room"] = parts[0]
        if len(parts) >= 2:
            location_parts["furniture"] = parts[1]
        if len(parts) >= 3:
            location_parts["spot"] = parts[2]
        rec = {
            "id": str(uuid.uuid4()),
            "name": name,
            "category": category_ref.current.value or "その他",
            "location": location,
            "location_parts": location_parts,
            "lost_date": (date_ref.current.value or "").strip() or datetime.now().strftime("%Y-%m-%d"),
            "found_date": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "resolved": False,
            "resolution_date": None,
        }
        records = records + [rec]
        if not save():
            e.page.show_snack_bar(ft.SnackBar(
                content=ft.Text("保存に失敗しました"), bgcolor=ft.Colors.RED_400))
            return
        e.page.show_snack_bar(ft.SnackBar(content=ft.Text("記録しました"), bgcolor=ft.Colors.TEAL_400))
        name_ref.current.value = ""
        category_ref.current.value = ""
        date_ref.current.value = datetime.now().strftime("%Y-%m-%d")
        location_ref.current.value = ""
        name_ref.current.update()
        category_ref.current.update()
        date_ref.current.update()
        location_ref.current.update()
        refresh()

    def find_record_idx(rid):
        for i, r in enumerate(records):
            if r.get("id") == rid:
                return i
        return None

    def delete_record(rid):
        nonlocal records
        idx = find_record_idx(rid)
        if idx is not None:
            records.pop(idx)
            save()
            refresh()

    def confirm_delete(rid, name):
        def do_delete(e):
            dlg.open = False
            dlg.update()
            delete_record(rid)
        dlg = ft.AlertDialog(
            modal=True,
            title=ft.Text(f"「{name}」を削除しますか？"),
            content=ft.Text("この操作は元に戻せません", size=13, color=ft.Colors.GREY_600),
            actions=[
                ft.TextButton("キャンセル", on_click=lambda e: setattr(dlg, 'open', False) or dlg.update()),
                ft.FilledButton("削除", on_click=do_delete, style=ft.ButtonStyle(bgcolor=ft.Colors.RED_400, color=ft.Colors.WHITE)),
            ],
        )
        page.show_dialog(dlg)

    def show_edit_dialog(rid):
        idx = find_record_idx(rid)
        if idx is None:
            return
        r = records[idx]
        edit_name = ft.TextField(label="なくした物", value=r.get("name", ""), width=300)
        edit_location = ft.TextField(label="見つかった場所", value=r.get("location", ""), width=300)
        edit_lost_date = ft.TextField(
            label="なくした日", value=r.get("lost_date", ""), width=300,
            read_only=True,
            on_focus=lambda _: open_edit_date_picker(edit_lost_date),
            suffix=ft.TextButton("日付選択", on_click=lambda _: open_edit_date_picker(edit_lost_date)),
        )
        edit_cat_opts = [ft.dropdown.Option(c) for c in categories]
        edit_category = ft.Dropdown(
            label="カテゴリ", value=r.get("category", "その他"),
            options=edit_cat_opts, width=300,
        )

        def open_edit_date_picker(field):
            def on_pick(e):
                val = e.control.value
                if val:
                    if hasattr(val, "strftime"):
                        field.value = val.strftime("%Y-%m-%d")
                    else:
                        field.value = str(val)[:10]
                    field.update()
            dp = ft.DatePicker(on_change=on_pick, first_date=datetime(2000, 1, 1), last_date=datetime.now())
            page.overlay.append(dp)
            dp.open = True
            dp.update()

        def save_edit(e):
            nonlocal records
            idx2 = find_record_idx(rid)
            if idx2 is None:
                return
            new_name = edit_name.value.strip()
            if not new_name:
                e.page.show_snack_bar(ft.SnackBar(content=ft.Text("名前を入力してください")))
                return
            records[idx2]["name"] = new_name
            records[idx2]["category"] = edit_category.value
            records[idx2]["location"] = edit_location.value.strip()
            new_parts = edit_location.value.strip().split(" > ")
            records[idx2]["location_parts"] = {}
            if len(new_parts) >= 1:
                records[idx2]["location_parts"]["room"] = new_parts[0]
            if len(new_parts) >= 2:
                records[idx2]["location_parts"]["furniture"] = new_parts[1]
            if len(new_parts) >= 3:
                records[idx2]["location_parts"]["spot"] = new_parts[2]
            records[idx2]["lost_date"] = edit_lost_date.value.strip() or records[idx2].get("lost_date", "")
            save()
            dlg.open = False
            dlg.update()
            refresh()
            e.page.show_snack_bar(ft.SnackBar(content=ft.Text("更新しました"), bgcolor=ft.Colors.TEAL_400))

        dlg = ft.AlertDialog(
            modal=True,
            title=ft.Text("記録を編集"),
            content=ft.Column([
                edit_name, edit_category, edit_lost_date, edit_location,
            ], tight=True, spacing=8, scroll=ft.ScrollMode.AUTO),
            actions=[
                ft.TextButton("キャンセル", on_click=lambda e: setattr(dlg, 'open', False) or dlg.update()),
                ft.FilledButton("保存", on_click=save_edit),
            ],
        )
        page.show_dialog(dlg)

    def mark_resolved(rid):
        nonlocal records
        idx = find_record_idx(rid)
        if idx is None:
            return
        records[idx]["resolved"] = True
        records[idx]["resolution_date"] = datetime.now().strftime("%Y-%m-%d %H:%M")
        save()
        page.show_snack_bar(ft.SnackBar(
            content=ft.Text(f"「{records[idx].get('name', '')}」を見つかりました！"), bgcolor=ft.Colors.TEAL_400))
        refresh()

    def show_export_dialog(e):
        data = json.dumps(records, ensure_ascii=False, indent=2)
        text_field = ft.TextField(
            value=data, multiline=True, min_lines=10, max_lines=20,
            width=500, read_only=True,
        )
        dlg = ft.AlertDialog(
            modal=True,
            title=ft.Text("データをエクスポート"),
            content=ft.Column([
                ft.Text("以下のJSONをコピーして保存してください:", size=13),
                text_field,
            ], tight=True, spacing=8),
            actions=[ft.TextButton("閉じる", on_click=lambda _: setattr(dlg, 'open', False) or dlg.update())],
        )
        e.page.show_dialog(dlg)

    def show_import_dialog(e):
        text_field = ft.TextField(
            multiline=True, min_lines=5, max_lines=15, width=500,
            hint_text="ここにJSONを貼り付け",
        )

        def do_import(ev):
            nonlocal records
            try:
                data = json.loads(text_field.value)
                if not isinstance(data, list):
                    raise ValueError("リスト形式のJSONが必要です")
                for item in data:
                    if not isinstance(item, dict) or "name" not in item:
                        raise ValueError("各アイテムに name フィールドが必要です")
                    item.setdefault("id", str(uuid.uuid4()))
                    item.setdefault("category", "その他")
                    item.setdefault("location", "")
                    item.setdefault("location_parts", {})
                    item.setdefault("lost_date", "")
                    item.setdefault("found_date", "")
                    item.setdefault("resolved", False)
                    item.setdefault("resolution_date", None)
                records = data
                save()
                dlg.open = False
                dlg.update()
                ev.page.show_snack_bar(ft.SnackBar(
                    content=ft.Text(f"{len(data)}件のデータをインポートしました"),
                    bgcolor=ft.Colors.TEAL_400))
                refresh()
            except Exception as ex:
                ev.page.show_snack_bar(ft.SnackBar(
                    content=ft.Text(f"インポートエラー: {ex}"),
                    bgcolor=ft.Colors.RED_400))

        def close(ev):
            dlg.open = False
            dlg.update()

        dlg = ft.AlertDialog(
            modal=True,
            title=ft.Text("データをインポート"),
            content=ft.Column([
                ft.Text("JSONデータを貼り付けてください:", size=13),
                text_field,
            ], tight=True, spacing=8),
            actions=[
                ft.TextButton("キャンセル", on_click=close),
                ft.FilledButton("インポート", on_click=do_import),
            ],
        )
        e.page.show_dialog(dlg)

    def rebuild_category_dropdowns():
        nonlocal categories
        opts = [ft.dropdown.Option("", "すべて")] + [ft.dropdown.Option(c) for c in categories]
        if search_dropdown_ref.current:
            search_dropdown_ref.current.options = opts
            search_dropdown_ref.current.update()
        cat_opts = [ft.dropdown.Option("", "選択してください")] + [ft.dropdown.Option(c) for c in categories]
        if category_ref.current:
            category_ref.current.options = cat_opts
            category_ref.current.update()

    def show_category_dialog(e):
        nonlocal categories
        cats = categories[:]
        cat_input = ft.TextField(label="新しいカテゴリ名", hint_text="例: 充電器", width=300)
        cat_list = ft.Column(spacing=4)

        def refresh_cat_ui():
            used = set(r.get("category", "") for r in records)
            rows = []
            for i, c in enumerate(cats):
                in_use = c in used
                btn = ft.TextButton("削除",
                    on_click=(lambda ev, idx=i: delete_category(idx)) if not in_use else None,
                )
                rows.append(ft.Row([
                    ft.Text(c, expand=True, size=14),
                    ft.Text("使用中" if in_use else "", size=11, color=ft.Colors.GREY_500, italic=True),
                    btn,
                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN))
            cat_list.controls = rows
            cat_list.update()

        def delete_category(idx):
            nonlocal categories
            cats.pop(idx)
            categories = cats[:]
            save_categories(categories)
            refresh_cat_ui()
            rebuild_category_dropdowns()

        def add_category(ev):
            nonlocal categories
            name = cat_input.value.strip()
            if not name:
                ev.page.show_snack_bar(ft.SnackBar(content=ft.Text("カテゴリ名を入力してください")))
                return
            if name in cats:
                ev.page.show_snack_bar(ft.SnackBar(content=ft.Text("既に存在するカテゴリです")))
                return
            cats.append(name)
            categories = cats[:]
            save_categories(categories)
            cat_input.value = ""
            cat_input.update()
            refresh_cat_ui()
            rebuild_category_dropdowns()

        def close_dlg(ev):
            dlg.open = False
            dlg.update()

        refresh_cat_ui()
        dlg = ft.AlertDialog(
            modal=True,
            title=ft.Text("カテゴリ管理"),
            content=ft.Column([
                ft.Row([
                    cat_input,
                    ft.FilledButton("追加", on_click=add_category),
                ], tight=True),
                ft.Divider(height=4),
                cat_list,
            ], tight=True, spacing=8, width=350),
            actions=[ft.TextButton("閉じる", on_click=close_dlg)],
        )
        e.page.show_dialog(dlg)

    def make_bar(pct, color):
        inner = ft.Container(height=8, width=f"{pct}%", bgcolor=color, border_radius=4)
        outer = ft.Container(height=8, bgcolor=ft.Colors.AMBER_100, border_radius=4)
        return ft.Stack([outer, inner])

    def make_tappable_btn(label, on_click, color=None):
        return ft.Container(
            content=ft.Text(label, size=13, color=color or ft.Colors.TEAL_700, weight=ft.FontWeight.W_500),
            padding=ft.padding.only(left=8, right=8, top=8, bottom=8),
            border_radius=6,
            ink=True,
            on_click=on_click,
        )

    def refresh():
        nonlocal chips_container, location_chips_container, results_container, simulation_container, history_container, ranking_container

        chips = []

        locs = list(dict.fromkeys(r.get("location", "").strip() for r in records if r.get("location", "").strip()))
        loc_chips = []
        for loc in locs[:10]:
            chip = ft.Container(
                content=ft.Text(loc, size=12),
                padding=8,
                bgcolor=ft.Colors.AMBER_100,
                border_radius=10,
                on_click=lambda e, l=loc: (setattr(location_ref.current, 'value', l), location_ref.current.update()),
                ink=True,
            )
            loc_chips.append(chip)
        if loc_chips:
            location_chips_container.controls = [
                ft.Text("よく使う場所 (タップで入力):", size=11, color=ft.Colors.GREY_600),
                ft.Row(loc_chips, wrap=True, spacing=4),
            ]
        else:
            location_chips_container.controls = []
        location_chips_container.update()
        unique = list(dict.fromkeys(r.get("name", "") for r in get_filtered() if r.get("name", "")))
        for name in unique:
            chip = ft.Container(
                content=ft.Text(name, size=13),
                padding=8,
                bgcolor=ft.Colors.AMBER_100,
                border_radius=12,
                on_click=lambda e, n=name: search_from_history(n),
                ink=True,
            )
            chips.append(ft.Row([chip], tight=True))
        chips_container.controls = chips

        if search_loading:
            results_container.controls = [ft.ProgressBar(color=ft.Colors.TEAL_600)]
            simulation_container.controls = []
        elif results is None:
            results_container.controls = [ft.Text("アイテムを入力して「探す」を押してください", color=ft.Colors.GREY_600)]
            simulation_container.controls = []
        elif not results:
            results_container.controls = [ft.Text("該当する記録がありません", color=ft.Colors.GREY_500)]
            simulation_container.controls = []
        else:
            name = search_val.strip()
            is_default = "一般的な傾向" in search_context_info
            rc = [
                ft.Text(f"「{name}」が見つかりそうな場所",
                        size=17, weight=ft.FontWeight.BOLD, color=ft.Colors.TEAL_800),
            ]
            if is_default:
                rc.append(ft.Text("まだ記録が少ないため、一般的な傾向を表示しています",
                                  size=11, color=ft.Colors.ORANGE_700, italic=True))
            rc.append(ft.Text(search_context_info, size=12, color=ft.Colors.GREY_600))
            if is_default:
                rc.append(ft.Text("このアイテムを実際に見つけたら記録しましょう！精度が上がります",
                                  size=11, color=ft.Colors.GREY_500, italic=True))
            rc.append(ft.Divider(height=4))

            matched_records = [r for r in get_filtered() if fuzzy_match(name, r.get("name", ""))]
            for loc, w, pct, is_top in results:
                color = ft.Colors.TEAL_700 if is_top else ft.Colors.TEAL_600
                contributing = [r for r in matched_records if r.get("location", "") == loc]
                contrib_text = ""
                if contributing:
                    tops = contributing[:3]
                    names_list = list(dict.fromkeys(r["name"] for r in tops))
                    contrib_text = "根拠: " + ", ".join(names_list)
                card = ft.Container(
                    content=ft.Column([
                        ft.Row([
                            ft.Text(loc, size=13, weight=(
                                ft.FontWeight.BOLD if is_top else ft.FontWeight.W_500), expand=True),
                            ft.Text(f"{pct:.0f}%", size=12, weight=ft.FontWeight.BOLD, color=color),
                        ]),
                        make_bar(pct, ft.Colors.TEAL_400 if is_top else ft.Colors.ORANGE_100),
                        ft.Text(contrib_text, size=10, color=ft.Colors.GREY_500, italic=True) if contrib_text else ft.Container(),
                    ], spacing=2),
                    padding=6,
                    bgcolor=ft.Colors.with_opacity(0.8, ft.Colors.AMBER_50) if is_top else ft.Colors.with_opacity(0.8, ft.Colors.WHITE),
                    border=ft.Border.all(1, ft.Colors.TEAL_300 if is_top else ft.Colors.AMBER_100),
                    border_radius=6,
                )
                rc.append(card)
            results_container.controls = rc
            simulation_container.controls = []

        if not records:
            history_container.controls = [
                ft.Container(
                    ft.Column([
                        ft.Text("まだ記録がありません", color=ft.Colors.TEAL_700),
                        ft.Text("「記録」タブからなくし物を追加しましょう", size=12, color=ft.Colors.GREY_500, italic=True),
                    ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=4),
                    padding=20, alignment=ft.Alignment.CENTER,
                ),
            ]
        else:
            hc = []
            for i, r in enumerate(reversed(records)):
                idx = len(records) - 1 - i
                rid = r.get("id", str(idx))
                cat = r.get("category", "")
                loc = r.get("location", "場所不明")
                fd = r.get("found_date", "")
                resolved = r.get("resolved", False)
                subtitle = f"{loc}  ({fd})"
                if cat:
                    subtitle = f"[{cat}] {subtitle}"
                if resolved:
                    subtitle += " 解決済み"
                trailing_btns = [
                    make_tappable_btn("編集", lambda e, rid=rid: show_edit_dialog(rid)),
                    make_tappable_btn("探す",
                        lambda e, n=r.get("name", ""): search_from_history(n)),
                ]
                if not resolved:
                    trailing_btns.insert(1, make_tappable_btn("解決",
                        lambda e, rid=rid: mark_resolved(rid),
                        color=ft.Colors.TEAL_600))
                trailing_btns.append(make_tappable_btn("削除",
                    lambda e, rid=rid, n=r.get("name", ""): confirm_delete(rid, n),
                    color=ft.Colors.RED_400))
                hc.append(
                    ft.Card(
                        ft.ListTile(
                            title=ft.Text(r.get("name", ""), weight=ft.FontWeight.W_500),
                            subtitle=ft.Text(subtitle, size=13),
                            trailing=ft.Row(trailing_btns, spacing=2),
                        ),
                        margin=3,
                    )
                )
            history_container.controls = hc

        if not records:
            ranking_container.controls = [
                ft.Container(
                    ft.Column([
                        ft.Text("まだデータがありません", color=ft.Colors.TEAL_700),
                        ft.Text("記録が増えるとランキングが表示されます", size=12, color=ft.Colors.GREY_500, italic=True),
                    ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=4),
                    padding=20, alignment=ft.Alignment.CENTER,
                ),
            ]
        else:
            name_counts = Counter(r.get("name", "") for r in records if r.get("name", "")).most_common()
            total = len(records)
            rc = [
                ft.Text("よくなくした物ランキング", size=18, weight=ft.FontWeight.BOLD, color=ft.Colors.TEAL_800),
                ft.Text(f"全 {total} 件の記録", size=12, color=ft.Colors.GREY_600, italic=True),
                ft.Divider(height=8),
            ]
            for rank, (name, cnt) in enumerate(name_counts, 1):
                pct = cnt / total * 100
                rc.append(
                    ft.Card(
                        ft.ListTile(
                            title=ft.Row([
                                ft.Text(f"#{rank}", size=13, color=ft.Colors.GREY_500),
                                ft.Text(name, size=16, weight=ft.FontWeight.W_500),
                            ]),
                            subtitle=ft.Text(f"{cnt}回 ({pct:.1f}%)", size=13, color=ft.Colors.GREY_600),
                            trailing=ft.TextButton("探す",
                                on_click=lambda e, n=name: search_from_history(n),
                            ),
                        ),
                        margin=3,
                    )
                )
            ranking_container.controls = rc

        chips_container.update()
        results_container.update()
        simulation_container.update()
        history_container.update()
        ranking_container.update()

    def refresh_analysis():
        nonlocal cal_year, cal_month
        analysis_progress.visible = True
        page.update()

        if not records:
            analysis_container.controls = [
                ft.Container(
                    ft.Column([
                        ft.Text("まだデータがありません", color=ft.Colors.TEAL_700),
                        ft.Text("記録が増えると分析が表示されます", size=12, color=ft.Colors.GREY_500, italic=True),
                    ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=4),
                    padding=20, alignment=ft.Alignment.CENTER,
                ),
            ]
            analysis_progress.visible = False
            analysis_container.update()
            analysis_progress.update()
            return

        sections = []

        lost_by_date = {}
        for r in records:
            d = (r.get("lost_date", "") or r.get("found_date", "")[:10])
            if d:
                lost_by_date.setdefault(d, []).append(r)

        min_d = datetime.now()
        if lost_by_date:
            dates = [d for d in lost_by_date if d]
            valid_dates = []
            for d in dates:
                try:
                    valid_dates.append(datetime.strptime(d, "%Y-%m-%d"))
                except ValueError:
                    pass
            if valid_dates:
                min_d = min(valid_dates)

        cal_header = ft.Row([
            ft.TextButton("<", on_click=lambda e: _navigate_cal(-1)),
            ft.Text(f"{cal_year}年 {cal_month}月", size=16, weight=ft.FontWeight.BOLD, expand=True, text_align=ft.TextAlign.CENTER),
            ft.TextButton(">", on_click=lambda e: _navigate_cal(1)),
        ], alignment=ft.MainAxisAlignment.CENTER)
        sections.append(cal_header)

        cal_grid = ft.Column(spacing=2)
        month_cal = calendar.monthcalendar(cal_year, cal_month)
        day_names = [w.replace("曜日", "") for w in WEEKDAYS_JP]
        cal_grid.controls.append(
            ft.Row([ft.Container(ft.Text(d, size=11, color=ft.Colors.GREY_600, text_align=ft.TextAlign.CENTER),
                                 width=42, height=24) for d in day_names], spacing=2, alignment=ft.MainAxisAlignment.CENTER)
        )
        for week in month_cal:
            week_row = []
            for day in week:
                if day == 0:
                    week_row.append(ft.Container(width=42, height=42))
                else:
                    date_str = f"{cal_year}-{cal_month:02d}-{day:02d}"
                    day_records = lost_by_date.get(date_str, [])
                    cnt = len(day_records)
                    is_today = date_str == datetime.now().strftime("%Y-%m-%d")
                    bg = ft.Colors.AMBER_100 if is_today else (ft.Colors.AMBER_50 if cnt > 0 else ft.Colors.GREY_100)
                    border = ft.Border.all(2, ft.Colors.TEAL_600) if is_today else None
                    day_text = ft.Text(str(day), size=13, weight=ft.FontWeight.BOLD if cnt > 0 else ft.FontWeight.NORMAL)
                    badge = None
                    if cnt > 0:
                        badge = ft.Container(
                            content=ft.Text(str(cnt), size=9, color=ft.Colors.WHITE),
                            bgcolor=ft.Colors.RED_400, border_radius=8,
                            width=16, height=16,
                            alignment=ft.Alignment.CENTER,
                            right=-4, top=-4,
                        )
                    stack_items = [day_text]
                    if badge:
                        stack_items.append(badge)
                    stack = ft.Stack(stack_items)
                    container = ft.Container(
                        content=stack,
                        width=42, height=42, bgcolor=bg, border=border,
                        border_radius=6, alignment=ft.Alignment.CENTER,
                        ink=True,
                        on_click=lambda e, ds=date_str, recs=day_records: _show_day_detail(ds, recs),
                    )
                    week_row.append(container)
            cal_grid.controls.append(ft.Row(week_row, spacing=2, alignment=ft.MainAxisAlignment.CENTER))
        sections.append(cal_grid)

        sections.append(ft.Divider(height=16))
        sections.append(ft.Text("解決状況分析", size=18, weight=ft.FontWeight.BOLD, color=ft.Colors.TEAL_800))
        sections.append(ft.Divider(height=8))

        resolved_records = [r for r in records if r.get("resolved")]
        unresolved_records = [r for r in records if not r.get("resolved")]
        resolved_total = len(resolved_records)
        unresolved_total = len(unresolved_records)
        total_recs = len(records)
        resolved_pct = resolved_total / total_recs * 100 if total_recs > 0 else 0

        sections.append(ft.Row([
            ft.Container(
                ft.Column([
                    ft.Text("解決済み", size=11, color=ft.Colors.GREY_600),
                    ft.Text(str(resolved_total), size=22, weight=ft.FontWeight.BOLD, color=ft.Colors.TEAL_700),
                ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=1),
                padding=10, border_radius=8,
                bgcolor=ft.Colors.with_opacity(0.8, ft.Colors.AMBER_50), expand=True, border=ft.Border.all(1, ft.Colors.ORANGE_100),
            ),
            ft.Container(
                ft.Column([
                    ft.Text("未解決", size=11, color=ft.Colors.GREY_600),
                    ft.Text(str(unresolved_total), size=22, weight=ft.FontWeight.BOLD, color=ft.Colors.BROWN_700),
                ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=1),
                padding=10, border_radius=8,
                bgcolor=ft.Colors.with_opacity(0.8, ft.Colors.ORANGE_50), expand=True, border=ft.Border.all(1, ft.Colors.BROWN_200),
            ),
            ft.Container(
                ft.Column([
                    ft.Text("解決率", size=11, color=ft.Colors.GREY_600),
                    ft.Text(f"{resolved_pct:.0f}%", size=22, weight=ft.FontWeight.BOLD, color=ft.Colors.TEAL_800),
                ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=1),
                padding=10, border_radius=8,
                bgcolor=ft.Colors.with_opacity(0.8, ft.Colors.AMBER_50), expand=True, border=ft.Border.all(1, ft.Colors.ORANGE_100),
            ),
        ], spacing=6))
        sections.append(make_bar(resolved_pct, ft.Colors.TEAL_600))
        sections.append(ft.Text(f"解決率 {resolved_pct:.0f}%", size=12, color=ft.Colors.GREY_600, italic=True))

        time_diffs = []
        for r in resolved_records:
            ld = r.get("lost_date", "")
            rd = r.get("resolution_date", "")
            if ld and rd:
                try:
                    lost = datetime.strptime(ld, "%Y-%m-%d")
                    res = datetime.strptime(rd, "%Y-%m-%d %H:%M")
                    diff_hours = (res - lost).total_seconds() / 3600
                    if diff_hours >= 0:
                        time_diffs.append(diff_hours)
                except ValueError:
                    pass

        if time_diffs:
            sections.append(ft.Divider(height=8))
            avg_h = sum(time_diffs) / len(time_diffs)
            min_h = min(time_diffs)
            max_h = max(time_diffs)
            sections.append(ft.Text("発見までの時間", size=15, weight=ft.FontWeight.BOLD, color=ft.Colors.TEAL_800))
            time_row = ft.Row([
                ft.Container(
                    ft.Column([
                        ft.Text("最短", size=10, color=ft.Colors.GREY_600),
                        ft.Text(f"{min_h/24:.1f}日" if min_h >= 24 else f"{min_h:.0f}時間",
                                size=14, weight=ft.FontWeight.BOLD, color=ft.Colors.TEAL_700),
                    ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=0),
                    padding=8, border_radius=8, bgcolor=ft.Colors.with_opacity(0.8, ft.Colors.AMBER_50), expand=True,
                ),
                ft.Container(
                    ft.Column([
                        ft.Text("平均", size=10, color=ft.Colors.GREY_600),
                        ft.Text(f"{avg_h/24:.1f}日" if avg_h >= 24 else f"{avg_h:.0f}時間",
                                size=14, weight=ft.FontWeight.BOLD, color=ft.Colors.BLUE_700),
                    ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=0),
                    padding=8, border_radius=8, bgcolor=ft.Colors.BLUE_50, expand=True,
                ),
                ft.Container(
                    ft.Column([
                        ft.Text("最長", size=10, color=ft.Colors.GREY_600),
                        ft.Text(f"{max_h/24:.1f}日" if max_h >= 24 else f"{max_h:.0f}時間",
                                size=14, weight=ft.FontWeight.BOLD, color=ft.Colors.RED_700),
                    ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=0),
                    padding=8, border_radius=8, bgcolor=ft.Colors.RED_50, expand=True,
                ),
            ], spacing=6)
            sections.append(time_row)

            bucket = Counter()
            for h in time_diffs:
                if h < 1:
                    bucket["1時間未満"] += 1
                elif h < 6:
                    bucket["1〜6時間"] += 1
                elif h < 24:
                    bucket["6〜24時間"] += 1
                elif h < 72:
                    bucket["1〜3日"] += 1
                else:
                    bucket["3日以上"] += 1
            sections.append(ft.Divider(height=8))
            sections.append(ft.Text("発見時間の分布", size=14, weight=ft.FontWeight.BOLD, color=ft.Colors.TEAL_800))
            for label, cnt in bucket.most_common():
                pct = cnt / len(time_diffs) * 100
                sections.append(ft.Column([
                    ft.Row([
                        ft.Text(label, size=12, expand=True),
                        ft.Text(f"{cnt}件", size=11, color=ft.Colors.GREY_600),
                    ]),
                    make_bar(pct, ft.Colors.TEAL_300),
                ], spacing=1))

        loc_rooms = Counter()
        loc_furniture = Counter()
        loc_combos = Counter()
        loc_len = 0
        for r in records:
            lp = r.get("location_parts", {}) or {}
            if lp.get("room"):
                loc_rooms[lp["room"]] += 1
                loc_len += 1
                if lp.get("furniture"):
                    key = f"{lp['room']} > {lp['furniture']}"
                    loc_furniture[key] += 1
                    if lp.get("spot"):
                        loc_combos[f"{key} > {lp['spot']}"] += 1

        if loc_rooms:
            sections.append(ft.Divider(height=16))
            sections.append(ft.Text("スポット分析", size=18, weight=ft.FontWeight.BOLD, color=ft.Colors.TEAL_800))
            sections.append(ft.Divider(height=8))
            sections.append(ft.Text("部屋別", size=14, weight=ft.FontWeight.BOLD, color=ft.Colors.TEAL_700))
            for room, cnt in loc_rooms.most_common(5):
                pct = cnt / loc_len * 100
                sections.append(ft.Row([
                    ft.Container(ft.Text(room, size=12, expand=True), expand=True),
                    ft.Container(ft.Text(f"{cnt}件 {pct:.0f}%", size=11, color=ft.Colors.GREY_600)),
                ]))
            if loc_furniture:
                sections.append(ft.Divider(height=4))
                sections.append(ft.Text("家具別（部屋 > 家具）", size=14, weight=ft.FontWeight.BOLD, color=ft.Colors.TEAL_700))
                for loc, cnt in loc_furniture.most_common(5):
                    pct = cnt / loc_len * 100
                    sections.append(ft.Row([
                        ft.Container(ft.Text(loc, size=12, expand=True, no_wrap=False), expand=True),
                        ft.Container(ft.Text(f"{cnt}件 {pct:.0f}%", size=11, color=ft.Colors.GREY_600)),
                    ]))
            if loc_combos:
                sections.append(ft.Divider(height=4))
                sections.append(ft.Text("ピンポイント（部屋 > 家具 > スポット）", size=14, weight=ft.FontWeight.BOLD, color=ft.Colors.TEAL_700))
                for loc, cnt in loc_combos.most_common(5):
                    pct = cnt / loc_len * 100
                    sections.append(ft.Row([
                        ft.Container(ft.Text(loc, size=11, expand=True, no_wrap=False), expand=True),
                        ft.Container(ft.Text(f"{cnt}件 {pct:.0f}%", size=10, color=ft.Colors.GREY_600)),
                    ]))

        analysis_container.controls = sections
        analysis_progress.visible = False
        page.update()

    def _navigate_cal(delta):
        nonlocal cal_year, cal_month
        cal_month += delta
        if cal_month > 12:
            cal_month = 1
            cal_year += 1
        elif cal_month < 1:
            cal_month = 12
            cal_year -= 1
        refresh_analysis()

    def _show_day_detail(date_str, day_records):
        if not day_records:
            page.show_snack_bar(ft.SnackBar(content=ft.Text(f"{date_str} の記録はありません")))
            return
        items_text = "\n".join(
            f"• {r['name']} ({r.get('location', '場所不明')})"
            for r in day_records
        )
        dlg = ft.AlertDialog(
            modal=True,
            title=ft.Text(f"{date_str} になくした物"),
            content=ft.Column([
                ft.Text(f"{len(day_records)}件の記録", size=13, color=ft.Colors.GREY_600),
                ft.Text(items_text, size=13),
            ], tight=True, spacing=8),
            actions=[ft.TextButton("閉じる", on_click=lambda e: setattr(dlg, 'open', False) or dlg.update())],
        )
        page.show_dialog(dlg)

    # --- Floorplan ---
    def build_floorplan_grid():
        nonlocal floorplan, floorplan_grid_container
        rows = floorplan["rows"]
        cols = floorplan["cols"]
        grid_rows = []
        for r in range(rows):
            row_cells = []
            for c in range(cols):
                cell = next((x for x in floorplan.get("cells", []) if x.get("r") == r and x.get("c") == c), None)
                label = cell.get("room", "") if cell else ""
                inner = [ft.Text(label, size=12, weight=ft.FontWeight.BOLD, text_align=ft.TextAlign.CENTER)]
                if cell:
                    furn_names = [f.get("name", "") for f in cell.get("furniture", [])]
                    if furn_names:
                        display = ", ".join(furn_names[:3])
                        if len(furn_names) > 3:
                            display += "…"
                        inner.append(ft.Text(display, size=8, color=ft.Colors.GREY_600, text_align=ft.TextAlign.CENTER, no_wrap=True, overflow=ft.TextOverflow.ELLIPSIS))
                cs = floorplan.get("cell_size", 80)
                cont = ft.Container(
                    content=ft.Column(inner, horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=1, tight=True),
                    width=cs, height=int(cs * 0.75),
                    bgcolor=ft.Colors.AMBER_50 if cell else ft.Colors.GREY_200,
                    border=ft.Border.all(1, ft.Colors.TEAL_300 if cell else ft.Colors.GREY_400),
                    border_radius=6, alignment=ft.Alignment.CENTER, ink=True,
                    on_click=lambda e, rr=r, cc=c: edit_cell_dialog(rr, cc),
                )
                row_cells.append(cont)
            grid_rows.append(ft.Row(row_cells, spacing=3, alignment=ft.MainAxisAlignment.CENTER))
        floorplan_grid_container.controls = grid_rows
        floorplan_grid_container.update()

    def edit_cell_dialog(r, c):
        nonlocal floorplan
        def find_cell():
            return next((x for x in floorplan.get("cells", []) if x.get("r") == r and x.get("c") == c), None)
        existing = find_cell()
        room_input = ft.TextField(label="部屋名", hint_text="例: リビング", value=existing.get("room", "") if existing else "", width=250)
        furniture_list = ft.Column(spacing=4)

        def rebuild_furniture_ui():
            cell = find_cell()
            if not cell:
                furniture_list.controls = [ft.Text("先に部屋名を入力して保存してください", size=12, color=ft.Colors.GREY_500, italic=True)]
            else:
                items = []
                for fi, furn in enumerate(cell.get("furniture", [])):
                    spot_chips = []
                    for si, spot in enumerate(furn.get("spots", [])):
                        chip = ft.Container(
                            content=ft.Row([
                                ft.Text(spot, size=11),
                                ft.Text("✕", size=10, color=ft.Colors.RED_400),
                            ], spacing=2),
                            padding=ft.padding.only(left=8, right=6, top=4, bottom=4),
                            bgcolor=ft.Colors.AMBER_100,
                            border_radius=8,
                            on_click=lambda e, f=fi, s=si: delete_spot(f, s),
                            ink=True,
                        )
                        spot_chips.append(chip)
                    items.append(ft.Container(
                        content=ft.Column([
                            ft.Row([
                                ft.Text(furn.get("name", ""), size=14, weight=ft.FontWeight.BOLD, expand=True),
                                ft.TextButton("＋スポット",
                                    on_click=lambda e, fn=furn.get("name", ""): add_spot_dialog(fn)),
                                ft.TextButton("削除",
                                    on_click=lambda e, f=fi: delete_furniture(f),
                                    style=ft.ButtonStyle(color=ft.Colors.RED_400)),
                            ]),
                            ft.Row(spot_chips, wrap=True, spacing=4) if spot_chips
                            else ft.Text("スポット未設定", size=11, color=ft.Colors.GREY_500, italic=True),
                        ], spacing=2),
                        padding=8,
                        bgcolor=ft.Colors.with_opacity(0.8, ft.Colors.AMBER_50),
                        border=ft.Border.all(1, ft.Colors.AMBER_200),
                        border_radius=6,
                    ))
                if not items:
                    items.append(ft.Text("家具がありません。「＋家具を追加」してください", size=12, color=ft.Colors.GREY_500, italic=True))
                furniture_list.controls = items
            furniture_list.update()

        def delete_furniture(fi):
            cell = find_cell()
            if cell and fi < len(cell.get("furniture", [])):
                cell["furniture"].pop(fi)
                save_floorplan(floorplan)
                rebuild_furniture_ui()

        def delete_spot(fi, si):
            cell = find_cell()
            if cell and fi < len(cell.get("furniture", [])):
                spots = cell["furniture"][fi].get("spots", [])
                if si < len(spots):
                    spots.pop(si)
                    save_floorplan(floorplan)
                    rebuild_furniture_ui()

        def add_furniture_dialog(ev):
            furn_input = ft.TextField(label="家具名", hint_text="例: ソファ, 机, 本棚", width=250)
            def confirm(ev2):
                name = furn_input.value.strip()
                if not name:
                    ev2.page.show_snack_bar(ft.SnackBar(content=ft.Text("家具名を入力してください")))
                    return
                cell = find_cell()
                if not cell:
                    floorplan["cells"].append({"r": r, "c": c, "room": room_input.value.strip() or "部屋", "furniture": []})
                    cell = floorplan["cells"][-1]
                cell.setdefault("furniture", []).append({"name": name, "spots": []})
                save_floorplan(floorplan)
                sub_dlg.open = False
                sub_dlg.update()
                rebuild_furniture_ui()
            sub_dlg = ft.AlertDialog(
                modal=True, title=ft.Text("家具を追加"),
                content=furn_input,
                actions=[
                    ft.TextButton("キャンセル", on_click=lambda e: setattr(sub_dlg, 'open', False) or sub_dlg.update()),
                    ft.FilledButton("追加", on_click=confirm),
                ],
            )
            page.show_dialog(sub_dlg)

        def add_spot_dialog(furn_name):
            spot_input = ft.TextField(label="スポット名", hint_text="例: 隙間, 天板, 引き出し", width=250)
            def confirm(ev2):
                name = spot_input.value.strip()
                if not name:
                    ev2.page.show_snack_bar(ft.SnackBar(content=ft.Text("スポット名を入力してください")))
                    return
                cell = find_cell()
                if cell:
                    for f in cell.setdefault("furniture", []):
                        if f.get("name") == furn_name:
                            f.setdefault("spots", []).append(name)
                            break
                    save_floorplan(floorplan)
                    sub_dlg.open = False
                    sub_dlg.update()
                    rebuild_furniture_ui()
            sub_dlg = ft.AlertDialog(
                modal=True, title=ft.Text(f"「{furn_name}」にスポットを追加"),
                content=spot_input,
                actions=[
                    ft.TextButton("キャンセル", on_click=lambda e: setattr(sub_dlg, 'open', False) or sub_dlg.update()),
                    ft.FilledButton("追加", on_click=confirm),
                ],
            )
            page.show_dialog(sub_dlg)

        def save_cell(ev):
            nonlocal floorplan
            room = room_input.value.strip()
            if not room:
                ev.page.show_snack_bar(ft.SnackBar(content=ft.Text("部屋名を入力してください")))
                return
            cell = find_cell()
            if cell:
                cell["room"] = room
            else:
                floorplan["cells"].append({"r": r, "c": c, "room": room, "furniture": []})
            save_floorplan(floorplan)
            dlg.open = False
            dlg.update()
            build_floorplan_grid()

        def delete_cell(ev):
            nonlocal floorplan
            floorplan["cells"] = [x for x in floorplan.get("cells", []) if not (x.get("r") == r and x.get("c") == c)]
            save_floorplan(floorplan)
            dlg.open = False
            dlg.update()
            build_floorplan_grid()

        rebuild_furniture_ui()
        dlg = ft.AlertDialog(
            modal=True,
            title=ft.Text(f"「{existing.get('room', '') if existing else f'セル ({r+1},{c+1})'}」を編集"),
            content=ft.Column([
                room_input,
                ft.Divider(height=4),
                ft.Row([
                    ft.Text("家具・スポット", size=13, weight=ft.FontWeight.BOLD, color=ft.Colors.TEAL_800, expand=True),
                    ft.TextButton("＋家具を追加", on_click=add_furniture_dialog),
                ]),
                furniture_list,
            ], tight=True, spacing=8, width=350, scroll=ft.ScrollMode.AUTO),
            actions=[
                ft.FilledButton("保存", on_click=save_cell),
                ft.TextButton("キャンセル", on_click=lambda e: setattr(dlg, 'open', False) or dlg.update()),
            ],
        )
        page.show_dialog(dlg)

    def resize_floorplan(rows, cols, cell_size=None):
        nonlocal floorplan
        old_cells = floorplan.get("cells", [])
        new_cells = [c for c in old_cells if c.get("r", 0) < rows and c.get("c", 0) < cols]
        floorplan["rows"] = rows
        floorplan["cols"] = cols
        floorplan["cells"] = new_cells
        if cell_size is not None:
            floorplan["cell_size"] = cell_size
        save_floorplan(floorplan)
        build_floorplan_grid()

    def show_floorplan_selector(e):
        def find_cell(rr, cc):
            return next((x for x in floorplan.get("cells", []) if x.get("r") == rr and x.get("c") == cc), None)
        rows = floorplan["rows"]
        cols = floorplan["cols"]
        path_text = ft.Text("部屋を選んでください", size=14, weight=ft.FontWeight.BOLD, color=ft.Colors.TEAL_800)
        content_area = ft.Column(spacing=4)

        def show_room_grid():
            path_text.value = "部屋を選んでください"
            path_text.update()
            grid_rows = []
            for r in range(rows):
                row_cells = []
                for c in range(cols):
                    cell = find_cell(r, c)
                    label = cell.get("room", "") if cell else f"({r+1},{c+1})"
                    cs_sel = min(floorplan.get("cell_size", 80), 100)
                    cont = ft.Container(
                        content=ft.Text(label, size=12, weight=ft.FontWeight.BOLD, text_align=ft.TextAlign.CENTER),
                        width=cs_sel, height=int(cs_sel * 0.65),
                        bgcolor=ft.Colors.AMBER_50 if cell else ft.Colors.GREY_200,
                        border=ft.Border.all(1, ft.Colors.TEAL_300 if cell else ft.Colors.GREY_400),
                        border_radius=6, alignment=ft.Alignment.CENTER, ink=True,
                        on_click=lambda ev, rr=r, cc=c: show_furniture_list(rr, cc),
                    )
                    row_cells.append(cont)
                grid_rows.append(ft.Row(row_cells, spacing=3, alignment=ft.MainAxisAlignment.CENTER))
            content_area.controls = [
                ft.Text("タップして部屋を選択", size=11, color=ft.Colors.GREY_600),
                ft.Column(grid_rows, spacing=3, horizontal_alignment=ft.CrossAxisAlignment.CENTER),
            ]
            content_area.update()

        def show_furniture_list(rr, cc):
            cell = find_cell(rr, cc)
            if not cell:
                set_location(f"({rr+1},{cc+1})")
                return
            path_text.value = cell.get("room", "")
            path_text.update()
            furn = cell.get("furniture", [])
            if not furn:
                set_location(cell.get("room", ""))
                return
            items = []
            for f in furn:
                items.append(ft.Container(
                    content=ft.Row([
                        ft.Text(f.get("name", ""), size=14, weight=ft.FontWeight.W_500, expand=True),
                        ft.Text("›", size=16, color=ft.Colors.GREY_500),
                    ]),
                    padding=12,
                    bgcolor=ft.Colors.AMBER_50,
                    border=ft.Border.all(1, ft.Colors.AMBER_200),
                    border_radius=6,
                    ink=True,
                    on_click=lambda ev, fn=f.get("name", ""): show_spot_list(rr, cc, fn),
                ))
            content_area.controls = [
                ft.TextButton("← 部屋一覧に戻る", on_click=lambda ev: show_room_grid()),
                ft.Divider(height=2),
                ft.Text("家具を選んでください", size=11, color=ft.Colors.GREY_600),
                ft.Column(items, spacing=4),
            ]
            content_area.update()

        def show_spot_list(rr, cc, furn_name):
            cell = find_cell(rr, cc)
            if not cell:
                set_location(f"({rr+1},{cc+1})")
                return
            furn = next((f for f in cell.get("furniture", []) if f.get("name") == furn_name), None)
            if not furn or not furn.get("spots"):
                set_location(f"{cell.get('room', '')} > {furn_name}")
                return
            path_text.value = f"{cell.get('room', '')} > {furn_name}"
            path_text.update()
            items = []
            for s in furn.get("spots", []):
                items.append(ft.Container(
                    content=ft.Text(s, size=13),
                    padding=10,
                    bgcolor=ft.Colors.AMBER_100,
                    border_radius=6,
                    ink=True,
                    on_click=lambda ev, sp=s: set_location(f"{cell.get('room', '')} > {furn_name} > {sp}"),
                ))
            content_area.controls = [
                ft.TextButton("← 家具一覧に戻る", on_click=lambda ev: show_furniture_list(rr, cc)),
                ft.Divider(height=2),
                ft.Text("スポットを選んでください", size=11, color=ft.Colors.GREY_600),
                ft.Column(items, spacing=4),
            ]
            content_area.update()

        def set_location(loc_text):
            location_ref.current.value = loc_text
            location_ref.current.update()
            dlg.open = False
            dlg.update()

        show_room_grid()
        dlg = ft.AlertDialog(
            modal=True,
            title=path_text,
            content=ft.Column([content_area], tight=True, spacing=8, width=300),
            actions=[ft.TextButton("キャンセル", on_click=lambda ev: setattr(dlg, 'open', False) or dlg.update())],
        )
        e.page.show_dialog(dlg)

    rows_input = ft.TextField(value=str(floorplan.get("rows", 3)), label="行", width=70,
                               keyboard_type=ft.KeyboardType.NUMBER, text_align=ft.TextAlign.CENTER)
    cols_input = ft.TextField(value=str(floorplan.get("cols", 3)), label="列", width=70,
                               keyboard_type=ft.KeyboardType.NUMBER, text_align=ft.TextAlign.CENTER)
    cell_size_options = [ft.dropdown.Option(str(s)) for s in (60, 80, 100, 120, 140)]
    cell_size_input = ft.Dropdown(
        label="セルサイズ",
        value=str(floorplan.get("cell_size", 80)),
        options=cell_size_options,
        width=100,
    )

    def on_resize_click(e):
        try:
            r = max(1, min(MAX_GRID, int(rows_input.value)))
            c = max(1, min(MAX_GRID, int(cols_input.value)))
            cs = max(40, min(200, int(cell_size_input.value)))
            resize_floorplan(r, c, cs)
            rows_input.value = str(r)
            cols_input.value = str(c)
            cell_size_input.value = str(cs)
            rows_input.update()
            cols_input.update()
            cell_size_input.update()
        except ValueError:
            e.page.show_snack_bar(ft.SnackBar(content=ft.Text("数字を入力してください")))

    floorplan_view = ft.Column([
        ft.Text("間取りを設定", size=22, weight=ft.FontWeight.BOLD),
        ft.Text("セルをタップして編集", size=12, color=ft.Colors.GREY_600, italic=True),
        ft.Divider(height=8),
        ft.Row([
            rows_input, ft.Text("×", size=16), cols_input, cell_size_input,
            ft.FilledButton("更新", on_click=on_resize_click),
        ], spacing=6),
        ft.Text("グリッドサイズ: 最大 30×30", size=11, color=ft.Colors.GREY_500),
        ft.Divider(height=8),
        floorplan_grid_container,
        ft.Divider(height=8),
        ft.TextButton("すべてリセット", on_click=lambda e: (resize_floorplan(3, 3, 80),
                     setattr(rows_input, 'value', '3'), rows_input.update(),
                     setattr(cols_input, 'value', '3'), cols_input.update(),
                     setattr(cell_size_input, 'value', '80'), cell_size_input.update()),
                     style=ft.ButtonStyle(color=ft.Colors.RED_400)),
    ], scroll=ft.ScrollMode.AUTO, spacing=12)

    search_dropdown = ft.Dropdown(
        ref=search_dropdown_ref,
        label="カテゴリで絞り込み",
        options=([ft.dropdown.Option("", "すべて")] + [ft.dropdown.Option(c) for c in categories]),
        width=300,
        on_select=on_search_cat_change,
    )

    search_view = ft.Column([
        ft.Row([
            ft.Text("焦らず、ゆっくり思い出しましょう", size=13, color=ft.Colors.TEAL_700, italic=True),
        ]),
        ft.Text("なくしものを探す", size=22, weight=ft.FontWeight.BOLD),
        ft.Divider(height=8),
        search_dropdown,
        ft.Row([
            ft.TextField(ref=search_ref, label="なくした物は？", hint_text="例: 財布、鍵、スマホ", expand=True),
            ft.FilledButton("探す", on_click=on_search_click),
        ]),
        chips_container,
        ft.Divider(height=8),
        ft.Container(content=results_container, expand=True),
        ft.Divider(height=8),
        simulation_container,
    ], scroll=ft.ScrollMode.AUTO, spacing=12)

    def on_date_selected(e):
        val = e.control.value
        if val:
            if hasattr(val, "strftime"):
                date_ref.current.value = val.strftime("%Y-%m-%d")
            else:
                date_ref.current.value = str(val)[:10]
            date_ref.current.update()

    date_picker = ft.DatePicker(
        on_change=on_date_selected,
        first_date=datetime(2000, 1, 1),
        last_date=datetime.now(),
    )

    def open_date_picker(e=None):
        date_picker.last_date = datetime.now()
        date_picker.open = True
        date_picker.update()

    record_view = ft.Column([
        ft.Text("見つけたらすぐに記録しましょう", size=13, color=ft.Colors.TEAL_700, italic=True),
        ft.Text("新しい記録", size=22, weight=ft.FontWeight.BOLD),
        ft.Divider(height=8),
        ft.TextField(ref=name_ref, label="なくした物", hint_text="例: 鍵、スマホ、財布", width=300),
        ft.Dropdown(
            ref=category_ref,
            label="カテゴリ",
            options=([ft.dropdown.Option("", "選択してください")] + [ft.dropdown.Option(c) for c in categories]),
            width=300,
        ),
        ft.TextButton("カテゴリ管理", on_click=show_category_dialog),
        ft.Row([
            ft.TextField(
                ref=date_ref,
                label="なくした日 (任意)",
                hint_text="タップしてカレンダーから選択",
                value=datetime.now().strftime("%Y-%m-%d"),
                width=300,
                read_only=True,
                on_focus=lambda _: open_date_picker(),
                suffix=ft.TextButton("日付選択", on_click=lambda _: open_date_picker()),
            ),
        ]),
        ft.TextField(ref=location_ref, label="見つかった場所", hint_text="例: ソファの隙間", width=300),
        ft.Column([
            location_chips_container,
            ft.Row([
                ft.TextButton("間取りから選ぶ", on_click=show_floorplan_selector,
                              style=ft.ButtonStyle(color=ft.Colors.TEAL_700)),
            ]),
        ]),
        ft.ElevatedButton("記録する", on_click=on_add_record),
        ft.Divider(height=16),
        ft.Row([
            ft.Text("記録履歴", size=16, weight=ft.FontWeight.BOLD),
            ft.Row([
                ft.TextButton("エクスポート", on_click=show_export_dialog),
                ft.TextButton("インポート", on_click=show_import_dialog),
            ]),
        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
        history_container,
    ], scroll=ft.ScrollMode.AUTO, spacing=12)

    ranking_view = ft.Column([ranking_container], scroll=ft.ScrollMode.AUTO, spacing=12)
    analysis_view = ft.Column([analysis_progress, analysis_container], scroll=ft.ScrollMode.AUTO, spacing=12)

    tabs = ft.Tabs(
        content=ft.Column([
            ft.TabBar(
                tabs=[
                    ft.Tab(label="探す"),
                    ft.Tab(label="記録"),
                    ft.Tab(label="間取り"),
                    ft.Tab(label="ランキング"),
                    ft.Tab(label="分析"),
                ],
                indicator_color=ft.Colors.TEAL_600,
                label_color=ft.Colors.TEAL_800,
                unselected_label_color=ft.Colors.GREY_600,
            ),
            ft.TabBarView(
                controls=[search_view, record_view, floorplan_view, ranking_view, analysis_view],
                expand=True,
            ),
        ], expand=True, spacing=0),
        length=5,
        selected_index=0,
        expand=True,
        on_change=lambda e: refresh_analysis() if e.control.selected_index == 4 else None,
    )

    page.appbar = ft.AppBar(
        title=ft.Row([ft.Text("なくしもの探知機", weight=ft.FontWeight.BOLD)], tight=True),
        bgcolor=ft.Colors.TEAL_800,
        color=ft.Colors.WHITE,
        center_title=True,
        actions=[
            ft.TextButton("エクスポート", on_click=show_export_dialog,
                          style=ft.ButtonStyle(color=ft.Colors.WHITE)),
            ft.TextButton("インポート", on_click=show_import_dialog,
                          style=ft.ButtonStyle(color=ft.Colors.WHITE)),
        ],
    )

    def on_page_load(e):
        refresh()

    page.overlay.append(date_picker)
    page.add(ft.Stack([
        ft.Container(expand=True, gradient=ft.LinearGradient(
            begin=ft.Alignment.TOP_LEFT, end=ft.Alignment.BOTTOM_RIGHT,
            colors=[ft.Colors.AMBER_50, ft.Colors.TEAL_50],
        )),
        ft.Container(expand=True, bgcolor=ft.Colors.with_opacity(0.15, ft.Colors.WHITE)),
        ft.SafeArea(expand=True, content=tabs),
    ], expand=True))

    page.update()
    load_from_storage()
    ensure_record_ids()
    refresh()
    build_floorplan_grid()
    page.on_load = on_page_load


ft.run(main, view=ft.AppView.WEB_BROWSER)
