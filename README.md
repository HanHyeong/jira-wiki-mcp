# jira-wiki

지라(Jira Server) REST API로 이슈 검색·상세·댓글·이력·첨부 다운로드를 CLI에서 처리하고, MCP 서버로 에디터 AI와 연결할 수 있는 작은 도구 모음입니다.

## 빠른 시작

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.example .env
# .env 에 JIRA_BASE_URL, JIRA_USER, JIRA_PASSWORD 입력

.venv/bin/python jira_search.py 'assignee = currentUser() ORDER BY updated DESC' -n 10
.venv/bin/python jira_search.py --issue PROJ-123
.venv/bin/python jira_search.py --users "홍길" -n 15
```

MCP·Cursor·VS Code 연결은 [JIRA_MCP_가이드.md](./JIRA_MCP_가이드.md)를 참고하세요.

## 라이선스

저장소에 별도 라이선스 파일이 없으면 회사/개인 정책에 맞게 추가하세요.
