from datetime import datetime
import uuid

import flet as ft

import storage
from constants import MAX_GRID
from mixins.search import SearchMixin
from mixins.records import RecordsMixin
from mixins.floorplan import FloorplanMixin
from mixins.analysis import AnalysisMixin
from mixins.refresh import RefreshMixin


class LostItemsApp(
    SearchMixin,
    RecordsMixin,
    FloorplanMixin,
    AnalysisMixin,
    RefreshMixin,
):
    def __init__(self, page: ft.Page):
        self.page = page
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

        self.records = storage.load_records(page)
        needs_save = False
        for r in self.records:
            if "id" not in r:
                r["id"] = str(uuid.uuid4())
                needs_save = True
        if needs_save:
            storage.save_records(page, self.records)

        self.categories = storage.load_categories()
        self.floorplan = storage.load_floorplan()
        self.floorplan.setdefault("cell_size", 80)
        if storage.migrate_floorplan_cells(self.floorplan.get("cells", [])):
            storage.save_floorplan(self.floorplan)
        self.search_val = ""
        self.search_cat = ""
        self.results = None
        self.search_context_info = ""
        self.search_loading = False

        self.cal_year = datetime.now().year
        self.cal_month = datetime.now().month

        self.search_ref = ft.Ref[ft.TextField]()
        self.name_ref = ft.Ref[ft.TextField]()
        self.date_ref = ft.Ref[ft.TextField]()
        self.location_ref = ft.Ref[ft.TextField]()
        self.category_ref = ft.Ref[ft.Dropdown]()
        self.search_dropdown_ref = ft.Ref[ft.Dropdown]()

        self.chips_container = ft.Column(spacing=4)
        self.location_chips_container = ft.Column(spacing=4)
        self.results_container = ft.Column(spacing=6)
        self.simulation_container = ft.Column(spacing=4)
        self.history_container = ft.Column(spacing=4)
        self.ranking_container = ft.Column(spacing=8)
        self.analysis_container = ft.Column(spacing=8)
        self.analysis_progress = ft.ProgressBar(visible=False, color=ft.Colors.TEAL_600)
        self.floorplan_grid_container = ft.Column(spacing=2, horizontal_alignment=ft.CrossAxisAlignment.CENTER)

        self.date_picker = ft.DatePicker(
            on_change=self.on_date_selected,
            first_date=datetime(2000, 1, 1),
            last_date=datetime.now(),
        )

        self.rows_input = ft.TextField(
            value=str(self.floorplan.get("rows", 3)), label="行", width=70,
            keyboard_type=ft.KeyboardType.NUMBER, text_align=ft.TextAlign.CENTER,
        )
        self.cols_input = ft.TextField(
            value=str(self.floorplan.get("cols", 3)), label="列", width=70,
            keyboard_type=ft.KeyboardType.NUMBER, text_align=ft.TextAlign.CENTER,
        )
        cell_size_options = [ft.dropdown.Option(str(s)) for s in (60, 80, 100, 120, 140)]
        self.cell_size_input = ft.Dropdown(
            label="セルサイズ",
            value=str(self.floorplan.get("cell_size", 80)),
            options=cell_size_options,
            width=100,
        )

        self._build_views()

    def on_date_selected(self, e):
        val = e.control.value
        if val:
            if hasattr(val, "strftime"):
                self.date_ref.current.value = val.strftime("%Y-%m-%d")
            else:
                self.date_ref.current.value = str(val)[:10]
            self.date_ref.current.update()

    def open_date_picker(self, e=None):
        self.date_picker.last_date = datetime.now()
        self.date_picker.open = True
        self.date_picker.update()

    def on_page_load(self, e):
        self.refresh()

    def _build_views(self):
        page = self.page

        search_dropdown = ft.Dropdown(
            ref=self.search_dropdown_ref,
            label="カテゴリで絞り込み",
            options=([ft.dropdown.Option("", "すべて")]
                     + [ft.dropdown.Option(c) for c in self.categories]),
            width=300,
            on_select=self.on_search_cat_change,
        )

        search_view = ft.Column([
            ft.Row([
                ft.Text("焦らず、ゆっくり思い出しましょう", size=13, color=ft.Colors.TEAL_700, italic=True),
            ]),
            ft.Text("なくしものを探す", size=22, weight=ft.FontWeight.BOLD),
            ft.Divider(height=8),
            search_dropdown,
            ft.Row([
                ft.TextField(ref=self.search_ref, label="なくした物は？",
                             hint_text="例: 財布、鍵、スマホ", expand=True),
                ft.FilledButton("探す", on_click=self.on_search_click),
            ]),
            self.chips_container,
            ft.Divider(height=8),
            ft.Container(content=self.results_container, expand=True),
            ft.Divider(height=8),
            self.simulation_container,
        ], scroll=ft.ScrollMode.AUTO, spacing=12)

        record_view = ft.Column([
            ft.Text("見つけたらすぐに記録しましょう", size=13, color=ft.Colors.TEAL_700, italic=True),
            ft.Text("新しい記録", size=22, weight=ft.FontWeight.BOLD),
            ft.Divider(height=8),
            ft.TextField(ref=self.name_ref, label="なくした物", hint_text="例: 鍵、スマホ、財布", width=300),
            ft.Dropdown(
                ref=self.category_ref,
                label="カテゴリ",
                options=([ft.dropdown.Option("", "選択してください")]
                         + [ft.dropdown.Option(c) for c in self.categories]),
                width=300,
            ),
            ft.TextButton("カテゴリ管理", on_click=self.show_category_dialog),
            ft.Row([
                ft.TextField(
                    ref=self.date_ref,
                    label="なくした日 (任意)",
                    hint_text="タップしてカレンダーから選択",
                    value=datetime.now().strftime("%Y-%m-%d"),
                    width=300,
                    read_only=True,
                    on_focus=lambda _: self.open_date_picker(),
                    suffix=ft.TextButton("日付選択", on_click=lambda _: self.open_date_picker()),
                ),
            ]),
            ft.TextField(ref=self.location_ref, label="見つかった場所",
                         hint_text="例: ソファの隙間", width=300),
            ft.Column([
                self.location_chips_container,
                ft.Row([
                    ft.TextButton("間取りから選ぶ", on_click=self.show_floorplan_selector,
                                  style=ft.ButtonStyle(color=ft.Colors.TEAL_700)),
                ]),
            ]),
            ft.ElevatedButton("記録する", on_click=self.on_add_record),
            ft.Divider(height=16),
            ft.Row([
                ft.Text("記録履歴", size=16, weight=ft.FontWeight.BOLD),
                ft.Row([
                    ft.TextButton("エクスポート", on_click=self.show_export_dialog),
                    ft.TextButton("インポート", on_click=self.show_import_dialog),
                ]),
            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            self.history_container,
        ], scroll=ft.ScrollMode.AUTO, spacing=12)

        floorplan_view = ft.Column([
            ft.Text("間取りを設定", size=22, weight=ft.FontWeight.BOLD),
            ft.Text("セルをタップして編集", size=12, color=ft.Colors.GREY_600, italic=True),
            ft.Divider(height=8),
            ft.Row([
                self.rows_input,
                ft.Text("×", size=16),
                self.cols_input,
                self.cell_size_input,
                ft.FilledButton("更新", on_click=self.on_resize_click),
            ], spacing=6),
            ft.Text("グリッドサイズ: 最大 30×30", size=11, color=ft.Colors.GREY_500),
            ft.Divider(height=8),
            self.floorplan_grid_container,
            ft.Divider(height=8),
            ft.TextButton("すべてリセット",
                on_click=lambda e: (
                    self.resize_floorplan(3, 3, 80),
                    setattr(self.rows_input, 'value', '3'),
                    self.rows_input.update(),
                    setattr(self.cols_input, 'value', '3'),
                    self.cols_input.update(),
                    setattr(self.cell_size_input, 'value', '80'),
                    self.cell_size_input.update(),
                ),
                style=ft.ButtonStyle(color=ft.Colors.RED_400)),
        ], scroll=ft.ScrollMode.AUTO, spacing=12)

        ranking_view = ft.Column([self.ranking_container], scroll=ft.ScrollMode.AUTO, spacing=12)
        analysis_view = ft.Column(
            [self.analysis_progress, self.analysis_container],
            scroll=ft.ScrollMode.AUTO, spacing=12,
        )

        tabs = ft.Tabs(
            content=ft.Column([
                ft.TabBar(
                    tabs=[
                        ft.Tab(label="探す"),
                        ft.Tab(label="記録"),
                        ft.Tab(label="間取り"),
                        ft.Tab(label="ランキング"),
                        ft.Tab(label="分析"),
                    ],
                    indicator_color=ft.Colors.TEAL_600,
                    label_color=ft.Colors.TEAL_800,
                    unselected_label_color=ft.Colors.GREY_600,
                ),
                ft.TabBarView(
                    controls=[search_view, record_view, floorplan_view, ranking_view, analysis_view],
                    expand=True,
                ),
            ], expand=True, spacing=0),
            length=5,
            selected_index=0,
            expand=True,
            on_change=lambda e: self.refresh_analysis()
            if e.control.selected_index == 4 else None,
        )

        page.appbar = ft.AppBar(
            title=ft.Row([ft.Text("なくしもの探知機", weight=ft.FontWeight.BOLD)], tight=True),
            bgcolor=ft.Colors.TEAL_800,
            color=ft.Colors.WHITE,
            center_title=True,
            actions=[
                ft.TextButton("エクスポート", on_click=self.show_export_dialog,
                              style=ft.ButtonStyle(color=ft.Colors.WHITE)),
                ft.TextButton("インポート", on_click=self.show_import_dialog,
                              style=ft.ButtonStyle(color=ft.Colors.WHITE)),
            ],
        )

        page.overlay.append(self.date_picker)
        page.add(ft.Stack([
            ft.Container(expand=True, gradient=ft.LinearGradient(
                begin=ft.Alignment.TOP_LEFT, end=ft.Alignment.BOTTOM_RIGHT,
                colors=[ft.Colors.AMBER_50, ft.Colors.TEAL_50],
            )),
            ft.Container(expand=True, bgcolor=ft.Colors.with_opacity(0.15, ft.Colors.WHITE)),
            ft.SafeArea(expand=True, content=tabs),
        ], expand=True))

        page.update()
        self.refresh()
        self.build_floorplan_grid()
        page.on_load = self.on_page_load
