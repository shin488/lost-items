from datetime import datetime
import json
import uuid

import flet as ft
import storage
from ui_components import make_tappable_btn


class RecordsMixin:
    def on_add_record(self, e):
        name = self.name_ref.current.value.strip()
        location = self.location_ref.current.value.strip()
        if not name:
            e.page.show_snack_bar(ft.SnackBar(
                content=ft.Text("「なくした物」を入力してください"), bgcolor=ft.Colors.RED_400))
            return
        if not location:
            e.page.show_snack_bar(ft.SnackBar(
                content=ft.Text("「見つかった場所」を入力してください"), bgcolor=ft.Colors.RED_400))
            return
        parts = location.split(" > ")
        location_parts = {}
        if len(parts) >= 1:
            location_parts["room"] = parts[0]
        if len(parts) >= 2:
            location_parts["furniture"] = parts[1]
        if len(parts) >= 3:
            location_parts["spot"] = parts[2]
        rec = {
            "id": str(uuid.uuid4()),
            "name": name,
            "category": self.category_ref.current.value or "その他",
            "location": location,
            "location_parts": location_parts,
            "lost_date": (self.date_ref.current.value or "").strip() or datetime.now().strftime("%Y-%m-%d"),
            "found_date": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "resolved": False,
            "resolution_date": None,
        }
        self.records = self.records + [rec]
        if not storage.save_records(self.page, self.records):
            e.page.show_snack_bar(ft.SnackBar(
                content=ft.Text("保存に失敗しました"), bgcolor=ft.Colors.RED_400))
            return
        e.page.show_snack_bar(ft.SnackBar(content=ft.Text("記録しました"), bgcolor=ft.Colors.TEAL_400))
        self.name_ref.current.value = ""
        self.category_ref.current.value = ""
        self.date_ref.current.value = datetime.now().strftime("%Y-%m-%d")
        self.location_ref.current.value = ""
        self.name_ref.current.update()
        self.category_ref.current.update()
        self.date_ref.current.update()
        self.location_ref.current.update()
        self.refresh()

    def find_record_idx(self, rid):
        for i, r in enumerate(self.records):
            if r.get("id") == rid:
                return i
        return None

    def delete_record(self, rid):
        idx = self.find_record_idx(rid)
        if idx is not None:
            self.records.pop(idx)
            storage.save_records(self.page, self.records)
            self.refresh()

    def confirm_delete(self, rid, name):
        def do_delete(e):
            dlg.open = False
            dlg.update()
            self.delete_record(rid)
        dlg = ft.AlertDialog(
            modal=True,
            title=ft.Text(f"「{name}」を削除しますか？"),
            content=ft.Text("この操作は元に戻せません", size=13, color=ft.Colors.GREY_600),
            actions=[
                ft.TextButton("キャンセル", on_click=lambda e: setattr(dlg, 'open', False) or dlg.update()),
                ft.FilledButton("削除", on_click=do_delete,
                                style=ft.ButtonStyle(bgcolor=ft.Colors.RED_400, color=ft.Colors.WHITE)),
            ],
        )
        self.page.show_dialog(dlg)

    def show_edit_dialog(self, rid):
        idx = self.find_record_idx(rid)
        if idx is None:
            return
        r = self.records[idx]
        edit_name = ft.TextField(label="なくした物", value=r.get("name", ""), width=300)
        edit_location = ft.TextField(label="見つかった場所", value=r.get("location", ""), width=300)
        edit_lost_date = ft.TextField(
            label="なくした日", value=r.get("lost_date", ""), width=300,
            read_only=True,
            on_focus=lambda _: self._open_edit_date_picker(edit_lost_date),
            suffix=ft.TextButton("日付選択",
                                 on_click=lambda _: self._open_edit_date_picker(edit_lost_date)),
        )
        edit_cat_opts = [ft.dropdown.Option(c) for c in self.categories]
        edit_category = ft.Dropdown(
            label="カテゴリ", value=r.get("category", "その他"),
            options=edit_cat_opts, width=300,
        )

        def save_edit(e):
            idx2 = self.find_record_idx(rid)
            if idx2 is None:
                return
            new_name = edit_name.value.strip()
            if not new_name:
                e.page.show_snack_bar(ft.SnackBar(content=ft.Text("名前を入力してください")))
                return
            self.records[idx2]["name"] = new_name
            self.records[idx2]["category"] = edit_category.value
            self.records[idx2]["location"] = edit_location.value.strip()
            new_parts = edit_location.value.strip().split(" > ")
            self.records[idx2]["location_parts"] = {}
            if len(new_parts) >= 1:
                self.records[idx2]["location_parts"]["room"] = new_parts[0]
            if len(new_parts) >= 2:
                self.records[idx2]["location_parts"]["furniture"] = new_parts[1]
            if len(new_parts) >= 3:
                self.records[idx2]["location_parts"]["spot"] = new_parts[2]
            self.records[idx2]["lost_date"] = edit_lost_date.value.strip() or self.records[idx2].get("lost_date", "")
            storage.save_records(self.page, self.records)
            dlg.open = False
            dlg.update()
            self.refresh()
            e.page.show_snack_bar(ft.SnackBar(content=ft.Text("更新しました"), bgcolor=ft.Colors.TEAL_400))

        dlg = ft.AlertDialog(
            modal=True,
            title=ft.Text("記録を編集"),
            content=ft.Column([
                edit_name, edit_category, edit_lost_date, edit_location,
            ], tight=True, spacing=8, scroll=ft.ScrollMode.AUTO),
            actions=[
                ft.TextButton("キャンセル", on_click=lambda e: setattr(dlg, 'open', False) or dlg.update()),
                ft.FilledButton("保存", on_click=save_edit),
            ],
        )
        self.page.show_dialog(dlg)

    def _open_edit_date_picker(self, field):
        def on_pick(e):
            val = e.control.value
            if val:
                if hasattr(val, "strftime"):
                    field.value = val.strftime("%Y-%m-%d")
                else:
                    field.value = str(val)[:10]
                field.update()
        dp = ft.DatePicker(on_change=on_pick, first_date=datetime(2000, 1, 1), last_date=datetime.now())
        self.page.overlay.append(dp)
        dp.open = True
        dp.update()

    def mark_resolved(self, rid):
        idx = self.find_record_idx(rid)
        if idx is None:
            return
        self.records[idx]["resolved"] = True
        self.records[idx]["resolution_date"] = datetime.now().strftime("%Y-%m-%d %H:%M")
        storage.save_records(self.page, self.records)
        self.page.show_snack_bar(ft.SnackBar(
            content=ft.Text(f"「{self.records[idx].get('name', '')}」を見つかりました！"),
            bgcolor=ft.Colors.TEAL_400))
        self.refresh()

    def show_export_dialog(self, e):
        data = json.dumps(self.records, ensure_ascii=False, indent=2)
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

    def show_import_dialog(self, e):
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
                    item.setdefault("id", str(uuid.uuid4()))
                    item.setdefault("category", "その他")
                    item.setdefault("location", "")
                    item.setdefault("location_parts", {})
                    item.setdefault("lost_date", "")
                    item.setdefault("found_date", "")
                    item.setdefault("resolved", False)
                    item.setdefault("resolution_date", None)
                self.records = data
                storage.save_records(self.page, self.records)
                dlg.open = False
                dlg.update()
                ev.page.show_snack_bar(ft.SnackBar(
                    content=ft.Text(f"{len(data)}件のデータをインポートしました"),
                    bgcolor=ft.Colors.TEAL_400))
                self.refresh()
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

    def rebuild_category_dropdowns(self):
        opts = [ft.dropdown.Option("", "すべて")] + [ft.dropdown.Option(c) for c in self.categories]
        if self.search_dropdown_ref.current:
            self.search_dropdown_ref.current.options = opts
            self.search_dropdown_ref.current.update()
        cat_opts = [ft.dropdown.Option("", "選択してください")] + [ft.dropdown.Option(c) for c in self.categories]
        if self.category_ref.current:
            self.category_ref.current.options = cat_opts
            self.category_ref.current.update()

    def show_category_dialog(self, e):
        cats = self.categories[:]
        cat_input = ft.TextField(label="新しいカテゴリ名", hint_text="例: 充電器", width=300)
        cat_list = ft.Column(spacing=4)

        def refresh_cat_ui():
            used = set(r.get("category", "") for r in self.records)
            rows = []
            for i, c in enumerate(cats):
                in_use = c in used
                btn = ft.TextButton("削除",
                    on_click=(lambda ev, idx=i: delete_category(idx)) if not in_use else None,
                )
                rows.append(ft.Row([
                    ft.Text(c, expand=True, size=14),
                    ft.Text("使用中" if in_use else "", size=11, color=ft.Colors.GREY_500, italic=True),
                    btn,
                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN))
            cat_list.controls = rows
            cat_list.update()

        def delete_category(idx):
            cats.pop(idx)
            self.categories = cats[:]
            storage.save_categories(self.categories)
            refresh_cat_ui()
            self.rebuild_category_dropdowns()

        def add_category(ev):
            name = cat_input.value.strip()
            if not name:
                ev.page.show_snack_bar(ft.SnackBar(content=ft.Text("カテゴリ名を入力してください")))
                return
            if name in cats:
                ev.page.show_snack_bar(ft.SnackBar(content=ft.Text("既に存在するカテゴリです")))
                return
            cats.append(name)
            self.categories = cats[:]
            storage.save_categories(self.categories)
            cat_input.value = ""
            cat_input.update()
            refresh_cat_ui()
            self.rebuild_category_dropdowns()

        def close_dlg(ev):
            dlg.open = False
            dlg.update()

        refresh_cat_ui()
        dlg = ft.AlertDialog(
            modal=True,
            title=ft.Text("カテゴリ管理"),
            content=ft.Column([
                ft.Row([
                    cat_input,
                    ft.FilledButton("追加", on_click=add_category),
                ], tight=True),
                ft.Divider(height=4),
                cat_list,
            ], tight=True, spacing=8, width=350),
            actions=[ft.TextButton("閉じる", on_click=close_dlg)],
        )
        e.page.show_dialog(dlg)

    def _render_history(self):
        if not self.records:
            self.history_container.controls = [
                ft.Container(
                    ft.Column([
                        ft.Text("まだ記録がありません", color=ft.Colors.TEAL_700),
                        ft.Text("「記録」タブからなくし物を追加しましょう", size=12, color=ft.Colors.GREY_500, italic=True),
                    ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=4),
                    padding=20, alignment=ft.Alignment.CENTER,
                ),
            ]
            return

        hc = []
        for i, r in enumerate(reversed(self.records)):
            idx = len(self.records) - 1 - i
            rid = r.get("id", str(idx))
            cat = r.get("category", "")
            loc = r.get("location", "場所不明")
            fd = r.get("found_date", "")
            resolved = r.get("resolved", False)
            subtitle = f"{loc}  ({fd})"
            if cat:
                subtitle = f"[{cat}] {subtitle}"
            if resolved:
                subtitle += " 解決済み"
            trailing_btns = [
                make_tappable_btn("編集", lambda e, rid=rid: self.show_edit_dialog(rid)),
                make_tappable_btn("探す",
                    lambda e, n=r.get("name", ""): self.search_from_history(n)),
            ]
            if not resolved:
                trailing_btns.insert(1, make_tappable_btn("解決",
                    lambda e, rid=rid: self.mark_resolved(rid),
                    color=ft.Colors.TEAL_600))
            trailing_btns.append(make_tappable_btn("削除",
                lambda e, rid=rid, n=r.get("name", ""): self.confirm_delete(rid, n),
                color=ft.Colors.RED_400))
            hc.append(
                ft.Card(
                    ft.ListTile(
                        title=ft.Text(r.get("name", ""), weight=ft.FontWeight.W_500),
                        subtitle=ft.Text(subtitle, size=13),
                        trailing=ft.Row(trailing_btns, spacing=2),
                    ),
                    margin=3,
                )
            )
        self.history_container.controls = hc

    def _render_ranking(self):
        if not self.records:
            self.ranking_container.controls = [
                ft.Container(
                    ft.Column([
                        ft.Text("まだデータがありません", color=ft.Colors.TEAL_700),
                        ft.Text("記録が増えるとランキングが表示されます", size=12, color=ft.Colors.GREY_500, italic=True),
                    ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=4),
                    padding=20, alignment=ft.Alignment.CENTER,
                ),
            ]
            return

        from collections import Counter
        name_counts = Counter(r.get("name", "") for r in self.records if r.get("name", "")).most_common()
        total = len(self.records)
        rc = [
            ft.Text("よくなくした物ランキング", size=18, weight=ft.FontWeight.BOLD, color=ft.Colors.TEAL_800),
            ft.Text(f"全 {total} 件の記録", size=12, color=ft.Colors.GREY_600, italic=True),
            ft.Divider(height=8),
        ]
        for rank, (name, cnt) in enumerate(name_counts, 1):
            pct = cnt / total * 100
            rc.append(
                ft.Card(
                    ft.ListTile(
                        title=ft.Row([
                            ft.Text(f"#{rank}", size=13, color=ft.Colors.GREY_500),
                            ft.Text(name, size=16, weight=ft.FontWeight.W_500),
                        ]),
                        subtitle=ft.Text(f"{cnt}回 ({pct:.1f}%)", size=13, color=ft.Colors.GREY_600),
                        trailing=ft.TextButton("探す",
                            on_click=lambda e, n=name: self.search_from_history(n),
                        ),
                    ),
                    margin=3,
                )
            )
        self.ranking_container.controls = rc
