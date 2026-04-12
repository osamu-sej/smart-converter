# SmartConverter - Claude Code 引き継ぎ文書

## プロジェクト概要

PDF / PPTX / DOCX / 画像ファイルをMarkdownに変換し、
Claude APIで内容改善後、PPTX / DOCX / Excelに出力するオールインワンツール。

**開発者：** Osamu（セブンイレブン・ジャパン OP情報部）  
**リポジトリ：** osamu-sej/smart-converter  
**フロントエンド：** Streamlit（Python）

---

## 設計思想

### 2トラック構成（1アプリで実現）

ユーザーがサイドバーのチェックボックスで機能をON/OFFする。
APIキーを持っている人は最強モード、持っていない人はそのまま無料モードで動く。
配布は1本で済む。

```
【無料モード（デフォルト）】
OpenDataLoader + pdfplumber → Markdown → Pandoc出力

【有料モード（オプション追加）】
+ Claude Vision API → 画像・スキャンの完全読解
+ Claude API       → Markdownの内容改善・整理
+ PaddleOCR-VL     → スキャンPDFの高精度OCR
```

---

## 技術スタック

### 変換エンジン（優先順位順）

| エンジン | 役割 | 費用 | 備考 |
|---------|------|------|------|
| OpenDataLoader | メイン変換エンジン | 無料 | 常時ON・最優先 |
| pdfplumber | 表抽出補完 | 無料 | 常時ON |
| Claude Vision API | 画像・図・スキャン読解 | 有料 | APIキー必要 |
| PaddleOCR-VL 0.9B | スキャンPDF OCR | 無料 | 初回モデルDL必要 |

### 出力エンジン
- **Pandoc**：Markdown → DOCX / PPTX / PDF変換（インストール済み前提）
- **python-pptx**：PPTXの高品質出力

---

## 実証済み動作コード（そのまま使える）

### OpenDataLoader（メイン変換）

```python
from opendataloader_pdf import convert
import os

def convert_with_opendataloader(input_path: str, output_dir: str) -> str:
    """
    PDFをMarkdownに変換する。
    実ファイル検証済み：西神奈川ZO報告書（8ページ・複雑表）で
    重要データ7/7全項目取得確認済み。
    """
    os.makedirs(output_dir, exist_ok=True)
    convert(
        input_path,
        output_dir=output_dir,
        format='markdown',
        quiet=True
    )
    # 出力ファイルを探して返す
    base = os.path.splitext(os.path.basename(input_path))[0]
    md_path = os.path.join(output_dir, base + '.md')
    if os.path.exists(md_path):
        with open(md_path, 'r') as f:
            return f.read()
    return ""
```

### pdfplumber（表抽出補完）

```python
import pdfplumber

def extract_tables_pdfplumber(pdf_path: str) -> list:
    """
    pdfplumberで表を抽出してMarkdown形式に変換。
    OpenDataLoaderで取りこぼした表の補完に使う。
    """
    tables_md = []
    with pdfplumber.open(pdf_path) as pdf:
        for page_num, page in enumerate(pdf.pages, 1):
            tables = page.extract_tables()
            for table in tables:
                if not table or not table[0]:
                    continue
                rows = []
                for i, row in enumerate(table):
                    cells = [str(c or '').replace('\n', ' ').strip() for c in row]
                    rows.append('| ' + ' | '.join(cells) + ' |')
                    if i == 0:
                        rows.append('|' + '|'.join(['---'] * len(row)) + '|')
                tables_md.append(f"<!-- P.{page_num} 表 -->\n" + '\n'.join(rows))
    return tables_md
```

### Claude Vision API（画像・スキャン読解）

```python
import anthropic
import base64
import fitz  # pymupdf

def convert_page_with_vision(page, api_key: str) -> str:
    """
    PDFページを画像化してClaude Visionで読解。
    スライド型PDF・画像内の数値・図解に有効。
    """
    client = anthropic.Anthropic(api_key=api_key)
    mat = fitz.Matrix(2.0, 2.0)  # 2x高解像度
    pix = page.get_pixmap(matrix=mat)
    img_b64 = base64.standard_b64encode(pix.tobytes("png")).decode()

    response = client.messages.create(
        model="claude-opus-4-5",
        max_tokens=2000,
        messages=[{
            "role": "user",
            "content": [
                {
                    "type": "image",
                    "source": {"type": "base64", "media_type": "image/png", "data": img_b64}
                },
                {
                    "type": "text",
                    "text": """このページの内容をMarkdown形式で完全に抽出してください。
ルール：
- 全テキストを抽出（見出し・本文・注記・ラベルすべて）
- 表はMarkdown表（| 列 | 列 |）で正確に再現
- グラフ・チャートは数値・凡例・軸ラベルをリスト形式で抽出
- 図解・フロー図はテキストで構造を表現
- ページ区切りは ## Page N で表現
- 日本語はそのまま日本語で出力
- 余分なコメント不要、内容のみ出力"""
                }
            ]
        }]
    )
    return response.content[0].text
```

### Pandoc出力（Markdown → DOCX/PPTX/PDF）

```python
import subprocess
import tempfile
import os

def convert_markdown_to_file(markdown: str, output_format: str, output_path: str) -> bool:
    """
    PandocでMarkdownを各種形式に変換。
    output_format: 'docx', 'pptx', 'pdf'
    実証済み：docx・pptx変換OK確認済み。
    """
    with tempfile.NamedTemporaryFile(mode='w', suffix='.md',
                                     delete=False, encoding='utf-8') as f:
        f.write(markdown)
        tmp_path = f.name

    try:
        result = subprocess.run(
            ['pandoc', tmp_path, '-o', output_path],
            capture_output=True, text=True, timeout=60
        )
        return result.returncode == 0
    finally:
        os.unlink(tmp_path)
```

