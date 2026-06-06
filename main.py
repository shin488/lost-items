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


@ft.component
def App(page: ft.Page):
    records, set_records = ft.use_state([])
    selected_tab, set_selected_tab = ft.use_state(0)
    search_value, set_search_value = ft.use_state("")
    search_category, set_search_category = ft.use_state("")
    search_results, set_search_results = ft.use_state(None)
    new_name, set_new_name = ft.use_state("")
    new_category, set_new_category = ft.use_state("")
    new_lost_date, set_new_lost_date = ft.use_state("")
    new_location, set_new_location = ft.use_state("")

    def load_from_storage():
        try:
            raw = page.client_storage.get(STORAGE_KEY)
            if raw and isinstance(raw, list):
                set_records(raw)
        except Exception:
            pass

    ft.use_effect(lambda: load_from_storage(), [])

    def save(recs):
        try:
            page.client_storage.set(STORAGE_KEY, recs)
        except Exception:
            pass

    def get_filtered():
        if not search_category:
            return records
        return [r for r in records if r.get("category", "") == search_category]

    def search_items(query):
        if not query:
            return None
        matched = [r for r in get_filtered()
                   if fuzzy_match(query, r["name"])]
        if not matched:
            return []
        total = len(matched)
        location_counts = Counter(r["location"] for r in matched).most_common()
        max_pct = location_counts[0][1] / total * 100 if location_counts else 0
        return [(loc or "場所不明", cnt,
                 cnt / total * 100, cnt / total * 100 == max_pct)
                for loc, cnt in location_counts]

    def do_search(e):
        query = search_value.strip()
        if not query:
            e.page.show_snack_bar(
                ft.SnackBar(content=ft.Text("なくした物を入力してください")))
            set_search_results([])
            return
        set_search_results(search_items(query))

    def search_from_history(name):
        set_search_value(name)
        set_selected_tab(0)
        set_search_results(search_items(name))

    def add_record(e):
        name = new_name.strip()
        location = new_location.strip()
        if not name:
            e.page.show_snack_bar(ft.SnackBar(
                content=ft.Text("「なくした物」を入力してください"),
                bgcolor=ft.Colors.RED_400))
            return
        if not location:
            e.page.show_snack_bar(ft.SnackBar(
                content=ft.Text("「見つかった場所」を入力してください"),
                bgcolor=ft.Colors.RED_400))
            return
        rec = {
            "name": name,
            "category": new_category or "その他",
            "location": location,
            "lost_date": new_lost_date.strip() or "",
            "found_date": datetime.now().strftime("%Y-%m-%d %H:%M"),
        }
        updated = records + [rec]
        set_records(updated)
        save(updated)
        set_new_name("")
        set_new_category("")
        set_new_lost_date("")
        set_new_location("")
        e.page.show_snack_bar(ft.SnackBar(
            content=ft.Text("記録しました"), bgcolor=ft.Colors.GREEN_400))

    def delete_record(idx):
        updated = records.copy()
        updated.pop(idx)
        set_records(updated)
        save(updated)

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
            try:
                data = json.loads(text_field.value)
                if not isinstance(data, list):
                    raise ValueError("リスト形式のJSONが必要です")
                for item in data:
                    if not isinstance(item, dict) or "name" not in item:
                        raise ValueError("各アイテムに name フィールドが必要です")
                set_records(data)
                save(data)
                dlg.open = False
                dlg.update()
                ev.page.show_snack_bar(ft.SnackBar(
                    content=ft.Text(f"{len(data)}件のデータをインポートしました"),
                    bgcolor=ft.Colors.GREEN_400))
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

    def build_search_results():
        if search_results is None:
            return []
        if not search_results:
            return [ft.Text("該当する記録がありません", italic=True, color=ft.Colors.GREY)]
        total = sum(cnt for _, cnt, _, _ in search_results)
        controls = [
            ft.Text(f"「{search_value.strip()}」が見つかりそうな場所",
                    size=16, weight=ft.FontWeight.BOLD),
            ft.Text(f"過去 {total} 件の記録をもとに予測",
                    size=12, color=ft.Colors.GREY, italic=True),
            ft.Divider(height=8),
        ]
        for loc, cnt, pct, is_top in search_results:
            controls.append(ft.Column([
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
        return controls

    def build_chips():
        unique = list(dict.fromkeys(r["name"] for r in get_filtered()))
        return [
            ft.Container(
                content=ft.Text(name, size=13),
                padding=ft.Padding(8, 4, 8, 4),
                bgcolor=ft.Colors.BLUE_50,
                border_radius=12,
                on_click=lambda e, n=name: search_from_history(n),
                ink=True,
            )
            for name in unique
        ]

    def build_history():
        if not records:
            return [ft.Text("まだ記録がありません", italic=True, color=ft.Colors.GREY)]
        controls = []
        for i, r in enumerate(reversed(records)):
            idx = len(records) - 1 - i
            cat = r.get("category", "")
            lost = r.get("lost_date", "")
            loc = r.get("location", "場所不明")
            fd = r.get("found_date", "")
            subtitle = f"{loc}  ({fd})"
            if cat:
                subtitle = f"[{cat}] {subtitle}"
            controls.append(
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
                                on_click=lambda e, i=idx: delete_record(i),
                            ),
                        ], spacing=0),
                    ),
                    margin=3,
                )
            )
        return controls

    def build_ranking():
        if not records:
            return [ft.Text("まだデータがありません", italic=True, color=ft.Colors.GREY)]
        name_counts = Counter(r["name"] for r in records).most_common()
        total = len(records)
        controls = [
            ft.Text("よくなくした物ランキング", size=18, weight=ft.FontWeight.BOLD),
            ft.Text(f"全 {total} 件の記録", size=12, color=ft.Colors.GREY, italic=True),
            ft.Divider(height=8),
        ]
        medals = {1: "\U0001F947", 2: "\U0001F948", 3: "\U0001F949"}
        for rank, (name, cnt) in enumerate(name_counts, 1):
            medal = medals.get(rank, f"  #{rank} ")
            pct = cnt / total * 100
            controls.append(
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
        return controls

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

    chips = build_chips()
    search_results_controls = build_search_results()
    history_controls = build_history()
    ranking_controls = build_ranking()

    tab_search = ft.Column([
        ft.Text("なくしものを探す", size=22, weight=ft.FontWeight.BOLD),
        ft.Divider(height=8),
        ft.Dropdown(
            label="カテゴリで絞り込み",
            value=search_category,
            options=([ft.dropdown.Option("", "すべて")] + [ft.dropdown.Option(c) for c in CATEGORIES]),
            on_change=lambda e: (set_search_category(e.control.value), set_search_results(None)),
            width=300,
        ),
        ft.Row([
            ft.TextField(
                label="なくした物は？", hint_text="例: 財布、鍵、スマホ",
                value=search_value,
                on_change=lambda e: set_search_value(e.control.value),
                expand=True,
            ),
            ft.Button("探す", on_click=do_search, icon=ft.Icons.SEARCH, height=48),
        ]),
        ft.Column([ft.Row([c], tight=True) for c in chips], spacing=4) if chips else ft.Container(),
        ft.Divider(height=8),
        *search_results_controls,
    ], scroll=ft.ScrollMode.AUTO, spacing=12)

    tab_record = ft.Column([
        ft.Text("新しい記録", size=22, weight=ft.FontWeight.BOLD),
        ft.Divider(height=8),
        ft.TextField(
            label="なくした物", hint_text="例: 鍵、スマホ、財布",
            width=300, value=new_name,
            on_change=lambda e: set_new_name(e.control.value),
        ),
        ft.Dropdown(
            label="カテゴリ", value=new_category,
            options=([ft.dropdown.Option("", "選択してください")] + [ft.dropdown.Option(c) for c in CATEGORIES]),
            on_change=lambda e: set_new_category(e.control.value),
            width=300,
        ),
        ft.TextField(
            label="なくした日 (任意)", hint_text="YYYY-MM-DD",
            width=300, value=new_lost_date,
            on_change=lambda e: set_new_lost_date(e.control.value),
        ),
        ft.TextField(
            label="見つかった場所", hint_text="例: ソファの隙間",
            width=300, value=new_location,
            on_change=lambda e: set_new_location(e.control.value),
        ),
        ft.Button("記録する", on_click=add_record, icon=ft.Icons.ADD, height=48),
        ft.Divider(height=16),
        ft.Row([
            ft.Text("記録履歴", size=16, weight=ft.FontWeight.BOLD),
            ft.Row([
                ft.TextButton("エクスポート", on_click=show_export_dialog),
                ft.TextButton("インポート", on_click=show_import_dialog),
            ]),
        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
        *history_controls,
    ], scroll=ft.ScrollMode.AUTO, spacing=12)

    tab_ranking = ft.Column(ranking_controls, scroll=ft.ScrollMode.AUTO, spacing=12)

    body = (empty_content if not records else
            ft.Tabs(
                selected_index=selected_tab,
                on_change=lambda e: set_selected_tab(e.control.selected_index),
                length=3,
                expand=True,
                content=ft.Column(
                    expand=True,
                    spacing=0,
                    controls=[
                        ft.TabBar(
                            tabs=[
                                ft.Tab(label="探す", icon=ft.Icons.SEARCH),
                                ft.Tab(label="記録", icon=ft.Icons.ADD_CIRCLE),
                                ft.Tab(label="ランキング", icon=ft.Icons.EMOJI_EVENTS),
                            ],
                        ),
                        ft.TabBarView(
                            expand=True,
                            controls=[
                                ft.Container(content=tab_search, padding=10),
                                ft.Container(content=tab_record, padding=10),
                                ft.Container(content=tab_ranking, padding=10),
                            ],
                        ),
                    ],
                ),
            ))

    return ft.Column([body], expand=True)


def main(p: ft.Page):
    p.title = "なくしもの探知機"
    p.theme_mode = ft.ThemeMode.LIGHT
    p.padding = 20
    p.scroll = ft.ScrollMode.AUTO
    p.render(App, page=p)


ft.run(main, view=ft.AppView.WEB_BROWSER)
