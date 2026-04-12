"""
Markdown 整形ユーティリティ
"""

import base64
import io
import os
import re


def clean_markdown(markdown: str) -> str:
    """3行以上連続する空白行を2行に圧縮し末尾を整形する。"""
    cleaned = re.sub(r'\n{3,}', '\n\n', markdown)
    return cleaned.strip()


def embed_images_as_base64(
    markdown: str,
    base_dir: str,
    max_size_bytes: int = 200_000,
    max_width_px: int = 800,
) -> str:
    """
    Markdown内の画像参照をbase64 data URIに変換して埋め込む。
    大きな画像はPILでリサイズ・圧縮してから埋め込む。
    max_size_bytes を超える場合はスキップ（元の参照のまま）。

    Args:
        markdown: 処理対象のMarkdown文字列
        base_dir: 画像ファイルを探すベースディレクトリ
        max_size_bytes: 埋め込む画像の上限サイズ（バイト）
        max_width_px: リサイズ後の最大幅（ピクセル）

    Returns:
        画像をbase64埋め込みに変換したMarkdown文字列
    """
    MIME_MAP = {
        '.png': 'image/png',
        '.jpg': 'image/jpeg',
        '.jpeg': 'image/jpeg',
        '.gif': 'image/gif',
        '.webp': 'image/webp',
    }

    def resize_image(full_path: str, max_width: int) -> bytes:
        """PILで画像をリサイズしてJPEGバイト列を返す。"""
        try:
            from PIL import Image
            with Image.open(full_path) as img:
                if img.mode not in ('RGB', 'RGBA'):
                    img = img.convert('RGB')
                elif img.mode == 'RGBA':
                    bg = Image.new('RGB', img.size, (255, 255, 255))
                    bg.paste(img, mask=img.split()[3])
                    img = bg
                if img.width > max_width:
                    ratio = max_width / img.width
                    new_size = (max_width, int(img.height * ratio))
                    img = img.resize(new_size, Image.LANCZOS)
                buf = io.BytesIO()
                img.save(buf, format='JPEG', quality=75, optimize=True)
                return buf.getvalue()
        except Exception:
            with open(full_path, 'rb') as f:
                return f.read()

    def replace_image(match: re.Match) -> str:
        alt = match.group(1)
        path = match.group(2)

        if path.startswith('data:'):
            return match.group(0)

        full_path = path if os.path.isabs(path) else os.path.join(base_dir, path)
        if not os.path.exists(full_path):
            return match.group(0)

        file_size = os.path.getsize(full_path)
        ext = os.path.splitext(full_path)[1].lower()

        if file_size > max_size_bytes:
            # リサイズして再試行
            data = resize_image(full_path, max_width_px)
            if len(data) > max_size_bytes * 2:
                return match.group(0)  # それでも大きすぎる場合はスキップ
            mime = 'image/jpeg'
        else:
            with open(full_path, 'rb') as f:
                data = f.read()
            mime = MIME_MAP.get(ext, 'image/png')

        encoded = base64.b64encode(data).decode()
        return f'![{alt}](data:{mime};base64,{encoded})'

    return re.sub(r'!\[([^\]]*)\]\(([^)]+)\)', replace_image, markdown)


def collect_image_paths(markdown: str, base_dir: str) -> list[tuple[str, str]]:
    """
    Markdown内の画像参照を収集してパスリストを返す。
    Streamlit の st.image() ギャラリー表示用。

    Returns:
        [(alt_text, absolute_path), ...]
    """
    results = []
    for match in re.finditer(r'!\[([^\]]*)\]\(([^)]+)\)', markdown):
        alt = match.group(1)
        path = match.group(2)
        if path.startswith('data:'):
            continue
        full_path = path if os.path.isabs(path) else os.path.join(base_dir, path)
        if os.path.exists(full_path):
            results.append((alt, full_path))
    return results


def strip_images_from_markdown(markdown: str) -> str:
    """
    プレビュー表示用にMarkdownから画像参照を除去する。
    (data URI や大きな画像参照によるブラウザ負荷を防ぐ)
    """
    return re.sub(r'!\[([^\]]*)\]\([^)]+\)', r'[画像: \1]', markdown)


def merge_markdown_sections(base: str, supplement: str, section_title: str = "") -> str:
    """ベースのMarkdownに補足セクションを追加する。"""
    if not supplement.strip():
        return base
    merged = base.rstrip()
    if section_title:
        merged += f"\n\n---\n\n## {section_title}\n\n"
    else:
        merged += "\n\n---\n\n"
    merged += supplement.strip()
    return merged


def count_markdown_stats(markdown: str) -> dict:
    """
    Markdownの統計情報を返す。
    base64データURIは文字数カウントから除外する。
    """
    # base64 data URI を除いた文字数を計算
    text_only = re.sub(r'data:[^;]+;base64,[A-Za-z0-9+/=]+', '[IMAGE]', markdown)
    lines = text_only.splitlines()
    headings = sum(1 for line in lines if line.startswith('#'))
    tables = sum(1 for line in lines if line.startswith('|'))
    images = len(re.findall(r'!\[', markdown))
    return {
        "chars": len(text_only),
        "lines": len(lines),
        "headings": headings,
        "tables": tables,
        "images": images,
    }
