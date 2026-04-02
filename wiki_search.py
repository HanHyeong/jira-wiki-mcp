#!/usr/bin/env python3
"""
Confluence(위키) REST API — CQL 검색.

환경 변수:
  WIKI_BASE_URL   기본: http://wiki.example.com:8080
  JIRA_USER, JIRA_PASSWORD  (지라와 동일 계정)
"""

from __future__ import annotations

import os
from typing import Any

import requests


DEFAULT_WIKI_BASE = "http://wiki.example.com:8080"


def try_get_wiki_config() -> tuple[str, str, str] | None:
    base = os.environ.get("WIKI_BASE_URL", DEFAULT_WIKI_BASE).rstrip("/")
    user = os.environ.get("JIRA_USER", "")
    password = os.environ.get("JIRA_PASSWORD", "")
    if not user or not password:
        return None
    return base, user, password


def _cql_escape_literal(s: str) -> str:
    return s.replace("\\", "\\\\").replace('"', '\\"')


def _build_cql(query: str) -> str:
    q = query.strip()
    if not q:
        return ""
    esc = _cql_escape_literal(q)
    return f'type in ("page","blogpost") and (text ~ "{esc}" or title ~ "{esc}")'


def _fallback_cql(query: str) -> str:
    esc = _cql_escape_literal(query.strip())
    return f'text ~ "{esc}"'


def _search_url_candidates(wiki_base: str) -> list[str]:
    b = wiki_base.rstrip("/")
    return [
        f"{b}/rest/api/content/search",
        f"{b}/wiki/rest/api/content/search",
        f"{b}/confluence/rest/api/content/search",
        f"{b}/rest/api/search",
        f"{b}/wiki/rest/api/search",
    ]


def search_wiki(
    wiki_base: str,
    user: str,
    password: str,
    query: str,
    limit: int,
    start: int,
) -> dict[str, Any]:
    q = str(query or "").strip()
    if not q:
        raise ValueError("검색어가 비어 있습니다.")

    lim = max(1, min(int(limit), 100))
    st = max(0, int(start))

    primary_cql = _build_cql(q)
    fallback_cql = _fallback_cql(q)
    auth = (user, password)
    headers = {"Accept": "application/json"}
    last_err: Exception | None = None

    for url in _search_url_candidates(wiki_base):
        for cql_try in (primary_cql, fallback_cql):
            try:
                r = requests.get(
                    url,
                    params={"cql": cql_try, "limit": lim, "start": st},
                    auth=auth,
                    headers=headers,
                    timeout=60,
                )
            except requests.RequestException as e:
                last_err = e
                continue
            if r.status_code == 404:
                break
            if r.status_code == 400 and cql_try != fallback_cql:
                continue
            r.raise_for_status()
            data = r.json()
            if isinstance(data, dict):
                data["_wikiSearchMeta"] = {
                    "endpoint": url,
                    "cql": cql_try,
                }
            return data

    if last_err is not None:
        raise last_err
    raise requests.HTTPError("위키 검색: 사용 가능한 REST 엔드포인트를 찾지 못했습니다.")


def main() -> None:
    import argparse
    import json
    import sys

    from jira_search import load_env_file

    root = os.path.dirname(os.path.abspath(__file__))
    load_env_file(os.path.join(root, ".env"))
    load_env_file(os.path.join(os.getcwd(), ".env"))

    parser = argparse.ArgumentParser(description="Confluence(위키) 검색어로 REST 검색, JSON 출력")
    parser.add_argument("query", help="검색어")
    parser.add_argument(
        "-n",
        "--max",
        type=int,
        default=20,
        metavar="N",
        help="최대 결과 수 (기본 20, 최대 100)",
    )
    parser.add_argument(
        "-s",
        "--start",
        type=int,
        default=0,
        help="시작 offset (페이징)",
    )
    args = parser.parse_args()

    cfg = try_get_wiki_config()
    if cfg is None:
        print(
            "JIRA_USER, JIRA_PASSWORD 가 필요합니다. WIKI_BASE_URL 은 선택(.env 또는 환경 변수).",
            file=sys.stderr,
        )
        sys.exit(1)
    base, user, password = cfg
    try:
        data = search_wiki(base, user, password, args.query, args.max, args.start)
    except requests.HTTPError as e:
        body = ""
        if e.response is not None:
            try:
                body = e.response.text[:2000]
            except Exception:
                body = str(e.response)
        print(f"HTTP 오류: {e}\n{body}", file=sys.stderr)
        sys.exit(1)
    except requests.RequestException as e:
        print(f"요청 실패: {e}", file=sys.stderr)
        sys.exit(1)
    except ValueError as e:
        print(str(e), file=sys.stderr)
        sys.exit(2)
    print(json.dumps(data, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
