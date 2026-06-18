import flet as ft
import storage
from constants import MAX_GRID


class FloorplanMixin:
    def build_floorplan_grid(self):
        rows = self.floorplan["rows"]
        cols = self.floorplan["cols"]
        grid_rows = []
        for r in range(rows):
            row_cells = []
            for c in range(cols):
                cell = next(
                    (x for x in self.floorplan.get("cells", []) if x.get("r") == r and x.get("c") == c),
                    None,
                )
                label = cell.get("room", "") if cell else ""
                inner = [ft.Text(label, size=12, weight=ft.FontWeight.BOLD, text_align=ft.TextAlign.CENTER)]
                if cell:
                    furn_names = [f.get("name", "") for f in cell.get("furniture", [])]
                    if furn_names:
                        display = ", ".join(furn_names[:3])
                        if len(furn_names) > 3:
                            display += "…"
                        inner.append(
                            ft.Text(display, size=8, color=ft.Colors.GREY_600,
                                    text_align=ft.TextAlign.CENTER, no_wrap=True,
                                    overflow=ft.TextOverflow.ELLIPSIS)
                        )
                cs = self.floorplan.get("cell_size", 80)
                cont = ft.Container(
                    content=ft.Column(inner, horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=1, tight=True),
                    width=cs, height=int(cs * 0.75),
                    bgcolor=ft.Colors.AMBER_50 if cell else ft.Colors.GREY_200,
                    border=ft.Border.all(1, ft.Colors.TEAL_300 if cell else ft.Colors.GREY_400),
                    border_radius=6, alignment=ft.Alignment.CENTER, ink=True,
                    on_click=lambda e, rr=r, cc=c: self.edit_cell_dialog(rr, cc),
                )
                row_cells.append(cont)
            grid_rows.append(ft.Row(row_cells, spacing=3, alignment=ft.MainAxisAlignment.CENTER))
        self.floorplan_grid_container.controls = grid_rows
        self.floorplan_grid_container.update()

    def edit_cell_dialog(self, r, c):
        def find_cell():
            return next(
                (x for x in self.floorplan.get("cells", []) if x.get("r") == r and x.get("c") == c),
                None,
            )
        existing = find_cell()
        room_input = ft.TextField(
            label="部屋名", hint_text="例: リビング",
            value=existing.get("room", "") if existing else "", width=250,
        )
        furniture_list = ft.Column(spacing=4)

        def rebuild_furniture_ui():
            cell = find_cell()
            if not cell:
                furniture_list.controls = [
                    ft.Text("先に部屋名を入力して保存してください", size=12, color=ft.Colors.GREY_500, italic=True)
                ]
            else:
                items = []
                for fi, furn in enumerate(cell.get("furniture", [])):
                    spot_chips = []
                    for si, spot in enumerate(furn.get("spots", [])):
                        chip = ft.Container(
                            content=ft.Row([
                                ft.Text(spot, size=11),
                                ft.Text("✕", size=10, color=ft.Colors.RED_400),
                            ], spacing=2),
                            padding=ft.padding.only(left=8, right=6, top=4, bottom=4),
                            bgcolor=ft.Colors.AMBER_100,
                            border_radius=8,
                            on_click=lambda e, f=fi, s=si: delete_spot(f, s),
                            ink=True,
                        )
                        spot_chips.append(chip)
                    items.append(ft.Container(
                        content=ft.Column([
                            ft.Row([
                                ft.Text(furn.get("name", ""), size=14, weight=ft.FontWeight.BOLD, expand=True),
                                ft.TextButton("＋スポット",
                                    on_click=lambda e, fn=furn.get("name", ""): add_spot_dialog(fn)),
                                ft.TextButton("削除",
                                    on_click=lambda e, f=fi: delete_furniture(f),
                                    style=ft.ButtonStyle(color=ft.Colors.RED_400)),
                            ]),
                            ft.Row(spot_chips, wrap=True, spacing=4) if spot_chips
                            else ft.Text("スポット未設定", size=11, color=ft.Colors.GREY_500, italic=True),
                        ], spacing=2),
                        padding=8,
                        bgcolor=ft.Colors.with_opacity(0.8, ft.Colors.AMBER_50),
                        border=ft.Border.all(1, ft.Colors.AMBER_200),
                        border_radius=6,
                    ))
                if not items:
                    items.append(
                        ft.Text("家具がありません。「＋家具を追加」してください",
                                size=12, color=ft.Colors.GREY_500, italic=True)
                    )
                furniture_list.controls = items
            furniture_list.update()

        def delete_furniture(fi):
            cell = find_cell()
            if cell and fi < len(cell.get("furniture", [])):
                cell["furniture"].pop(fi)
                storage.save_floorplan(self.floorplan)
                rebuild_furniture_ui()

        def delete_spot(fi, si):
            cell = find_cell()
            if cell and fi < len(cell.get("furniture", [])):
                spots = cell["furniture"][fi].get("spots", [])
                if si < len(spots):
                    spots.pop(si)
                    storage.save_floorplan(self.floorplan)
                    rebuild_furniture_ui()

        def add_furniture_dialog(ev):
            furn_input = ft.TextField(label="家具名", hint_text="例: ソファ, 机, 本棚", width=250)

            def confirm(ev2):
                name = furn_input.value.strip()
                if not name:
                    ev2.page.show_snack_bar(ft.SnackBar(content=ft.Text("家具名を入力してください")))
                    return
                cell = find_cell()
                if not cell:
                    self.floorplan["cells"].append({
                        "r": r, "c": c, "room": room_input.value.strip() or "部屋", "furniture": []
                    })
                    cell = self.floorplan["cells"][-1]
                cell.setdefault("furniture", []).append({"name": name, "spots": []})
                storage.save_floorplan(self.floorplan)
                sub_dlg.open = False
                sub_dlg.update()
                rebuild_furniture_ui()
            sub_dlg = ft.AlertDialog(
                modal=True, title=ft.Text("家具を追加"),
                content=furn_input,
                actions=[
                    ft.TextButton("キャンセル", on_click=lambda e: setattr(sub_dlg, 'open', False) or sub_dlg.update()),
                    ft.FilledButton("追加", on_click=confirm),
                ],
            )
            self.page.show_dialog(sub_dlg)

        def add_spot_dialog(furn_name):
            spot_input = ft.TextField(label="スポット名", hint_text="例: 隙間, 天板, 引き出し", width=250)

            def confirm(ev2):
                name = spot_input.value.strip()
                if not name:
                    ev2.page.show_snack_bar(ft.SnackBar(content=ft.Text("スポット名を入力してください")))
                    return
                cell = find_cell()
                if cell:
                    for f in cell.setdefault("furniture", []):
                        if f.get("name") == furn_name:
                            f.setdefault("spots", []).append(name)
                            break
                    storage.save_floorplan(self.floorplan)
                    sub_dlg.open = False
                    sub_dlg.update()
                    rebuild_furniture_ui()
            sub_dlg = ft.AlertDialog(
                modal=True, title=ft.Text(f"「{furn_name}」にスポットを追加"),
                content=spot_input,
                actions=[
                    ft.TextButton("キャンセル", on_click=lambda e: setattr(sub_dlg, 'open', False) or sub_dlg.update()),
                    ft.FilledButton("追加", on_click=confirm),
                ],
            )
            self.page.show_dialog(sub_dlg)

        def save_cell(ev):
            room = room_input.value.strip()
            if not room:
                ev.page.show_snack_bar(ft.SnackBar(content=ft.Text("部屋名を入力してください")))
                return
            cell = find_cell()
            if cell:
                cell["room"] = room
            else:
                self.floorplan["cells"].append({"r": r, "c": c, "room": room, "furniture": []})
            storage.save_floorplan(self.floorplan)
            dlg.open = False
            dlg.update()
            self.build_floorplan_grid()

        def delete_cell(ev):
            self.floorplan["cells"] = [
                x for x in self.floorplan.get("cells", [])
                if not (x.get("r") == r and x.get("c") == c)
            ]
            storage.save_floorplan(self.floorplan)
            dlg.open = False
            dlg.update()
            self.build_floorplan_grid()

        rebuild_furniture_ui()
        dlg = ft.AlertDialog(
            modal=True,
            title=ft.Text(
                f"「{existing.get('room', '') if existing else f'セル ({r+1},{c+1})'}」を編集"
            ),
            content=ft.Column([
                room_input,
                ft.Divider(height=4),
                ft.Row([
                    ft.Text("家具・スポット", size=13, weight=ft.FontWeight.BOLD, color=ft.Colors.TEAL_800, expand=True),
                    ft.TextButton("＋家具を追加", on_click=add_furniture_dialog),
                ]),
                furniture_list,
            ], tight=True, spacing=8, width=350, scroll=ft.ScrollMode.AUTO),
            actions=[
                ft.FilledButton("保存", on_click=save_cell),
                ft.TextButton("キャンセル", on_click=lambda e: setattr(dlg, 'open', False) or dlg.update()),
            ],
        )
        self.page.show_dialog(dlg)

    def resize_floorplan(self, rows, cols, cell_size=None):
        old_cells = self.floorplan.get("cells", [])
        new_cells = [c for c in old_cells if c.get("r", 0) < rows and c.get("c", 0) < cols]
        self.floorplan["rows"] = rows
        self.floorplan["cols"] = cols
        self.floorplan["cells"] = new_cells
        if cell_size is not None:
            self.floorplan["cell_size"] = cell_size
        storage.save_floorplan(self.floorplan)
        self.build_floorplan_grid()

    def show_floorplan_selector(self, e):
        def find_cell(rr, cc):
            return next(
                (x for x in self.floorplan.get("cells", []) if x.get("r") == rr and x.get("c") == cc),
                None,
            )
        rows = self.floorplan["rows"]
        cols = self.floorplan["cols"]
        path_text = ft.Text("部屋を選んでください", size=14, weight=ft.FontWeight.BOLD, color=ft.Colors.TEAL_800)
        content_area = ft.Column(spacing=4)

        def show_room_grid():
            path_text.value = "部屋を選んでください"
            path_text.update()
            grid_rows = []
            for r in range(rows):
                row_cells = []
                for c in range(cols):
                    cell = find_cell(r, c)
                    label = cell.get("room", "") if cell else f"({r+1},{c+1})"
                    cs_sel = min(self.floorplan.get("cell_size", 80), 100)
                    cont = ft.Container(
                        content=ft.Text(label, size=12, weight=ft.FontWeight.BOLD, text_align=ft.TextAlign.CENTER),
                        width=cs_sel, height=int(cs_sel * 0.65),
                        bgcolor=ft.Colors.AMBER_50 if cell else ft.Colors.GREY_200,
                        border=ft.Border.all(1, ft.Colors.TEAL_300 if cell else ft.Colors.GREY_400),
                        border_radius=6, alignment=ft.Alignment.CENTER, ink=True,
                        on_click=lambda ev, rr=r, cc=c: show_furniture_list(rr, cc),
                    )
                    row_cells.append(cont)
                grid_rows.append(ft.Row(row_cells, spacing=3, alignment=ft.MainAxisAlignment.CENTER))
            content_area.controls = [
                ft.Text("タップして部屋を選択", size=11, color=ft.Colors.GREY_600),
                ft.Column(grid_rows, spacing=3, horizontal_alignment=ft.CrossAxisAlignment.CENTER),
            ]
            content_area.update()

        def show_furniture_list(rr, cc):
            cell = find_cell(rr, cc)
            if not cell:
                set_location(f"({rr+1},{cc+1})")
                return
            path_text.value = cell.get("room", "")
            path_text.update()
            furn = cell.get("furniture", [])
            if not furn:
                set_location(cell.get("room", ""))
                return
            items = []
            for f in furn:
                items.append(ft.Container(
                    content=ft.Row([
                        ft.Text(f.get("name", ""), size=14, weight=ft.FontWeight.W_500, expand=True),
                        ft.Text("›", size=16, color=ft.Colors.GREY_500),
                    ]),
                    padding=12,
                    bgcolor=ft.Colors.AMBER_50,
                    border=ft.Border.all(1, ft.Colors.AMBER_200),
                    border_radius=6,
                    ink=True,
                    on_click=lambda ev, fn=f.get("name", ""): show_spot_list(rr, cc, fn),
                ))
            content_area.controls = [
                ft.TextButton("← 部屋一覧に戻る", on_click=lambda ev: show_room_grid()),
                ft.Divider(height=2),
                ft.Text("家具を選んでください", size=11, color=ft.Colors.GREY_600),
                ft.Column(items, spacing=4),
            ]
            content_area.update()

        def show_spot_list(rr, cc, furn_name):
            cell = find_cell(rr, cc)
            if not cell:
                set_location(f"({rr+1},{cc+1})")
                return
            furn = next((f for f in cell.get("furniture", []) if f.get("name") == furn_name), None)
            if not furn or not furn.get("spots"):
                set_location(f"{cell.get('room', '')} > {furn_name}")
                return
            path_text.value = f"{cell.get('room', '')} > {furn_name}"
            path_text.update()
            items = []
            for s in furn.get("spots", []):
                items.append(ft.Container(
                    content=ft.Text(s, size=13),
                    padding=10,
                    bgcolor=ft.Colors.AMBER_100,
                    border_radius=6,
                    ink=True,
                    on_click=lambda ev, sp=s: set_location(f"{cell.get('room', '')} > {furn_name} > {sp}"),
                ))
            content_area.controls = [
                ft.TextButton("← 家具一覧に戻る", on_click=lambda ev: show_furniture_list(rr, cc)),
                ft.Divider(height=2),
                ft.Text("スポットを選んでください", size=11, color=ft.Colors.GREY_600),
                ft.Column(items, spacing=4),
            ]
            content_area.update()

        def set_location(loc_text):
            self.location_ref.current.value = loc_text
            self.location_ref.current.update()
            dlg.open = False
            dlg.update()

        show_room_grid()
        dlg = ft.AlertDialog(
            modal=True,
            title=path_text,
            content=ft.Column([content_area], tight=True, spacing=8, width=300),
            actions=[ft.TextButton("キャンセル", on_click=lambda ev: setattr(dlg, 'open', False) or dlg.update())],
        )
        e.page.show_dialog(dlg)

    def on_resize_click(self, e):
        try:
            r = max(1, min(MAX_GRID, int(self.rows_input.value)))
            c = max(1, min(MAX_GRID, int(self.cols_input.value)))
            cs = max(40, min(200, int(self.cell_size_input.value)))
            self.resize_floorplan(r, c, cs)
            self.rows_input.value = str(r)
            self.cols_input.value = str(c)
            self.cell_size_input.value = str(cs)
            self.rows_input.update()
            self.cols_input.update()
            self.cell_size_input.update()
        except ValueError:
            e.page.show_snack_bar(ft.SnackBar(content=ft.Text("数字を入力してください")))
