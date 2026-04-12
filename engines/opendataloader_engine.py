"""
OpenDataLoader エンジン
メイン変換エンジン。PDF → Markdown変換に使用。
Apache 2.0ライセンス（商用・配布完全OK）
実証済み：西神奈川ZO報告書（8ページ・複雑表）で重要データ7/7全項目取得確認済み。
"""

import os
import tempfile


def convert_with_opendataloader(input_path: str, output_dir: str) -> str:
    """
    PDFをMarkdownに変換する。

    Args:
        input_path: 変換元ファイルのパス（PDF）
        output_dir: Markdownファイルと画像の出力先ディレクトリ

    Returns:
        変換されたMarkdown文字列。失敗時は空文字列。
    """
    try:
        from opendataloader_pdf import convert
    except ImportError:
        raise ImportError(
            "opendataloader-pdf がインストールされていません。\n"
            "pip install opendataloader-pdf を実行してください。"
        )

    os.makedirs(output_dir, exist_ok=True)
    convert(
        input_path,
        output_dir=output_dir,
        format='markdown',
        quiet=True
    )

    base = os.path.splitext(os.path.basename(input_path))[0]
    md_path = os.path.join(output_dir, base + '.md')
    if os.path.exists(md_path):
        with open(md_path, 'r', encoding='utf-8') as f:
            return f.read()
    return ""


def convert_file_with_opendataloader(input_path: str) -> tuple[str, str]:
    """
    一時ディレクトリを作成してファイルをMarkdownに変換する。
    画像ファイルも保持するため、呼び出し元が output_dir を管理する。

    Args:
        input_path: 変換元ファイルのパス

    Returns:
        (markdown文字列, 出力ディレクトリパス)
        ※ output_dir は呼び出し元が cleanup_temp_dir() で削除すること
    """
    output_dir = tempfile.mkdtemp(prefix="smart_converter_")
    markdown = convert_with_opendataloader(input_path, output_dir)
    return markdown, output_dir
