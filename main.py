from datetime import datetime
from collections import Counter
import json
import unicodedata

import flet as ft

STORAGE_KEY = "lost_items_v4"
CATEGORIES = ["財布", "鍵", "スマホ", "イヤホン", "傘", "本", "文房具", "衣類", "カバン", "その他"]


def fuzzy_match(query: str, text: str) -> bool:
    q = unicodedata.normalize("NFKC", query.strip().lower())
    t = unicodedata.normalize("NFKC", text.strip().lower())
    return bool(q) and (q in t)


def main(page: ft.Page):
    page.title = "なくしもの探知機"
    page.theme_mode = ft.ThemeMode.LIGHT
    page.padding = 20
    page.scroll = ft.ScrollMode.AUTO

    records = []
    current_tab = 0
    search_val = ""
    search_cat = ""
    results = None
    record_name = ""
    record_cat = ""
    record_date = ""
    record_loc = ""

    search_dropdown = ft.Dropdown(
        label="カテゴリで絞り込み",
        options=([ft.dropdown.Option("", "すべて")] + [ft.dropdown.Option(c) for c in CATEGORIES]),
        width=300,
    )
    search_field = ft.TextField(
        label="なくした物は？", hint_text="例: 財布、鍵、スマホ", expand=True,
    )
    chips_container = ft.Column(spacing=4)
    results_container = ft.Column(spacing=6)
    name_field = ft.TextField(
        label="なくした物", hint_text="例: 鍵、スマホ、財布", width=300,
    )
    category_dropdown = ft.Dropdown(
        label="カテゴリ",
        options=([ft.dropdown.Option("", "選択してください")] + [ft.dropdown.Option(c) for c in CATEGORIES]),
        width=300,
    )
    date_field = ft.TextField(
        label="なくした日 (任意)", hint_text="YYYY-MM-DD", width=300,
    )
    location_field = ft.TextField(
        label="見つかった場所", hint_text="例: ソファの隙間", width=300,
    )
    history_container = ft.Column(spacing=4)
    ranking_container = ft.Column(spacing=8)

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
        nonlocal search_val, results, current_tab
        search_val = name
        search_field.value = name
        results = do_search(name)
        current_tab = 0
        root_tabs.selected_index = 0
        refresh()

    def on_search_click(e):
        nonlocal results
        q = search_field.value.strip()
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
        nonlocal records, record_name, record_cat, record_date, record_loc
        name = name_field.value.strip()
        location = location_field.value.strip()
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
            "category": category_dropdown.value or "その他",
            "location": location,
            "lost_date": date_field.value.strip() or "",
            "found_date": datetime.now().strftime("%Y-%m-%d %H:%M"),
        }
        records = records + [rec]
        save()
        e.page.show_snack_bar(ft.SnackBar(content=ft.Text("記録しました"), bgcolor=ft.Colors.GREEN_400))
        name_field.value = ""
        category_dropdown.value = ""
        date_field.value = ""
        location_field.value = ""
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

    def on_tab_change(e):
        nonlocal current_tab
        current_tab = e.control.selected_index

    def refresh():
        nonlocal chips_container, results_container, history_container, ranking_container

        chips = []
        unique = list(dict.fromkeys(r["name"] for r in get_filtered()))
        for name in unique:
            chip = ft.Container(
                content=ft.Text(name, size=13),
                padding=ft.Padding(8, 4, 8, 4),
                bgcolor=ft.Colors.BLUE_50,
                border_radius=12,
                on_click=lambda e, n=name: search_from_history(n),
                ink=True,
            )
            chips.append(ft.Row([chip], tight=True))
        chips_container.controls = chips

        if results is None:
            results_container.controls = []
        elif not results:
            results_container.controls = [ft.Text("該当する記録がありません", italic=True, color=ft.Colors.GREY)]
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
                rc.append(ft.Column([
                    ft.Row([
                        ft.Row([
                            ft.Text("👑 " if is_top else "", size=14),
                            ft.Text(loc, size=15, weight=(
                                ft.FontWeight.BOLD if is_top else ft.FontWeight.NORMAL), expand=True),
                        ], spacing=0),
                        ft.Text(f"{pct:.0f}%", size=14, weight=ft.FontWeight.BOLD, color=ft.Colors.BLUE_700),
                    ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                    ft.Stack([
                        ft.Container(height=12, bgcolor=ft.Colors.GREY_200, border_radius=6),
                        ft.Container(height=12, width=f"{pct}%",
                                     bgcolor=ft.Colors.BLUE_400 if not is_top else ft.Colors.ORANGE_400,
                                     border_radius=6),
                    ]),
                    ft.Text(f"{cnt}件", size=11, color=ft.Colors.GREY_600),
                ], spacing=2))
            results_container.controls = rc

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
        history_container.update()
        ranking_container.update()

    search_dropdown.on_change = on_search_cat_change
    search_field.on_change = lambda e: setattr(search_field, 'value', e.control.value)
    name_field.on_change = lambda e: setattr(name_field, 'value', e.control.value)
    category_dropdown.on_change = lambda e: setattr(category_dropdown, 'value', e.control.value)
    date_field.on_change = lambda e: setattr(date_field, 'value', e.control.value)
    location_field.on_change = lambda e: setattr(location_field, 'value', e.control.value)

    tab_search = ft.Column([
        ft.Text("なくしものを探す", size=22, weight=ft.FontWeight.BOLD),
        ft.Divider(height=8),
        search_dropdown,
        ft.Row([search_field, ft.Button("探す", on_click=on_search_click, icon=ft.Icons.SEARCH, height=48)]),
        chips_container,
        ft.Divider(height=8),
        results_container,
    ], scroll=ft.ScrollMode.AUTO, spacing=12)

    tab_record = ft.Column([
        ft.Text("新しい記録", size=22, weight=ft.FontWeight.BOLD),
        ft.Divider(height=8),
        name_field,
        category_dropdown,
        date_field,
        location_field,
        ft.Button("記録する", on_click=on_add_record, icon=ft.Icons.ADD, height=48),
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

    tab_ranking = ft.Column([ranking_container], scroll=ft.ScrollMode.AUTO, spacing=12)

    empty_content = ft.Container(
        padding=40,
        content=ft.Column([
            ft.Text("\U0001F50D", size=64),
            ft.Text("まだ記録がありません", size=20, weight=ft.FontWeight.BOLD, color=ft.Colors.GREY_700),
            ft.Container(height=8),
            ft.Text("\U0001F4DD 使い方", size=16, weight=ft.FontWeight.W_500),
            ft.Container(height=4),
            ft.Text("① 「記録」タブでなくした物と見つかった場所を登録", size=14, color=ft.Colors.GREY_600),
            ft.Text("② 同じ物をまたなくしたら「探す」タブで検索", size=14, color=ft.Colors.GREY_600),
            ft.Text("③ 過去のデータから最もありそうな場所を予測表示", size=14, color=ft.Colors.GREY_600),
        ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=4),
    )

    root_tabs = ft.Tabs(
        selected_index=0,
        on_change=on_tab_change,
        tabs=[
            ft.Tab(
                text="探す",
                icon=ft.Icons.SEARCH,
                content=ft.Container(content=tab_search, padding=10),
            ),
            ft.Tab(
                text="記録",
                icon=ft.Icons.ADD_CIRCLE,
                content=ft.Container(content=tab_record, padding=10),
            ),
            ft.Tab(
                text="ランキング",
                icon=ft.Icons.EMOJI_EVENTS,
                content=ft.Container(content=tab_ranking, padding=10),
            ),
        ],
        expand=True,
    )

    load_from_storage()

    page.add(root_tabs)

    page.update()
    refresh()


ft.run(main, view=ft.AppView.WEB_BROWSER)
