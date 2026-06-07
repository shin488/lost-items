# なくしもの探知機

Flet Web アプリ（Pyodide / GitHub Pages デプロイ）

## 重要: 命令形API必須
宣言的API (`@ft.component` + `page.render()`) は Pyodide で動かない。
必ず命令形API (`def main(page):` + `page.add()` + `page.update()`) を使う。

## 構成
- `main.py` — 全実装（命令形API, ft.Tabs + TabBar + TabBarView パターン）
- `.github/workflows/deploy.yml` — GitHub Actions 自動デプロイ
- `requirements.txt`: `flet>=0.85.0`
- storage key: `lost_items_v4`

## 使用Flet機能
- `ft.Tabs` + `ft.TabBar` + `ft.TabBarView` (Materialタブ)
- `ft.AppBar` (タイトルバー + Export/Import)
- `ft.Ref[ft.TextField]()` (リファレンスによる制御)
- `ft.Theme` + `ft.ColorScheme` (色テーマ)
- `ft.ProgressBar` (分析ローディング)
- `ft.SafeArea` (モバイルセーフエリア対応)
- `ft.Card` + `ft.ListTile` (履歴・ランキング表示)
- `ft.AlertDialog` + `ft.SnackBar` (ダイアログ)
- `page.client_storage` (データ永続化)
- `ft.Colors`, `ft.Icons`, `ft.FontWeight` など

## 最終状態
- 白画面バグ修正済み
- `ft.Tabs` + `ft.AppBar` + `ft.Ref` + `ft.Theme` + `ft.ProgressBar` + `ft.SafeArea` を追加
- **次回: プッシュ後 https://shin488.github.io/lost-items/ を確認**
