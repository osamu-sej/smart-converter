"""
PaddleOCR-VL エンジン（Phase 3）
スキャンPDFの高精度OCR。
初回起動時にHuggingFaceからモデルDL（約0.9GB）が必要。
"""


def convert_with_paddleocr(image_path: str) -> str:
    """
    PaddleOCR-VLで画像からテキストを抽出する。

    Args:
        image_path: 画像ファイルのパス

    Returns:
        抽出されたテキスト文字列
    """
    # Phase 3 で実装
    raise NotImplementedError("PaddleOCR エンジンは Phase 3 で実装予定です。")
