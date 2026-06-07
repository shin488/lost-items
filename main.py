from datetime import datetime
from collections import Counter, defaultdict
import json
import unicodedata

import flet as ft

STORAGE_KEY = "lost_items_v4"
CATEGORIES = ["財布", "鍵", "スマホ", "イヤホン", "傘", "本", "文房具", "衣類", "カバン", "その他"]
WEEKDAYS_JP = ["月曜", "火曜", "水曜", "木曜", "金曜", "土曜", "日曜"]


def fuzzy_match(query: str, text: str) -> bool:
    q = unicodedata.normalize("NFKC", query.strip().lower())
    t = unicodedata.normalize("NFKC", text.strip().lower())
    return bool(q) and (q in t)


def parse_weekday(d: str):
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%m-%d", "%m/%d"):
        try:
            return datetime.strptime(d, fmt).weekday()
        except ValueError:
            pass
    return None


def main(page: ft.Page):
    page.title = "なくしもの探知機"

    page.theme = ft.Theme(
        color_scheme=ft.ColorScheme(
            primary=ft.Colors.DEEP_PURPLE,
            primary_container=ft.Colors.DEEP_PURPLE_100,
            secondary=ft.Colors.TEAL,
            secondary_container=ft.Colors.TEAL_100,
            surface=ft.Colors.GREY_50,
            surface_container=ft.Colors.GREY_100,
        ),
        use_material3=True,
    )

    page.scroll = ft.ScrollMode.AUTO
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
    analysis_progress = ft.ProgressBar(visible=False)

    def load_from_storage():
        nonlocal records
        try:
            raw = page.client_storage.get(STORAGE_KEY)
            if raw and isinstance(raw, list):
                records = raw
        except Exception:
            pass

    def save():
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
        tabs.update()
        refresh()

    def on_tab_change(e):
        idx = int(e.data)
        if idx == 3:
            refresh_analysis()

    def on_search_click(e):
        nonlocal results
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
            "lost_date": date_ref.current.value.strip() or datetime.now().strftime("%Y-%m-%d"),
            "found_date": datetime.now().strftime("%Y-%m-%d %H:%M"),
        }
        records = records + [rec]
        save()
        e.page.show_snack_bar(ft.SnackBar(content=ft.Text("記録しました"), bgcolor=ft.Colors.GREEN_400))
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
                    bgcolor=ft.Colors.GREEN_400))
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
        outer = ft.Container(height=12, bgcolor=ft.Colors.GREY_200, border_radius=6)
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
                bgcolor=ft.Colors.DEEP_PURPLE_50,
                border_radius=12,
                on_click=lambda e, n=name: search_from_history(n),
                ink=True,
            )
            chips.append(ft.Row([chip], tight=True))
        chips_container.controls = chips

        if results is None:
            results_container.controls = [ft.Text("アイテムを入力して「探す」を押してください", italic=True, color=ft.Colors.GREY)]
            simulation_container.controls = []
        elif not results:
            results_container.controls = [ft.Text("該当する記録がありません", italic=True, color=ft.Colors.GREY)]
            simulation_container.controls = []
        else:
            total = sum(cnt for _, cnt, _, _ in results)
            rc = [
                ft.Text(f"「{search_val.strip()}」が見つかりそうな場所",
                        size=16, weight=ft.FontWeight.BOLD),
                ft.Text(f"過去 {total} 件の記録をもとに予測",
                        size=12, color=ft.Colors.GREY, italic=True),
                ft.Divider(height=8),
            ]
            for loc, cnt, pct, is_top in results:
                color = ft.Colors.DEEP_ORANGE_400 if is_top else ft.Colors.INDIGO_400
                rc.append(ft.Column([
                    ft.Row([
                        ft.Text("👑 " if is_top else "", size=14),
                        ft.Text(loc, size=15, weight=(
                            ft.FontWeight.BOLD if is_top else ft.FontWeight.NORMAL), expand=True),
                        ft.Text(f"{pct:.0f}%", size=14, weight=ft.FontWeight.BOLD, color=color),
                    ]),
                    make_bar(pct, color),
                    ft.Text(f"{cnt}件", size=11, color=ft.Colors.GREY_600),
                ], spacing=2))
            results_container.controls = rc

            sim_matched = [r for r in get_filtered() if fuzzy_match(search_val, r["name"])]
            sim_results = do_time_simulation(search_val, sim_matched)
            if sim_results:
                now = datetime.now()
                wd_name = ["月", "火", "水", "木", "金", "土", "日"][now.weekday()]
                sim = [
                    ft.Divider(height=16),
                    ft.Text("もしもシミュレーター", size=16, weight=ft.FontWeight.BOLD),
                    ft.Text(f"今は{wd_name}曜日 {now.hour}時台。過去の同時期のデータから予測",
                            size=12, color=ft.Colors.GREY, italic=True),
                    ft.Divider(height=4),
                ]
                for loc, sc, pct, is_top in sim_results:
                    color = ft.Colors.TEAL_400 if is_top else ft.Colors.BLUE_300
                    sim.append(ft.Column([
                        ft.Row([
                            ft.Text("🔍 " if is_top else "  ", size=14),
                            ft.Text(loc, size=14, weight=(
                                ft.FontWeight.BOLD if is_top else ft.FontWeight.NORMAL), expand=True),
                            ft.Text(f"{pct:.0f}%", size=13, weight=ft.FontWeight.BOLD, color=color),
                        ]),
                        make_bar(pct, color),
                    ], spacing=1))
                simulation_container.controls = sim
            else:
                simulation_container.controls = []

        if not records:
            history_container.controls = [ft.Text("まだ記録がありません", italic=True, color=ft.Colors.GREY)]
        else:
            hc = []
            for i, r in enumerate(reversed(records)):
                idx = len(records) - 1 - i
                cat = r.get("category", "")
                loc = r.get("location", "場所不明")
                fd = r.get("found_date", "")
                subtitle = f"{loc}  ({fd})"
                if cat:
                    subtitle = f"[{cat}] {subtitle}"
                hc.append(
                    ft.Card(
                        ft.ListTile(
                            title=ft.Text(r["name"], weight=ft.FontWeight.W_500),
                            subtitle=ft.Text(subtitle, size=13),
                            trailing=ft.Row([
                                ft.IconButton(
                                    ft.Icons.SEARCH, icon_color=ft.Colors.BLUE_300,
                                    tooltip="このアイテムを探す",
                                    on_click=lambda e, n=r["name"]: search_from_history(n),
                                ),
                                ft.IconButton(
                                    ft.Icons.DELETE_OUTLINE, icon_color=ft.Colors.RED_300,
                                    tooltip="削除",
                                    on_click=lambda e, i=idx: delete_record(i),
                                ),
                            ], spacing=0),
                        ),
                        margin=3,
                    )
                )
            history_container.controls = hc

        if not records:
            ranking_container.controls = [ft.Text("まだデータがありません", italic=True, color=ft.Colors.GREY)]
        else:
            name_counts = Counter(r["name"] for r in records).most_common()
            total = len(records)
            rc = [
                ft.Text("よくなくした物ランキング", size=18, weight=ft.FontWeight.BOLD),
                ft.Text(f"全 {total} 件の記録", size=12, color=ft.Colors.GREY, italic=True),
                ft.Divider(height=8),
            ]
            medals = {1: "\U0001F947", 2: "\U0001F948", 3: "\U0001F949"}
            for rank, (name, cnt) in enumerate(name_counts, 1):
                medal = medals.get(rank, f"  #{rank} ")
                pct = cnt / total * 100
                rc.append(
                    ft.Card(
                        ft.ListTile(
                            leading=ft.Text(medal, size=24),
                            title=ft.Row([
                                ft.Text(f"#{rank}", size=13, color=ft.Colors.GREY_500),
                                ft.Text(name, size=16, weight=ft.FontWeight.W_500),
                            ]),
                            subtitle=ft.Text(f"{cnt}回 ({pct:.1f}%)", size=13, color=ft.Colors.GREY_600),
                            trailing=ft.IconButton(
                                ft.Icons.SEARCH, icon_color=ft.Colors.BLUE_300,
                                tooltip="このアイテムを探す",
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
            focus_icon = "🎯"
        elif ratio < 0.5:
            focus_type = "バランス型"
            focus_desc = "まんべんなく色々なくします"
            focus_icon = "⚖️"
        else:
            focus_type = "分散型"
            focus_desc = "毎回違う物をなくすのが特徴です"
            focus_icon = "🌈"

        name_counts = Counter(items)
        repeat_items = [(n, c) for n, c in name_counts.most_common() if c >= 3]

        cats = [r.get("category", "その他") for r in records]
        top_cat = Counter(cats).most_common(1)[0][0] if cats else "—"

        locs = [r.get("location", "") for r in records if r.get("location")]
        loc_diversity = len(set(locs)) / total if total > 0 else 0

        weekday_counts = Counter()
        for r in records:
            d = r.get("lost_date", "") or r.get("found_date", "")[:10]
            wd = parse_weekday(d)
            if wd is not None:
                weekday_counts[wd] += 1

        if weekday_counts:
            peak_wd = weekday_counts.most_common(1)[0][0]
            peak_wd_name = WEEKDAYS_JP[peak_wd]
        else:
            peak_wd_name = "—"

        lines = []
        lines.append(f"{focus_icon} タイプ: {focus_type}")
        lines.append(f"  {focus_desc}")
        lines.append(f"  なくし物の種類: {unique_items}種類 / 全{total}回")
        if repeat_items:
            top_repeat = repeat_items[0]
            lines.append(f"🏆 最多記録: 「{top_repeat[0]}」を{top_repeat[1]}回")
        lines.append(f"📂 よくなくすカテゴリ: {top_cat}")
        if weekday_counts:
            lines.append(f"📅 ピーク曜日: {peak_wd_name}")

        title = f"{focus_icon} あなたは「{focus_type}」"
        return [title] + lines

    def refresh_analysis():
        analysis_progress.visible = True
        analysis_progress.update()

        if not records:
            analysis_container.controls = [ft.Text("まだデータがありません", italic=True, color=ft.Colors.GREY)]
            analysis_progress.visible = False
            analysis_container.update()
            analysis_progress.update()
            return

        items = [r["name"] for r in records]
        total = len(records)
        unique_items = len(set(items))
        top_item = Counter(items).most_common(1)[0] if items else ("", 0)
        locations = Counter(r["location"] for r in records).most_common(1)
        top_loc = locations[0] if locations else ("", 0)

        weekday_item = defaultdict(lambda: Counter())
        weekday_total = Counter()
        for r in records:
            d = r.get("lost_date", "") or r.get("found_date", "")[:10]
            wd = parse_weekday(d)
            if wd is not None:
                weekday_total[wd] += 1
                weekday_item[wd][r["name"]] += 1

        has_weekday = bool(weekday_total)
        best_wd = weekday_total.most_common(1)[0][0] if has_weekday else None

        sections = []

        diagnosis_lines = build_diagnosis(items, total, unique_items, top_item)
        if diagnosis_lines:
            sections.append(ft.Container(
                ft.Column([
                    ft.Text(diagnosis_lines[0], size=16, weight=ft.FontWeight.BOLD),
                    ft.Divider(height=4),
                ] + [ft.Text(l, size=13, color=ft.Colors.GREY_700) for l in diagnosis_lines[1:]] +
                    ([
                        ft.Divider(height=4),
                        ft.Text("💡 同じ物を3回以上なくすと診断に反映されます", size=11, color=ft.Colors.GREY_400, italic=True),
                    ] if not diagnosis_lines[1].startswith("🏆") else []),
                    spacing=2,
                ),
                padding=12, border_radius=8, bgcolor=ft.Colors.AMBER_50,
            ))
            sections.append(ft.Divider(height=12))

        sections.append(ft.Text("全体統計", size=18, weight=ft.FontWeight.BOLD))
        sections.append(ft.Divider(height=8))
        row1 = ft.Row([
            ft.Container(
                ft.Column([
                    ft.Text("総記録数", size=11, color=ft.Colors.GREY_600),
                    ft.Text(str(total), size=22, weight=ft.FontWeight.BOLD, color=ft.Colors.DEEP_PURPLE_700),
                ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=1),
                padding=10, border_radius=8,
                bgcolor=ft.Colors.DEEP_PURPLE_50, expand=True,
            ),
            ft.Container(
                ft.Column([
                    ft.Text("なくした物", size=11, color=ft.Colors.GREY_600),
                    ft.Text(str(unique_items), size=22, weight=ft.FontWeight.BOLD, color=ft.Colors.TEAL_700),
                ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=1),
                padding=10, border_radius=8,
                bgcolor=ft.Colors.TEAL_50, expand=True,
            ),
            ft.Container(
                ft.Column([
                    ft.Text("最多なくし物", size=11, color=ft.Colors.GREY_600),
                    ft.Text(top_item[0], size=14, weight=ft.FontWeight.BOLD),
                    ft.Text(f"{top_item[1]}回", size=11, color=ft.Colors.GREY_600),
                ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=1),
                padding=10, border_radius=8,
                bgcolor=ft.Colors.ORANGE_50, expand=True,
            ),
            ft.Container(
                ft.Column([
                    ft.Text("最多発見場所", size=11, color=ft.Colors.GREY_600),
                    ft.Text(top_loc[0], size=14, weight=ft.FontWeight.BOLD),
                    ft.Text(f"{top_loc[1]}回", size=11, color=ft.Colors.GREY_600),
                ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=1),
                padding=10, border_radius=8,
                bgcolor=ft.Colors.PURPLE_50, expand=True,
            ),
        ], spacing=6)
        sections.append(row1)

        if has_weekday:
            sections.append(ft.Divider(height=16))
            sections.append(ft.Text("なくしやすい曜日", size=18, weight=ft.FontWeight.BOLD))
            sections.append(ft.Divider(height=8))

            for wd_idx in range(7):
                cnt = weekday_total.get(wd_idx, 0)
                pct = cnt / total * 100
                is_top_wd = wd_idx == best_wd
                color = ft.Colors.RED_400 if is_top_wd else ft.Colors.DEEP_PURPLE_300
                items_on_day = weekday_item[wd_idx].most_common(3)
                items_str = "  ".join(f"{n}({c})" for n, c in items_on_day) if items_on_day else "—"
                sections.append(ft.Column([
                    ft.Row([
                        ft.Text(f"{WEEKDAYS_JP[wd_idx]}", size=14, weight=(
                            ft.FontWeight.BOLD if is_top_wd else ft.FontWeight.NORMAL), expand=True),
                        ft.Text(f"{cnt}回", size=12, weight=ft.FontWeight.BOLD),
                    ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                    make_bar(pct, color),
                    ft.Text(items_str, size=11, color=ft.Colors.GREY_600, italic=True),
                ], spacing=2))

        sections.append(ft.Divider(height=16))
        sections.append(ft.Text("アイテム × 場所 の相関", size=18, weight=ft.FontWeight.BOLD))
        sections.append(ft.Text("アイテムごとによく見つかる場所 TOP3", size=12, color=ft.Colors.GREY, italic=True))
        sections.append(ft.Divider(height=8))

        item_locations = defaultdict(lambda: Counter())
        for r in records:
            item_locations[r["name"]][r["location"]] += 1

        item_counts = Counter(items).most_common(10)
        for name, cnt in item_counts:
            top_locs = item_locations[name].most_common(3)
            loc_chips = []
            for loc, lc in top_locs:
                loc_chips.append(ft.Container(
                    content=ft.Text(f"{loc} ({lc}回)", size=12),
                    padding=8,
                    bgcolor=ft.Colors.TEAL_50,
                    border_radius=8,
                ))
            sections.append(ft.Card(
                ft.ListTile(
                    title=ft.Text(name, weight=ft.FontWeight.W_500),
                    subtitle=ft.Row(loc_chips, wrap=True, spacing=4) if loc_chips else ft.Text("データなし", size=12, color=ft.Colors.GREY),
                    trailing=ft.Text(f"{cnt}回", size=13, color=ft.Colors.BLUE_700),
                ),
                margin=3,
            ))

        if has_weekday:
            sections.append(ft.Divider(height=16))
            sections.append(ft.Text("アイテム × 曜日 の相関", size=18, weight=ft.FontWeight.BOLD))
            sections.append(ft.Text("アイテムをなくしやすい曜日の傾向", size=12, color=ft.Colors.GREY, italic=True))
            sections.append(ft.Divider(height=8))

            item_weekday = defaultdict(lambda: Counter())
            for r in records:
                d = r.get("lost_date", "") or r.get("found_date", "")[:10]
                wd = parse_weekday(d)
                if wd is not None:
                    item_weekday[r["name"]][wd] += 1

            for name, cnt in item_counts[:5]:
                wd_counts = item_weekday[name]
                if not wd_counts:
                    continue
                top_wd = wd_counts.most_common(1)[0]
                wd_dots = []
                for wd_idx in range(7):
                    wc = wd_counts.get(wd_idx, 0)
                    is_active = wc > 0
                    is_best = wd_idx == top_wd[0]
                    wd_dots.append(ft.Container(
                        content=ft.Text(WEEKDAYS_JP[wd_idx][0], size=10,
                                       color=ft.Colors.WHITE if is_active else ft.Colors.GREY_400),
                        width=28, height=28,
                        bgcolor=ft.Colors.RED_400 if is_best else (ft.Colors.BLUE_300 if is_active else ft.Colors.GREY_200),
                        border_radius=14,
                        alignment=ft.Alignment.CENTER,
                    ))
                sections.append(ft.Card(
                    ft.ListTile(
                        title=ft.Text(name, weight=ft.FontWeight.W_500),
                        subtitle=ft.Row(wd_dots, spacing=4),
                        trailing=ft.Text(f"{cnt}回", size=13, color=ft.Colors.BLUE_700),
                    ),
                    margin=3,
                ))

        analysis_container.controls = sections
        analysis_progress.visible = False
        analysis_container.update()
        analysis_progress.update()

    search_dropdown = ft.Dropdown(
        ref=search_dropdown_ref,
        label="カテゴリで絞り込み",
        options=([ft.dropdown.Option("", "すべて")] + [ft.dropdown.Option(c) for c in CATEGORIES]),
        width=300,
        on_select=on_search_cat_change,
    )

    search_view = ft.Column([
        ft.Text("なくしものを探す", size=22, weight=ft.FontWeight.BOLD),
        ft.Divider(height=8),
        search_dropdown,
        ft.Row([
            ft.TextField(ref=search_ref, label="なくした物は？", hint_text="例: 財布、鍵、スマホ", expand=True),
            ft.Button("探す", on_click=on_search_click, icon=ft.Icons.SEARCH),
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
                width=300,
                read_only=True,
                on_focus=lambda _: open_date_picker(),
                suffix=ft.IconButton(ft.Icons.CALENDAR_MONTH, on_click=lambda _: open_date_picker()),
            ),
        ]),
        ft.TextField(ref=location_ref, label="見つかった場所", hint_text="例: ソファの隙間", width=300),
        ft.Button("記録する", on_click=on_add_record, icon=ft.Icons.ADD),
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

    analysis_view = ft.Column([
        analysis_progress,
        analysis_container,
    ], scroll=ft.ScrollMode.AUTO, spacing=12)

    tabs = ft.Tabs(
        selected_index=0,
        length=4,
        expand=True,
        on_change=on_tab_change,
        content=ft.Column([
            ft.TabBar(
                tabs=[
                    ft.Tab(label="探す", icon=ft.Icons.SEARCH),
                    ft.Tab(label="記録", icon=ft.Icons.ADD_CIRCLE_OUTLINE),
                    ft.Tab(label="ランキング", icon=ft.Icons.EMOJI_EVENTS),
                    ft.Tab(label="分析", icon=ft.Icons.ANALYTICS),
                ],
            ),
            ft.TabBarView(
                expand=True,
                controls=[search_view, record_view, ranking_view, analysis_view],
            ),
        ]),
    )

    page.appbar = ft.AppBar(
        title=ft.Text("なくしもの探知機", weight=ft.FontWeight.BOLD),
        bgcolor=ft.Colors.DEEP_PURPLE,
        color=ft.Colors.WHITE,
        center_title=True,
        actions=[
            ft.IconButton(ft.Icons.FILE_DOWNLOAD, icon_color=ft.Colors.WHITE,
                          tooltip="エクスポート", on_click=show_export_dialog),
            ft.IconButton(ft.Icons.FILE_UPLOAD, icon_color=ft.Colors.WHITE,
                          tooltip="インポート", on_click=show_import_dialog),
        ],
    )

    page.overlay.append(date_picker)
    page.add(ft.SafeArea(tabs))

    page.update()
    load_from_storage()
    refresh()

    page.on_load = lambda e: (load_from_storage(), refresh())


ft.run(main, view=ft.AppView.WEB_BROWSER)
