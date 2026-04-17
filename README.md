# jira-wiki

지라(Jira Server) REST API로 이슈 검색·상세·댓글·이력·첨부 다운로드를 CLI에서 처리하고, **MCP 서버**로 에디터 AI와 연결할 수 있는 작은 도구 모음입니다.

**버전**은 [`project_version.py`](./project_version.py)의 `__version__` 한 곳에서 관리합니다. CLI는 `jira_search.py --version`, `wiki_search.py --version` 으로 확인할 수 있습니다. 변경 요약은 [CHANGELOG.md](./CHANGELOG.md)를 참고하세요. Cursor에서 코드·동작을 바꿀 때는 [`.cursor/rules/version-changelog.mdc`](./.cursor/rules/version-changelog.mdc) 규칙에 따라 버전과 변경 이력을 함께 올립니다. MCP에서는 같은 서버 프로세스로 **위키(Confluence) 검색**(`wiki_search`)과 **페이지 본문 조회**(`wiki_get_page`)도 제공합니다.

## 빠른 시작

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.example .env
# .env 에 JIRA_BASE_URL, JIRA_USER, JIRA_PASSWORD 입력
# 위키 주소가 기본값(http://wiki.example.com:8080)과 다르면 WIKI_BASE_URL 추가

.venv/bin/python jira_search.py 'assignee = currentUser() ORDER BY updated DESC' -n 10
.venv/bin/python jira_search.py --issue PROJ-123
.venv/bin/python jira_search.py --users "홍길" -n 15
# 이슈 댓글 등록
.venv/bin/python jira_search.py --post-comment-on CSA10-36630 --comment-body "댓글 내용"

# 위키(Confluence) 검색 — 문서코드·키워드 그대로 (예: P1599)
.venv/bin/python wiki_search.py "P1599" -n 10
.venv/bin/python wiki_search.py "메신저" -n 10
# 본문 조회 — 반드시 숫자 pageId (검색 JSON의 id). P1599는 검색어로만 사용
.venv/bin/python wiki_search.py --page 344872205
```

MCP·Cursor·VS Code·**Claude Desktop** 연결, 지라·위키 도구 목록·환경 변수 설명은 [JIRA_WIKI_MCP_가이드.md](./JIRA_WIKI_MCP_가이드.md)를 참고하세요. 지라 댓글은 MCP **`jira_add_comment`** 또는 위 CLI로 등록합니다. 상태 전이는 MCP **`jira_list_transitions`** / **`jira_transition_issue`**, 담당자는 **`jira_set_assignee`**(계정 확인은 **`jira_search_users`**)를 사용합니다. 위키는 터미널 **`wiki_search.py`** 또는 MCP **`wiki_search`** / **`wiki_get_page`** 로 쓸 수 있습니다. 계정은 지라와 동일(`JIRA_USER` / `JIRA_PASSWORD`)입니다.

## 라이선스

[MIT License](./LICENSE) — 누구나 자유롭게 사용·수정·배포할 수 있습니다.
