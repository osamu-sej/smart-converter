"""
OpenRouter エンジン - Gemma4 via OpenRouter API
google/gemma-4-26b-a4b-it:free を使ってMarkdownを改善する。
OpenRouterの無料枠を使用（APIキーのみ必要・GPU不要）。
"""

import requests

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
DEFAULT_MODEL = "google/gemma-4-26b-a4b-it:free"
MAX_INPUT_CHARS = 6000  # クラウドAPIなので余裕を持たせる

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


def is_openrouter_available(api_key: str) -> bool:
    """OpenRouter APIキーが有効か確認する。"""
    if not api_key or not api_key.startswith("sk-or-"):
        return False
    try:
        r = requests.get(
            f"{OPENROUTER_BASE_URL}/models",
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=5,
        )
        return r.status_code == 200
    except Exception:
        return False


def improve_markdown_with_openrouter(
    markdown: str,
    api_key: str,
    model: str = DEFAULT_MODEL,
    max_chars: int = MAX_INPUT_CHARS,
    timeout: int = 60,
) -> tuple[str, bool]:
    """
    OpenRouter経由でGemma4によるMarkdown改善を行う。

    Args:
        markdown: 改善対象のMarkdown文字列
        api_key: OpenRouter APIキー（sk-or-...）
        model: 使用モデル名
        max_chars: 入力の最大文字数
        timeout: タイムアウト秒数

    Returns:
        (改善されたMarkdown文字列, 切り詰めが発生したか)

    Raises:
        RuntimeError: API呼び出し失敗時
    """
    truncated = len(markdown) > max_chars
    input_md = markdown[:max_chars] if truncated else markdown

    prompt = _IMPROVE_PROMPT.format(markdown=input_md)

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://github.com/osamu-sej/smart-converter",
        "X-Title": "SmartConverter",
    }

    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.3,
        "max_tokens": 4096,
    }

    try:
        r = requests.post(
            f"{OPENROUTER_BASE_URL}/chat/completions",
            headers=headers,
            json=payload,
            timeout=timeout,
        )
        r.raise_for_status()
        data = r.json()
        content = data["choices"][0]["message"]["content"].strip()
        return content, truncated
    except requests.exceptions.ConnectionError:
        raise RuntimeError("OpenRouterに接続できません。ネットワークを確認してください。")
    except requests.exceptions.Timeout:
        raise RuntimeError(f"OpenRouterの応答がタイムアウトしました（{timeout}秒）。")
    except requests.exceptions.HTTPError as e:
        status = e.response.status_code if e.response else "不明"
        if status == 401:
            raise RuntimeError("APIキーが無効です。OpenRouterのキーを確認してください。")
        elif status == 429:
            raise RuntimeError("レート制限に達しました。しばらく待ってから再試行してください。")
        else:
            raise RuntimeError(f"APIエラー（{status}）: {e}")
