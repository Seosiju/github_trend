"""GitHub Trending -> Slack digest 엔트리포인트.

사용:
    python main.py            # 수집 -> dedup -> (선택)요약 -> Slack 전송
    python main.py --dry-run  # 전송 없이 payload만 출력
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import yaml

import slack
import summarizer
import trending

STATE_FILE = os.environ.get("STATE_FILE", "state.json")


def load_state(path: Path) -> dict:
    if path.exists():
        try:
            return json.loads(path.read_text())
        except Exception:
            pass
    return {"sent": {}}


def prune(state: dict, days: int) -> dict:
    cutoff = date.today() - timedelta(days=days)
    state["sent"] = {
        name: d
        for name, d in state.get("sent", {}).items()
        if _parse_date(d) and _parse_date(d) >= cutoff
    }
    return state


def _parse_date(s: str):
    try:
        return date.fromisoformat(s)
    except Exception:
        return None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="config.yaml")
    parser.add_argument("--dry-run", action="store_true", help="Slack 전송 없이 payload 출력")
    args = parser.parse_args()

    config = yaml.safe_load(Path(args.config).read_text())
    # Slack 명령/수동 실행에서 기간 오버라이드 (daily|weekly|monthly|yearly|rising)
    override = os.environ.get("PERIOD_OVERRIDE")
    if override in ("daily", "weekly", "monthly", "yearly", "rising"):
        config["period"] = override
    state_path = Path(STATE_FILE)
    state = prune(load_state(state_path), int(config.get("dedup_days", 14)))

    repos = trending.collect(config)
    # 수동 요청(slash command/수동 실행)은 dedup을 건너뛰고 항상 목록을 보여준다
    if os.environ.get("BYPASS_DEDUP") == "true":
        fresh = repos
    else:
        fresh = [r for r in repos if r["fullname"] not in state["sent"]]
    print(f"[info] collected={len(repos)} fresh={len(fresh)}")

    summaries = summarizer.summarize(fresh, config)
    today = datetime.now(timezone.utc).astimezone().date().isoformat()
    payload = slack.build_payload(
        today,
        fresh,
        summaries,
        period=config.get("period", "daily"),
        filters={"languages": config.get("languages"), "keywords": config.get("keywords")},
    )

    if args.dry_run:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0

    webhook = os.environ.get("SLACK_WEBHOOK_URL")
    if not webhook:
        print("[error] SLACK_WEBHOOK_URL is not set", file=sys.stderr)
        return 1

    try:
        slack.send(webhook, payload)
    except Exception as e:
        state_path.write_text(json.dumps(state, indent=2))  # 전송 실패 시 sent 기록 안 함
        print(f"[error] Slack send failed: {e}", file=sys.stderr)
        return 1

    for r in fresh:
        state["sent"][r["fullname"]] = today
    state_path.write_text(json.dumps(state, indent=2))
    print(f"[info] sent {len(fresh)} repos")
    return 0


if __name__ == "__main__":
    sys.exit(main())
