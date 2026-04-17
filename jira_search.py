#!/usr/bin/env python3
"""
Jira 이슈 검색 CLI (웹 UI 없이 REST API 사용).

환경 변수:
  JIRA_BASE_URL  예: http://jira.example.com:8080
  JIRA_USER      로그인 아이디
  JIRA_PASSWORD  비밀번호 (또는 PAT가 있다면 그 값)

선택: .env 파일을 쓰려면 `pip install python-dotenv` 후 스크립트에 load_dotenv() 추가.
"""

from __future__ import annotations

import argparse
import base64
import html
import json
import os
import re
import sys
from typing import Any
from urllib.parse import quote

import requests

from project_version import __version__


def load_env_file(path: str = ".env") -> None:
    """간단한 KEY=VALUE .env 로더 (외부 의존 없음)."""
    if not os.path.isfile(path):
        return
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" not in line:
                continue
            key, _, val = line.partition("=")
            key = key.strip()
            val = val.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = val


def try_get_config() -> tuple[str, str, str] | None:
    base = os.environ.get("JIRA_BASE_URL", "").rstrip("/")
    user = os.environ.get("JIRA_USER", "")
    password = os.environ.get("JIRA_PASSWORD", "")
    if not base or not user or not password:
        return None
    return base, user, password


def get_config() -> tuple[str, str, str]:
    c = try_get_config()
    if c is None:
        print(
            "JIRA_BASE_URL, JIRA_USER, JIRA_PASSWORD 환경 변수를 설정하세요.\n"
            "예: export JIRA_BASE_URL=http://jira.example.com:8080\n"
            "    export JIRA_USER=...\n"
            "    export JIRA_PASSWORD=...\n"
            "또는 프로젝트 루트에 .env 파일을 두어도 됩니다.",
            file=sys.stderr,
        )
        sys.exit(1)
    return c


def search_issues(
    base_url: str,
    user: str,
    password: str,
    jql: str,
    max_results: int,
    start_at: int,
    fields: list[str] | None,
) -> dict[str, Any]:
    url = f"{base_url}/rest/api/2/search"
    payload: dict[str, Any] = {
        "jql": jql,
        "maxResults": max_results,
        "startAt": start_at,
    }
    if fields:
        payload["fields"] = fields
    r = requests.post(
        url,
        json=payload,
        auth=(user, password),
        headers={"Content-Type": "application/json"},
        timeout=60,
    )
    if r.status_code == 404:
        # 일부 서버는 api/3만 노출
        url3 = f"{base_url}/rest/api/3/search"
        r = requests.post(
            url3,
            json=payload,
            auth=(user, password),
            headers={"Content-Type": "application/json"},
            timeout=60,
        )
    r.raise_for_status()
    return r.json()


