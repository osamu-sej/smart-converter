"""
MarkItDown エンジン
PPTX / DOCX / 画像ファイルの変換に使用。
OpenDataLoader より PPTX/DOCX の精度が高い。
"""


def convert_with_markitdown(input_path: str) -> str:
    """
    MarkItDownでファイルをMarkdownに変換する。
    PPTX / DOCX / 画像ファイルに対して高精度な変換が可能。

    Args:
        input_path: 変換元ファイルのパス

    Returns:
        変換されたMarkdown文字列
    """
    try:
        from markitdown import MarkItDown
    except ImportError:
        raise ImportError(
            "markitdown がインストールされていません。\n"
            'pip install "markitdown[all]" を実行してください。'
        )

    md = MarkItDown()
    result = md.convert(input_path)
    return result.text_content or ""


def extract_text_pymupdf(pdf_path: str) -> str:
    """
    PyMuPDF (fitz) でPDFのテキストを抽出する。
    OpenDataLoaderの補完として使用。
    テキストが多いページに有効。

    Args:
        pdf_path: PDFファイルのパス

    Returns:
        抽出されたMarkdown文字列
    """
    try:
        import fitz
    except ImportError:
        raise ImportError(
            "pymupdf がインストールされていません。\n"
            "pip install pymupdf を実行してください。"
        )

    doc = fitz.open(pdf_path)
    sections = []

    for page_num, page in enumerate(doc, 1):
        text = page.get_text().strip()
        if text:
            sections.append(f"## Page {page_num}\n\n{text}")

    doc.close()
    return "\n\n".join(sections)


def merge_extraction_results(primary: str, secondary: str) -> str:
    """
    2つの抽出結果をマージする。
    primaryが十分な量を持っている場合はそのまま返す。
    primaryが貧弱な場合はsecondaryで補完する。

    Args:
        primary: メイン抽出結果（OpenDataLoader等）
        secondary: 補完抽出結果（PyMuPDF等）

    Returns:
        マージされたMarkdown文字列
    """
    primary_chars = len(primary.strip())
    secondary_chars = len(secondary.strip())

    # primaryが十分あればそのまま使う
    if primary_chars >= 500:
        return primary

    # primaryが貧弱でsecondaryが充実している場合は補完
    if secondary_chars > primary_chars:
        if primary_chars > 0:
            return primary + "\n\n---\n\n## PyMuPDF 補完抽出\n\n" + secondary
        return secondary

    return primary
