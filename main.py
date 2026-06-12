from datetime import datetime
from collections import Counter, defaultdict
import json
import unicodedata
import calendar

import flet as ft

STORAGE_KEY = "lost_items_v4"
CATEGORIES = ["財布", "鍵", "スマホ", "イヤホン", "傘", "本", "文房具", "衣類", "カバン", "その他"]
WEEKDAYS_JP = ["月曜", "火曜", "水曜", "木曜", "金曜", "土曜", "日曜"]

# フリー自然画像（Unsplash）— 背景に控えめに使用、起動ごとにランダム選択
import random as _random
BG_IMAGES = [
    "https://images.unsplash.com/photo-1506744038136-46273834b3fb?auto=format&fit=crop&w=1920&q=80",
    "https://images.unsplash.com/photo-1470071459604-3b5ec3a7fe05?auto=format&fit=crop&w=1920&q=80",
    "https://images.unsplash.com/photo-1441974231531-c6227db76b6e?auto=format&fit=crop&w=1920&q=80",
    "https://images.unsplash.com/photo-1484542603127-984f4f7d6f96?auto=format&fit=crop&w=1920&q=80",
    "https://images.unsplash.com/photo-1518173946687-a36e968f88f2?auto=format&fit=crop&w=1920&q=80",
    "https://images.unsplash.com/photo-1501785888041-af3ef285b470?auto=format&fit=crop&w=1920&q=80",
    "https://images.unsplash.com/photo-1469474968028-56623f02e42e?auto=format&fit=crop&w=1920&q=80",
    "https://images.unsplash.com/photo-1507525428034-b723cf961d3e?auto=format&fit=crop&w=1920&q=80",
    "https://images.unsplash.com/photo-1472214103451-9374bd1c798e?auto=format&fit=crop&w=1920&q=80",
    "https://images.unsplash.com/photo-1505118380757-91f5f5632de0?auto=format&fit=crop&w=1920&q=80",
]
BG_IMAGE = _random.choice(BG_IMAGES)


def fuzzy_match(query: str, text: str) -> bool:
    q = unicodedata.normalize("NFKC", query.strip().lower())
    t = unicodedata.normalize("NFKC", text.strip().lower())
    return bool(q) and (q in t)