def _normalize_picker_user_entries(items: list[Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        u = item.get("user") if isinstance(item.get("user"), dict) else item
        if not isinstance(u, dict):
            continue
        if u.get("name") or u.get("key") or u.get("displayName") or u.get("accountId"):
            out.append(u)
    return out


def _users_from_picker_payload(data: Any) -> list[dict[str, Any]] | None:
    if isinstance(data, list):
        return _normalize_picker_user_entries(data)
    if not isinstance(data, dict):
        return None
    for key in ("users", "suggestions", "values", "items"):
        arr = data.get(key)
        if isinstance(arr, list):
            return _normalize_picker_user_entries(arr)
    return None


def search_users(
    base_url: str,
    user: str,
    password: str,
    query: str,
    max_results: int = 20,
) -> list[dict[str, Any]]:
    """
    지라 웹의 사용자 필드 자동완성과 비슷한 검색.
    GET /rest/api/2/user/picker 를 우선 사용하고, 실패 시 user/search 등으로 폴백.
    """
    q = quote(query.strip(), safe="")
    n = max(1, min(int(max_results), 1000))
    auth = (user, password)
    headers = {"Accept": "application/json"}
    last_err: requests.HTTPError | None = None

    url_picker = f"{base_url}/rest/api/2/user/picker?query={q}&maxResults={n}"
    try:
        r = requests.get(url_picker, auth=auth, headers=headers, timeout=60)
        if r.ok:
            parsed = _users_from_picker_payload(r.json())
            if parsed is not None and len(parsed) > 0:
                return parsed[:n]
        elif r.status_code not in (400, 404, 405):
            r.raise_for_status()
    except requests.HTTPError as e:
        last_err = e

    for param in ("username", "query"):
        url = f"{base_url}/rest/api/2/user/search?{param}={q}&maxResults={n}"
        try:
            r = requests.get(url, auth=auth, headers=headers, timeout=60)
            if r.ok:
                data = r.json()
                if isinstance(data, list):
                    return data[:n]
            elif r.status_code not in (400, 404):
                r.raise_for_status()
        except requests.HTTPError as e:
            last_err = e

    url3 = f"{base_url}/rest/api/3/user/search?query={q}&maxResults={n}"
    r3 = requests.get(url3, auth=auth, headers=headers, timeout=60)
    try:
        r3.raise_for_status()
    except requests.HTTPError as e:
        if last_err:
            raise last_err from e
        raise
    data3 = r3.json()
    if isinstance(data3, list):
        return data3[:n]
    if isinstance(data3, dict):
        arr = data3.get("users") or data3.get("values")
        if isinstance(arr, list):
            return arr[:n]
    return []


def format_users_list(users: list[dict[str, Any]]) -> str:
    if not users:
        return "일치하는 사용자가 없습니다."
    lines: list[str] = [f"사용자 {len(users)}명\n"]
    for u in users:
        name = u.get("name") or u.get("key") or ""
        dn = u.get("displayName") or ""
        email = u.get("emailAddress") or ""
        active = u.get("active")
        extra = f"  ({email})" if email else ""
        act = "" if active is None else (" [활성]" if active else " [비활성]")
        lines.append(f"· {name}\t{dn}{extra}{act}")
    return "\n".join(lines)


def get_issue(
    base_url: str,
    user: str,
    password: str,
    issue_key: str,
) -> dict[str, Any]:
    q = "expand=renderedFields,names,changelog"
    url = f"{base_url}/rest/api/2/issue/{quote(issue_key, safe='')}?{q}"
    r = requests.get(
        url,
        auth=(user, password),
        headers={"Accept": "application/json"},
        timeout=60,
    )
    if r.status_code == 404:
        url3 = f"{base_url}/rest/api/3/issue/{quote(issue_key, safe='')}?expand=renderedFields,names,changelog"
        r = requests.get(
            url3,
            auth=(user, password),
            headers={"Accept": "application/json"},
            timeout=60,
        )
    r.raise_for_status()
    return r.json()


def get_issue_transitions(
    base_url: str,
    user: str,
    password: str,
    issue_key: str,
) -> dict[str, Any]:
    """GET /issue/{key}/transitions — 허용 전이 목록."""
    key_q = quote((issue_key or "").strip(), safe="")
    if not key_q:
        raise ValueError("issue_key 가 비어 있습니다.")
    b = base_url.rstrip("/")
    url = f"{b}/rest/api/2/issue/{key_q}/transitions"
    r = requests.get(
        url,
        auth=(user, password),
        headers={"Accept": "application/json"},
        timeout=60,
    )
    if r.status_code == 404:
        url3 = f"{b}/rest/api/3/issue/{key_q}/transitions"
        r = requests.get(
            url3,
            auth=(user, password),
            headers={"Accept": "application/json"},
            timeout=60,
        )
    r.raise_for_status()
    return r.json()


def get_issue_status_summary(
    base_url: str,
    user: str,
    password: str,
    issue_key: str,
) -> tuple[str, str]:
    """이슈 키와 현재 상태 이름만 조회 (전이 안내용 경량 호출)."""
    key_q = quote((issue_key or "").strip(), safe="")
    if not key_q:
        raise ValueError("issue_key 가 비어 있습니다.")
    b = base_url.rstrip("/")
    url = f"{b}/rest/api/2/issue/{key_q}?fields=status"
    r = requests.get(
        url,
        auth=(user, password),
        headers={"Accept": "application/json"},
        timeout=60,
    )
    if r.status_code == 404:
        url3 = f"{b}/rest/api/3/issue/{key_q}?fields=status"
        r = requests.get(
            url3,
            auth=(user, password),
            headers={"Accept": "application/json"},
            timeout=60,
        )
    r.raise_for_status()
    data = r.json()
    key_out = str(data.get("key") or (issue_key or "").strip())
    f = data.get("fields") or {}
    st = f.get("status") if isinstance(f.get("status"), dict) else {}
    status_name = str(st.get("name") or "").strip()
    return key_out, status_name


def do_issue_transition(
    base_url: str,
    user: str,
    password: str,
    issue_key: str,
    transition_id: str,
    fields: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """POST /issue/{key}/transitions — 한 단계 상태 전이."""
    key = (issue_key or "").strip()
    if not key:
        raise ValueError("issue_key 가 비어 있습니다.")
    tid = str(transition_id or "").strip()
    if not tid:
        raise ValueError("transition_id 가 비어 있습니다.")
    key_q = quote(key, safe="")
    body: dict[str, Any] = {"transition": {"id": tid}}
    if fields:
        body["fields"] = fields
    b = base_url.rstrip("/")
    url = f"{b}/rest/api/2/issue/{key_q}/transitions"
    r = requests.post(
        url,
        json=body,
        auth=(user, password),
        headers={"Content-Type": "application/json"},
        timeout=60,
    )
    if r.status_code == 404:
        url3 = f"{b}/rest/api/3/issue/{key_q}/transitions"
        r = requests.post(
            url3,
            json=body,
            auth=(user, password),
            headers={"Content-Type": "application/json"},
            timeout=60,
        )
    r.raise_for_status()
    if not r.content or not r.content.strip():
        return {}
    try:
        return r.json()
    except ValueError:
        return {}


def set_issue_assignee(
    base_url: str,
    user: str,
    password: str,
    issue_key: str,
    assignee_login: str | None = None,
    assignee_account_id: str | None = None,
) -> dict[str, Any]:
    """PUT /issue/{key} — 담당자(assignee)만 변경하거나 해제.

    - Server/Data Center: ``assignee_login`` 에 Jira **로그인 name** (``jira_search_users`` 결과의 name).
    - Jira Cloud: ``assignee_account_id`` 만 사용 (REST v3 ``accountId``).
    - 담당 해제: ``assignee_login``·``assignee_account_id`` 모두 비우거나
      ``assignee_login`` 을 ``(없음)``, ``-``, ``none`` 등으로 둔다.
    """
    key = (issue_key or "").strip()
    if not key:
        raise ValueError("issue_key 가 비어 있습니다.")
    aid = (assignee_account_id or "").strip()
    login = (assignee_login or "").strip()
    if aid and login:
        raise ValueError("assignee_login 과 assignee_account_id 는 하나만 지정하세요.")

    key_q = quote(key, safe="")
    b = base_url.rstrip("/")

    if aid:
        body: dict[str, Any] = {"fields": {"assignee": {"accountId": aid}}}
        urls = [f"{b}/rest/api/3/issue/{key_q}", f"{b}/rest/api/2/issue/{key_q}"]
    elif not login or login.lower() in ("null", "(없음)", "-", "none", "clear"):
        body = {"fields": {"assignee": None}}
        urls = [f"{b}/rest/api/2/issue/{key_q}", f"{b}/rest/api/3/issue/{key_q}"]
    else:
        body = {"fields": {"assignee": {"name": login}}}
        urls = [f"{b}/rest/api/2/issue/{key_q}", f"{b}/rest/api/3/issue/{key_q}"]

    last_exc: requests.HTTPError | None = None
    last_resp: requests.Response | None = None
    for url in urls:
        r = requests.put(
            url,
            json=body,
            auth=(user, password),
            headers={"Content-Type": "application/json"},
            timeout=60,
        )
        last_resp = r
        if r.status_code == 404:
            continue
        try:
            r.raise_for_status()
        except requests.HTTPError as e:
            last_exc = e
            continue
        if not r.content or not r.content.strip():
            return {}
        try:
            return r.json()
        except ValueError:
            return {}
    if last_exc:
        raise last_exc
    if last_resp is not None:
        last_resp.raise_for_status()
    raise RuntimeError("담당자 변경: 응답 없음")


def format_transitions_block(
    issue_key: str,
    current_status: str,
    transitions_payload: dict[str, Any],
) -> str:
    tlist = transitions_payload.get("transitions") or []
    lines = [
        f"이슈: {issue_key}",
        f"현재 상태: {current_status or '(알 수 없음)'}",
        "",
        "다음에 수행 가능한 전이(워크플로 작업):",
    ]
    if not isinstance(tlist, list) or not tlist:
        lines.append("(없음 — 종료·권한·조건 등으로 전이가 없을 수 있음)")
        return "\n".join(lines)
    for t in tlist:
        if not isinstance(t, dict):
            continue
        tid = t.get("id", "")
        tname = t.get("name") or ""
        to = t.get("to") if isinstance(t.get("to"), dict) else {}
        to_name = (to or {}).get("name") or ""
        lines.append(f"  · transition_id={tid}\t「{tname}」 → 상태「{to_name}」")
    lines.append("")
    lines.append(
        "사용자가 목표 상태(예: 접수)를 말했을 때: 위 목록에서 "
        "전이 이름 또는 이동 후 상태(to)가 일치하는 transition_id 하나를 고른 뒤 "
        "jira_transition_issue 로 실행한다. "
        "일치하는 것이 없거나 여러 개면 이 목록을 사용자에게 보여 주고 선택하게 한다."
    )
    return "\n".join(lines)


def _fetch_comment_page_v2(
    base_url: str,
    user: str,
    password: str,
    key_q: str,
    start: int,
    page_size: int,
) -> dict[str, Any]:
    variants = [
        f"?startAt={start}&maxResults={page_size}&expand=renderedBody&orderBy=created",
        f"?startAt={start}&maxResults={page_size}&expand=renderedBody",
        f"?startAt={start}&maxResults={page_size}",
    ]
    last_exc: requests.HTTPError | None = None
    for qs in variants:
        url = f"{base_url}/rest/api/2/issue/{key_q}/comment{qs}"
        r = requests.get(
            url,
            auth=(user, password),
            headers={"Accept": "application/json"},
            timeout=60,
        )
        if r.status_code == 404:
            break
        if r.status_code == 400:
            continue
        try:
            r.raise_for_status()
        except requests.HTTPError as e:
            last_exc = e
            continue
        return r.json()
    if last_exc:
        raise last_exc
    url3 = f"{base_url}/rest/api/3/issue/{key_q}/comment?startAt={start}&maxResults={page_size}"
    r = requests.get(
        url3,
        auth=(user, password),
        headers={"Accept": "application/json"},
        timeout=60,
    )
    r.raise_for_status()
    return r.json()


def get_issue_comments(
    base_url: str,
    user: str,
    password: str,
    issue_key: str,
    max_total: int = 500,
    page_size: int = 50,
) -> list[dict[str, Any]]:
    key_q = quote(issue_key, safe="")
    collected: list[dict[str, Any]] = []
    start = 0
    while len(collected) < max_total:
        data = _fetch_comment_page_v2(
            base_url, user, password, key_q, start, page_size
        )
        chunk = data.get("comments") or []
        collected.extend(chunk)
        total = data.get("total")
        if total is None:
            total = len(collected) if not chunk else start + len(chunk)
        else:
            total = int(total)
        if not chunk or start + len(chunk) >= total:
            break
        start += len(chunk)
    try:
        collected.sort(key=lambda c: (c.get("created") or ""))
    except Exception:
        pass
    return collected[:max_total]


def _adf_paragraph_document(text: str) -> dict[str, Any]:
    """Jira REST API 3.x 댓글용 최소 ADF 문서."""
    return {
        "type": "doc",
        "version": 1,
        "content": [
            {
                "type": "paragraph",
                "content": [{"type": "text", "text": text}],
            }
        ],
    }


def add_issue_comment(
    base_url: str,
    user: str,
    password: str,
    issue_key: str,
    body_text: str,
) -> dict[str, Any]:
    """
    이슈에 댓글 등록. Server는 보통 REST v2 문자열 body, 일부 환경은 v3 ADF만 허용.
    """
    key = (issue_key or "").strip()
    text = (body_text or "").strip()
    if not key:
        raise ValueError("issue_key 가 비어 있습니다.")
    if not text:
        raise ValueError("댓글 본문이 비어 있습니다.")

    key_q = quote(key, safe="")
    auth = (user, password)
    headers = {"Accept": "application/json", "Content-Type": "application/json"}
    url2 = f"{base_url.rstrip('/')}/rest/api/2/issue/{key_q}/comment"

    r2 = requests.post(
        url2,
        json={"body": text},
        auth=auth,
        headers=headers,
        timeout=60,
    )
    if r2.status_code in (200, 201):
        return r2.json()

    if r2.status_code not in (400, 404, 415):
        r2.raise_for_status()

    url3 = f"{base_url.rstrip('/')}/rest/api/3/issue/{key_q}/comment"
    r3 = requests.post(
        url3,
        json={"body": _adf_paragraph_document(text)},
        auth=auth,
        headers=headers,
        timeout=60,
    )
    r3.raise_for_status()
    return r3.json()


def _adf_to_plain(node: Any) -> str:
    if node is None:
        return ""
    if isinstance(node, str):
        return node
    if isinstance(node, dict):
        if node.get("type") == "text" and "text" in node:
            return str(node["text"])
        inner = node.get("content")
        if isinstance(inner, list):
            return "".join(_adf_to_plain(x) for x in inner)
        return ""
    if isinstance(node, list):
        return "".join(_adf_to_plain(x) for x in node)
    return ""


def _comment_body_text(c: dict[str, Any]) -> str:
    rb = c.get("renderedBody")
    if isinstance(rb, str) and rb.strip():
        return _strip_html(rb)
    body = c.get("body")
    if isinstance(body, str) and body.strip():
        return body.strip()
    if isinstance(body, dict):
        t = _adf_to_plain(body).strip()
        return t if t else "(구조화 본문 — --json 으로 확인)"
    return "(없음)"


def format_attachments_block(fields: dict[str, Any]) -> str:
    att = fields.get("attachment")
    if not isinstance(att, list) or not att:
        return ""
    lines: list[str] = ["── 첨부파일 ──"]
    for a in att:
        if not isinstance(a, dict):
            continue
        fn = a.get("filename") or "?"
        aid = a.get("id", "")
        sz = a.get("size")
        mt = a.get("mimeType") or ""
        url = a.get("content") or ""
        who = _person_name(a.get("author"))
        when = a.get("created") or ""
        lines.append(f"· [{aid}] {fn}")
        lines.append(f"  크기: {sz} bytes  타입: {mt}  업로드: {when}  {who}")
        if url:
            lines.append(f"  content URL: {url}")
    lines.append(
        "  ※ URL은 지라 로그인(세션) 또는 API와 동일한 Basic 인증이 있어야 열립니다."
        " 로컬 저장: --save-attachments 디렉터리"
    )
    return "\n".join(lines)


def _safe_attachment_filename(name: str) -> str:
    name = (name or "file").replace("\x00", "")
    for c in '<>:"/\\|?*\n\r\t':
        name = name.replace(c, "_")
    name = name.strip(" .")
    return name or "file"


def save_issue_attachments(
    user: str,
    password: str,
    fields: dict[str, Any],
    dest_dir: str,
) -> list[str]:
    att = fields.get("attachment")
    if not isinstance(att, list) or not att:
        return []
    os.makedirs(dest_dir, exist_ok=True)
    saved: list[str] = []
    for a in att:
        if not isinstance(a, dict):
            continue
        url = a.get("content")
        if not isinstance(url, str) or not url.strip():
            continue
        aid = str(a.get("id") or "x")
        base = _safe_attachment_filename(str(a.get("filename") or f"attachment_{aid}"))
        path = os.path.join(dest_dir, f"{aid}_{base}")
        n = 0
        while os.path.exists(path):
            n += 1
            root, ext = os.path.splitext(base)
            path = os.path.join(dest_dir, f"{aid}_{root}_{n}{ext}")
        r = requests.get(
            url,
            auth=(user, password),
            stream=True,
            timeout=120,
        )
        r.raise_for_status()
        with open(path, "wb") as out:
            for chunk in r.iter_content(chunk_size=256 * 1024):
                if chunk:
                    out.write(chunk)
        saved.append(path)
    return saved


def fetch_issue_attachments_inline(
    user: str,
    password: str,
    fields: dict[str, Any],
    max_bytes_per_file: int = 2_000_000,
    max_total_bytes: int = 8_000_000,
) -> list[dict[str, Any]]:
    """
    첨부를 메모리로 받아 base64로 반환. Claude Desktop 등에서 로컬 경로 공유가 안 될 때 사용.
    큰 파일은 skipped 로 건너뜀.
    """
    att = fields.get("attachment")
    if not isinstance(att, list) or not att:
        return []
    max_bytes_per_file = max(1024, int(max_bytes_per_file))
    max_total_bytes = max(1024, int(max_total_bytes))
    out: list[dict[str, Any]] = []
    total_encoded = 0

    for a in att:
        if not isinstance(a, dict):
            continue
        url = a.get("content")
        if not isinstance(url, str) or not url.strip():
            continue
        fn = str(a.get("filename") or "?")
        aid = str(a.get("id") or "")
        mt = str(a.get("mimeType") or "application/octet-stream")
        sz_meta = a.get("size")
        try:
            if sz_meta is not None and int(sz_meta) > max_bytes_per_file:
                out.append(
                    {
                        "filename": fn,
                        "attachment_id": aid,
                        "mimeType": mt,
                        "skipped": True,
                        "reason": f"이슈 메타 크기 {sz_meta} bytes > 한도 {max_bytes_per_file}",
                    }
                )
                continue
        except (TypeError, ValueError):
            pass

        r = requests.get(
            url,
            auth=(user, password),
            stream=True,
            timeout=120,
        )
        r.raise_for_status()
        chunks: list[bytes] = []
        nread = 0
        too_big = False
        for chunk in r.iter_content(chunk_size=65536):
            if not chunk:
                continue
            nread += len(chunk)
            if nread > max_bytes_per_file:
                too_big = True
                break
            chunks.append(chunk)
        if too_big:
            out.append(
                {
                    "filename": fn,
                    "attachment_id": aid,
                    "mimeType": mt,
                    "skipped": True,
                    "reason": f"실제 다운로드 크기 > 한도 {max_bytes_per_file} bytes",
                }
            )
            continue

        data = b"".join(chunks)
        ln = len(data)
        if ln == 0:
            out.append(
                {
                    "filename": fn,
                    "attachment_id": aid,
                    "mimeType": mt,
                    "skipped": True,
                    "reason": "빈 파일",
                }
            )
            continue
        if total_encoded + ln > max_total_bytes:
            out.append(
                {
                    "filename": fn,
                    "attachment_id": aid,
                    "mimeType": mt,
                    "skipped": True,
                    "reason": f"누적 한도 초과 (max_total_bytes={max_total_bytes})",
                }
            )
            continue

        total_encoded += ln
        b64 = base64.standard_b64encode(data).decode("ascii")
        out.append(
            {
                "filename": fn,
                "attachment_id": aid,
                "mimeType": mt,
                "size": ln,
                "content_base64": b64,
            }
        )
    return out


def format_changelog(issue: dict[str, Any]) -> str:
    ch = issue.get("changelog")
    if not isinstance(ch, dict):
        return ""
    histories = ch.get("histories") or []
    if not isinstance(histories, list) or not histories:
        return ""
    lines = ["", "── 변경 이력 ──"]
    for h in histories:
        if not isinstance(h, dict):
            continue
        who = _person_name(h.get("author"))
        when = h.get("created") or ""
        lines.append(f"[{when}] {who or '(시스템)'}")
        items = h.get("items") or []
        if not isinstance(items, list):
            continue
        for it in items:
            if not isinstance(it, dict):
                continue
            field = it.get("field") or it.get("fieldId") or "?"
            frm = it.get("fromString")
            to = it.get("toString")
            if frm is None and to is None:
                continue
            lines.append(f"  · {field}: {frm!r} → {to!r}")
    return "\n".join(lines)


def format_comments_block(comments: list[dict[str, Any]]) -> str:
    if not comments:
        return "\n\n── 댓글 ──\n(없음)"
    lines = ["", "── 댓글 ──"]
    for i, c in enumerate(comments, 1):
        if not isinstance(c, dict):
            continue
        who = _person_name(c.get("author"))
        when = c.get("created") or ""
        lines.append(f"--- #{i} [{when}] {who} ---")
        lines.append(_comment_body_text(c))
        lines.append("")
    return "\n".join(lines).rstrip()


def _person_name(p: Any) -> str:
    if not isinstance(p, dict):
        return ""
    return (p.get("displayName") or p.get("name") or "").strip()


def _strip_html(s: str) -> str:
    t = re.sub(r"<[^>]+>", " ", s)
    t = html.unescape(t)
    t = re.sub(r"\s+", " ", t).strip()
    return t


def format_issue_detail(
    issue: dict[str, Any],
    comments: list[dict[str, Any]] | None = None,
) -> str:
    key = issue.get("key", "?")
    f = issue.get("fields") or {}
    lines: list[str] = [
        f"이슈: {key}",
        f"요약: {f.get('summary') or ''}",
    ]
    it = f.get("issuetype")
    if isinstance(it, dict) and it.get("name"):
        lines.append(f"유형: {it['name']}")
    st = f.get("status")
    if isinstance(st, dict) and st.get("name"):
        lines.append(f"상태: {st['name']}")
    pr = f.get("priority")
    if isinstance(pr, dict) and pr.get("name"):
        lines.append(f"우선순위: {pr['name']}")
    lines.append(f"담당: {_person_name(f.get('assignee')) or '(없음)'}")
    lines.append(f"보고자: {_person_name(f.get('reporter')) or '(없음)'}")
    if f.get("created"):
        lines.append(f"생성: {f['created']}")
    if f.get("updated"):
        lines.append(f"수정: {f['updated']}")
    res = f.get("resolution")
    if isinstance(res, dict) and res.get("name"):
        lines.append(f"해결: {res['name']}")
    comps = f.get("components")
    if isinstance(comps, list) and comps:
        names = [c.get("name") for c in comps if isinstance(c, dict) and c.get("name")]
        if names:
            lines.append(f"구성요소: {', '.join(names)}")
    labels = f.get("labels")
    if isinstance(labels, list) and labels:
        lines.append(f"라벨: {', '.join(str(x) for x in labels)}")

    desc_plain = f.get("description")
    desc_text = ""
    if isinstance(desc_plain, str) and desc_plain.strip():
        desc_text = desc_plain.strip()
    rf = issue.get("renderedFields") or {}
    if not desc_text and isinstance(rf.get("description"), str) and rf["description"].strip():
        desc_text = _strip_html(rf["description"])
    lines.append("")
    lines.append("설명:")
    lines.append(desc_text if desc_text else "(없음)")
    att_txt = format_attachments_block(f)
    if att_txt:
        lines.append("")
        lines.extend(att_txt.split("\n"))

    text = "\n".join(lines)
    text += format_changelog(issue)
    text += format_comments_block(comments if comments is not None else [])
    return text


def format_issue(issue: dict[str, Any]) -> str:
    key = issue.get("key", "?")
    fields = issue.get("fields") or {}
    summary = fields.get("summary") or ""
    st = fields.get("status") or {}
    status_name = st.get("name", "") if isinstance(st, dict) else ""
    assignee = fields.get("assignee")
    assignee_name = ""
    if isinstance(assignee, dict):
        assignee_name = assignee.get("displayName") or assignee.get("name") or ""
    line = f"{key}\t{status_name}\t{assignee_name}\t{summary}"
    return line


def main() -> None:
    load_env_file()

    parser = argparse.ArgumentParser(description="Jira JQL 검색 / 이슈 상세 조회")
    parser.add_argument(
        "-V",
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )
    parser.add_argument(
        "-i",
        "--issue",
        metavar="KEY",
        help="이슈 키(예: PROJ-123) 상세 조회 — 지정 시 JQL 검색은 하지 않음",
    )
    parser.add_argument(
        "-u",
        "--users",
        metavar="QUERY",
        help="사용자 검색(웹 자동완성과 유사). 아이디·이름 일부 입력 — JQL 검색과 동시 사용 불가",
    )
    parser.add_argument(
        "jql",
        nargs="?",
        default="assignee = currentUser() ORDER BY updated DESC",
        help="JQL (기본: 내 담당 이슈 최근순)",
    )
    parser.add_argument("-n", "--max", type=int, default=20, help="최대 개수 (기본 20)")
    parser.add_argument("-s", "--start", type=int, default=0, help="페이지 시작 offset")
    parser.add_argument(
        "-j",
        "--json",
        action="store_true",
        help="응답을 JSON으로 출력 (검색: Jira search API 그대로, 상세: issue+comments)",
    )
    parser.add_argument(
        "--fields",
        type=str,
        default="summary,status,assignee,updated",
        help="콤마로 구분한 필드 목록",
    )
    parser.add_argument(
        "--save-attachments",
        metavar="DIR",
        help="--issue 와 함께 사용: 첨부파일을 해당 폴더에 다운로드",
    )
    parser.add_argument(
        "--post-comment-on",
        metavar="KEY",
        dest="post_comment_issue",
        help="이슈에 댓글 등록 — 반드시 --comment-body 와 함께",
    )
    parser.add_argument(
        "--comment-body",
        metavar="TEXT",
        dest="comment_body",
        help="등록할 댓글 본문",
    )
    args = parser.parse_args()

    if args.save_attachments and not args.issue:
        print("--save-attachments 는 --issue 와 함께 써야 합니다.", file=sys.stderr)
        sys.exit(2)
    if args.users and args.issue:
        print("--users 와 --issue 는 함께 쓸 수 없습니다.", file=sys.stderr)
        sys.exit(2)
    if args.post_comment_issue or args.comment_body:
        if not args.post_comment_issue or not args.comment_body:
            print(
                "--post-comment-on 과 --comment-body 는 둘 다 지정해야 합니다.",
                file=sys.stderr,
            )
            sys.exit(2)
        if args.issue or args.users:
            print(
                "--post-comment-on 은 --issue / --users 와 함께 쓸 수 없습니다.",
                file=sys.stderr,
            )
            sys.exit(2)

    base, user, password = get_config()

    if args.post_comment_issue:
        key = str(args.post_comment_issue).strip()
        body = str(args.comment_body or "").strip()
        if not body:
            print("댓글 본문이 비어 있습니다.", file=sys.stderr)
            sys.exit(2)
        try:
            out = add_issue_comment(base, user, password, key, body)
        except ValueError as e:
            print(str(e), file=sys.stderr)
            sys.exit(2)
        except requests.HTTPError as e:
            err_body = ""
            if e.response is not None:
                try:
                    err_body = e.response.text[:2000]
                except Exception:
                    err_body = str(e.response)
            print(f"HTTP 오류: {e}\n{err_body}", file=sys.stderr)
            sys.exit(1)
        except requests.RequestException as e:
            print(f"요청 실패: {e}", file=sys.stderr)
            sys.exit(1)
        if args.json:
            print(json.dumps(out, ensure_ascii=False, indent=2))
        else:
            aid = out.get("id", "?")
            au = out.get("author") if isinstance(out.get("author"), dict) else {}
            aname = (au.get("displayName") or au.get("name") or "").strip()
            when = out.get("created") or ""
            print(f"댓글 등록됨 id={aid} 작성자={aname or '(알 수 없음)'} 시각={when}")
        return
    field_list = [f.strip() for f in args.fields.split(",") if f.strip()]

    if args.users is not None:
        q = str(args.users).strip()
        if not q:
            print("사용자 검색어가 비어 있습니다.", file=sys.stderr)
            sys.exit(2)
        try:
            ulist = search_users(base, user, password, q, args.max)
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
        if args.json:
            print(json.dumps(ulist, ensure_ascii=False, indent=2))
        else:
            print(format_users_list(ulist))
        return

    try:
        if args.issue:
            data = get_issue(base, user, password, args.issue.strip())
        else:
            data = search_issues(
                base, user, password, args.jql, args.max, args.start, field_list
            )
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

    if args.issue:
        comments = get_issue_comments(base, user, password, args.issue.strip())
        if args.save_attachments:
            try:
                saved = save_issue_attachments(
                    user,
                    password,
                    data.get("fields") or {},
                    args.save_attachments,
                )
            except requests.HTTPError as e:
                print(f"첨부 다운로드 실패: {e}", file=sys.stderr)
                sys.exit(1)
            except OSError as e:
                print(f"파일 저장 실패: {e}", file=sys.stderr)
                sys.exit(1)
            if saved:
                print("첨부 저장:", file=sys.stderr)
                for p in saved:
                    print(f"  {p}", file=sys.stderr)
            else:
                print("저장할 첨부가 없습니다.", file=sys.stderr)
        if args.json:
            out = {"issue": data, "comments": comments}
            print(json.dumps(out, ensure_ascii=False, indent=2))
        else:
            print(format_issue_detail(data, comments))
        return

    if args.json:
        print(json.dumps(data, ensure_ascii=False, indent=2))
        return

    total = data.get("total", 0)
    issues = data.get("issues") or []
    print(f"총 {total}건 (표시 {len(issues)}건)\n")
    for issue in issues:
        print(format_issue(issue))


if __name__ == "__main__":
    main()
