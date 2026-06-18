import flet as ft


class RefreshMixin:
    def refresh(self):
        self._render_location_chips()
        self._render_search_chips()
        done = self._render_results()
        if not done:
            self._build_result_cards()
        self._render_history()
        self._render_ranking()
        self._update_all()

    def _render_location_chips(self):
        locs = list(
            dict.fromkeys(
                r.get("location", "").strip()
                for r in self.records if r.get("location", "").strip()
            )
        )
        loc_chips = []
        for loc in locs[:10]:
            chip = ft.Container(
                content=ft.Text(loc, size=12),
                padding=8,
                bgcolor=ft.Colors.AMBER_100,
                border_radius=10,
                on_click=lambda e, l=loc: (
                    setattr(self.location_ref.current, 'value', l),
                    self.location_ref.current.update(),
                ),
                ink=True,
            )
            loc_chips.append(chip)
        if loc_chips:
            self.location_chips_container.controls = [
                ft.Text("よく使う場所 (タップで入力):", size=11, color=ft.Colors.GREY_600),
                ft.Row(loc_chips, wrap=True, spacing=4),
            ]
        else:
            self.location_chips_container.controls = []
        self.location_chips_container.update()

    def _render_search_chips(self):
        unique = list(
            dict.fromkeys(
                r.get("name", "") for r in self.get_filtered() if r.get("name", "")
            )
        )
        chips = []
        for name in unique:
            chip = ft.Container(
                content=ft.Text(name, size=13),
                padding=8,
                bgcolor=ft.Colors.AMBER_100,
                border_radius=12,
                on_click=lambda e, n=name: self.search_from_history(n),
                ink=True,
            )
            chips.append(ft.Row([chip], tight=True))
        self.chips_container.controls = chips

    def _update_all(self):
        self.chips_container.update()
        self.results_container.update()
        self.simulation_container.update()
        self.history_container.update()
        self.ranking_container.update()
