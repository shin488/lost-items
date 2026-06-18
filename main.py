import flet as ft
from app import LostItemsApp


def main(page: ft.Page):
    LostItemsApp(page)


ft.run(main, view=ft.AppView.WEB_BROWSER)
