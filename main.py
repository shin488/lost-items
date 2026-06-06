import json
from datetime import datetime
from collections import Counter

import flet as ft

STORAGE_KEY = "lost_items_v2"


def main(page: ft.Page):
    page.title = "なくしもの記録"
    page.theme_mode = ft.ThemeMode.LIGHT
    page.padding = 20
    page.scroll = ft.ScrollMode.AUTO

    records = []

    name_input = ft.TextField(
        label="なくした物",
        hint_text="例: 鍵、スマホ、財布",
        width=300,
        autofocus=True,
    )
    location_input = ft.TextField(
        label="見つかった場所",
        hint_text="例: ソファの隙間",
        width=300,
    )

    ranking_list = ft.Column(spacing=4)
    history_list = ft.Column(spacing=4)
    empty_ranking = ft.Text("まだ記録がありません", italic=True, color=ft.Colors.GREY)
    empty_history = ft.Text("まだ記録がありません", italic=True, color=ft.Colors.GREY)

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

    def refresh():
        ranking_list.controls.clear()
        history_list.controls.clear()

        counts = Counter(r["name"] for r in records).most_common()
        if counts:
            for rank, (name, cnt) in enumerate(counts, 1):
                medal = {1: "🥇", 2: "🥈", 3: "🥉"}.get(rank, f"#{rank}")
                badge = ft.Container(
                    ft.Text(f"{cnt}回", weight=ft.FontWeight.BOLD, size=13),
                    padding=ft.padding.symmetric(horizontal=12, vertical=4),
                    bgcolor=ft.Colors.RED_50 if cnt >= 3 else ft.Colors.GREY_200,
                    border_radius=12,
                )
                ranking_list.controls.append(
                    ft.ListTile(
                        leading=ft.Text(medal, size=20),
                        title=ft.Text(name, size=16, weight=ft.FontWeight.W_500),
                        trailing=badge,
                    )
                )
        else:
            ranking_list.controls.append(empty_ranking)

        for i, r in enumerate(reversed(records)):
            idx = len(records) - 1 - i
            date_str = r.get("date", "")
            subtitle_parts = [r.get("location", "場所不明")]
            if date_str:
                subtitle_parts.append(f"({date_str})")
            history_list.controls.append(
                ft.Card(
                    ft.ListTile(
                        title=ft.Text(r["name"], weight=ft.FontWeight.W_500),
                        subtitle=ft.Text(" / ".join(subtitle_parts), size=13),
                        trailing=ft.IconButton(
                            ft.Icons.DELETE_OUTLINE,
                            icon_color=ft.Colors.RED_300,
                            on_click=lambda e, i=idx: delete_item(i),
                        ),
                    ),
                    margin=3,
                )
            )
        if not records:
            history_list.controls.append(empty_history)
        page.update()

    def delete_item(idx):
        records.pop(idx)
        save()
        refresh()

    def add_record(e):
        name = name_input.value.strip()
        if not name:
            page.show_snack_bar(
                ft.SnackBar(
                    content=ft.Text("「なくした物」を入力してください"),
                    bgcolor=ft.Colors.RED_400,
                )
            )
            return
        records.append({
            "name": name,
            "location": location_input.value.strip(),
            "date": datetime.now().strftime("%Y-%m-%d %H:%M"),
        })
        save()
        name_input.value = ""
        location_input.value = ""
        name_input.focus()
        page.show_snack_bar(
            ft.SnackBar(
                content=ft.Text("記録しました"),
                bgcolor=ft.Colors.GREEN_400,
            )
        )
        refresh()

    record_tab = ft.Column(
        [
            ft.Text("記録", size=22, weight=ft.FontWeight.BOLD),
            ft.Divider(height=8),
            name_input,
            ft.Text("任意", size=12, color=ft.Colors.GREY),
            location_input,
            ft.Button(
                "記録する",
                on_click=add_record,
                icon=ft.Icons.ADD,
                height=48,
                width=200,
            ),
        ],
        scroll=ft.ScrollMode.AUTO,
        spacing=12,
    )

    ranking_tab = ft.Column(
        [
            ft.Text("よくなくす物ランキング", size=22, weight=ft.FontWeight.BOLD),
            ft.Divider(height=8),
            ranking_list,
        ],
        scroll=ft.ScrollMode.AUTO,
        spacing=12,
    )

    history_tab = ft.Column(
        [
            ft.Text("履歴", size=22, weight=ft.FontWeight.BOLD),
            ft.Divider(height=8),
            history_list,
        ],
        scroll=ft.ScrollMode.AUTO,
        spacing=12,
    )

    page.add(
        ft.Tabs(
            length=3,
            expand=True,
            content=ft.Column(
                expand=True,
                spacing=0,
                controls=[
                    ft.TabBar(
                        tabs=[
                            ft.Tab(label="記録", icon=ft.Icons.ADD_CIRCLE),
                            ft.Tab(label="ランキング", icon=ft.Icons.EMOJI_EVENTS),
                            ft.Tab(label="履歴", icon=ft.Icons.LIST),
                        ],
                    ),
                    ft.TabBarView(
                        expand=True,
                        controls=[
                            ft.Container(content=record_tab, padding=10),
                            ft.Container(content=ranking_tab, padding=10),
                            ft.Container(content=history_tab, padding=10),
                        ],
                    ),
                ],
            ),
        )
    )
    records[:] = load()
    refresh()


ft.run(main, view=ft.AppView.WEB_BROWSER)
