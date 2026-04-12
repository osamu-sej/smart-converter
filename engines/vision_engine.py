"""
Claude Vision エンジン（Phase 2）
PDF ページを画像化して Claude Vision API で読解する。
APIキーが必要。
"""


def convert_page_with_vision(page, api_key: str) -> str:
    """
    PDFページを画像化してClaude Visionで読解する。
    スライド型PDF・画像内の数値・図解に有効。

    Args:
        page: PyMuPDF の Page オブジェクト
        api_key: Anthropic API キー

    Returns:
        読解されたMarkdown文字列
    """
    # Phase 2 で実装
    raise NotImplementedError("Claude Vision エンジンは Phase 2 で実装予定です。")


def detect_page_strategy(page, pdf_path: str, page_num: int) -> str:
    """
    ページの特性を見てエンジンを自動選択する。

    実測値（西神奈川ZO）：
    - テキスト密度 0.001未満 → スライド型画像 → Vision推奨
    - 画像埋め込み多数 → Vision推奨
    - テキスト密度 0.01以上 → テキスト抽出OK

    Returns:
        'vision' / 'hybrid' / 'text'
    """
    text = page.get_text().strip()
    images = page.get_images()
    area = page.rect.width * page.rect.height
    density = len(text) / area if area > 0 else 0

    if density < 0.005 or len(images) > 3:
        return "vision"
    elif density < 0.02:
        return "hybrid"
    else:
        return "text"
