# jira-wiki

지라(Jira Server) REST API로 이슈 검색·상세·댓글·이력·첨부 다운로드를 CLI에서 처리하고, **MCP 서버**로 에디터 AI와 연결할 수 있는 작은 도구 모음입니다. MCP에서는 같은 서버 프로세스로 **위키(Confluence) 검색**(`wiki_search`)도 제공합니다.

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

# 위키(Confluence) 검색 — JIRA_USER / JIRA_PASSWORD 동일, JSON 출력
.venv/bin/python wiki_search.py "메신저" -n 10
```

MCP·Cursor·VS Code·**Claude Desktop** 연결, 지라·위키 도구 목록·환경 변수 설명은 [JIRA_WIKI_MCP_가이드.md](./JIRA_WIKI_MCP_가이드.md)를 참고하세요. 위키는 터미널에서 **`wiki_search.py`** 로도 검색할 수 있고, MCP 도구 **`wiki_search`** 로도 호출할 수 있습니다. 계정은 지라와 동일(`JIRA_USER` / `JIRA_PASSWORD`)입니다.

## 라이선스

저장소에 별도 라이선스 파일이 없으면 회사/개인 정책에 맞게 추가하세요.
