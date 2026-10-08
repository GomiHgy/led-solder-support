# LEDテープ はんだ付けサポート

非エンジニア・電子工作初心者向けの、作業ガイド＋写真レビュー用プロンプト出力ページです。
**はんだ付け → 覆う前に写真確認・修正 → 必要な電気的確認 → 絶縁・補強**の順で案内します。

対象は**定格DC 5V・12V・24VのLEDテープ・LEDリング**です。電源は製品の定格電圧と一致させます。5〜24Vの任意の電圧を使ってよいという意味ではありません。

## まず使う

完成済みの `index.html` をブラウザーで開いてください。外部ライブラリ・外部フォント・サーバー・APIキーは不要です。通常の利用にビルドやPythonは必要ありません。

ヘッダーの「言語」で次の9ロケールを選べます。ガイド、入力欄、操作結果、コピー・保存するAI用プロンプトも選択した言語に切り替わります。切り替えても入力した型番や相談内容、LEDの形・作業状態は保持します。

| ロケール | 選択欄の表示 | 言語 |
| --- | --- | --- |
| `ja` | 日本語 | 日本語 |
| `en` | English | 英語 |
| `zh` | 简体中文 | 中国語（簡体字） |
| `zh-TW` | 繁體中文 | 中国語（台湾繁体字） |
| `es` | Español | スペイン語 |
| `de` | Deutsch | ドイツ語 |
| `fr` | Français | フランス語 |
| `ko` | 한국어 | 韓国語 |
| `pt` | Português | ポルトガル語 |

簡体字中国語のロケールコードは、以前の `zh-CN` から `zh` へ統一しています。

「表示テーマ」は自動・ライト・ダークから選べます。自動では端末の配色設定に追従します。印刷時はライト配色になります。言語・テーマの選択は保存せず、ページを開き直すと日本語・自動に戻ります。

1. 作業前の注意点を確認します。
2. 「AI用プロンプトをコピー」を押します。任意でLEDの形、作業状態、型番・電圧、気になる点を追記できます。
3. 画像入力対応AIのチャットへ貼り付け、はんだ付け後・覆う前の写真を同じチャットに送ります。
4. 必要な修正と確認を行い、そのあとに絶縁・補強へ進みます。

AIモデルは画像入力対応のものを使用します。特定のモデル名には依存しません。推論レベルを選択できる場合は「高」が目安です。推論レベルを高くしても、不鮮明な写真を推測で補ってよいわけではありません。

このページに画像のアップロード先・AI解析機能はありません。別のAIへ渡す依頼文を作るツールです。AIサービス側での画像や入力内容の取り扱いは、利用者がそのサービスの設定・規約を確認してください。

## 今回の重要な変更（v1.3）

9ロケールすべてで、切断済みLEDテープの端子を識別するルールを更新しました。切断端で「GND」の末尾の「D」だけが残る場合、その一文字をデータ端子と決めつけず、同じテープの隣のLED区画・次の切断位置の完全な印字、対応するパッド位置、見える配線パターンを照合します。

WS2812B系・SK6812系の一般的な5V・3パッドのテープでは、GND–データ–+5V（入力側ならGND–DIN–+5V）を候補にします。回転・表裏・鏡像や製品ごとの基板設計を考慮し、実物の印字・製品資料を優先します。中央がデータ端子であることと、DIN／DOUTの判別を分け、矢印と信号方向を確認します。チップのピン配列をテープのパッド配列として流用しません。

隣の区画が上側GND・下側+5Vで、同じ向きの接合部が上から黒・黄・赤なら、黒＝GND、黄＝データ、赤＝+5Vという推定を根拠とともに示す例を追加しました。線の色を他の写真の役割判定へ固定して使わず、写真外の配線先・測定が必要な導通や短絡とは区別します。印字の欠けや色だけを理由に配線交換を勧めません。

