#!/usr/bin/env python3
"""
Jira MCP 서버 (stdio / JSON-RPC). Cursor·Claude Desktop 등 MCP 클라이언트에서 사용.

설정: 스크립트와 같은 디렉터리의 .env 또는 환경 변수
  JIRA_BASE_URL, JIRA_USER, JIRA_PASSWORD
  WIKI_BASE_URL (선택, 기본 http://wiki.example.com:8080) — 위키 검색은 JIRA_USER / JIRA_PASSWORD 사용

Cursor 예시 (mcp.json):
  "jira": {
    "command": "/절대경로/jira-wiki/.venv/bin/python",
    "args": ["/절대경로/jira-wiki/mcp_jira_server.py"]
  }

stdout에는 JSON-RPC만 출력합니다 (디버그는 stderr).
"""

from __future__ import annotations

import json
import os
import sys
from typing import Any

import requests

import jira_search as js
import wiki_search as ws
from project_version import __version__ as SERVER_VERSION

PROTOCOL_VERSION = "2024-11-05"
SERVER_NAME = "jira-wiki"


def _bootstrap_env() -> None:
    root = os.path.dirname(os.path.abspath(__file__))
    js.load_env_file(os.path.join(root, ".env"))
    js.load_env_file(os.path.join(os.getcwd(), ".env"))


def _send(obj: dict[str, Any]) -> None:
    sys.stdout.write(json.dumps(obj, ensure_ascii=False) + "\n")
    sys.stdout.flush()


def _read_request() -> dict[str, Any] | None:
    fin = sys.stdin.buffer
    line = fin.readline()
    if not line:
        return None
    if line.lower().startswith(b"content-length:"):
        try:
            length = int(line.decode("ascii", errors="ignore").split(":", 1)[1].strip())
        except (ValueError, IndexError):
            return None
        while True:
            sep = fin.readline()
            if sep in (b"\r\n", b"\n", b""):
                break
        body = fin.read(length)
        if not body:
            return None
        return json.loads(body.decode("utf-8"))
    line = line.strip()
    if not line:
        return _read_request()
    return json.loads(line.decode("utf-8"))


def _tool_text(text: str, is_error: bool = False) -> dict[str, Any]:
    return {
        "content": [{"type": "text", "text": text}],
        "isError": is_error,
    }


def _parse_fields(s: str | None) -> list[str] | None:
    if not s or not str(s).strip():
        return None
    return [x.strip() for x in str(s).split(",") if x.strip()]