---

## ページ種別の自動判定ロジック

```python
import fitz

def detect_page_strategy(page, pdf_path: str, page_num: int) -> str:
    """
    ページの特性を見てエンジンを自動選択する。
    
    実測値（西神奈川ZO）：
    - テキスト密度 0.001未満 → スライド型画像 → Vision推奨
    - 画像埋め込み多数 → Vision推奨
    - テキスト密度 0.01以上 → テキスト抽出OK
    """
    text = page.get_text().strip()
    images = page.get_images()
    area = page.rect.width * page.rect.height
    density = len(text) / area if area > 0 else 0

    if density < 0.005 or len(images) > 3:
        return "vision"      # Claude Vision推奨
    elif density < 0.02:
        return "hybrid"      # OpenDataLoader + Vision
    else:
        return "text"        # OpenDataLoader のみでOK
```

---

## 既知の制約・注意点

### OpenDataLoader
- `pip install opendataloader-pdf` で即動作（モデルDL不要）
- Apache 2.0ライセンス（商用・配布完全OK）
- 画像参照は `![image N](xxx_images/imageFileN.png)` 形式で出力される
- 画像ファイルは `出力ディレクトリ/元ファイル名_images/` に保存される

### PaddleOCR-VL
- `pip install paddleocr paddlepaddle` でインストール可能
- **初回起動時にHuggingFaceからモデルDL（約0.9GB）が必要**
- Codespaces環境ではHuggingFaceへのアクセスがブロックされる場合あり
- その場合はModelScopeからのDLを試す
- GPU推奨だがCPUでも動作可能（低速）

### Claude Vision API
- `anthropic` パッケージが必要
- モデル：`claude-opus-4-5`（最高精度）または `claude-haiku-4-5-20251001`（高速・安価）
- PDF直接送信は `anthropic-beta: pdfs-2024-09-25` ヘッダーが必要
- ページを画像化してから送る方法が確実

### Pandoc
- Codespacesには未インストールの場合あり
- インストール：`sudo apt-get install pandoc`
- PPTX出力は構造は正しいがデザインはシンプル

### MarkItDown（参考・今回は補助的に使用）
- `pip install "markitdown[all]"` でインストール済み
- スライド型PDFには限界あり（テキストは取れるが表・画像は弱い）
- OCRプラグイン：`markitdown-ocr`（`register_converter`で登録）

---

## ファイル構成（推奨）

```
smart-converter/
├── app.py                 # Streamlitメインアプリ
├── requirements.txt       # 依存パッケージ
├── CLAUDE.md             # このファイル（Claude Code設定）
├── .env.example          # APIキーのサンプル（実際の.envはgitignore）
├── engines/
│   ├── __init__.py
│   ├── opendataloader_engine.py   # OpenDataLoader変換
│   ├── pdfplumber_engine.py       # 表抽出補完
│   ├── vision_engine.py           # Claude Vision
│   ├── paddleocr_engine.py        # PaddleOCR-VL
│   └── pandoc_engine.py           # 出力変換
├── utils/
│   ├── __init__.py
│   ├── file_utils.py              # ファイル操作
│   └── markdown_utils.py          # Markdown整形
└── tests/
    └── test_engines.py            # 各エンジンのテスト
```

---

## requirements.txt（確認済みパッケージ）

```
streamlit
opendataloader-pdf
pdfplumber
pymupdf
pdfplumber
anthropic
markitdown[all]
markitdown-ocr
python-pptx
pillow
```

---

## Streamlit UIの設計仕様

### サイドバー（設定）
```
📁 ファイルアップロード
   対応形式: PDF / PPTX / DOCX / JPG / PNG

🔧 変換エンジン設定
   [✅] OpenDataLoader（無料・常時有効）
   [✅] pdfplumber 表抽出補完（無料）
   [ ] Claude Vision（APIキー必要）
   [ ] PaddleOCR-VL（初回モデルDL必要）

🤖 AI改善設定
   [ ] Claude APIで内容改善
   
🔑 Anthropic API Key
   [入力欄]（未入力時は無料機能のみ）

📤 出力形式
   [✅] Markdown
   [ ] Word (.docx)
   [ ] PowerPoint (.pptx)
   [ ] PDF
```

### メインエリア
- 変換進捗バー
- Markdownプレビュー（タブ切替：ソース / レンダリング）
- ダウンロードボタン
- エンジン別取得結果の比較表示（デバッグ用）

---

## 開発優先順位

1. **Phase 1（まず動かす）**
   - OpenDataLoader + pdfplumber でPDF→Markdown変換
   - Streamlit基本UI
   - Pandocでダウンロード

2. **Phase 2（精度向上）**
   - Claude Vision API連携
   - ページ種別自動判定ロジック

3. **Phase 3（オプション）**
   - PaddleOCR-VL連携
   - Claude APIによるMarkdown改善

---

## テスト用ファイル情報

今日の検証で使ったファイル（精度確認済み）：
- `_秘B_25年12月_AIカウンセリング分析活用報告_西神奈川__1.pdf`
  - 8ページ・スライド型・複雑表あり・画像多数
  - OpenDataLoaderで重要データ7/7取得確認済み
- `セッション資料_マスクドアナライズ.pdf`
  - 26ページ・スライド型・テキスト少なめ
- `Gemini_Generated_Image_.png`
  - 画像のみ → Visionなしでは0文字

---

## 最初にClaude Codeに指示すること

```
このCLAUDE.mdを読んで内容を把握してください。
その後、Phase 1から開発を始めてください。

まず以下を作成してください：
1. requirements.txt
2. engines/ ディレクトリと各エンジンファイルの雛形
3. app.py（Streamlit基本UI）

動作確認はサンプルPDFで行います。
```
