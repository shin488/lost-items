from datetime import datetime
from collections import Counter, defaultdict
import json
import unicodedata
import calendar

import flet as ft

STORAGE_KEY = "lost_items_v4"
CATEGORIES = ["財布", "鍵", "スマホ", "イヤホン", "傘", "本", "文房具", "衣類", "カバン", "その他"]
WEEKDAYS_JP = ["月曜", "火曜", "水曜", "木曜", "金曜", "土曜", "日曜"]


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
            primary=ft.Colors.GREEN_800,
            primary_container=ft.Colors.GREEN_100,
            secondary=ft.Colors.BROWN_700,
            secondary_container=ft.Colors.ORANGE_50,
            surface=ft.Colors.GREEN_50,
            surface_container=ft.Colors.AMBER_50,
        ),
        use_material3=True,
    )
    page.bgcolor = ft.Colors.GREEN_50

    page.scroll = ft.ScrollMode.AUTO
    page.theme_mode = ft.ThemeMode.LIGHT
    page.window.title_bar_buttons_hidden = True
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
    analysis_progress = ft.ProgressBar(visible=False, color=ft.Colors.GREEN_600)

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
        tabs.update()
        refresh()

    def on_tab_change(e):
        idx = int(e.data)
        if idx == 3:
            refresh_analysis()

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

    def mark_resolved(idx):
        nonlocal records
        records[idx]["resolved"] = True
        records[idx]["resolution_date"] = datetime.now().strftime("%Y-%m-%d %H:%M")
        save()
        page.show_snack_bar(ft.SnackBar(
            content=ft.Text(f"「{records[idx]['name']}」を見つかりました！"), bgcolor=ft.Colors.GREEN_400))
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
        outer = ft.Container(height=12, bgcolor=ft.Colors.GREEN_100, border_radius=6)
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
                bgcolor=ft.Colors.GREEN_100,
                border_radius=12,
                on_click=lambda e, n=name: search_from_history(n),
                ink=True,
            )
            chips.append(ft.Row([chip], tight=True))
        chips_container.controls = chips

        if results is None:
            results_container.controls = [
                ft.Container(
                    ft.Column([
                        ft.Text("🔍", size=40),
                        ft.Text("アイテムを入力して「探す」を押してください", color=ft.Colors.GREEN_700),
                        ft.Text("焦らず、ゆっくり思い出しましょう", size=12, color=ft.Colors.GREY_500, italic=True),
                    ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=4),
                    padding=20, alignment=ft.Alignment.CENTER,
                ),
            ]
            simulation_container.controls = []
        elif not results:
            results_container.controls = [
                ft.Container(
                    ft.Column([
                        ft.Text("🌿", size=40),
                        ft.Text("該当する記録がありません", color=ft.Colors.GREEN_700),
                        ft.Text("別のキーワードで試してみましょう", size=12, color=ft.Colors.GREY_500, italic=True),
                    ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=4),
                    padding=20, alignment=ft.Alignment.CENTER,
                ),
            ]
            simulation_container.controls = []
        else:
            total = sum(cnt for _, cnt, _, _ in results)
            name = search_val.strip()
            rc = [
                ft.Text(f"🔎 「{name}」が見つかりそうな場所",
                        size=17, weight=ft.FontWeight.BOLD, color=ft.Colors.GREEN_800),
                ft.Text(f"🌿 過去 {total} 件の記録から予測",
                        size=12, color=ft.Colors.GREY_600),
                ft.Divider(height=4, color=ft.Colors.GREEN_200),
            ]
            for loc, cnt, pct, is_top in results:
                color = ft.Colors.GREEN_700 if is_top else ft.Colors.GREEN_600
                card = ft.Container(
                    content=ft.Column([
                        ft.Row([
                            ft.Text(loc, size=14, weight=(
                                ft.FontWeight.BOLD if is_top else ft.FontWeight.W_500), expand=True),
                            ft.Text(f"{pct:.0f}%", size=15, weight=ft.FontWeight.BOLD, color=color),
                        ]),
                        make_bar(pct, ft.Colors.GREEN_400 if is_top else ft.Colors.GREEN_200),
                        ft.Text(f"{cnt}件", size=11, color=ft.Colors.GREY_600),
                    ], spacing=3),
                    padding=10,
                    bgcolor=ft.Colors.GREEN_50 if is_top else ft.Colors.WHITE,
                    border=ft.border.all(1, ft.Colors.GREEN_300 if is_top else ft.Colors.GREEN_100),
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
                    ft.Divider(height=16, color=ft.Colors.GREEN_200),
                    ft.Text("⏰ もしもシミュレーター", size=16, weight=ft.FontWeight.BOLD, color=ft.Colors.GREEN_800),
                    ft.Text(f"🌱 今は{wd_name}曜日 {now.hour}時台のデータから予測",
                            size=12, color=ft.Colors.GREY_600),
                    ft.Divider(height=4),
                ]
                for loc, sc, pct, is_top in sim_results:
                    color = ft.Colors.BROWN_700 if is_top else ft.Colors.GREEN_600
                    card = ft.Container(
                        content=ft.Column([
                            ft.Row([
                                ft.Text(loc, size=14, weight=(
                                    ft.FontWeight.BOLD if is_top else ft.FontWeight.W_500), expand=True),
                                ft.Text(f"{pct:.0f}%", size=14, weight=ft.FontWeight.BOLD, color=color),
                            ]),
                            make_bar(pct, ft.Colors.BROWN_300 if is_top else ft.Colors.GREEN_200),
                        ], spacing=3),
                        padding=10,
                        bgcolor=ft.Colors.ORANGE_50 if is_top else ft.Colors.WHITE,
                        border=ft.border.all(1, ft.Colors.BROWN_200 if is_top else ft.Colors.GREEN_100),
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
                        ft.Text("📝", size=40),
                        ft.Text("まだ記録がありません", color=ft.Colors.GREEN_700),
                        ft.Text("「記録」タブからなくし物を追加してみましょう", size=12, color=ft.Colors.GREY_500, italic=True),
                    ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=4),
                    padding=20, alignment=ft.Alignment.CENTER,
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
                    subtitle += "  ✅ 解決済み"
                trailing_btns = [
                    ft.IconButton(
                        ft.Icons.SEARCH, icon_color=ft.Colors.BLUE_300,
                        tooltip="このアイテムを探す",
                        on_click=lambda e, n=r["name"]: search_from_history(n),
                    ),
                ]
                if not resolved:
                    trailing_btns.insert(0, ft.IconButton(
                        ft.Icons.CHECK_CIRCLE_OUTLINE, icon_color=ft.Colors.GREEN_400,
                        tooltip="見つかった！",
                        on_click=lambda e, i=idx: mark_resolved(i),
                    ))
                trailing_btns.append(ft.IconButton(
                    ft.Icons.DELETE_OUTLINE, icon_color=ft.Colors.RED_300,
                    tooltip="削除",
                    on_click=lambda e, i=idx: delete_record(i),
                ))
                hc.append(
                    ft.Card(
                        ft.ListTile(
                            title=ft.Text(r["name"], weight=ft.FontWeight.W_500),
                            subtitle=ft.Text(subtitle, size=13),
                            trailing=ft.Row(trailing_btns, spacing=0),
                        ),
                        margin=3, elevation=2,
                    )
                )
            history_container.controls = hc

        if not records:
            ranking_container.controls = [
                ft.Container(
                    ft.Column([
                        ft.Text("🏆", size=40),
                        ft.Text("まだデータがありません", color=ft.Colors.GREEN_700),
                        ft.Text("記録が増えるとランキングが表示されます", size=12, color=ft.Colors.GREY_500, italic=True),
                    ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=4),
                    padding=20, alignment=ft.Alignment.CENTER,
                ),
            ]
        else:
            name_counts = Counter(r["name"] for r in records).most_common()
            total = len(records)
            rc = [
                ft.Container(
                    ft.Column([
                        ft.Text("🏆 よくなくした物ランキング", size=18, weight=ft.FontWeight.BOLD, color=ft.Colors.GREEN_800),
                        ft.Text(f"全 {total} 件の記録", size=12, color=ft.Colors.GREY_600, italic=True),
                    ], spacing=0),
                    padding=ft.padding.only(bottom=4),
                ),
                ft.Divider(height=8, color=ft.Colors.GREEN_200),
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
                        margin=3, elevation=2,
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
            advice_lines.append(f"💡 {peak_wd_name}は特に注意！この曜日によくなくしています")
        if top_cat != "—":
            advice_lines.append(f"💡 「{top_cat}」カテゴリの管理を見直してみましょう")
        if repeat_items:
            top_repeat = repeat_items[0]
            advice_lines.append(f"💡 「{top_repeat[0]}」は{top_repeat[1]}回もなくしています！定位置を決めてみては？")
        if resolution_rate > 50:
            advice_lines.append(f"✅ 解決率 {resolution_rate:.0f}%！なくしても見つけるのが上手です")
        else:
            advice_lines.append(f"🔍 解決率 {resolution_rate:.0f}%…なくしたらすぐに探す習慣を")
        if avg_hours is not None:
            if avg_hours < 24:
                advice_lines.append(f"⚡ 平均 {avg_hours:.0f}時間で見つけています！素早い！")
            elif avg_hours < 72:
                advice_lines.append(f"⏳ 平均 {avg_hours:.0f}時間で発見。1〜2日以内には見つかります")
            else:
                days = avg_hours / 24
                advice_lines.append(f"🐢 平均 {days:.1f}日かかっています。見つけたらすぐ記録しましょう")

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
        lines.append(f"✅ 解決率: {resolution_rate:.0f}% ({resolved_cnt}/{total})")

        title = f"{focus_icon} あなたは「{focus_type}」"
        lines.append("")
        lines.append("🌲 なくしても焦らずに — きっと見つかります")
        return [title] + lines + [""] + advice_lines

    def refresh_analysis():
        analysis_progress.visible = True
        analysis_progress.update()

        if not records:
            analysis_container.controls = [
                ft.Container(
                    ft.Column([
                        ft.Text("📊", size=40),
                        ft.Text("まだデータがありません", color=ft.Colors.GREEN_700),
                        ft.Text("記録が増えると分析が表示されます", size=12, color=ft.Colors.GREY_500, italic=True),
                    ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=4),
                    padding=20, alignment=ft.Alignment.CENTER,
                ),
            ]
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
                ] + [ft.Text(l, size=13, color=ft.Colors.GREY_700) for l in diagnosis_lines[1:]],
                    spacing=2,
                ),
                padding=12, border_radius=8, bgcolor=ft.Colors.GREEN_50, border=ft.border.all(1, ft.Colors.GREEN_200),
            ))
            sections.append(ft.Divider(height=12, color=ft.Colors.GREEN_200))

        sections.append(ft.Text("📊 全体統計", size=18, weight=ft.FontWeight.BOLD, color=ft.Colors.GREEN_800))
        sections.append(ft.Divider(height=8))
        row1 = ft.Row([
            ft.Container(
                ft.Column([
                    ft.Text("総記録数", size=11, color=ft.Colors.GREY_600),
                    ft.Text(str(total), size=22, weight=ft.FontWeight.BOLD, color=ft.Colors.GREEN_800),
                ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=1),
                padding=10, border_radius=8,
                bgcolor=ft.Colors.GREEN_50, expand=True, border=ft.border.all(1, ft.Colors.GREEN_200),
            ),
            ft.Container(
                ft.Column([
                    ft.Text("なくした物", size=11, color=ft.Colors.GREY_600),
                    ft.Text(str(unique_items), size=22, weight=ft.FontWeight.BOLD, color=ft.Colors.BROWN_700),
                ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=1),
                padding=10, border_radius=8,
                bgcolor=ft.Colors.ORANGE_50, expand=True, border=ft.border.all(1, ft.Colors.BROWN_200),
            ),
            ft.Container(
                ft.Column([
                    ft.Text("最多なくし物", size=11, color=ft.Colors.GREY_600),
                    ft.Text(top_item[0], size=14, weight=ft.FontWeight.BOLD, color=ft.Colors.GREEN_800),
                    ft.Text(f"{top_item[1]}回", size=11, color=ft.Colors.GREY_600),
                ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=1),
                padding=10, border_radius=8,
                bgcolor=ft.Colors.GREEN_50, expand=True, border=ft.border.all(1, ft.Colors.GREEN_200),
            ),
            ft.Container(
                ft.Column([
                    ft.Text("最多発見場所", size=11, color=ft.Colors.GREY_600),
                    ft.Text(top_loc[0], size=14, weight=ft.FontWeight.BOLD, color=ft.Colors.BROWN_700),
                    ft.Text(f"{top_loc[1]}回", size=11, color=ft.Colors.GREY_600),
                ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=1),
                padding=10, border_radius=8,
                bgcolor=ft.Colors.ORANGE_50, expand=True, border=ft.border.all(1, ft.Colors.BROWN_200),
            ),
        ], spacing=6)
        sections.append(row1)

        if has_weekday:
            sections.append(ft.Divider(height=16, color=ft.Colors.GREEN_200))
            sections.append(ft.Text("📅 なくしやすい曜日", size=18, weight=ft.FontWeight.BOLD, color=ft.Colors.GREEN_800))
            sections.append(ft.Divider(height=8))

            for wd_idx in range(7):
                cnt = weekday_total.get(wd_idx, 0)
                pct = cnt / total * 100
                is_top_wd = wd_idx == best_wd
                color = ft.Colors.GREEN_700 if is_top_wd else ft.Colors.GREEN_300
                items_on_day = weekday_item[wd_idx].most_common(3)
                items_str = "  ".join(f"{n}({c})" for n, c in items_on_day) if items_on_day else "—"
                sections.append(ft.Column([
                    ft.Row([
                        ft.Text(f"{WEEKDAYS_JP[wd_idx]}", size=14, weight=(
                            ft.FontWeight.BOLD if is_top_wd else ft.FontWeight.NORMAL), expand=True),
                        ft.Text(f"{cnt}回", size=12, weight=ft.FontWeight.BOLD),
                    ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                    make_bar(pct, color),
                    ft.Container(
                        ft.Text(items_str, size=11, color=ft.Colors.GREY_600, italic=True),
                        padding=ft.padding.only(left=4),
                    ),
                ], spacing=2))

        sections.append(ft.Divider(height=16, color=ft.Colors.GREEN_200))
        sections.append(ft.Text("📍 アイテム × 場所 の相関", size=18, weight=ft.FontWeight.BOLD, color=ft.Colors.GREEN_800))
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
                    bgcolor=ft.Colors.GREEN_100,
                    border_radius=8,
                ))
            sections.append(ft.Card(
                ft.ListTile(
                    title=ft.Text(name, weight=ft.FontWeight.W_500),
                    subtitle=ft.Row(loc_chips, wrap=True, spacing=4) if loc_chips else ft.Text("データなし", size=12, color=ft.Colors.GREY),
                    trailing=ft.Text(f"{cnt}回", size=13, color=ft.Colors.BLUE_700),
                ),
                margin=3, elevation=2,
            ))

        if has_weekday:
            sections.append(ft.Divider(height=16, color=ft.Colors.GREEN_200))
            sections.append(ft.Text("🗓️ アイテム × 曜日 の相関", size=18, weight=ft.FontWeight.BOLD, color=ft.Colors.GREEN_800))
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
                        bgcolor=ft.Colors.GREEN_700 if is_best else (ft.Colors.GREEN_300 if is_active else ft.Colors.GREY_200),
                        border_radius=14,
                        alignment=ft.Alignment.CENTER,
                    ))
                sections.append(ft.Card(
                    ft.ListTile(
                        title=ft.Text(name, weight=ft.FontWeight.W_500),
                        subtitle=ft.Row(wd_dots, spacing=4),
                        trailing=ft.Text(f"{cnt}回", size=13, color=ft.Colors.BLUE_700),
                    ),
                    margin=3, elevation=2,
                ))

        sections.append(ft.Divider(height=16, color=ft.Colors.GREEN_200))
        sections.append(ft.Text("📅 なくし物カレンダー", size=18, weight=ft.FontWeight.BOLD, color=ft.Colors.GREEN_800))
        sections.append(ft.Text("日付をタップでその日の記録を表示", size=12, color=ft.Colors.GREY, italic=True))
        sections.append(ft.Divider(height=8))

        lost_by_date = defaultdict(list)
        for r in records:
            d = r.get("lost_date", "") or r.get("found_date", "")[:10]
            if d:
                lost_by_date[d].append(r)

        if lost_by_date:
            all_dates = [datetime.strptime(d, "%Y-%m-%d") for d in lost_by_date if d]
            min_d = min(all_dates)
            max_d = max(all_dates)
        else:
            min_d = datetime.now()
            max_d = datetime.now()

        cal_year = getattr(refresh_analysis, "cal_year", max_d.year)
        cal_month = getattr(refresh_analysis, "cal_month", max_d.month)

        cal_header = ft.Row([
            ft.IconButton(ft.Icons.NAVIGATE_BEFORE, tooltip="前の月",
                          on_click=lambda e: _navigate_cal(-1)),
            ft.Text(f"{cal_year}年 {cal_month}月", size=16, weight=ft.FontWeight.BOLD, expand=True, text_align=ft.TextAlign.CENTER),
            ft.IconButton(ft.Icons.NAVIGATE_NEXT, tooltip="次の月",
                          on_click=lambda e: _navigate_cal(1)),
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
                    bg = ft.Colors.GREEN_100 if is_today else (ft.Colors.GREEN_50 if cnt > 0 else ft.Colors.GREY_100)
                    border = ft.border.all(2, ft.Colors.GREEN_600) if is_today else None
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

        sections.append(ft.Divider(height=16, color=ft.Colors.GREEN_200))
        sections.append(ft.Text("✅ 解決状況分析", size=18, weight=ft.FontWeight.BOLD, color=ft.Colors.GREEN_800))
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
                    ft.Text(str(resolved_total), size=22, weight=ft.FontWeight.BOLD, color=ft.Colors.GREEN_700),
                ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=1),
                padding=10, border_radius=8,
                bgcolor=ft.Colors.GREEN_50, expand=True, border=ft.border.all(1, ft.Colors.GREEN_200),
            ),
            ft.Container(
                ft.Column([
                    ft.Text("未解決", size=11, color=ft.Colors.GREY_600),
                    ft.Text(str(unresolved_total), size=22, weight=ft.FontWeight.BOLD, color=ft.Colors.BROWN_700),
                ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=1),
                padding=10, border_radius=8,
                bgcolor=ft.Colors.ORANGE_50, expand=True, border=ft.border.all(1, ft.Colors.BROWN_200),
            ),
            ft.Container(
                ft.Column([
                    ft.Text("解決率", size=11, color=ft.Colors.GREY_600),
                    ft.Text(f"{resolved_pct:.0f}%", size=22, weight=ft.FontWeight.BOLD, color=ft.Colors.GREEN_800),
                ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=1),
                padding=10, border_radius=8,
                bgcolor=ft.Colors.GREEN_50, expand=True, border=ft.border.all(1, ft.Colors.GREEN_200),
            ),
        ], spacing=6))
        sections.append(make_bar(resolved_pct, ft.Colors.GREEN_600))
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
            sections.append(ft.Text("⏱️ 発見までの時間", size=15, weight=ft.FontWeight.BOLD, color=ft.Colors.GREEN_800))
            time_row = ft.Row([
                ft.Container(
                    ft.Column([
                        ft.Text("最短", size=10, color=ft.Colors.GREY_600),
                        ft.Text(f"{min_h/24:.1f}日" if min_h >= 24 else f"{min_h:.0f}時間",
                                size=14, weight=ft.FontWeight.BOLD, color=ft.Colors.GREEN_700),
                    ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=0),
                    padding=8, border_radius=8, bgcolor=ft.Colors.GREEN_50, expand=True,
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
            sections.append(ft.Text("📊 発見時間の分布", size=14, weight=ft.FontWeight.BOLD, color=ft.Colors.GREEN_800))
            for label, cnt in bucket.most_common():
                pct = cnt / len(time_diffs) * 100
                sections.append(ft.Column([
                    ft.Row([
                        ft.Text(label, size=12, expand=True),
                        ft.Text(f"{cnt}件", size=11, color=ft.Colors.GREY_600),
                    ]),
                    make_bar(pct, ft.Colors.GREEN_300),
                ], spacing=1))

        analysis_container.controls = sections
        analysis_progress.visible = False
        analysis_container.update()
        analysis_progress.update()

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
        ft.Container(
            ft.Column([
                ft.Text("🍃 焦らず、ゆっくり思い出しましょう", size=13, color=ft.Colors.GREEN_700, italic=True),
                ft.Text("なくしものを探す", size=22, weight=ft.FontWeight.BOLD),
            ], spacing=0),
            padding=ft.padding.only(bottom=4),
        ),
        ft.Divider(height=8, color=ft.Colors.GREEN_200),
        search_dropdown,
        ft.Row([
            ft.TextField(ref=search_ref, label="なくした物は？", hint_text="例: 財布、鍵、スマホ", expand=True),
            ft.Button("探す", on_click=on_search_click, icon=ft.Icons.SEARCH),
        ]),
        chips_container,
        ft.Divider(height=8, color=ft.Colors.GREEN_200),
        results_container,
        ft.Divider(height=8, color=ft.Colors.GREEN_200),
        simulation_container,
    ], scroll=ft.ScrollMode.AUTO, spacing=12, bgcolor=ft.Colors.GREEN_50)

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
        ft.Container(
            ft.Column([
                ft.Text("🌱 見つけたらすぐに記録しましょう", size=13, color=ft.Colors.GREEN_700, italic=True),
                ft.Text("新しい記録", size=22, weight=ft.FontWeight.BOLD),
            ], spacing=0),
            padding=ft.padding.only(bottom=4),
        ),
        ft.Divider(height=8, color=ft.Colors.GREEN_200),
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
                suffix=ft.IconButton(ft.Icons.CALENDAR_MONTH, on_click=lambda _: open_date_picker()),
            ),
        ]),
        ft.TextField(ref=location_ref, label="見つかった場所", hint_text="例: ソファの隙間", width=300),
        ft.Button("🌿 記録する", on_click=on_add_record, icon=ft.Icons.ADD),
        ft.Divider(height=16, color=ft.Colors.GREEN_200),
        ft.Row([
            ft.Text("📝 記録履歴", size=16, weight=ft.FontWeight.BOLD, color=ft.Colors.GREEN_800),
            ft.Row([
                ft.TextButton("エクスポート", on_click=show_export_dialog),
                ft.TextButton("インポート", on_click=show_import_dialog),
            ]),
        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
        history_container,
    ], scroll=ft.ScrollMode.AUTO, spacing=12, bgcolor=ft.Colors.GREEN_50)

    ranking_view = ft.Column([ranking_container], scroll=ft.ScrollMode.AUTO, spacing=12, bgcolor=ft.Colors.GREEN_50)

    analysis_view = ft.Column([
        analysis_progress,
        analysis_container,
    ], scroll=ft.ScrollMode.AUTO, spacing=12, bgcolor=ft.Colors.GREEN_50)

    tabs = ft.Tabs(
        selected_index=0,
        length=4,
        expand=True,
        on_change=on_tab_change,
        content=ft.Column([
            ft.TabBar(
                bgcolor=ft.Colors.GREEN_50,
                indicator_color=ft.Colors.GREEN_700,
                label_color=ft.Colors.GREEN_800,
                unselected_label_color=ft.Colors.GREY_600,
                tabs=[
                    ft.Tab(label="探す", icon=ft.Icons.SEARCH),
                    ft.Tab(label="記録", icon=ft.Icons.ADD_CIRCLE_OUTLINE),
                    ft.Tab(label="ランキング", icon=ft.Icons.EMOJI_EVENTS),
                    ft.Tab(label="分析", icon=ft.Icons.ANALYTICS),
                ],
            ),
            ft.TabBarView(
                expand=True,
                bgcolor=ft.Colors.GREEN_50,
                controls=[search_view, record_view, ranking_view, analysis_view],
            ),
        ]),
    )

    page.appbar = ft.AppBar(
        title=ft.Row([
            ft.Text("🌲 ", size=22),
            ft.Text("なくしもの探知機", weight=ft.FontWeight.BOLD),
        ], tight=True),
        bgcolor=ft.Colors.GREEN_900,
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
    page.add(ft.Container(ft.SafeArea(tabs), bgcolor=ft.Colors.GREEN_50, expand=True))

    page.update()
    load_from_storage()
    refresh()

    page.on_load = lambda e: (load_from_storage(), refresh())


ft.run(main, view=ft.AppView.WEB_BROWSER)
