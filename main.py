from datetime import datetime
from collections import Counter

import flet as ft

STORAGE_KEY = "lost_items_v3"


def main(page: ft.Page):
    page.title = "なくしもの探知機"
    page.theme_mode = ft.ThemeMode.LIGHT
    page.padding = 20
    page.scroll = ft.ScrollMode.AUTO

    records = []

    def load():
        try:
            raw = page.client_storage.get(STORAGE_KEY)
            if raw and isinstance(raw, list):
                return raw
        except Exception:
            pass
        return []

    def save():
        try:
            page.client_storage.set(STORAGE_KEY, records)
        except Exception:
            pass

    search_input = ft.TextField(
        label="なくした物は？",
        hint_text="例: 財布、鍵、スマホ",
        width=300,
        autofocus=True,
    )
    result_column = ft.Column(spacing=4)

    name_input = ft.TextField(
        label="なくした物",
        hint_text="例: 鍵、スマホ、財布",
        width=300,
    )
    location_input = ft.TextField(
        label="見つかった場所",
        hint_text="例: ソファの隙間",
        width=300,
    )

    def do_search(e):
        result_column.controls.clear()
        query = search_input.value.strip().lower()
        if not query:
            page.show_snack_bar(
                ft.SnackBar(content=ft.Text("なくした物を入力してください"))
            )
            page.update()
            return

        matched = [r for r in records if r["name"].strip().lower() == query]
        if not matched:
            result_column.controls.append(
                ft.Text("該当する記録がありません", italic=True, color=ft.Colors.GREY)
            )
            page.update()
            return

        total = len(matched)
        location_counts = Counter(r["location"] for r in matched).most_common()

        result_column.controls.append(
            ft.Text(f"「{search_input.value.strip()}」が見つかりそうな場所",
                    size=16, weight=ft.FontWeight.BOLD)
        )
        result_column.controls.append(
            ft.Text(f"過去 {total} 件の記録をもとに予測",
                    size=12, color=ft.Colors.GREY, italic=True)
        )
        result_column.controls.append(ft.Divider(height=8))

        max_pct = location_counts[0][1] / total * 100 if location_counts else 0

        for loc, cnt in location_counts:
            pct = cnt / total * 100
            is_top = pct == max_pct
            result_column.controls.append(
                ft.Column([
                    ft.Row([
                        ft.Row([
                            ft.Text("👑 " if is_top else "", size=14),
                            ft.Text(loc or "場所不明", size=15,
                                    weight=ft.FontWeight.BOLD if is_top else ft.FontWeight.NORMAL,
                                    expand=True),
                        ], spacing=0),
                        ft.Text(f"{pct:.0f}%", size=14,
                                weight=ft.FontWeight.BOLD,
                                color=ft.Colors.BLUE_700),
                    ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                    ft.Stack([
                        ft.Container(
                            height=12,
                            bgcolor=ft.Colors.GREY_200,
                            border_radius=6,
                        ),
                        ft.Container(
                            height=12,
                            width=f"{pct}%",
                            bgcolor=ft.Colors.BLUE_400 if not is_top else ft.Colors.ORANGE_400,
                            border_radius=6,
                        ),
                    ]),
                    ft.Text(f"{cnt}件", size=11, color=ft.Colors.GREY_600),
                ], spacing=2)
            )
        page.update()

    def delete_record(idx):
        records.pop(idx)
        save()
        refresh_history()

    def add_record(e):
        name = name_input.value.strip()
        location = location_input.value.strip()
        if not name:
            page.show_snack_bar(
                ft.SnackBar(
                    content=ft.Text("「なくした物」を入力してください"),
                    bgcolor=ft.Colors.RED_400,
                )
            )
            return
        if not location:
            page.show_snack_bar(
                ft.SnackBar(
                    content=ft.Text("「見つかった場所」を入力してください"),
                    bgcolor=ft.Colors.RED_400,
                )
            )
            return
        records.append({
            "name": name,
            "location": location,
            "date": datetime.now().strftime("%Y-%m-%d %H:%M"),
        })
        save()
        name_input.value = ""
        location_input.value = ""
        name_input.focus()
        page.show_snack_bar(
            ft.SnackBar(content=ft.Text("記録しました"), bgcolor=ft.Colors.GREEN_400)
        )
        refresh_history()

    history_list = ft.Column(spacing=4)

    def refresh_history():
        history_list.controls.clear()
        if not records:
            history_list.controls.append(
                ft.Text("まだ記録がありません", italic=True, color=ft.Colors.GREY)
            )
            page.update()
            return
        for i, r in enumerate(reversed(records)):
            idx = len(records) - 1 - i
            history_list.controls.append(
                ft.Card(
                    ft.ListTile(
                        title=ft.Text(r["name"], weight=ft.FontWeight.W_500),
                        subtitle=ft.Text(f"{r.get('location', '場所不明')}  ({r.get('date', '')})",
                                        size=13),
                        trailing=ft.IconButton(
                            ft.Icons.DELETE_OUTLINE,
                            icon_color=ft.Colors.RED_300,
                            on_click=lambda e, i=idx: delete_record(i),
                        ),
                    ),
                    margin=3,
                )
            )
        page.update()

    search_tab = ft.Column([
        ft.Text("なくしものを探す", size=22, weight=ft.FontWeight.BOLD),
        ft.Divider(height=8),
        search_input,
        ft.Button("探す", on_click=do_search, icon=ft.Icons.SEARCH, height=48),
        ft.Divider(height=16),
        result_column,
    ], scroll=ft.ScrollMode.AUTO, spacing=12)

    record_tab = ft.Column([
        ft.Text("新しい記録", size=22, weight=ft.FontWeight.BOLD),
        ft.Divider(height=8),
        name_input,
        location_input,
        ft.Button("記録する", on_click=add_record, icon=ft.Icons.ADD, height=48),
        ft.Divider(height=16),
        ft.Text("記録履歴", size=16, weight=ft.FontWeight.BOLD),
        history_list,
    ], scroll=ft.ScrollMode.AUTO, spacing=12)

    page.add(
        ft.Tabs(
            length=2,
            expand=True,
            content=ft.Column(
                expand=True,
                spacing=0,
                controls=[
                    ft.TabBar(
                        tabs=[
                            ft.Tab(label="探す", icon=ft.Icons.SEARCH),
                            ft.Tab(label="記録", icon=ft.Icons.ADD_CIRCLE),
                        ],
                    ),
                    ft.TabBarView(
                        expand=True,
                        controls=[
                            ft.Container(content=search_tab, padding=10),
                            ft.Container(content=record_tab, padding=10),
                        ],
                    ),
                ],
            ),
        )
    )

    records[:] = load()
    refresh_history()


ft.run(main, view=ft.AppView.WEB_BROWSER)
