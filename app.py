"""
SmartConverter - メインアプリ
PDF / PPTX / DOCX / 画像 → Markdown（yaml:imageブロック付き）変換ツール
Markdownから高再現性でPPTX / PDFに復元可能。
"""

import io
import os
import zipfile

import streamlit as st
from dotenv import load_dotenv

from engines.opendataloader_engine import convert_file_with_opendataloader
from engines.pdfplumber_engine import extract_tables_pdfplumber, merge_tables_into_markdown
from engines.markitdown_engine import convert_with_markitdown, extract_text_pymupdf, merge_extraction_results
from engines.image_extractor import extract_images_with_coords, build_markdown_with_image_yaml
from engines.layout_engine import markdown_to_pptx_with_layout, markdown_to_pdf_with_layout
from engines.pandoc_engine import convert_markdown_to_bytes, is_pandoc_available
from engines.gemma_engine import (
    is_ollama_available,
    list_ollama_models,
    improve_markdown_with_gemma,
    DEFAULT_MODEL,
    OLLAMA_BASE_URL,
)
from engines.openrouter_engine import (
    improve_markdown_with_openrouter,
    DEFAULT_MODEL as OPENROUTER_DEFAULT_MODEL,
)
from utils.file_utils import save_uploaded_file, get_file_extension, cleanup_temp_dir
from utils.markdown_utils import (
    clean_markdown,
    collect_image_paths,
    strip_images_from_markdown,
    count_markdown_stats,
)

load_dotenv()


def _load_css(path: str) -> None:
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)


# ──────────────────────────────────────────
# ページ設定
# ──────────────────────────────────────────
st.set_page_config(
    page_title="SmartConverter",
    page_icon="📄",
    layout="wide",
)
_load_css(os.path.join(os.path.dirname(__file__), "styles", "main.css"))

# ──────────────────────────────────────────
# セッション状態の初期化
# ──────────────────────────────────────────
for key, default in [
    ("output_dir", None),
    ("markdown_result", ""),
    ("last_file_name", ""),
]:
    if key not in st.session_state:
        st.session_state[key] = default

# ──────────────────────────────────────────
# サイドバー
# ──────────────────────────────────────────
with st.sidebar:
    st.title("📄 SmartConverter")
    st.caption("PDF / PPTX / DOCX / 画像 → Markdown 変換ツール")
    st.divider()

    st.subheader("📁 ファイルアップロード")
    uploaded_file = st.file_uploader(
        "対応形式: PDF / PPTX / DOCX / JPG / PNG",
        type=["pdf", "pptx", "docx", "jpg", "jpeg", "png"],
        label_visibility="collapsed",
    )

    st.divider()

    st.subheader("🔧 変換エンジン設定")
    st.checkbox("OpenDataLoader（無料・常時有効）", value=True, disabled=True)
    use_pdfplumber = st.checkbox("pdfplumber 表抽出補完", value=True)
    use_pymupdf = st.checkbox(
        "PyMuPDF テキスト補完", value=False,
        help="テキスト抽出量が少ない場合のみ補完。重いPDFでは無効推奨。",
    )
    use_image_extract = st.checkbox(
        "画像を座標付きで抽出（yaml:image）", value=True,
        help="画像の位置情報をYAMLとしてMarkdownに埋め込みます。PPTX/PDF復元時に活用。",
    )
    st.checkbox("Claude Vision（Phase 2）", value=False, disabled=True)
    st.checkbox("PaddleOCR-VL（Phase 3）", value=False, disabled=True)

    st.divider()

    st.subheader("🤖 AI改善設定（Gemma4）")

    # OpenRouter APIキー
    openrouter_api_key = st.text_input(
        "OpenRouter APIキー",
        type="password",
        value=os.getenv("OPENROUTER_API_KEY", ""),
        placeholder="sk-or-...",
        label_visibility="collapsed",
    )
    if openrouter_api_key:
        st.success("OpenRouter APIキー設定済み", icon="✅")
        use_gemma4_improve = st.checkbox(
            "Gemma4 でMarkdown改善（無料・クラウド）",
            value=False,
            help=f"モデル: {OPENROUTER_DEFAULT_MODEL}",
        )
    else:
        st.info("OpenRouter APIキーを入力するとGemma4が使えます", icon="🔑")
        use_gemma4_improve = False

    st.divider()

    # Ollama（ローカル）
    _ollama_ok = is_ollama_available()
    _ollama_models = list_ollama_models() if _ollama_ok else []
    if _ollama_ok:
        st.caption("🟢 Ollama 起動中（ローカル）")
        _model_options = _ollama_models if _ollama_models else [DEFAULT_MODEL]
        selected_model = st.selectbox("Ollamaモデル", _model_options, index=0)
        use_gemma_improve = st.checkbox("Ollama でMarkdown改善（ローカル）", value=False)
        ollama_url = OLLAMA_BASE_URL
    else:
        use_gemma_improve = False
        selected_model = DEFAULT_MODEL
        ollama_url = OLLAMA_BASE_URL

    st.subheader("🔑 Anthropic API Key")
    api_key_input = st.text_input(
        "APIキー", type="password",
        value=os.getenv("ANTHROPIC_API_KEY", ""),
        placeholder="sk-ant-...",
        label_visibility="collapsed",
    )
    if api_key_input:
        st.success("APIキー設定済み", icon="✅")
    else:
        st.info("未入力：無料機能のみ使用", icon="ℹ️")

    st.divider()

    st.subheader("📤 出力形式")
    output_markdown = st.checkbox("Markdown (.md)", value=True)
    output_zip = st.checkbox("ZIP（Markdown + 画像フォルダ）", value=True)
    output_pptx = st.checkbox("PowerPoint (.pptx) ※高再現", value=False)
    output_pdf_rl = st.checkbox("PDF（ReportLab）", value=False)
    output_docx = st.checkbox("Word (.docx) via Pandoc", value=False)

