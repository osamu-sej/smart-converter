"""
画像抽出エンジン
PyMuPDF で PDF の各ページから画像とバウンディングボックスを抽出し、
正規化座標（0-1）付きのメタデータを生成する。
"""

import os
from dataclasses import dataclass, field, asdict


@dataclass
class ImageMeta:
    """1枚の画像のメタデータ。"""
    id: str                  # "p1_img1" 形式
    path: str                # images/ からの相対パス
    page: int                # ページ番号（1始まり）
    # 正規化座標（ページサイズを1とした割合）
    x: float                 # 左端
    y: float                 # 上端
    width: float             # 幅
    height: float            # 高さ
    # 元PDF座標（参照用）
    x_pt: float
    y_pt: float
    w_pt: float
    h_pt: float
    page_w_pt: float
    page_h_pt: float

    def to_dict(self) -> dict:
        return asdict(self)


def extract_images_with_coords(
    pdf_path: str,
    output_dir: str,
    min_size_pt: float = 20.0,
) -> list[ImageMeta]:
    """
    PDFから全ページの画像を座標付きで抽出する。

    Args:
        pdf_path: 入力PDFパス
        output_dir: 画像の保存先ルートディレクトリ
        min_size_pt: この幅/高さ(pt)未満の画像は無視（アイコン等を除外）

    Returns:
        ImageMeta のリスト（ページ順・画像順）
    """
    try:
        import fitz
    except ImportError:
        raise ImportError("pip install pymupdf を実行してください。")

    images_dir = os.path.join(output_dir, "images")
    os.makedirs(images_dir, exist_ok=True)

    doc = fitz.open(pdf_path)
    results: list[ImageMeta] = []

    for page_num, page in enumerate(doc, 1):
        page_rect = page.rect
        page_w = page_rect.width
        page_h = page_rect.height

        img_list = page.get_images(full=True)

        for img_idx, img in enumerate(img_list, 1):
            xref = img[0]

            # 画像のバウンディングボックスを取得
            rects = page.get_image_rects(img)
            if not rects:
                continue

            rect = rects[0]
            x0, y0 = rect.x0, rect.y0
            w = rect.x1 - rect.x0
            h = rect.y1 - rect.y0

            # 極小画像（罫線・アイコン等）は除外
            if w < min_size_pt or h < min_size_pt:
                continue

            # 画像データを抽出・保存
            try:
                base_image = doc.extract_image(xref)
            except Exception:
                continue

            img_bytes = base_image.get("image", b"")
            img_ext = base_image.get("ext", "png")
            if not img_bytes:
                continue

            img_filename = f"p{page_num}_img{img_idx}.{img_ext}"
            img_path = os.path.join(images_dir, img_filename)
            with open(img_path, "wb") as f:
                f.write(img_bytes)

            results.append(ImageMeta(
                id=f"p{page_num}_img{img_idx}",
                path=f"images/{img_filename}",
                page=page_num,
                x=round(x0 / page_w, 4),
                y=round(y0 / page_h, 4),
                width=round(w / page_w, 4),
                height=round(h / page_h, 4),
                x_pt=round(x0, 2),
                y_pt=round(y0, 2),
                w_pt=round(w, 2),
                h_pt=round(h, 2),
                page_w_pt=round(page_w, 2),
                page_h_pt=round(page_h, 2),
            ))

    doc.close()
    return results


def build_markdown_with_image_yaml(
    markdown: str,
    images: list[ImageMeta],
) -> str:
    """
    Markdownのページ見出し（## Page N）の直後に
    yaml:image ブロックを挿入して返す。

    ページ見出しが見つからない場合は末尾に追加。

    Args:
        markdown: ベースのMarkdown文字列
        images: extract_images_with_coords() の戻り値

    Returns:
        yaml:image ブロックを含むMarkdown文字列
    """
    import re
    import yaml
    from collections import defaultdict

    if not images:
        return markdown

    # ページごとに画像をグループ化
    by_page: dict[int, list[ImageMeta]] = defaultdict(list)
    for img in images:
        by_page[img.page].append(img)

    def image_yaml_block(img: ImageMeta) -> str:
        data = img.to_dict()
        yaml_str = yaml.dump(data, allow_unicode=True,
                             default_flow_style=False, sort_keys=False)
        return f"```yaml:image\n{yaml_str.rstrip()}\n```"

    lines = markdown.splitlines()
    result: list[str] = []
    inserted_pages: set[int] = set()

    for line in lines:
        result.append(line)
        # ## Page N 形式の見出しを検出
        m = re.match(r"^##\s+[Pp]age\s+(\d+)", line)
        if m:
            page_num = int(m.group(1))
            if page_num in by_page and page_num not in inserted_pages:
                result.append("")
                for img in by_page[page_num]:
                    result.append(image_yaml_block(img))
                    result.append("")
                inserted_pages.add(page_num)

    # ページ見出しで挿入できなかった画像を末尾に追加
    remaining = {p: imgs for p, imgs in by_page.items()
                 if p not in inserted_pages}
    if remaining:
        result.append("\n---\n\n## 抽出画像\n")
        for page_num in sorted(remaining):
            result.append(f"\n### Page {page_num}\n")
            for img in remaining[page_num]:
                result.append(image_yaml_block(img))
                result.append("")

    return "\n".join(result)
