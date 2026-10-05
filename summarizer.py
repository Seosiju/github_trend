"""Optional LLM 요약. OPENAI_API_KEY가 없거나 실패하면 빈 dict를 반환하고 원문을 쓴다."""

from __future__ import annotations

import json
import os

_LANG_NAMES = {"ko": "Korean", "en": "English"}

_SYSTEM_PROMPT = """You summarize GitHub repositories for a daily digest.
For each repository in the user's JSON input, write {sentences} in {language}:
what the project is and why a developer might care.
Return STRICT JSON: {{"fullname": "summary", ...}} using the exact input keys.
No markdown, no extra keys, no commentary."""


def summarize(repos: list[dict], config: dict) -> dict:
    """repo fullname -> 요약 문자열. 사용 불가/실패 시 {}."""
    if not repos or not config.get("use_llm", True):
        return {}
    if not os.environ.get("OPENAI_API_KEY"):
        print("[info] OPENAI_API_KEY not set; using raw descriptions")
        return {}

    model = os.environ.get("OPENAI_MODEL") or config.get("llm_model", "gpt-5-mini")
    language = _LANG_NAMES.get(config.get("summary_language", "ko"), "Korean")

    items = [
        {
            "fullname": r["fullname"],
            "description": r["description"],
            "language": r["language"],
            "stars_today": r["stars_today"],
        }
        for r in repos
    ]

    try:
        from openai import OpenAI

        resp = OpenAI().chat.completions.create(
            model=model,
            response_format={"type": "json_object"},
            messages=[
                {
                    "role": "system",
                    "content": _SYSTEM_PROMPT.format(
                        sentences="1-2 short sentences", language=language
                    ),
                },
                {
                    "role": "user",
                    "content": json.dumps(items, ensure_ascii=False),
                },
            ],
            max_completion_tokens=4000,
        )
        data = json.loads(resp.choices[0].message.content)
        return {k: str(v).strip() for k, v in data.items()}
    except Exception as e:
        print(f"[warn] LLM summary skipped: {e}")
        return {}
