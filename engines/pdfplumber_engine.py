"""
pdfplumber エンジン
表抽出補完エンジン。OpenDataLoaderで取りこぼした表の補完に使用。
"""


def extract_tables_pdfplumber(pdf_path: str) -> list[str]:
    """
    pdfplumberで表を抽出してMarkdown形式に変換。

    Args:
        pdf_path: PDFファイルのパス

    Returns:
        Markdown形式の表文字列リスト
    """
    try:
        import pdfplumber
    except ImportError:
        raise ImportError(
            "pdfplumber がインストールされていません。\n"
            "pip install pdfplumber を実行してください。"
        )

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


def merge_tables_into_markdown(markdown: str, tables: list[str]) -> str:
    """
    pdfplumberで抽出した表をMarkdownの末尾に追加する。

    Args:
        markdown: ベースのMarkdown文字列
        tables: Markdown形式の表文字列リスト

    Returns:
        表を追加したMarkdown文字列
    """
    if not tables:
        return markdown

    appended = markdown.rstrip()
    appended += "\n\n---\n\n## 補完抽出テーブル（pdfplumber）\n\n"
    appended += "\n\n".join(tables)
    return appended