# ──────────────────────────────────────────
# メインエリア
# ──────────────────────────────────────────
st.markdown("""
<div style="
    background: linear-gradient(135deg, #4f46e5 0%, #7c3aed 100%);
    border-radius: 16px;
    padding: 1.75rem 2rem;
    margin-bottom: 1.5rem;
    color: white;
">
    <div style="font-size:2rem; font-weight:700; letter-spacing:-0.02em; margin-bottom:0.3rem;">
        📄 SmartConverter
    </div>
    <div style="font-size:0.95rem; opacity:0.85;">
        PDF / PPTX / DOCX / 画像 を Markdown に変換し、高再現性で PPTX / PDF に復元できます
    </div>
</div>
""", unsafe_allow_html=True)

if not uploaded_file:
    st.info("👈 サイドバーからファイルをアップロードしてください。", icon="📂")
    st.stop()

ext = get_file_extension(uploaded_file.name)
engine_label = {
    ".pdf":  "OpenDataLoader + pdfplumber + PyMuPDF画像抽出",
    ".pptx": "MarkItDown + PyMuPDF画像抽出",
    ".docx": "MarkItDown",
    ".jpg":  "MarkItDown",
    ".jpeg": "MarkItDown",
    ".png":  "MarkItDown",
}.get(ext, "OpenDataLoader")

col_btn, col_info = st.columns([2, 8])
with col_btn:
    convert_button = st.button("🚀 変換開始", type="primary", use_container_width=True)
with col_info:
    st.caption(f"使用エンジン: **{engine_label}**")

