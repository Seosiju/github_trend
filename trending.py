"""GitHub Trending 수집과 필터링. 스크레이핑은 gtrending 라이브러리에 위임한다."""

from __future__ import annotations

from gtrending import fetch_repos


def _normalize(repo: dict) -> dict:
    return {
        "fullname": repo["fullname"],
        "url": repo["url"],
        "description": (repo.get("description") or "").strip(),
        "language": repo.get("language") or "",
        "stars": repo.get("stars") or 0,
        "stars_today": repo.get("currentPeriodStars") or 0,
        "author": repo.get("author") or "",
    }


def _matches(repo: dict, languages: set, keywords: list) -> bool:
    # 언어 OR 키워드: 하나만 맞으면 통과시켜 좋은 repo를 놓치지 않는다.
    lang_ok = not languages or repo["language"].lower() in languages
    text = f"{repo['fullname']} {repo['description']}".lower()
    kw_ok = not keywords or any(k.lower() in text for k in keywords)
    return lang_ok or kw_ok


def collect(config: dict) -> list[dict]:
    """전체 + 관심 언어별 trending을 모아 필터/정렬/상한 적용 후 반환한다."""
    languages = {str(l).lower() for l in (config.get("languages") or [])}
    keywords = config.get("keywords") or []
    period = config.get("period", "daily")
    # 전체 목록 + 언어별 목록. 언어별 slug는 소문자 형태가 대부분 그대로 동작한다.
    sources = [None] + sorted(languages)

    seen: set = set()
    repos: list[dict] = []
    for lang in sources:
        try:
            fetched = fetch_repos(language=lang, since=period)
        except Exception as e:
            print(f"[warn] trending fetch failed (language={lang}): {e}")
            continue
        for raw in fetched:
            if raw["fullname"] not in seen:
                seen.add(raw["fullname"])
                repos.append(_normalize(raw))

    picked = [r for r in repos if _matches(r, languages, keywords)]
    picked.sort(key=lambda r: r["stars_today"], reverse=True)
    return picked[: int(config.get("max_repositories", 10))]
