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
from urllib.parse import quote, urljoin

import requests

from jira_search import _strip_html
from project_version import __version__


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


def normalize_wiki_page_id(ref: str) -> str:
    """
    Confluence content id는 REST에서 숫자만 사용합니다.
    'P1599' 같은 문서코드·검색어는 wiki_search(query=...) 로 조회하세요 (페이지 id가 아님).
    """
    s = (ref or "").strip()
    if not s:
        return ""
    if s.isdigit():
        return s
    return ""


def _content_get_url_candidates(wiki_base: str, page_id: str) -> list[str]:
    cid = quote(str(page_id).strip(), safe="")
    b = wiki_base.rstrip("/")
    return [
        f"{b}/rest/api/content/{cid}",
        f"{b}/wiki/rest/api/content/{cid}",
        f"{b}/confluence/rest/api/content/{cid}",
    ]


_EXPAND_TRIES = (
    "body.view,body.storage,space,version,ancestors",
    "body.view,body.storage,space,version",
    "body.view,space,version",
    "space,version",
)


def get_wiki_page(
    wiki_base: str,
    user: str,
    password: str,
    page_ref: str,
) -> dict[str, Any]:
    """
    GET /rest/api/content/{id} — 본문·스페이스·버전 등.
    page_ref: wiki_search 결과의 숫자 content id만 허용.
    """
    nid = normalize_wiki_page_id(page_ref)
    if not nid:
        raise ValueError(
            "content id는 숫자만 가능합니다 (wiki_search JSON의 id / content.id). "
            "'P1599' 같은 문서코드·키워드는 wiki_search 의 검색어(query)로 조회한 뒤, "
            "나온 페이지의 숫자 id로 다시 조회하세요."
        )

    auth = (user, password)
    headers = {"Accept": "application/json"}
    last_err: Exception | None = None

    for url in _content_get_url_candidates(wiki_base, nid):
        for expand in _EXPAND_TRIES:
            try:
                r = requests.get(
                    url,
                    params={"expand": expand},
                    auth=auth,
                    headers=headers,
                    timeout=60,
                )
            except requests.RequestException as e:
                last_err = e
                continue
            if r.status_code == 404:
                break
            if r.status_code == 400:
                continue
            try:
                r.raise_for_status()
            except requests.HTTPError as e:
                last_err = e
                continue
            data = r.json()
            if isinstance(data, dict):
                data["_wikiGetMeta"] = {"endpoint": url, "expand": expand}
            return data

    if last_err is not None:
        raise last_err
    raise requests.HTTPError(
        f"위키 페이지 조회 실패: id={nid!r}. URL·권한·ID를 확인하세요."
    )


def format_wiki_page_detail(page: dict[str, Any], wiki_base: str) -> str:
    """REST content 객체를 읽기 쉬운 텍스트로 (본문은 렌더 HTML에서 태그 제거)."""
    page = dict(page)
    page.pop("_wikiGetMeta", None)

    title = page.get("title") or "?"
    pid = page.get("id", "")
    ptype = page.get("type") or ""
    lines: list[str] = [
        f"제목: {title}",
        f"content ID: {pid}",
        f"타입: {ptype}",
    ]

    space = page.get("space") or {}
    if isinstance(space, dict):
        sk = space.get("key") or ""
        sn = space.get("name") or ""
        if sk or sn:
            lines.append(f"스페이스: {sk}" + (f" ({sn})" if sn else ""))

    ver = page.get("version") or {}
    if isinstance(ver, dict) and ver.get("number") is not None:
        lines.append(f"버전: {ver['number']}")
        if ver.get("when"):
            lines.append(f"수정 시각: {ver['when']}")

    ancestors = page.get("ancestors") or []
    if isinstance(ancestors, list) and ancestors:
        titles: list[str] = []
        for a in ancestors:
            if isinstance(a, dict) and a.get("title"):
                titles.append(str(a["title"]))
        if titles:
            lines.append("경로: " + " > ".join(titles))

    links = page.get("_links") or {}
    if isinstance(links, dict):
        webui = links.get("webui")
        if isinstance(webui, str) and webui.strip():
            wu = webui.strip()
            if wu.startswith("http"):
                lines.append(f"웹 URL: {wu}")
            else:
                lines.append(f"웹 URL: {urljoin(wiki_base.rstrip('/') + '/', wu)}")

    body = page.get("body") or {}
    text = ""
    if isinstance(body, dict):
        view = body.get("view")
        if isinstance(view, dict) and isinstance(view.get("value"), str):
            text = _strip_html(view["value"])
        if not text.strip():
            storage = body.get("storage")
            if isinstance(storage, dict) and isinstance(storage.get("value"), str):
                raw = storage["value"]
                text = _strip_html(raw) if "<" in raw else raw

    lines.append("")
    lines.append("── 본문 ──")
    lines.append(text.strip() if text.strip() else "(본문 없음 — 권한·expand 제한일 수 있음. output_format=json 으로 원본 확인)")

    return "\n".join(lines)


def main() -> None:
    import argparse
    import json
    import sys

    from jira_search import load_env_file

    root = os.path.dirname(os.path.abspath(__file__))
    load_env_file(os.path.join(root, ".env"))
    load_env_file(os.path.join(os.getcwd(), ".env"))

    parser = argparse.ArgumentParser(
        description="Confluence(위키) 검색(JSON) 또는 페이지 본문 조회(--page)"
    )
    parser.add_argument(
        "-V",
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )
    parser.add_argument(
        "query",
        nargs="?",
        default=None,
        help="검색어 (--page 사용 시 생략 가능)",
    )
    parser.add_argument(
        "--page",
        metavar="ID",
        dest="page_id",
        default=None,
        help="숫자 content id로 본문 조회 (예: 344872205). P1599 같은 코드는 검색어로 wiki_search 사용",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="--page 일 때 원본 JSON 출력 (기본은 읽기 쉬운 텍스트)",
    )
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
        if args.page_id is not None:
            if str(args.page_id).strip() == "":
                print("--page ID 가 비어 있습니다.", file=sys.stderr)
                sys.exit(2)
            data = get_wiki_page(base, user, password, str(args.page_id))
            if args.json:
                print(json.dumps(data, ensure_ascii=False, indent=2))
            else:
                print(format_wiki_page_detail(data, base))
            return

        q = (args.query or "").strip()
        if not q:
            print("검색어(query) 또는 --page ID 가 필요합니다.", file=sys.stderr)
            sys.exit(2)
        data = search_wiki(base, user, password, q, args.max, args.start)
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
