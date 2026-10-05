"""Slack Incoming Webhook 메시지 생성과 전송."""

from __future__ import annotations

import requests

MAX_BLOCKS = 45  # Slack 한 메시지당 block 상한 여유분

_PERIOD_LABEL = {
    "daily": "Daily",
    "weekly": "Weekly",
    "monthly": "Monthly",
    "yearly": "Yearly · 최근 1년 신생",
    "rising": "Rising · 최근 30일 신생",
}
_STARS_LABEL = {"daily": "today", "weekly": "this week", "monthly": "this month"}


def _context(text: str) -> dict:
    return {"type": "context", "elements": [{"type": "mrkdwn", "text": text}]}


def _repo_blocks(idx: int, repo: dict, summaries: dict, stars_label: str) -> list:
    summary = summaries.get(repo["fullname"]) or repo["description"] or "(no description)"
    lang = f" · {repo['language']}" if repo["language"] else ""
    if repo["stars_today"]:
        meta = f":star: +{repo['stars_today']:,} {stars_label} · {repo['stars']:,} total{lang}"
    elif repo.get("created_at"):
        meta = f":star: {repo['stars']:,} total{lang} · created {repo['created_at']}"
    else:
        meta = f":star: {repo['stars']:,} total{lang}"
    tag = ":fire: 인기급상승 — " if repo.get("respiked") else ""
    return [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"{tag}*{idx}. <{repo['url']}|{repo['fullname']}>*\n{summary}",
            },
        },
        _context(meta),
    ]


def build_payload(
    date_str: str,
    repos: list[dict],
    summaries: dict,
    period: str = "daily",
    filters: dict | None = None,
) -> dict:
    period_label = _PERIOD_LABEL.get(period, period.title())
    stars_label = _STARS_LABEL.get(period, "today")
    title = f"GitHub Trending — {period_label} · {date_str}"

    if not repos:
        return {
            "text": f"{title}: 새 항목 없음",
            "blocks": [
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*{title}*\n이번 기간에 조건에 맞는 새 repo가 없습니다.",
                    },
                }
            ],
        }

    blocks = [
        {"type": "header", "text": {"type": "plain_text", "text": title}},
    ]
    for i, repo in enumerate(repos, 1):
        blocks += _repo_blocks(i, repo, summaries, stars_label)
        blocks.append({"type": "divider"})

    if filters:
        langs = ", ".join(filters.get("languages") or []) or "all"
        kws = ", ".join(filters.get("keywords") or []) or "-"
        blocks.append(_context(f"filters — languages: {langs} · keywords: {kws}"))

    # block 상한 초과 시 divider/context를 빼고 compact하게 재구성
    if len(blocks) > MAX_BLOCKS:
        blocks = [{"type": "header", "text": {"type": "plain_text", "text": title}}]
        for i, repo in enumerate(repos, 1):
            blocks += _repo_blocks(i, repo, summaries, stars_label)

    return {
        "text": f"{title} ({len(repos)} repos)",
        "blocks": blocks[:MAX_BLOCKS],
    }


def send(webhook_url: str, payload: dict) -> None:
    resp = requests.post(webhook_url, json=payload, timeout=15)
    if resp.status_code != 200 or resp.text.strip() != "ok":
        raise RuntimeError(f"Slack webhook failed: {resp.status_code} {resp.text}")
