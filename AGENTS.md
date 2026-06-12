# なくしもの探知機

Flet Web アプリ（Pyodide / GitHub Pages デプロイ）

## 重要: 命令形API必須
宣言的API (`@ft.component` + `page.render()`) は Pyodide で動かない。
必ず命令形API (`def main(page):` + `page.add()` + `page.update()`) を使う。

## 警告: 白画面の原因（絶対にやること）
Flet 0.85.2 では以下の操作が**存在しないキーワード引数**で `TypeError` を起こし、白画面になる：

### ❌ 禁止
- `Column(bgcolor=...)` — Column/Row に bgcolor は存在しない
- `TabBar(bgcolor=...)`
- `TabBarView(bgcolor=...)`
- `SafeArea(bgcolor=...)`
- `page.bgcolor = ...` — Pageにも存在しない
- `page.window.title_bar_buttons_hidden = True` — Web/Pyodide未対応
- `ft.NavigationBar` / `ft.Dismissible` — Web/Pyodideで不具合多数

### ✅ 許可（安全）
- `ft.Container(bgcolor=...)` — Containerのみ bgcolor を持つ
- `ft.AppBar(bgcolor=...)`
- `ft.Card(margin=..., elevation=...)`

### テーマで背景色を変える方法
`page.theme = ft.Theme(color_scheme=ft.ColorScheme(surface=...))`
→ `surface` を変えれば TabBarView などの背景色も変わる。

## 構成
- `main.py` — 全実装（命令形API, TabBar + TabBarView パターン）
- `.github/workflows/deploy.yml` — GitHub Actions 自動デプロイ（`flet build web` → `scripts/patch-pwa.sh`）
- `pwa/manifest.json` — PWAマニフェスト（テーマカラー#00695C）
- `pwa/service-worker.js` — PWAキャッシュSW（プリキャッシュ＋stale-while-revalidate）
- `scripts/patch-pwa.sh` — ビルド後パッチ（manifest/SW/index.htmlにPWAメタタグ注入）
- `requirements.txt`: `flet==0.85.2`
- storage key: `lost_items_v4`（localStorage直接保存）

## 使用Flet機能（実際に動作確認済み）
- `ft.Tabs` + `ft.TabBar` + `ft.TabBarView`
- `ft.AppBar` (タイトルバー + Export/Import)
- `ft.Ref[ft.TextField]()` (リファレンスによる制御)
- `ft.Theme` + `ft.ColorScheme` (色テーマ)
- `ft.ProgressBar` (分析ローディング)
- `ft.SafeArea` (モバイルセーフエリア)
- `ft.Card` + `ft.ListTile` + `elevation`
- `ft.Container(bgcolor=...)` (背景色)
- `ft.AlertDialog` + `ft.SnackBar`
- `js.window.localStorage`（データ永続化、フォールバック: page.client_storage）

## PWA
- manifest.json: テーマカラー#00695C、表示モードstandalone、アイコン5種類
- Service Worker: プリキャッシュ（app shell）+ stale-while-revalidate
- iOS: apple-mobile-web-app-capable, black-translucent, 各種touch-icon（180/152/120/76）
- アイコンはFletデフォルト（Flutterロゴ） — 差し替えたい場合は `build/web/icons/` のPNGを上書き
- `scripts/patch-pwa.sh` が `flet build web` 後にPWA関連ファイルを注入

## 最終状態
- 森テーマ（深緑GREEN_800 / アースブラウンBROWN_700）
- 白画面対策：Containerのみbgcolor、Column/TabBar/TabBarView/Pageには設定しない
- **次回: プッシュ後 https://shin488.github.io/lost-items/ を確認**