TOOLS: list[dict[str, Any]] = [
    {
        "name": "jira_search",
        "description": "JQL로 이슈 검색. Jira REST /search 응답(JSON)을 문자열로 반환.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "jql": {
                    "type": "string",
                    "description": "JQL 쿼리",
                },
                "max_results": {
                    "type": "integer",
                    "default": 20,
                    "description": "최대 결과 수",
                },
                "start_at": {
                    "type": "integer",
                    "default": 0,
                    "description": "페이지 시작 offset",
                },
                "fields": {
                    "type": "string",
                    "description": "콤마로 구분한 필드 (비우면 Jira 기본)",
                },
            },
            "required": ["jql"],
        },
    },
    {
        "name": "jira_search_users",
        "description": "사용자 아이디·이름 일부로 검색(웹 UI 사용자 필드 자동완성과 유사). JSON 배열 문자열 반환.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "검색어(로그인 id 또는 표시 이름 일부)",
                },
                "max_results": {
                    "type": "integer",
                    "default": 20,
                    "description": "최대 인원",
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "jira_get_issue",
        "description": "이슈 키로 상세 조회. 본문·첨부 메타·변경 이력·댓글 포함 텍스트 또는 JSON.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "issue_key": {"type": "string", "description": "예: PROJ-123"},
                "output_format": {
                    "type": "string",
                    "enum": ["text", "json"],
                    "default": "text",
                    "description": "text=읽기 쉬운 요약, json=issue+comments 원본",
                },
                "include_comments": {
                    "type": "boolean",
                    "default": True,
                },
            },
            "required": ["issue_key"],
        },
    },
    {
        "name": "jira_download_attachments",
        "description": "이슈 첨부를 dest_dir에 저장. dest_dir는 반드시 실제 Mac/Windows 사용자 경로(예: /Users/이름/Downloads/jira_files). Claude가 /tmp 등만 쓰면 앱에서 파일이 안 보일 수 있음.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "issue_key": {"type": "string"},
                "dest_dir": {
                    "type": "string",
                    "description": "저장 폴더 — 절대 경로 권장. ~ 는 홈으로 확장됨. 예: /Users/me/Downloads/jira_CSA10-36630",
                },
            },
            "required": ["issue_key", "dest_dir"],
        },
    },
    {
        "name": "jira_fetch_attachments",
        "description": "이슈 첨부를 MCP 응답 JSON으로 반환(content_base64). Claude Desktop 등 디스크 경로가 공유 안 될 때 이미지·작은 파일 확인용. 큰 파일은 skipped.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "issue_key": {"type": "string", "description": "예: CSA10-36630"},
                "max_bytes_per_file": {
                    "type": "integer",
                    "default": 2000000,
                    "description": "파일당 최대 바이트 (기본 2MB)",
                },
                "max_total_bytes": {
                    "type": "integer",
                    "default": 8000000,
                    "description": "전체 누적 최대 (기본 8MB)",
                },
            },
            "required": ["issue_key"],
        },
    },
    {
        "name": "wiki_search",
        "description": "Confluence(위키) 전문 검색. query에 문서코드·키워드 그대로 (예: P1599). 목록·숫자 id만 JSON 반환. 본문은 wiki_get_page(숫자 id).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "검색어(제목·본문 일치)",
                },
                "max_results": {
                    "type": "integer",
                    "default": 20,
                    "description": "최대 결과 수 (1~100)",
                },
                "start_at": {
                    "type": "integer",
                    "default": 0,
                    "description": "페이지 시작 offset",
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "wiki_get_page",
        "description": "Confluence 페이지 본문 조회. content_id는 숫자 id만 (wiki_search 결과). P1599 같은 문서코드는 wiki_search(query)로 검색.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "content_id": {
                    "type": "string",
                    "description": "숫자 content id만 (예: 344872205). wiki_search 결과의 id 또는 content.id. P1599는 검색어이므로 wiki_search 사용",
                },
                "output_format": {
                    "type": "string",
                    "enum": ["text", "json"],
                    "default": "text",
                    "description": "text=본문 요약, json=API 전체 JSON",
                },
            },
            "required": ["content_id"],
        },
    },
]


