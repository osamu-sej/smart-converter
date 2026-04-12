"""
Pandoc エンジン
Markdown → DOCX / PPTX / PDF 変換に使用。
事前に pandoc のインストールが必要: sudo apt-get install pandoc
実証済み：docx・pptx変換OK確認済み。
"""

import os
import subprocess
import tempfile


SUPPORTED_FORMATS = ["docx", "pptx", "pdf"]


def is_pandoc_available() -> bool:
    """pandoc がインストールされているか確認する。"""
    try:
        result = subprocess.run(
            ["pandoc", "--version"],
            capture_output=True,
            text=True,
            timeout=10
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def convert_markdown_to_file(markdown: str, output_format: str, output_path: str) -> bool:
    """
    PandocでMarkdownを各種形式に変換する。

    Args:
        markdown: 変換元のMarkdown文字列
        output_format: 出力形式（'docx', 'pptx', 'pdf'）
        output_path: 出力ファイルのパス

    Returns:
        変換成功時はTrue、失敗時はFalse
    """
    if output_format not in SUPPORTED_FORMATS:
        raise ValueError(f"未対応の出力形式: {output_format}。対応形式: {SUPPORTED_FORMATS}")

    if not is_pandoc_available():
        raise RuntimeError(
            "pandoc がインストールされていません。\n"
            "sudo apt-get install pandoc を実行してください。"
        )

    with tempfile.NamedTemporaryFile(
        mode='w', suffix='.md', delete=False, encoding='utf-8'
    ) as f:
        f.write(markdown)
        tmp_path = f.name

    try:
        result = subprocess.run(
            ['pandoc', tmp_path, '-o', output_path],
            capture_output=True,
            text=True,
            timeout=60
        )
        if result.returncode != 0:
            raise RuntimeError(
                f"pandoc エラー (exit {result.returncode}):\n{result.stderr}"
            )
        return True
    finally:
        os.unlink(tmp_path)


def convert_markdown_to_bytes(markdown: str, output_format: str) -> bytes:
    """
    PandocでMarkdownを変換し、バイト列で返す。
    Streamlitのダウンロードボタン用。

    Args:
        markdown: 変換元のMarkdown文字列
        output_format: 出力形式（'docx', 'pptx', 'pdf'）

    Returns:
        変換されたファイルのバイト列
    """
    suffix_map = {"docx": ".docx", "pptx": ".pptx", "pdf": ".pdf"}
    suffix = suffix_map[output_format]

    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as out_f:
        out_path = out_f.name

    try:
        convert_markdown_to_file(markdown, output_format, out_path)
        with open(out_path, 'rb') as f:
            return f.read()
    finally:
        if os.path.exists(out_path):
            os.unlink(out_path)
