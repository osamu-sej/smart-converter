"""
Gemma エンジン - Ollama 経由のローカル AI 改善
Gemma4（または他のOllamaモデル）でMarkdownを改善・整形する。
APIキー不要・完全ローカル動作。
"""

import requests

OLLAMA_BASE_URL = "http://localhost:11434"
DEFAULT_MODEL = "gemma4:e4b"

_IMPROVE_PROMPT = """\
以下のMarkdownドキュメントを改善してください。

改善ルール：
- 見出し構造（#, ##, ###）を整理・統一する
- 箇条書きを読みやすく整える
- 表（Markdown table）のフォーマットを統一する
- 重複・冗長な内容を削除する
- 全体の流れを論理的に整える
- 言語はそのまま維持する（日本語→日本語）
- ```yaml:image ... ``` ブロックは一切変更せずそのまま保持する
- 内容（数値・固有名詞・事実）は変えない

Markdownのみ出力してください（前置き・説明文は不要）。

---
{markdown}
---"""


def is_ollama_available(base_url: str = OLLAMA_BASE_URL) -> bool:
    """Ollamaが起動しているか確認する。"""
    try:
        r = requests.get(f"{base_url}/api/tags", timeout=3)
        return r.status_code == 200
    except Exception:
        return False


def list_ollama_models(base_url: str = OLLAMA_BASE_URL) -> list[str]:
    """Ollamaで利用可能なモデル一覧を返す。"""
    try:
        r = requests.get(f"{base_url}/api/tags", timeout=3)
        r.raise_for_status()
        data = r.json()
        return [m["name"] for m in data.get("models", [])]
    except Exception:
        return []


def improve_markdown_with_gemma(
    markdown: str,
    model: str = DEFAULT_MODEL,
    base_url: str = OLLAMA_BASE_URL,
    timeout: int = 180,
) -> str:
    """
    GemmaモデルでMarkdownを改善する。

    Args:
        markdown: 改善対象のMarkdown文字列
        model: 使用するOllamaモデル名（例: "gemma4:e4b"）
        base_url: OllamaのベースURL
        timeout: タイムアウト秒数

    Returns:
        改善されたMarkdown文字列

    Raises:
        requests.RequestException: Ollamaへの接続エラー
        ValueError: モデルが見つからない場合
    """
    prompt = _IMPROVE_PROMPT.format(markdown=markdown)

    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "stream": False,
        "options": {
            "temperature": 0.3,  # 低めで安定した出力
            "num_predict": 8192,
        },
    }

    try:
        r = requests.post(
            f"{base_url}/api/chat",
            json=payload,
            timeout=timeout,
        )
        r.raise_for_status()
        data = r.json()
        return data["message"]["content"].strip()
    except requests.exceptions.ConnectionError:
        raise RuntimeError(
            "Ollamaに接続できません。`ollama serve` が起動しているか確認してください。"
        )
    except requests.exceptions.Timeout:
        raise RuntimeError(
            f"Ollamaの応答がタイムアウトしました（{timeout}秒）。"
            "大きなドキュメントの場合はタイムアウト値を増やしてください。"
        )
