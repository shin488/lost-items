from datetime import datetime
from collections import Counter
import calendar

import flet as ft
from constants import WEEKDAYS_JP
from ui_components import make_bar


class AnalysisMixin:
    def refresh_analysis(self):
        self.analysis_progress.visible = True
        self.page.update()

        if not self.records:
            self.analysis_container.controls = [
                ft.Container(
                    ft.Column([
                        ft.Text("まだデータがありません", color=ft.Colors.TEAL_700),
                        ft.Text("記録が増えると分析が表示されます", size=12, color=ft.Colors.GREY_500, italic=True),
                    ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=4),
                    padding=20, alignment=ft.Alignment.CENTER,
                ),
            ]
            self.analysis_progress.visible = False
            self.analysis_container.update()
            self.analysis_progress.update()
            return

        sections = []

        lost_by_date = {}
        for r in self.records:
            d = (r.get("lost_date", "") or r.get("found_date", "")[:10])
            if d:
                lost_by_date.setdefault(d, []).append(r)

        valid_dates = []
        for d in lost_by_date:
            try:
                valid_dates.append(datetime.strptime(d, "%Y-%m-%d"))
            except ValueError:
                pass

        cal_header = ft.Row([
            ft.TextButton("<", on_click=lambda e: self._navigate_cal(-1)),
            ft.Text(f"{self.cal_year}年 {self.cal_month}月", size=16, weight=ft.FontWeight.BOLD,
                    expand=True, text_align=ft.TextAlign.CENTER),
            ft.TextButton(">", on_click=lambda e: self._navigate_cal(1)),
        ], alignment=ft.MainAxisAlignment.CENTER)
        sections.append(cal_header)

        cal_grid = ft.Column(spacing=2)
        month_cal = calendar.monthcalendar(self.cal_year, self.cal_month)
        day_names = [w.replace("曜日", "") for w in WEEKDAYS_JP]
        cal_grid.controls.append(
            ft.Row(
                [ft.Container(ft.Text(d, size=11, color=ft.Colors.GREY_600, text_align=ft.TextAlign.CENTER),
                              width=42, height=24) for d in day_names],
                spacing=2, alignment=ft.MainAxisAlignment.CENTER,
            )
        )
        for week in month_cal:
            week_row = []
            for day in week:
                if day == 0:
                    week_row.append(ft.Container(width=42, height=42))
                else:
                    date_str = f"{self.cal_year}-{self.cal_month:02d}-{day:02d}"
                    day_records = lost_by_date.get(date_str, [])
                    cnt = len(day_records)
                    is_today = date_str == datetime.now().strftime("%Y-%m-%d")
                    bg = ft.Colors.AMBER_100 if is_today else (
                        ft.Colors.AMBER_50 if cnt > 0 else ft.Colors.GREY_100)
                    border = ft.Border.all(2, ft.Colors.TEAL_600) if is_today else None
                    day_text = ft.Text(
                        str(day), size=13,
                        weight=ft.FontWeight.BOLD if cnt > 0 else ft.FontWeight.NORMAL,
                    )
                    badge = None
                    if cnt > 0:
                        badge = ft.Container(
                            content=ft.Text(str(cnt), size=9, color=ft.Colors.WHITE),
                            bgcolor=ft.Colors.RED_400, border_radius=8,
                            width=16, height=16,
                            alignment=ft.Alignment.CENTER,
                            right=-4, top=-4,
                        )
                    stack_items = [day_text]
                    if badge:
                        stack_items.append(badge)
                    container = ft.Container(
                        content=ft.Stack(stack_items),
                        width=42, height=42, bgcolor=bg, border=border,
                        border_radius=6, alignment=ft.Alignment.CENTER,
                        ink=True,
                        on_click=lambda e, ds=date_str, recs=day_records: self._show_day_detail(ds, recs),
                    )
                    week_row.append(container)
            cal_grid.controls.append(ft.Row(week_row, spacing=2, alignment=ft.MainAxisAlignment.CENTER))
        sections.append(cal_grid)

        sections.append(ft.Divider(height=16))
        sections.append(ft.Text("解決状況分析", size=18, weight=ft.FontWeight.BOLD, color=ft.Colors.TEAL_800))
        sections.append(ft.Divider(height=8))

        resolved_records = [r for r in self.records if r.get("resolved")]
        unresolved_records = [r for r in self.records if not r.get("resolved")]
        resolved_total = len(resolved_records)
        unresolved_total = len(unresolved_records)
        total_recs = len(self.records)
        resolved_pct = resolved_total / total_recs * 100 if total_recs > 0 else 0

        sections.append(ft.Row([
            ft.Container(
                ft.Column([
                    ft.Text("解決済み", size=11, color=ft.Colors.GREY_600),
                    ft.Text(str(resolved_total), size=22, weight=ft.FontWeight.BOLD, color=ft.Colors.TEAL_700),
                ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=1),
                padding=10, border_radius=8,
                bgcolor=ft.Colors.with_opacity(0.8, ft.Colors.AMBER_50), expand=True,
                border=ft.Border.all(1, ft.Colors.ORANGE_100),
            ),
            ft.Container(
                ft.Column([
                    ft.Text("未解決", size=11, color=ft.Colors.GREY_600),
                    ft.Text(str(unresolved_total), size=22, weight=ft.FontWeight.BOLD, color=ft.Colors.BROWN_700),
                ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=1),
                padding=10, border_radius=8,
                bgcolor=ft.Colors.with_opacity(0.8, ft.Colors.ORANGE_50), expand=True,
                border=ft.Border.all(1, ft.Colors.BROWN_200),
            ),
            ft.Container(
                ft.Column([
                    ft.Text("解決率", size=11, color=ft.Colors.GREY_600),
                    ft.Text(f"{resolved_pct:.0f}%", size=22, weight=ft.FontWeight.BOLD, color=ft.Colors.TEAL_800),
                ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=1),
                padding=10, border_radius=8,
                bgcolor=ft.Colors.with_opacity(0.8, ft.Colors.AMBER_50), expand=True,
                border=ft.Border.all(1, ft.Colors.ORANGE_100),
            ),
        ], spacing=6))
        sections.append(make_bar(resolved_pct, ft.Colors.TEAL_600))
        sections.append(ft.Text(f"解決率 {resolved_pct:.0f}%", size=12, color=ft.Colors.GREY_600, italic=True))

        time_diffs = []
        for r in resolved_records:
            ld = r.get("lost_date", "")
            rd = r.get("resolution_date", "")
            if ld and rd:
                try:
                    lost = datetime.strptime(ld, "%Y-%m-%d")
                    res = datetime.strptime(rd, "%Y-%m-%d %H:%M")
                    diff_hours = (res - lost).total_seconds() / 3600
                    if diff_hours >= 0:
                        time_diffs.append(diff_hours)
                except ValueError:
                    pass

        if time_diffs:
            sections.append(ft.Divider(height=8))
            avg_h = sum(time_diffs) / len(time_diffs)
            min_h = min(time_diffs)
            max_h = max(time_diffs)
            sections.append(ft.Text("発見までの時間", size=15, weight=ft.FontWeight.BOLD, color=ft.Colors.TEAL_800))
            sections.append(ft.Row([
                ft.Container(
                    ft.Column([
                        ft.Text("最短", size=10, color=ft.Colors.GREY_600),
                        ft.Text(f"{min_h/24:.1f}日" if min_h >= 24 else f"{min_h:.0f}時間",
                                size=14, weight=ft.FontWeight.BOLD, color=ft.Colors.TEAL_700),
                    ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=0),
                    padding=8, border_radius=8, bgcolor=ft.Colors.with_opacity(0.8, ft.Colors.AMBER_50), expand=True,
                ),
                ft.Container(
                    ft.Column([
                        ft.Text("平均", size=10, color=ft.Colors.GREY_600),
                        ft.Text(f"{avg_h/24:.1f}日" if avg_h >= 24 else f"{avg_h:.0f}時間",
                                size=14, weight=ft.FontWeight.BOLD, color=ft.Colors.BLUE_700),
                    ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=0),
                    padding=8, border_radius=8, bgcolor=ft.Colors.BLUE_50, expand=True,
                ),
                ft.Container(
                    ft.Column([
                        ft.Text("最長", size=10, color=ft.Colors.GREY_600),
                        ft.Text(f"{max_h/24:.1f}日" if max_h >= 24 else f"{max_h:.0f}時間",
                                size=14, weight=ft.FontWeight.BOLD, color=ft.Colors.RED_700),
                    ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=0),
                    padding=8, border_radius=8, bgcolor=ft.Colors.RED_50, expand=True,
                ),
            ], spacing=6))

            bucket = Counter()
            for h in time_diffs:
                if h < 1:
                    bucket["1時間未満"] += 1
                elif h < 6:
                    bucket["1〜6時間"] += 1
                elif h < 24:
                    bucket["6〜24時間"] += 1
                elif h < 72:
                    bucket["1〜3日"] += 1
                else:
                    bucket["3日以上"] += 1
            sections.append(ft.Divider(height=8))
            sections.append(ft.Text("発見時間の分布", size=14, weight=ft.FontWeight.BOLD, color=ft.Colors.TEAL_800))
            for label, cnt in bucket.most_common():
                pct = cnt / len(time_diffs) * 100
                sections.append(ft.Column([
                    ft.Row([
                        ft.Text(label, size=12, expand=True),
                        ft.Text(f"{cnt}件", size=11, color=ft.Colors.GREY_600),
                    ]),
                    make_bar(pct, ft.Colors.TEAL_300),
                ], spacing=1))

        loc_rooms = Counter()
        loc_furniture = Counter()
        loc_combos = Counter()
        loc_len = 0
        for r in self.records:
            lp = r.get("location_parts", {}) or {}
            if lp.get("room"):
                loc_rooms[lp["room"]] += 1
                loc_len += 1
                if lp.get("furniture"):
                    key = f"{lp['room']} > {lp['furniture']}"
                    loc_furniture[key] += 1
                    if lp.get("spot"):
                        loc_combos[f"{key} > {lp['spot']}"] += 1

        if loc_rooms:
            sections.append(ft.Divider(height=16))
            sections.append(ft.Text("スポット分析", size=18, weight=ft.FontWeight.BOLD, color=ft.Colors.TEAL_800))
            sections.append(ft.Divider(height=8))
            sections.append(ft.Text("部屋別", size=14, weight=ft.FontWeight.BOLD, color=ft.Colors.TEAL_700))
            for room, cnt in loc_rooms.most_common(5):
                pct = cnt / loc_len * 100
                sections.append(ft.Row([
                    ft.Container(ft.Text(room, size=12, expand=True), expand=True),
                    ft.Container(ft.Text(f"{cnt}件 {pct:.0f}%", size=11, color=ft.Colors.GREY_600)),
                ]))
            if loc_furniture:
                sections.append(ft.Divider(height=4))
                sections.append(ft.Text("家具別（部屋 > 家具）", size=14, weight=ft.FontWeight.BOLD, color=ft.Colors.TEAL_700))
                for loc, cnt in loc_furniture.most_common(5):
                    pct = cnt / loc_len * 100
                    sections.append(ft.Row([
                        ft.Container(ft.Text(loc, size=12, expand=True, no_wrap=False), expand=True),
                        ft.Container(ft.Text(f"{cnt}件 {pct:.0f}%", size=11, color=ft.Colors.GREY_600)),
                    ]))
            if loc_combos:
                sections.append(ft.Divider(height=4))
                sections.append(ft.Text("ピンポイント（部屋 > 家具 > スポット）", size=14, weight=ft.FontWeight.BOLD, color=ft.Colors.TEAL_700))
                for loc, cnt in loc_combos.most_common(5):
                    pct = cnt / loc_len * 100
                    sections.append(ft.Row([
                        ft.Container(ft.Text(loc, size=11, expand=True, no_wrap=False), expand=True),
                        ft.Container(ft.Text(f"{cnt}件 {pct:.0f}%", size=10, color=ft.Colors.GREY_600)),
                    ]))

        self.analysis_container.controls = sections
        self.analysis_progress.visible = False
        self.page.update()

    def _navigate_cal(self, delta):
        self.cal_month += delta
        if self.cal_month > 12:
            self.cal_month = 1
            self.cal_year += 1
        elif self.cal_month < 1:
            self.cal_month = 12
            self.cal_year -= 1
        self.refresh_analysis()

    def _show_day_detail(self, date_str, day_records):
        if not day_records:
            self.page.show_snack_bar(ft.SnackBar(content=ft.Text(f"{date_str} の記録はありません")))
            return
        items_text = "\n".join(
            f"• {r['name']} ({r.get('location', '場所不明')})"
            for r in day_records
        )
        dlg = ft.AlertDialog(
            modal=True,
            title=ft.Text(f"{date_str} になくした物"),
            content=ft.Column([
                ft.Text(f"{len(day_records)}件の記録", size=13, color=ft.Colors.GREY_600),
                ft.Text(items_text, size=13),
            ], tight=True, spacing=8),
            actions=[ft.TextButton("閉じる", on_click=lambda e: setattr(dlg, 'open', False) or dlg.update())],
        )
        self.page.show_dialog(dlg)