入力／出力と矢印の関係は [AdafruitのNeoPixelはんだ付けガイド](https://learn.adafruit.com/make-it-glow-how-to-solder-neopixels-a-beginners-guide/soldering-strips) を確認しました（2026年10月8日）。切断端の欠けた印字を隣の区画と照合するルールは、今回提示された写真の誤認事例への対策です。実際の画像対応AIの再判定結果は未検証です。[端子判定の回帰確認ケース](tests/terminal_mapping_cases.md) に期待する応答と未実施の確認を記録しています。

### 維持している機能と確認順序

EdelWorksの提供ロゴ原本を使用し、対象電圧を明記しました。ダークモードと9ロケールの切り替えに対応しています。各言語のプロンプトは同じ確認手順・安全ルールを維持し、選択した言語でAIへ返答を依頼します。

熱収縮チューブ・接着剤・樹脂・テープなどで接合部を覆うのは、写真での外観確認と必要な修正のあとです。補強前の写真を接合不良と判定したり、「先にチューブで覆ってから撮影」と誘導したりしないルールを最優先で追加しました。

構造上あとから通せないチューブは、必要な場合だけ事前に線やテープへ通して待避できます。確認前に接合部を覆ったり、収縮させたりはしません。すでに覆われている場合は、覆う前の写真があればそれを使い、撮影だけのために無理に剥がしません。

絶縁・補強は接合不良を隠して直す方法ではありません。外観が良好でも電気的接続・強度・耐久性・通電の安全は保証しません。点灯前には製品の定格・極性・配線・絶縁などを別途確認します。

## GitHub Pagesで公開する

新しい公開用リポジトリを作るか、既存の公開用リポジトリを使います。既存サイトの `index.html` を意図せず上書きしないよう注意してください。

1. ZIPを展開し、`led-solder-support` フォルダーの**中身**をリポジトリのルートへ置きます。公開に最低限必要なのは `index.html` と `.nojekyll` です。
2. GitHubのリポジトリで **Settings → Pages** を開きます。
3. **Build and deployment → Source → Deploy from a branch** を選びます。
4. ブランチを `main`（または公開したいブランチ）、フォルダーを **/(root)** にして保存します。
5. デプロイ完了後、Pagesの設定に表示されるURLを開きます。

配布したHTMLは生成済みなので、GitHub Actionsで独自のビルド処理を設定する必要はありません。サイト本体に外部ファイルへの参照がないため、プロジェクトのサブパスでも動作する構成です。

GitHub公式の公開手順（2026年10月7日確認）：
https://docs.github.com/en/pages/getting-started-with-github-pages/configuring-a-publishing-source-for-your-github-pages-site

公開設定・公開URLでの動作確認は、この説明書の検証範囲に含めていません。実際の配信状態はGitHub Pages側で確認してください。

## ファイル構成

```text
index.html                         完成済みの単一HTML（CSS・JS・ロゴ・9ロケール内蔵）
.nojekyll                          静的ファイルとして公開するための指定
README.md                          この説明書
build.py                           Python標準ライブラリのみの生成スクリプト
src/index.template.html            画面・CSS・JavaScriptの編集元
src/locales.json                   対応ロケール・表示名・選択順序の共通定義
src/translations/*.json            日本語以外の8ロケールのUI翻訳辞書
assets/edelworks_logo_origin.png   提供されたロゴ原本（ビルドでHTMLへ埋め込み）
prompts/led_solder_review_ja.txt    写真レビュー用プロンプトの編集元
prompts/led_solder_review_en.txt    英語版プロンプト
prompts/led_solder_review_zh.txt    簡体字中国語版プロンプト
prompts/led_solder_review_zh-TW.txt 台湾繁体字中国語版プロンプト
prompts/led_solder_review_es.txt    スペイン語版プロンプト
prompts/led_solder_review_de.txt    ドイツ語版プロンプト
prompts/led_solder_review_fr.txt    フランス語版プロンプト
prompts/led_solder_review_ko.txt    韓国語版プロンプト
prompts/led_solder_review_pt.txt    ポルトガル語版プロンプト
tests/check_static.py             ビルドとHTMLの基本チェック
tests/check_browser.py            Chromiumでの表示・操作チェック
tests/check_browser_cdp.mjs       Node標準APIのみのChromium表示・操作チェック
tests/terminal_mapping_cases.md   画像対応AIで確認する端子判定の回帰ケース
TEST_REPORT.md                     納品時の確認範囲と制限
```

## 編集する

プロンプトは `prompts/led_solder_review_*.txt` の各言語版を、画面・スタイル・動作は `src/index.template.html` を変更します。UIの日本語文を変更した場合は `src/translations/*.json` の原文キーと8ロケールの訳も合わせて更新し、次を実行します。

```sh
python build.py
python tests/check_static.py
```

`index.html` が更新されます。Python 3.9以降を使用してください。編集後は再生成した `index.html` もコミットしてください。完成HTMLへの直接編集もできますが、次のビルドで上書きされます。

各言語のプロンプト、翻訳辞書、ロケール定義、ロゴ画像は `build.py` がHTMLへ埋め込みます。言語の選択欄も `src/locales.json` から生成するため、画面と内部のロケール一覧を手作業で同期する必要はありません。日本語の固定プロンプトは、JavaScript無効時にも読めるテキスト欄へ同じ原本から埋め込みます。完成HTMLを配布・公開する際に、`assets/` や `src/` を一緒に配信する必要はありません。

ローカルHTTPサーバーで確認する場合：

```sh
python -m http.server 8000
```

ブラウザーで `http://localhost:8000/` を開きます。

## コピー・保存について

コピーはClipboard APIを試し、利用できなければ互換コピーを試します。両方失敗した場合は全文を表示して選択し、手動コピーを案内します。HTTPS公開時でも、ブラウザー・埋め込み先・権限設定によって自動コピーを使えない場合があります。

「テキストで保存」は、入力した状況も含む依頼文をUTF-8（BOM付き）で保存します。ファイル名は選択言語に合わせた `led-solder-review-<ロケール>.txt` です。例：`led-solder-review-ja.txt`、`led-solder-review-zh.txt`、`led-solder-review-zh-TW.txt`。

JavaScriptが無効な場合も日本語の固定プロンプトの全文は読めますが、言語・テーマの切り替え、状況の自動追記・自動コピー・保存は動作しません。端末設定に応じたダーク配色はJavaScriptなしでも適用されます。

## データの扱い

アプリはフォーム内容をサーバーへ送信しません。画像の受け取り、API呼び出し、解析タグ、Cookie、localStorageを使用していません。入力欄には `autocomplete="off"` を指定していますが、ブラウザー側のフォーム復元までは制御しません。

公開サイトへのアクセスログは配信サービス側で扱われる場合があります。コピー後に利用者がAIへ送信する情報は、このページとは別のサービスで処理されます。

## ブラウザーのテスト（開発者向け・任意）

Node.js 18以降とインストール済みのChromiumを使う場合は、追加パッケージなしで実行できます。WindowsではPlaywrightのChromiumキャッシュ、続いて標準配置のGoogle Chromeを探します。別の場所にあるブラウザーは `--browser` で指定してください。

```sh
node tests/check_browser_cdp.mjs --screenshots tests/artifacts/cdp
```

```sh
node tests/check_browser_cdp.mjs --browser "C:/path/to/chrome.exe" --screenshots tests/artifacts/cdp
```

CDP版はローカルHTMLをブラウザーへ直接読み込み、9ロケール・3テーマ・7画面幅の189条件、コピー経路、9ロケールのダウンロード、JavaScript無効時の表示を確認します。検証レポート、各ロケールのスクリーンショット、ダウンロードしたテキストを指定先へ保存します。

PythonとPlaywrightを使う場合：

```sh
python -m pip install playwright
python -m playwright install chromium
python tests/check_browser.py
```

既存のChromium実行ファイルを指定する場合：

```sh
python tests/check_browser.py --browser /usr/bin/chromium
```

通常は完成HTMLをブラウザーに直接読み込ませてテストします。実際のHTTP配信も含める場合は、別の端末でローカルサーバーを起動してから実行します。

```sh
python tests/check_browser.py --url http://localhost:8000/index.html
```

クリップボードの成功・権限拒否は、権限に依存しないようテスト内でAPIを置き換えて確認します。OSのクリップボードまで書き込めることを保証するテストではありません。公開後は実際の端末でもコピー・貼り付けを確認してください。

## 公開前に確認すること

スマートフォンの実機、利用するAIへの貼り付け、良好・短絡・ピンぼけ・補強前・被覆済みの写真での返答を確認してください。今回のテストはWebページの表示・操作とプロンプト内容が対象で、写真レビューAIの正答率を評価したものではありません。


基本事項の参考にしたメーカー・開発元の資料は、ページ下部の「参考資料・ガイドの範囲」から開けます。特定製品の電圧・配線は、その製品の資料を優先します。
