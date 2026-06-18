import flet as ft


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