def _call_tool(name: str, arguments: dict[str, Any] | None) -> dict[str, Any]:
    arguments = arguments or {}
    if name in ("wiki_search", "wiki_get_page"):
        wcfg = ws.try_get_wiki_config()
        if wcfg is None:
            return _tool_text(
                "위키 도구에 JIRA_USER, JIRA_PASSWORD 가 필요합니다. "
                "선택적으로 WIKI_BASE_URL(기본: http://wiki.example.com:8080)을 .env 에 넣을 수 있습니다.",
                is_error=True,
            )
        wiki_base, user, password = wcfg
        try:
            if name == "wiki_search":
                q = str(arguments.get("query") or "").strip()
                if not q:
                    return _tool_text("query 가 필요합니다.", is_error=True)
                data = ws.search_wiki(
                    wiki_base,
                    user,
                    password,
                    q,
                    int(arguments.get("max_results") or 20),
                    int(arguments.get("start_at") or 0),
                )
                return _tool_text(json.dumps(data, ensure_ascii=False, indent=2))

            page_ref = str(arguments.get("content_id") or "").strip()
            if not page_ref:
                return _tool_text(
                    "content_id 에는 숫자 id만 넣으세요 (wiki_search 결과). "
                    "P1599 같은 문서코드는 wiki_search 의 query 로 검색하세요.",
                    is_error=True,
                )
            data = ws.get_wiki_page(wiki_base, user, password, page_ref)
            fmt = (arguments.get("output_format") or "text").lower()
            if fmt == "json":
                return _tool_text(json.dumps(data, ensure_ascii=False, indent=2))
            return _tool_text(ws.format_wiki_page_detail(data, wiki_base))
        except ValueError as e:
            return _tool_text(str(e), is_error=True)
        except requests.HTTPError as e:
            body = ""
            if e.response is not None:
                try:
                    body = e.response.text[:4000]
                except Exception:
                    body = str(e.response)
            return _tool_text(f"HTTP 오류: {e}\n{body}", is_error=True)
        except requests.RequestException as e:
            return _tool_text(f"요청 실패: {e}", is_error=True)
        except Exception as e:
            return _tool_text(f"오류: {e!r}", is_error=True)

    cfg = js.try_get_config()
    if cfg is None:
        return _tool_text(
            "JIRA_BASE_URL, JIRA_USER, JIRA_PASSWORD 가 설정되지 않았습니다. "
            "mcp_jira_server.py 와 같은 폴더의 .env 또는 MCP env 에 넣어 주세요.",
            is_error=True,
        )
    base, user, password = cfg

    try:
        if name == "jira_search":
            jql = arguments.get("jql")
            if not jql:
                return _tool_text("jql 이 필요합니다.", is_error=True)
            data = js.search_issues(
                base,
                user,
                password,
                str(jql),
                int(arguments.get("max_results") or 20),
                int(arguments.get("start_at") or 0),
                _parse_fields(arguments.get("fields")),
            )
            return _tool_text(json.dumps(data, ensure_ascii=False, indent=2))

        if name == "jira_search_users":
            q = str(arguments.get("query") or "").strip()
            if not q:
                return _tool_text("query 가 필요합니다.", is_error=True)
            ulist = js.search_users(
                base,
                user,
                password,
                q,
                int(arguments.get("max_results") or 20),
            )
            return _tool_text(json.dumps(ulist, ensure_ascii=False, indent=2))

        if name == "jira_get_issue":
            key = arguments.get("issue_key")
            if not key:
                return _tool_text("issue_key 가 필요합니다.", is_error=True)
            key = str(key).strip()
            issue = js.get_issue(base, user, password, key)
            inc = arguments.get("include_comments", True)
            comments: list[dict[str, Any]] = []
            if inc:
                comments = js.get_issue_comments(base, user, password, key)
            fmt = (arguments.get("output_format") or "text").lower()
            if fmt == "json":
                return _tool_text(
                    json.dumps(
                        {"issue": issue, "comments": comments},
                        ensure_ascii=False,
                        indent=2,
                    )
                )
            return _tool_text(js.format_issue_detail(issue, comments))

        if name == "jira_download_attachments":
            key = str(arguments.get("issue_key") or "").strip()
            dest = str(arguments.get("dest_dir") or "").strip()
            if not key or not dest:
                return _tool_text("issue_key 와 dest_dir 가 필요합니다.", is_error=True)
            dest_abs = os.path.abspath(os.path.expanduser(dest))
            issue = js.get_issue(base, user, password, key)
            paths = js.save_issue_attachments(
                user, password, issue.get("fields") or {}, dest_abs
            )
            if not paths:
                return _tool_text("첨부가 없거나 다운로드할 URL이 없습니다.")
            lines = [
                f"저장 위치(절대 경로): {dest_abs}",
                "각 파일 존재 여부는 서버 프로세스 기준입니다. Finder에서 위 폴더를 직접 여세요.",
                "",
            ]
            for p in paths:
                exists = os.path.isfile(p)
                sz = os.path.getsize(p) if exists else -1
                lines.append(f"· {p}")
                lines.append(f"  존재: {exists}, 크기: {sz} bytes")
            lines.append(
                "\n※ Claude Desktop: dest_dir 로 /tmp, ./mcp_out 등 가상 경로만 쓰면 "
                "본인 Mac에 파일이 생기지 않을 수 있습니다. "
                "반드시 /Users/본인계정/Downloads/jira_attach 처럼 실제 홈 디렉터리 경로를 지정하세요."
            )
            return _tool_text("\n".join(lines), is_error=False)

        if name == "jira_fetch_attachments":
            key = str(arguments.get("issue_key") or "").strip()
            if not key:
                return _tool_text("issue_key 가 필요합니다.", is_error=True)
            mpf = int(arguments.get("max_bytes_per_file") or 2_000_000)
            mtot = int(arguments.get("max_total_bytes") or 8_000_000)
            issue = js.get_issue(base, user, password, key)
            items = js.fetch_issue_attachments_inline(
                user, password, issue.get("fields") or {}, mpf, mtot
            )
            if not items:
                return _tool_text("첨부가 없거나 가져올 URL이 없습니다.")
            return _tool_text(json.dumps(items, ensure_ascii=False, indent=2))

        return _tool_text(f"알 수 없는 도구: {name}", is_error=True)
    except requests.HTTPError as e:
        body = ""
        if e.response is not None:
            try:
                body = e.response.text[:4000]
            except Exception:
                body = str(e.response)
        return _tool_text(f"HTTP 오류: {e}\n{body}", is_error=True)
    except requests.RequestException as e:
        return _tool_text(f"요청 실패: {e}", is_error=True)
    except OSError as e:
        return _tool_text(f"파일/경로 오류: {e}", is_error=True)
    except Exception as e:
        return _tool_text(f"오류: {e!r}", is_error=True)