# ──────────────────────────────────────────
# 変換処理
# ──────────────────────────────────────────
if convert_button:
    if st.session_state.output_dir:
        cleanup_temp_dir(st.session_state.output_dir)
        st.session_state.output_dir = None

    progress = st.progress(0, text="変換を開始しています...")
    status = st.empty()
    markdown_result = ""
    tmp_path = None
    output_dir = None

    try:
        status.info("📥 ファイルを読み込んでいます...")
        tmp_path = save_uploaded_file(uploaded_file)
        progress.progress(10)

        if ext == ".pdf":
            # ── PDF変換パイプライン ──
            status.info("⚙️ OpenDataLoader で変換中...")
            try:
                markdown_result, output_dir = convert_file_with_opendataloader(tmp_path)
                st.session_state.output_dir = output_dir
            except Exception as e:
                st.warning(f"OpenDataLoader エラー（スキップ）: {e}")
            progress.progress(35)

            if use_pymupdf:
                status.info("🔍 PyMuPDF テキスト補完中...")
                try:
                    pymupdf_text = extract_text_pymupdf(tmp_path)
                    markdown_result = merge_extraction_results(markdown_result, pymupdf_text)
                except Exception as e:
                    st.warning(f"PyMuPDF エラー（スキップ）: {e}")
            progress.progress(50)

            if use_pdfplumber:
                status.info("📊 pdfplumber 表抽出中...")
                try:
                    tables = extract_tables_pdfplumber(tmp_path)
                    if tables:
                        markdown_result = merge_tables_into_markdown(markdown_result, tables)
                except Exception as e:
                    st.warning(f"pdfplumber エラー（スキップ）: {e}")
            progress.progress(65)

            if use_image_extract and output_dir:
                status.info("🖼️ 画像を座標付きで抽出中...")
                try:
                    images = extract_images_with_coords(tmp_path, output_dir)
                    if images:
                        markdown_result = build_markdown_with_image_yaml(
                            markdown_result, images
                        )
                        status.info(f"🖼️ {len(images)} 枚の画像を座標付きで抽出しました。")
                except Exception as e:
                    st.warning(f"画像抽出エラー（スキップ）: {e}")
            progress.progress(85)

        else:
            # ── PPTX / DOCX / 画像変換パイプライン ──
            status.info(f"⚙️ MarkItDown で変換中... ({ext})")
            try:
                markdown_result = convert_with_markitdown(tmp_path)
            except Exception as e:
                st.error(f"MarkItDown 変換エラー: {e}")
                st.stop()
            progress.progress(80)

        markdown_result = clean_markdown(markdown_result)
        progress.progress(90)

        # ── OpenRouter Gemma4 改善（優先） ──
        if use_gemma4_improve and markdown_result:
            status.info("🤖 Gemma4（OpenRouter）でMarkdown改善中...")
            try:
                from engines.openrouter_engine import MAX_INPUT_CHARS as OR_MAX
                improved, was_truncated = improve_markdown_with_openrouter(
                    markdown_result,
                    api_key=openrouter_api_key,
                )
                if was_truncated:
                    markdown_result = improved + "\n\n---\n\n" + markdown_result[OR_MAX:]
                    st.info(f"ℹ️ 入力が長いため先頭 {OR_MAX} 文字のみ改善しました。")
                else:
                    markdown_result = improved
                st.toast("Gemma4改善完了（OpenRouter）", icon="🤖")
            except Exception as e:
                st.warning(f"Gemma4改善エラー（スキップ）: {e}")

        # ── Ollama ローカル改善 ──
        elif use_gemma_improve and markdown_result:
            status.info(f"🤖 Gemma（{selected_model}）でMarkdown改善中（CPU実行・しばらくお待ちください）...")
            try:
                improved, was_truncated = improve_markdown_with_gemma(
                    markdown_result,
                    model=selected_model,
                    base_url=ollama_url,
                )
                # 改善部分を先頭に挿入し、切り詰めた場合は残りをそのまま末尾に付ける
                if was_truncated:
                    from engines.gemma_engine import MAX_INPUT_CHARS
                    markdown_result = improved + "\n\n---\n\n" + markdown_result[MAX_INPUT_CHARS:]
                    st.info(f"ℹ️ 入力が長いため先頭 {MAX_INPUT_CHARS} 文字のみ改善しました。残りはそのまま結合しています。")
                else:
                    markdown_result = improved
                st.toast(f"Gemma改善完了（{selected_model}）", icon="🤖")
            except Exception as e:
                st.warning(f"Gemma改善エラー（スキップ）: {e}")

        progress.progress(100, text="✅ 変換完了！")
        status.success("変換が完了しました！")

        st.session_state.markdown_result = markdown_result
        st.session_state.last_file_name = uploaded_file.name

    except Exception as e:
        st.error(f"予期しないエラー: {e}")
        st.stop()
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)

# ──────────────────────────────────────────
# 結果表示
# ──────────────────────────────────────────
if not st.session_state.markdown_result:
    st.stop()

markdown = st.session_state.markdown_result
file_name = st.session_state.last_file_name
output_dir = st.session_state.output_dir
base_name = os.path.splitext(file_name)[0]

st.divider()
st.markdown("### 📋 変換結果")

stats = count_markdown_stats(markdown)
c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("文字数", f"{stats['chars']:,}")
c2.metric("行数", f"{stats['lines']:,}")
c3.metric("見出し数", stats['headings'])
c4.metric("表の行数", stats['tables'])
c5.metric("画像数", stats['images'])

# プレビュー（画像YAML・base64を除去して軽量表示）
preview_md = strip_images_from_markdown(markdown)
import re
preview_md = re.sub(r"```yaml:image\n.*?```", "[📷 画像ブロック（YAMLあり）]", preview_md, flags=re.DOTALL)

