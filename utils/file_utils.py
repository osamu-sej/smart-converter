"""
ファイル操作ユーティリティ
"""

import os
import shutil
import tempfile


SUPPORTED_EXTENSIONS = {".pdf", ".pptx", ".docx", ".jpg", ".jpeg", ".png"}


def get_file_extension(filename: str) -> str:
    """ファイル名から拡張子を小文字で返す。"""
    return os.path.splitext(filename)[1].lower()


def is_supported_file(filename: str) -> bool:
    """対応フォーマットのファイルか確認する。"""
    return get_file_extension(filename) in SUPPORTED_EXTENSIONS


def save_uploaded_file(uploaded_file) -> str:
    """
    Streamlit の UploadedFile を一時ファイルに保存する。

    Args:
        uploaded_file: streamlit.runtime.uploaded_file_manager.UploadedFile

    Returns:
        保存された一時ファイルのパス
    """
    ext = get_file_extension(uploaded_file.name)
    with tempfile.NamedTemporaryFile(
        suffix=ext, delete=False
    ) as tmp:
        tmp.write(uploaded_file.getbuffer())
        return tmp.name


def cleanup_temp_dir(dir_path: str) -> None:
    """一時ディレクトリを削除する。"""
    if os.path.exists(dir_path):
        shutil.rmtree(dir_path)