def _handle(req: dict[str, Any]) -> None:
    method = req.get("method")
    params = req.get("params") or {}

    if method is None:
        return

    # JSON-RPC Notification: id 없음(또는 null) → 응답 없음
    if "id" not in req or req.get("id") is None:
        return

    rid = req["id"]

    if method == "initialize":
        _send(
            {
                "jsonrpc": "2.0",
                "id": rid,
                "result": {
                    "protocolVersion": PROTOCOL_VERSION,
                    "capabilities": {"tools": {}},
                    "serverInfo": {"name": SERVER_NAME, "version": SERVER_VERSION},
                },
            }
        )
        return

    if method == "tools/list":
        _send(
            {
                "jsonrpc": "2.0",
                "id": rid,
                "result": {"tools": TOOLS},
            }
        )
        return

    if method == "tools/call":
        name = (params.get("name") or "").strip()
        args = params.get("arguments")
        if not isinstance(args, dict):
            args = {}
        result = _call_tool(name, args)
        _send({"jsonrpc": "2.0", "id": rid, "result": result})
        return

    if method == "ping":
        _send({"jsonrpc": "2.0", "id": rid, "result": {}})
        return

    if method == "resources/list":
        _send({"jsonrpc": "2.0", "id": rid, "result": {"resources": []}})
        return

    if method == "prompts/list":
        _send({"jsonrpc": "2.0", "id": rid, "result": {"prompts": []}})
        return

    _send(
        {
            "jsonrpc": "2.0",
            "id": rid,
            "error": {"code": -32601, "message": f"Method not found: {method}"},
        }
    )


def main() -> None:
    _bootstrap_env()
    while True:
        try:
            req = _read_request()
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            print(f"MCP: 잘못된 JSON: {e}", file=sys.stderr)
            continue
        if req is None:
            break
        if not isinstance(req, dict):
            continue
        try:
            _handle(req)
        except BrokenPipeError:
            break


if __name__ == "__main__":
    main()