tab_source, tab_preview = st.tabs(["📝 ソース（yaml:image含む）", "👁️ プレビュー"])
with tab_source:
    st.text_area("", markdown, height=420, label_visibility="collapsed")
with tab_preview:
    st.markdown(preview_md)

# 画像ギャラリー
if output_dir:
    image_paths = collect_image_paths(markdown, output_dir)
    # images/ フォルダからも直接収集
    images_folder = os.path.join(output_dir, "images")
    if os.path.exists(images_folder):
        for fname in sorted(os.listdir(images_folder)):
            fpath = os.path.join(images_folder, fname)
            if fname.lower().endswith((".png", ".jpg", ".jpeg")):
                if (fname, fpath) not in image_paths:
                    image_paths.append((fname, fpath))

    if image_paths:
        st.divider()
        st.markdown(f"### 🖼️ 抽出画像 ({len(image_paths)} 枚)")
        cols = st.columns(min(len(image_paths), 4))
        for i, (alt, path) in enumerate(image_paths):
            with cols[i % 4]:
                try:
                    st.image(path, caption=alt or f"画像 {i+1}", use_container_width=True)
                except Exception:
                    st.caption(f"⚠️ 表示できない画像: {alt}")

# ──────────────────────────────────────────
# ダウンロード
# ──────────────────────────────────────────
st.divider()
st.markdown("### 📥 ダウンロード")

dl_cols = st.columns(5)

# Markdown（yaml:imageブロック付き）
if output_markdown:
    with dl_cols[0]:
        st.download_button(
            label="⬇️ Markdown",
            data=markdown.encode("utf-8"),
            file_name=f"{base_name}.md",
            mime="text/markdown",
            use_container_width=True,
            help="yaml:imageブロック付きの完全版Markdown",
        )

# ZIP（Markdown + images/ フォルダ）
if output_zip and output_dir:
    with dl_cols[1]:
        try:
            zip_buf = io.BytesIO()
            with zipfile.ZipFile(zip_buf, "w", zipfile.ZIP_DEFLATED) as zf:
                zf.writestr(f"{base_name}.md", markdown.encode("utf-8"))
                images_folder = os.path.join(output_dir, "images")
                if os.path.exists(images_folder):
                    for fname in os.listdir(images_folder):
                        fpath = os.path.join(images_folder, fname)
                        zf.write(fpath, f"images/{fname}")
            st.download_button(
                label="⬇️ ZIP",
                data=zip_buf.getvalue(),
                file_name=f"{base_name}_smart.zip",
                mime="application/zip",
                use_container_width=True,
                help="Markdown + 画像フォルダの完全セット",
            )
        except Exception as e:
            st.error(f"ZIP作成エラー: {e}")

# PPTX（高再現・座標配置）
if output_pptx:
    with dl_cols[2]:
        try:
            base_dir = output_dir or os.getcwd()
            pptx_bytes = markdown_to_pptx_with_layout(markdown, base_dir)
            st.download_button(
                label="⬇️ PPTX（高再現）",
                data=pptx_bytes,
                file_name=f"{base_name}.pptx",
                mime="application/vnd.openxmlformats-officedocument.presentationml.presentation",
                use_container_width=True,
                help="yaml:image座標を使って画像を正確に配置",
            )
        except Exception as e:
            st.error(f"PPTX変換エラー: {e}")

# PDF（ReportLab）
if output_pdf_rl:
    with dl_cols[3]:
        try:
            base_dir = output_dir or os.getcwd()
            pdf_bytes = markdown_to_pdf_with_layout(markdown, base_dir)
            st.download_button(
                label="⬇️ PDF（高再現）",
                data=pdf_bytes,
                file_name=f"{base_name}.pdf",
                mime="application/pdf",
                use_container_width=True,
            )
        except Exception as e:
            st.error(f"PDF変換エラー: {e}")

# DOCX（Pandoc）
if output_docx:
    with dl_cols[4]:
        try:
            docx_bytes = convert_markdown_to_bytes(markdown, "docx")
            st.download_button(
                label="⬇️ DOCX",
                data=docx_bytes,
                file_name=f"{base_name}.docx",
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                use_container_width=True,
            )
        except Exception as e:
            st.error(f"DOCX変換エラー: {e}")
