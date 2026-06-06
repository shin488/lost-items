# なくしもの探知機

Flet Web アプリ（Pyodide / GitHub Pages デプロイ）

## 重要: 命令形API必須
宣言的API (`@ft.component` + `page.render()`) は Pyodide で動かない。
必ず命令形API (`def main(page):` + `page.add()` + `page.update()`) を使う。

## 構成
- `main.py` — 全実装（命令形API, TabBar+TabBarView パターン）
- `.github/workflows/deploy.yml` — GitHub Actions 自動デプロイ
- `requirements.txt`: `flet>=0.85.0`
- storage key: `lost_items_v4`

## 最終状態
- `main.py` を命令形APIに書き換え・ビルド成功・プッシュ済み (ccb5f1d)
- 白画面バグ修正のデプロイが GitHub Actions で進行中
- **次回: https://shin488.github.io/lost-items/ を確認し、3タブ表示されるか検証**
