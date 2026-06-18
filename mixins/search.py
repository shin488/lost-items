import flet as ft
import predict
import utils


class SearchMixin:
    def get_filtered(self):
        if not self.search_cat:
            return self.records
        return [r for r in self.records if r.get("category", "") == self.search_cat]

    def search_from_history(self, name):
        self.search_val = name
        self.search_ref.current.value = name
        self.search_ref.current.update()
        self.search_loading = True
        self.refresh()
        self.results, self.search_context_info = predict.unified_predict(
            name, self.records, self.search_cat
        )
        self.search_loading = False
        self.tabs.selected_index = 0
        self.tabs.update()
        self.refresh()

    def on_search_click(self, e):
        q = self.search_ref.current.value.strip()
        if not q:
            e.page.show_snack_bar(ft.SnackBar(content=ft.Text("なくした物を入力してください")))
            self.results = []
            self.refresh()
            return
        self.search_val = q
        self.search_loading = True
        self.refresh()
        self.results, self.search_context_info = predict.unified_predict(
            q, self.records, self.search_cat
        )
        self.search_loading = False
        self.refresh()

    def on_search_cat_change(self, e):
        self.search_cat = e.control.value
        self.results = None
        self.refresh()

    def _render_results(self):
        if self.search_loading:
            self.results_container.controls = [ft.ProgressBar(color=ft.Colors.TEAL_600)]
            self.simulation_container.controls = []
            return True
        if self.results is None:
            self.results_container.controls = [
                ft.Text("アイテムを入力して「探す」を押してください", color=ft.Colors.GREY_600)
            ]
            self.simulation_container.controls = []
            return True
        if not self.results:
            self.results_container.controls = [ft.Text("該当する記録がありません", color=ft.Colors.GREY_500)]
            self.simulation_container.controls = []
            return True
        return False

    def _build_result_cards(self):
        name = self.search_val.strip()
        is_default = "一般的な傾向" in self.search_context_info
        rc = [
            ft.Text(
                f"「{name}」が見つかりそうな場所",
                size=17, weight=ft.FontWeight.BOLD, color=ft.Colors.TEAL_800,
            ),
        ]
        if is_default:
            rc.append(
                ft.Text(
                    "まだ記録が少ないため、一般的な傾向を表示しています",
                    size=11, color=ft.Colors.ORANGE_700, italic=True,
                )
            )
        rc.append(ft.Text(self.search_context_info, size=12, color=ft.Colors.GREY_600))
        if is_default:
            rc.append(
                ft.Text(
                    "このアイテムを実際に見つけたら記録しましょう！精度が上がります",
                    size=11, color=ft.Colors.GREY_500, italic=True,
                )
            )
        rc.append(ft.Divider(height=4))

        from ui_components import make_bar

        matched_records = [
            r for r in self.get_filtered() if utils.fuzzy_match(name, r.get("name", ""))
        ]
        for loc, w, pct, is_top in self.results:
            color = ft.Colors.TEAL_700 if is_top else ft.Colors.TEAL_600
            contributing = [r for r in matched_records if r.get("location", "") == loc]
            contrib_text = ""
            if contributing:
                tops = contributing[:3]
                names_list = list(dict.fromkeys(r["name"] for r in tops))
                contrib_text = "根拠: " + ", ".join(names_list)
            card = ft.Container(
                content=ft.Column([
                    ft.Row([
                        ft.Text(loc, size=13, weight=(
                            ft.FontWeight.BOLD if is_top else ft.FontWeight.W_500), expand=True),
                        ft.Text(f"{pct:.0f}%", size=12, weight=ft.FontWeight.BOLD, color=color),
                    ]),
                    make_bar(pct, ft.Colors.TEAL_400 if is_top else ft.Colors.ORANGE_100),
                    ft.Text(contrib_text, size=10, color=ft.Colors.GREY_500, italic=True)
                    if contrib_text else ft.Container(),
                ], spacing=2),
                padding=6,
                bgcolor=ft.Colors.with_opacity(0.8, ft.Colors.AMBER_50) if is_top
                else ft.Colors.with_opacity(0.8, ft.Colors.WHITE),
                border=ft.Border.all(1, ft.Colors.TEAL_300 if is_top else ft.Colors.AMBER_100),
                border_radius=6,
            )
            rc.append(card)
        self.results_container.controls = rc
        self.simulation_container.controls = []
