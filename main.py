from datetime import datetime
from collections import Counter

import flet as ft

STORAGE_KEY = "lost_items_v3"


@ft.component
def App(page: ft.Page):
    records, set_records = ft.use_state([])
    search_value, set_search_value = ft.use_state("")
    name_value, set_name_value = ft.use_state("")
    location_value, set_location_value = ft.use_state("")
    search_results, set_search_results = ft.use_state(None)

    def load():
        try:
            raw = page.client_storage.get(STORAGE_KEY)
            if raw and isinstance(raw, list):
                set_records(raw)
        except Exception:
            pass

    ft.use_effect(lambda: load(), [])

    def save(recs):
        try:
            page.client_storage.set(STORAGE_KEY, recs)
        except Exception:
            pass

    def do_search(e):
        query = search_value.strip().lower()
        if not query:
            e.page.show_snack_bar(
                ft.SnackBar(content=ft.Text("なくした物を入力してください"))
            )
            set_search_results([])
            return

        matched = [r for r in records if r["name"].strip().lower() == query]
        if not matched:
            set_search_results([])
            return

        total = len(matched)
        location_counts = Counter(r["location"] for r in matched).most_common()
        max_pct = location_counts[0][1] / total * 100 if location_counts else 0

        results = []
        for loc, cnt in location_counts:
            pct = cnt / total * 100
            results.append((loc or "場所不明", cnt, pct, pct == max_pct))
        set_search_results(results)

    def add_record(e):
        name = name_value.strip()
        location = location_value.strip()
        if not name:
            e.page.show_snack_bar(
                ft.SnackBar(
                    content=ft.Text("「なくした物」を入力してください"),
                    bgcolor=ft.Colors.RED_400,
                )
            )
            return
        if not location:
            e.page.show_snack_bar(
                ft.SnackBar(
                    content=ft.Text("「見つかった場所」を入力してください"),
                    bgcolor=ft.Colors.RED_400,
                )
            )
            return

        new_record = {
            "name": name,
            "location": location,
            "date": datetime.now().strftime("%Y-%m-%d %H:%M"),
        }
        updated = records + [new_record]
        set_records(updated)
        save(updated)
        set_name_value("")
        set_location_value("")
        e.page.show_snack_bar(
            ft.SnackBar(content=ft.Text("記録しました"), bgcolor=ft.Colors.GREEN_400)
        )

    def delete_record(idx):
        updated = records.copy()
        updated.pop(idx)
        set_records(updated)
        save(updated)

    result_controls = []
    if search_results is None:
        pass
    elif len(search_results) == 0:
        result_controls.append(
            ft.Text("該当する記録がありません", italic=True, color=ft.Colors.GREY)
        )
    else:
        total = sum(cnt for _, cnt, _, _ in search_results)
        result_controls = [
            ft.Text(
                f"「{search_value.strip()}」が見つかりそうな場所",
                size=16, weight=ft.FontWeight.BOLD,
            ),
            ft.Text(
                f"過去 {total} 件の記録をもとに予測",
                size=12, color=ft.Colors.GREY, italic=True,
            ),
            ft.Divider(height=8),
        ]
        for loc, cnt, pct, is_top in search_results:
            result_controls.append(
                ft.Column([
                    ft.Row([
                        ft.Row([
                            ft.Text("👑 " if is_top else "", size=14),
                            ft.Text(loc, size=15,
                                    weight=ft.FontWeight.BOLD if is_top else ft.FontWeight.NORMAL,
                                    expand=True),
                        ], spacing=0),
                        ft.Text(f"{pct:.0f}%", size=14,
                                weight=ft.FontWeight.BOLD, color=ft.Colors.BLUE_700),
                    ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                    ft.Stack([
                        ft.Container(height=12, bgcolor=ft.Colors.GREY_200, border_radius=6),
                        ft.Container(
                            height=12, width=f"{pct}%",
                            bgcolor=ft.Colors.BLUE_400 if not is_top else ft.Colors.ORANGE_400,
                            border_radius=6,
                        ),
                    ]),
                    ft.Text(f"{cnt}件", size=11, color=ft.Colors.GREY_600),
                ], spacing=2)
            )

    history_controls = []
    if not records:
        history_controls.append(
            ft.Text("まだ記録がありません", italic=True, color=ft.Colors.GREY)
        )
    else:
        for i, r in enumerate(reversed(records)):
            idx = len(records) - 1 - i
            history_controls.append(
                ft.Card(
                    ft.ListTile(
                        title=ft.Text(r["name"], weight=ft.FontWeight.W_500),
                        subtitle=ft.Text(
                            f"{r.get('location', '場所不明')}  ({r.get('date', '')})", size=13
                        ),
                        trailing=ft.IconButton(
                            ft.Icons.DELETE_OUTLINE,
                            icon_color=ft.Colors.RED_300,
                            on_click=lambda e, i=idx: delete_record(i),
                        ),
                    ),
                    margin=3,
                )
            )

    search_tab = ft.Column([
        ft.Text("なくしものを探す", size=22, weight=ft.FontWeight.BOLD),
        ft.Divider(height=8),
        ft.TextField(
            label="なくした物は？",
            hint_text="例: 財布、鍵、スマホ",
            width=300,
            value=search_value,
            on_change=lambda e: set_search_value(e.control.value),
        ),
        ft.Button("探す", on_click=do_search, icon=ft.Icons.SEARCH, height=48),
        ft.Divider(height=16),
        *result_controls,
    ], scroll=ft.ScrollMode.AUTO, spacing=12)

    record_tab = ft.Column([
        ft.Text("新しい記録", size=22, weight=ft.FontWeight.BOLD),
        ft.Divider(height=8),
        ft.TextField(
            label="なくした物",
            hint_text="例: 鍵、スマホ、財布",
            width=300,
            value=name_value,
            on_change=lambda e: set_name_value(e.control.value),
        ),
        ft.TextField(
            label="見つかった場所",
            hint_text="例: ソファの隙間",
            width=300,
            value=location_value,
            on_change=lambda e: set_location_value(e.control.value),
        ),
        ft.Button("記録する", on_click=add_record, icon=ft.Icons.ADD, height=48),
        ft.Divider(height=16),
        ft.Text("記録履歴", size=16, weight=ft.FontWeight.BOLD),
        *history_controls,
    ], scroll=ft.ScrollMode.AUTO, spacing=12)

    return ft.Tabs(
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


def main(p: ft.Page):
    p.title = "なくしもの探知機"
    p.theme_mode = ft.ThemeMode.LIGHT
    p.padding = 20
    p.scroll = ft.ScrollMode.AUTO
    p.render(App, page=p)


ft.run(main, view=ft.AppView.WEB_BROWSER)