def parse_weekday(d: str):
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y-%m-%d %H:%M", "%m-%d", "%m/%d"):
        try:
            return datetime.strptime(d, fmt).weekday()
        except ValueError:
            pass
    return None


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
    search_val = ""
    search_cat = ""
    results = None

    search_ref = ft.Ref[ft.TextField]()
    name_ref = ft.Ref[ft.TextField]()
    date_ref = ft.Ref[ft.TextField]()
    location_ref = ft.Ref[ft.TextField]()
    category_ref = ft.Ref[ft.Dropdown]()
    search_dropdown_ref = ft.Ref[ft.Dropdown]()

    chips_container = ft.Column(spacing=4)
    results_container = ft.Column(spacing=6)
    simulation_container = ft.Column(spacing=4)
    history_container = ft.Column(spacing=4)
    ranking_container = ft.Column(spacing=8)
    analysis_container = ft.Column(spacing=8)
    analysis_progress = ft.ProgressBar(visible=False, color=ft.Colors.TEAL_600)

    def load_from_storage():
        nonlocal records
        try:
            from js import window
            raw = window.localStorage.getItem(STORAGE_KEY)
            if raw is not None:
                data = json.loads(raw)
                if isinstance(data, list):
                    records = data
        except Exception:
            try:
                raw = page.client_storage.get(STORAGE_KEY)
                if raw and isinstance(raw, list):
                    records = raw
            except Exception:
                pass

    def save():
        try:
            from js import window
            window.localStorage.setItem(STORAGE_KEY, json.dumps(records, ensure_ascii=False))
        except Exception:
            try:
                page.client_storage.set(STORAGE_KEY, records)
            except Exception:
                pass

    def get_filtered():
        nonlocal search_cat
        if not search_cat:
            return records
        return [r for r in records if r.get("category", "") == search_cat]

    def do_search(query):
        if not query:
            return None
        matched = [r for r in get_filtered() if fuzzy_match(query, r["name"])]
        if not matched:
            return []
        total = len(matched)
        location_counts = Counter(r["location"] for r in matched).most_common()
        max_pct = location_counts[0][1] / total * 100 if location_counts else 0
        return [(loc or "場所不明", cnt, cnt / total * 100, cnt / total * 100 == max_pct)
                for loc, cnt in location_counts]

    def search_from_history(name):
        nonlocal search_val, results
        search_val = name
        search_ref.current.value = name
        results = do_search(name)
        tabs.selected_index = 0
        refresh()



    def on_search_click(e):
        nonlocal search_val, results
        q = search_ref.current.value.strip()
        if not q:
            e.page.show_snack_bar(ft.SnackBar(content=ft.Text("なくした物を入力してください")))
            results = []
            refresh()
            return
        search_val = q
        results = do_search(q)
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
        rec = {
            "name": name,
            "category": category_ref.current.value or "その他",
            "location": location,
            "lost_date": (date_ref.current.value or "").strip() or datetime.now().strftime("%Y-%m-%d"),
            "found_date": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "resolved": False,
            "resolution_date": None,
        }
        records = records + [rec]
        save()
        e.page.show_snack_bar(ft.SnackBar(content=ft.Text("記録しました"), bgcolor=ft.Colors.TEAL_400))
        name_ref.current.value = ""
        category_ref.current.value = ""
        date_ref.current.value = ""
        location_ref.current.value = ""
        refresh()

    def delete_record(idx):
        nonlocal records
        records.pop(idx)
        save()
        refresh()

    def mark_resolved(idx):
        nonlocal records
        records[idx]["resolved"] = True
        records[idx]["resolution_date"] = datetime.now().strftime("%Y-%m-%d %H:%M")
        save()
        page.show_snack_bar(ft.SnackBar(
            content=ft.Text(f"「{records[idx]['name']}」を見つかりました！"), bgcolor=ft.Colors.TEAL_400))
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

    def make_bar(pct, color):
        inner = ft.Container(height=12, width=f"{pct}%", bgcolor=color, border_radius=6)
        outer = ft.Container(height=12, bgcolor=ft.Colors.AMBER_100, border_radius=6)
        return ft.Stack([outer, inner])

    def do_time_simulation(query, matched_records):
        if not matched_records:
            return []
        now = datetime.now()
        current_hour = now.hour
        current_wd = now.weekday()

        scored = []
        for r in matched_records:
            fd = r.get("found_date", "")
            try:
                dt = datetime.strptime(fd, "%Y-%m-%d %H:%M")
            except ValueError:
                try:
                    dt = datetime.strptime(fd, "%Y-%m-%d")
                except ValueError:
                    continue
            hour_diff = abs(dt.hour - current_hour)
            wd_match = 1 if dt.weekday() == current_wd else 0
            time_score = max(0, 1 - hour_diff / 12)
            score = time_score * 0.6 + wd_match * 0.4
            scored.append((r["location"], score))
        if not scored:
            return []
        location_scores = Counter()
        for loc, sc in scored:
            location_scores[loc] += sc
        total_score = sum(location_scores.values())
        ranked = [(loc, sc, sc / total_score * 100) for loc, sc in location_scores.most_common()]
        max_pct = ranked[0][2] if ranked else 0
        return [(loc, sc, pct, pct == max_pct) for loc, sc, pct in ranked]

    def refresh():
        nonlocal chips_container, results_container, simulation_container, history_container, ranking_container

        chips = []
        unique = list(dict.fromkeys(r["name"] for r in get_filtered()))
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

        if results is None:
            results_container.controls = [ft.Text("アイテムを入力して「探す」を押してください", color=ft.Colors.GREY_500)]
            simulation_container.controls = []
        elif not results:
            results_container.controls = [ft.Text("該当する記録がありません", color=ft.Colors.GREY_500)]
            simulation_container.controls = []
        else:
            total = sum(cnt for _, cnt, _, _ in results)
            name = search_val.strip()
            rc = [
                ft.Text(f"「{name}」が見つかりそうな場所",
                        size=17, weight=ft.FontWeight.BOLD, color=ft.Colors.TEAL_800),
                ft.Text(f"過去 {total} 件の記録から予測",
                        size=12, color=ft.Colors.GREY_600),
                ft.Divider(height=4),
            ]
            for loc, cnt, pct, is_top in results:
                color = ft.Colors.TEAL_700 if is_top else ft.Colors.TEAL_600
                card = ft.Container(
                    content=ft.Column([
                        ft.Row([
                            ft.Text(loc, size=14, weight=(
                                ft.FontWeight.BOLD if is_top else ft.FontWeight.W_500), expand=True),
                            ft.Text(f"{pct:.0f}%", size=15, weight=ft.FontWeight.BOLD, color=color),
                        ]),
                        make_bar(pct, ft.Colors.TEAL_400 if is_top else ft.Colors.ORANGE_100),
                        ft.Text(f"{cnt}件", size=11, color=ft.Colors.GREY_600),
                    ], spacing=3),
                    padding=10,
                    bgcolor=ft.Colors.with_opacity(0.8, ft.Colors.AMBER_50) if is_top else ft.Colors.with_opacity(0.8, ft.Colors.WHITE),
                    border=ft.Border.all(1, ft.Colors.TEAL_300 if is_top else ft.Colors.AMBER_100),
                    border_radius=8,
                )
                rc.append(card)
            results_container.controls = rc

            sim_matched = [r for r in get_filtered() if fuzzy_match(search_val, r["name"])]
            sim_results = do_time_simulation(search_val, sim_matched)
            if sim_results:
                now = datetime.now()
                wd_name = ["月", "火", "水", "木", "金", "土", "日"][now.weekday()]
                sim = [
                    ft.Divider(height=16),
                    ft.Text("もしもシミュレーター", size=16, weight=ft.FontWeight.BOLD, color=ft.Colors.TEAL_800),
                    ft.Text(f"今は{wd_name}曜日 {now.hour}時台のデータから予測",
                            size=12, color=ft.Colors.GREY_600),
                    ft.Divider(height=4),
                ]
                for loc, sc, pct, is_top in sim_results:
                    color = ft.Colors.BROWN_700 if is_top else ft.Colors.TEAL_600
                    card = ft.Container(
                        content=ft.Column([
                            ft.Row([
                                ft.Text(loc, size=14, weight=(
                                    ft.FontWeight.BOLD if is_top else ft.FontWeight.W_500), expand=True),
                                ft.Text(f"{pct:.0f}%", size=14, weight=ft.FontWeight.BOLD, color=color),
                            ]),
                            make_bar(pct, ft.Colors.BROWN_300 if is_top else ft.Colors.ORANGE_100),
                        ], spacing=3),
                        padding=10,
                        bgcolor=ft.Colors.with_opacity(0.8, ft.Colors.ORANGE_50) if is_top else ft.Colors.with_opacity(0.8, ft.Colors.WHITE),
                        border=ft.Border.all(1, ft.Colors.BROWN_200 if is_top else ft.Colors.AMBER_100),
                        border_radius=8,
                    )
                    sim.append(card)
                simulation_container.controls = sim
            else:
                simulation_container.controls = []

        if not records:
            history_container.controls = [
                ft.Container(
                    ft.Column([
                        ft.Text("まだ記録がありません", color=ft.Colors.TEAL_700),
                        ft.Text("「記録」タブからなくし物を追加しましょう", size=12, color=ft.Colors.GREY_500, italic=True),
                    ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=4),
                    padding=20, alignment=ft.Alignment.CENTER,
                    image=ft.DecorationImage(src=BG_IMAGE, opacity=0.5, fit=ft.BoxFit.COVER),
                ),
            ]
        else:
            hc = []
            for i, r in enumerate(reversed(records)):
                idx = len(records) - 1 - i
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
                    ft.TextButton("探す",
                        on_click=lambda e, n=r["name"]: search_from_history(n),
                    ),
                ]
                if not resolved:
                    trailing_btns.insert(0, ft.TextButton("解決",
                        on_click=lambda e, i=idx: mark_resolved(i),
                    ))
                trailing_btns.append(ft.TextButton("削除",
                    on_click=lambda e, i=idx: delete_record(i),
                ))
                hc.append(
                    ft.Card(
                        ft.ListTile(
                            title=ft.Text(r["name"], weight=ft.FontWeight.W_500),
                            subtitle=ft.Text(subtitle, size=13),
                            trailing=ft.Row(trailing_btns, spacing=0),
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
                    image=ft.DecorationImage(src=BG_IMAGE, opacity=0.5, fit=ft.BoxFit.COVER),
                ),
            ]
        else:
            name_counts = Counter(r["name"] for r in records).most_common()
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

    def build_diagnosis(items, total, unique_items, top_item):
        if not items:
            return []
        ratio = unique_items / total if total > 0 else 0
        if ratio < 0.25:
            focus_type = "集中型"
            focus_desc = "同じ物を繰り返しなくす傾向があります"
        elif ratio < 0.5:
            focus_type = "バランス型"
            focus_desc = "まんべんなく色々なくします"
        else:
            focus_type = "分散型"
            focus_desc = "毎回違う物をなくすのが特徴です"

        name_counts = Counter(items)
        repeat_items = [(n, c) for n, c in name_counts.most_common() if c >= 3]

        cats = [r.get("category", "その他") for r in records]
        top_cat = Counter(cats).most_common(1)[0][0] if cats else "—"

        weekday_counts = Counter()
        for r in records:
            d = r.get("lost_date", "") or r.get("found_date", "")[:10]
            wd = parse_weekday(d)
            if wd is not None:
                weekday_counts[wd] += 1

        peak_wd_name = "—"
        if weekday_counts:
            peak_wd = weekday_counts.most_common(1)[0][0]
            peak_wd_name = WEEKDAYS_JP[peak_wd]

        resolved_list = [r for r in records if r.get("resolved")]
        resolved_cnt = len(resolved_list)
        resolution_rate = resolved_cnt / total * 100 if total > 0 else 0

        time_diffs = []
        for r in resolved_list:
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

        avg_hours = sum(time_diffs) / len(time_diffs) if time_diffs else None

        advice_lines = []
        if peak_wd_name != "—":
            advice_lines.append(f"{peak_wd_name}は特に注意！この曜日によくなくしています")
        if top_cat != "—":
            advice_lines.append(f"「{top_cat}」カテゴリの管理を見直してみましょう")
        if repeat_items:
            top_repeat = repeat_items[0]
            advice_lines.append(f"「{top_repeat[0]}」は{top_repeat[1]}回もなくしています！定位置を決めてみては？")
        if resolution_rate > 50:
            advice_lines.append(f"解決率 {resolution_rate:.0f}%！なくしても見つけるのが上手です")
        else:
            advice_lines.append(f"解決率 {resolution_rate:.0f}%…なくしたらすぐに探す習慣を")
        if avg_hours is not None:
            if avg_hours < 24:
                advice_lines.append(f"平均 {avg_hours:.0f}時間で見つけています！素早い！")
            elif avg_hours < 72:
                advice_lines.append(f"平均 {avg_hours:.0f}時間で発見。1〜2日以内には見つかります")
            else:
                days = avg_hours / 24
                advice_lines.append(f"平均 {days:.1f}日かかっています。見つけたらすぐ記録しましょう")

        lines = []
        lines.append(f"タイプ: {focus_type}")
        lines.append(f"{focus_desc}")
        lines.append(f"なくし物の種類: {unique_items}種類 / 全{total}回")
        if repeat_items:
            top_repeat = repeat_items[0]
            lines.append(f"最多記録: 「{top_repeat[0]}」を{top_repeat[1]}回")
        lines.append(f"よくなくすカテゴリ: {top_cat}")
        if weekday_counts:
            lines.append(f"ピーク曜日: {peak_wd_name}")
        lines.append(f"解決率: {resolution_rate:.0f}% ({resolved_cnt}/{total})")

        title = f"あなたは「{focus_type}」"
        return [title] + lines + [""] + advice_lines

    def refresh_analysis():
        analysis_progress.visible = True

        if not records:
            analysis_container.controls = [
                ft.Container(
                    ft.Column([
                        ft.Text("まだデータがありません", color=ft.Colors.TEAL_700),
                        ft.Text("記録が増えると分析が表示されます", size=12, color=ft.Colors.GREY_500, italic=True),
                    ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=4),
                    padding=20, alignment=ft.Alignment.CENTER,
                    image=ft.DecorationImage(src=BG_IMAGE, opacity=0.5, fit=ft.BoxFit.COVER),
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
        max_d = datetime.now()
        if lost_by_date:
            dates = [d for d in lost_by_date if d]
            if dates:
                min_d = datetime.strptime(min(dates), "%Y-%m-%d")

        cal_year = getattr(refresh_analysis, "cal_year", max_d.year)
        cal_month = getattr(refresh_analysis, "cal_month", max_d.month)

        cal_header = ft.Row([
            ft.TextButton("<", on_click=lambda e: _navigate_cal(-1)),
            ft.Text(f"{cal_year}年 {cal_month}月", size=16, weight=ft.FontWeight.BOLD, expand=True, text_align=ft.TextAlign.CENTER),
            ft.TextButton(">", on_click=lambda e: _navigate_cal(1)),
        ], alignment=ft.MainAxisAlignment.CENTER)
        sections.append(cal_header)

        cal_grid = ft.Column(spacing=2)
        month_cal = calendar.monthcalendar(cal_year, cal_month)
        day_names = ["月", "火", "水", "木", "金", "土", "日"]
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

        analysis_container.controls = sections
        analysis_progress.visible = False
        page.update()

    def _navigate_cal(delta):
        cy = getattr(refresh_analysis, "cal_year", datetime.now().year)
        cm = getattr(refresh_analysis, "cal_month", datetime.now().month)
        cm += delta
        if cm > 12:
            cm = 1
            cy += 1
        elif cm < 1:
            cm = 12
            cy -= 1
        refresh_analysis.cal_year = cy
        refresh_analysis.cal_month = cm
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

    search_dropdown = ft.Dropdown(
        ref=search_dropdown_ref,
        label="カテゴリで絞り込み",
        options=([ft.dropdown.Option("", "すべて")] + [ft.dropdown.Option(c) for c in CATEGORIES]),
        width=300,
        on_select=on_search_cat_change,
    )

    search_view = ft.Column([
        ft.Text("焦らず、ゆっくり思い出しましょう", size=13, color=ft.Colors.TEAL_700, italic=True),
        ft.Text("なくしものを探す", size=22, weight=ft.FontWeight.BOLD),
        ft.Divider(height=8),
        search_dropdown,
        ft.Row([
            ft.TextField(ref=search_ref, label="なくした物は？", hint_text="例: 財布、鍵、スマホ", expand=True),
            ft.FilledButton("探す", on_click=on_search_click),
        ]),
        chips_container,
        ft.Divider(height=8),
        results_container,
        ft.Divider(height=8),
        simulation_container,
    ], scroll=ft.ScrollMode.AUTO, spacing=12)

    def on_date_selected(e):
        val = e.control.value
        if val:
            date_ref.current.value = val.strftime("%Y-%m-%d")
            date_ref.current.update()

    date_picker = ft.DatePicker(
        on_change=on_date_selected,
        first_date=datetime(2000, 1, 1),
        last_date=datetime.now(),
    )

    def open_date_picker(e=None):
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
            options=([ft.dropdown.Option("", "選択してください")] + [ft.dropdown.Option(c) for c in CATEGORIES]),
            width=300,
        ),
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
                    ft.Tab(label="ランキング"),
                    ft.Tab(label="分析"),
                ],
                indicator_color=ft.Colors.TEAL_600,
                label_color=ft.Colors.TEAL_800,
                unselected_label_color=ft.Colors.GREY_600,
            ),
            ft.TabBarView(
                controls=[search_view, record_view, ranking_view, analysis_view],
                expand=True,
            ),
        ], expand=True, spacing=0),
        length=4,
        selected_index=0,
        expand=True,
        on_change=lambda e: refresh_analysis() if e.control.selected_index == 3 else None,
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

    page.overlay.append(date_picker)
    page.add(ft.Stack([
        ft.Container(expand=True, image=ft.DecorationImage(src=BG_IMAGE, opacity=1.0, fit=ft.BoxFit.COVER)),
        ft.Container(expand=True, bgcolor=ft.Colors.with_opacity(0.55, ft.Colors.WHITE)),
        ft.SafeArea(expand=True, content=tabs),
    ], expand=True))

    page.update()
    load_from_storage()
    refresh()

    page.on_load = lambda e: (load_from_storage(), refresh())


ft.run(main, view=ft.AppView.WEB_BROWSER)
