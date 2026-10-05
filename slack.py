"""Slack Incoming Webhook 메시지 생성과 전송."""

from __future__ import annotations

import requests

MAX_BLOCKS = 45  # Slack 한 메시지당 block 상한 여유분


def _repo_text(idx: int, repo: dict, summaries: dict) -> str:
    summary = summaries.get(repo["fullname"]) or repo["description"] or "(no description)"
    lang = f" · {repo['language']}" if repo["language"] else ""
    return (
        f"*{idx}. <{repo['url']}|{repo['fullname']}>*\n"
        f":star: +{repo['stars_today']:,} today · {repo['stars']:,} total{lang}\n"
        f"{summary}"
    )


def build_payload(date_str: str, repos: list[dict], summaries: dict) -> dict:
    if not repos:
        return {
            "text": f"GitHub Trending — {date_str}: 새 항목 없음",
            "blocks": [
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*GitHub Trending — {date_str}*\n오늘은 조건에 맞는 새 repo가 없습니다.",
                    },
                }
            ],
        }

    blocks = [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": f"GitHub Trending — {date_str}"},
        }
    ]
    for i, repo in enumerate(repos, 1):
        blocks.append(
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": _repo_text(i, repo, summaries)},
            }
        )
    return {
        "text": f"GitHub Trending — {date_str} ({len(repos)} repos)",
        "blocks": blocks[:MAX_BLOCKS],
    }


def send(webhook_url: str, payload: dict) -> None:
    resp = requests.post(webhook_url, json=payload, timeout=15)
    if resp.status_code != 200 or resp.text.strip() != "ok":
        raise RuntimeError(f"Slack webhook failed: {resp.status_code} {resp.text}")
