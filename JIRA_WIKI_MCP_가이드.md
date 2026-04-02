# Jira·Wiki MCP 사용 가이드

이 프로젝트의 `mcp_jira_server.py`는 **MCP(Model Context Protocol)** 로 **지라** 검색·이슈 조회·첨부 다운로드와 **위키(Confluence)** 검색을 **에디터 안의 AI**가 도구처럼 호출할 수 있게 해 줍니다.

---

## MCP가 뭔가요?

짧게 말하면, **AI와 외부 프로그램을 연결하는 표준 “콘센트”**입니다.  
에디터(Cursor, VS Code 등)가 백그라운드에서 우리 Python 서버를 띄우고, AI가 `jira_search`·`wiki_search` 같은 **도구**를 호출하면 서버가 지라·위키 REST API에 요청하고 결과를 돌려줍니다.

- 사용자가 매번 터미널에서 `python jira_search.py …`를 치지 않아도 됩니다.
- 대신 **에디터에 MCP 서버를 한 번 등록**해 두어야 합니다.

---

## 어떻게 “구동”하나요?

**보통은 따로 구동하지 않습니다.**

1. Cursor / VS Code가 MCP 설정을 읽습니다.
2. 채팅·에이전트가 지라 도구가 필요하다고 판단하면 **자동으로**  
   `python mcp_jira_server.py` 같은 명령을 **자식 프로세스**로 실행합니다.
3. 에디터와 서버는 **표준 입출력(stdio)** 으로만 대화합니다. (별도 포트·URL 없음)

즉, **MCP 서버는 “에디터가 필요할 때 켜는 백그라운드 프로그램”**에 가깝습니다.

수동으로 테스트하고 싶다면(선택):

```bash
cd /프로젝트/jira-wiki
.venv/bin/python mcp_jira_server.py
```

이 상태에서는 터미널이 멈춘 것처럼 보이는 것이 정상입니다. 실제 사용은 에디터가 프로세스를 띄우는 방식이 일반적입니다.

---

## Cursor에서 등록하기

1. **Cursor 설정**을 엽니다.  
   `Settings` → **Features** → **MCP** (또는 설정 검색창에 “MCP”).
2. **Add new MCP server** / **Edit in settings.json** 등으로 MCP 목록에 서버를 추가합니다.
3. 아래처럼 **프로젝트 절대 경로**에 맞게 수정합니다.

```json
{
  "mcpServers": {
    "jira-wiki": {
      "command": "/본인경로/jira-wiki/.venv/bin/python",
      "args": ["/본인경로/jira-wiki/mcp_jira_server.py"],
      "env": {
        "JIRA_BASE_URL": "http://jira.example.com:8080",
        "JIRA_USER": "본인아이디",
        "JIRA_PASSWORD": "본인비밀번호",
        "WIKI_BASE_URL": "http://wiki.example.com:8080"
      }
    }
  }
}
```

위키를 쓰지 않거나 기본 주소(`http://wiki.example.com:8080`)를 그대로 쓰면 **`WIKI_BASE_URL` 항목은 통째로 생략**해도 됩니다.

- Cursor 버전에 따라 키 이름이 `mcpServers` 가 아닐 수 있습니다. UI에 안내된 형식을 따르세요.
- `WIKI_BASE_URL`은 **선택**입니다. 생략하면 위키 검색 기본 주소로 `http://wiki.example.com:8080` 이 쓰입니다. 회사 위키가 `/wiki` 같은 **컨텍스트 경로**만 열려 있다면 `http://호스트:포트/wiki` 처럼 경로까지 넣는 것이 안전합니다.
- 비밀번호를 JSON에 넣기 싫다면 **아래 “자격 증명 넣는 방법”**의 `.env` / `envFile` 방식을 VS Code 예시처럼 적용할 수 있는지 Cursor 문서를 확인하세요.

등록 후 채팅에서 예를 들어 다음처럼 요청해 볼 수 있습니다.

- “내 담당 이슈 JQL로 검색해 줘”
- “CSA10-44546 이슈 상세랑 댓글 요약해 줘”
- “위키에서 ○○ 키워드로 페이지 검색해 줘”

에이전트가 **`jira_search` / `jira_get_issue` / `jira_download_attachments`** 또는 **`wiki_search`** 등 필요한 도구를 호출합니다.

---

## VS Code에서 등록하기

VS Code는 **MCP 공식 지원**이 있으며, 워크스페이스에 `.vscode/mcp.json` 을 두는 방식이 문서화되어 있습니다.

예시 (경로는 본인 환경에 맞게 수정):

```json
{
  "servers": {
    "jira-wiki": {
      "type": "stdio",
      "command": "${workspaceFolder}/.venv/bin/python",
      "args": ["${workspaceFolder}/mcp_jira_server.py"],
      "envFile": "${workspaceFolder}/.env"
    }
  }
}
```

- `envFile`에 `JIRA_BASE_URL`, `JIRA_USER`, `JIRA_PASSWORD`가 들어 있는 **`.env`** 를 지정하면 JSON 안에 비밀번호를 쓰지 않아도 됩니다. 위키 검색에 쓸 **`WIKI_BASE_URL`**(선택)도 같은 파일에 두면 됩니다.
- Copilot 등 **MCP를 쓰는 AI 기능**이 켜져 있어야 도구가 호출됩니다.

자세한 최신 옵션은 [VS Code MCP 문서](https://code.visualstudio.com/docs/copilot/customization/mcp-servers)를 참고하세요.

---

## 제공되는 도구 (5개)

| 도구 이름 | 하는 일 |
| --- | --- |
| `jira_search` | JQL 검색 → JSON 문자열로 결과 |
| `jira_search_users` | 사용자 id·이름 일부 검색(웹 자동완성과 유사) → JSON 배열 문자열 |
| `jira_get_issue` | 이슈 키로 상세(본문·첨부 메타·이력·댓글) — `text` 또는 `json` |
| `jira_download_attachments` | 첨부를 `dest_dir` 폴더에 저장 (Basic 인증) |
| `wiki_search` | 위키(Confluence) **검색어**로 페이지·블로그 제목·본문 CQL 검색 → JSON 문자열 |

지라 관련 도구는 CLI의 `jira_search.py`와 같은 **지라 URL·계정**을 사용합니다.

---

## 위키(Confluence) 검색 (`wiki_search`)

- **계정**: 지라와 동일하게 `JIRA_USER`, `JIRA_PASSWORD`(Basic 인증)를 사용합니다. 위키 전용 별도 변수는 없습니다.
- **주소**: `WIKI_BASE_URL` 환경 변수로 지정합니다. **비우거나 생략**하면 기본값 `http://wiki.example.com:8080` 이 사용됩니다.
- **인자**:
  - `query` (필수): 검색어
  - `max_results` (선택, 기본 20, 최대 100)
  - `start_at` (선택, 기본 0): 다음 페이지 조회 시 offset
- **응답**: Confluence REST API JSON 문자열입니다. 실제로 호출에 성공한 엔드포인트와 사용한 CQL은 `_wikiSearchMeta` 필드에 붙습니다.
- **동작 요약**: 서버 버전·설치 경로에 따라 `/rest/api/content/search` 또는 `/rest/api/search` 등 여러 URL을 순서대로 시도하고, 복잡한 CQL이 거절되면 단순 `text ~ "검색어"` 형태로 한 번 더 시도합니다.

**위키만** 쓰고 지라 URL이 없을 때는 `wiki_search`만 호출하면 되며, 이때도 **`JIRA_USER` / `JIRA_PASSWORD`는 필수**입니다. (`JIRA_BASE_URL` 없이도 위키 도구는 동작합니다.)

---

## 다른 사용자도 쓰려면? 아이디/비밀번호는 접속할 때마다?

**아니요. “접속할 때마다” 입력하는 방식이 아닙니다.**

MCP 서버는 **프로세스가 시작될 때** 환경 변수(또는 `.env`)로 자격 증명을 읽습니다.

- **각 사용자는 자기 지라 계정**을 써야 합니다. (권한·감사·보안)
- 설정 방법은 보통 다음 중 하나입니다.
  1. **`.env`** 파일 (프로젝트 루트, **Git에 올리지 않음** — 이미 `.gitignore`에 포함하는 것을 권장)
  2. MCP 설정의 **`env`** 블록 (본인 PC의 사용자 설정 파일에만 저장)
  3. VS Code의 **`envFile`** (위 예시)

위키 주소가 기본값과 다르면 `.env`에 `WIKI_BASE_URL`만 추가로 적어 두면 됩니다.

**팀원에게는** 저장소에는 `.env.example` 처럼 **키 이름만** 공유하고, 값은 각자 로컬에만 두는 방식이 안전합니다.

---

## 요약

| 질문 | 답 |
| --- | --- |
| VS Code / Cursor에 등록해서 쓸 수 있나요? | **예.** 설정에 서버를 추가하면 됩니다. |
| 어떻게 구동하나요? | **에디터가 자동으로** Python 서버를 subprocess로 실행합니다. |
| 매번 아이디/비밀번호를 입력하나요? | **아니요.** `.env` 또는 MCP `env` / `envFile`에 한 번 넣어 둡니다. |
| 위키도 같은 서버에서 쓰나요? | **`wiki_search` 도구**로 검색합니다. 계정은 지라와 동일, 주소는 `WIKI_BASE_URL`(선택). |
| 다른 사람은? | **각자 자기 계정**으로 같은 방식 설정. 비밀번호 공유·저장소 커밋은 피하세요. |

---

## 문제가 생기면

- **설정을 못 읽는다**: `JIRA_BASE_URL` 끝 슬래시 없이, `JIRA_USER` / `JIRA_PASSWORD` 오타 확인.
- **위키 검색이 404·엔드포인트 없음**: `WIKI_BASE_URL`에 **컨텍스트 경로**(`/wiki` 등)를 포함해야 하는지 확인합니다. 에러 응답 본문과 `_wikiSearchMeta`의 `endpoint`를 보면 어떤 URL로 시도했는지 알 수 있습니다.
- **위키만 쓰는데 도구가 자격 증명 없다고 한다**: `wiki_search`도 `JIRA_USER`, `JIRA_PASSWORD`를 읽습니다. 변수 이름이 지라와 같아 헷갈릴 수 있으나, 위키 로그인에도 동일 값을 넣으면 됩니다.
- **도구가 안 보인다**: Cursor/VS Code에서 MCP 서버가 **Enabled** 인지, 해당 채널이 MCP 도구를 쓰는지 확인.
- **Python 버전**: 이 프로젝트 MCP 서버는 **Python 3.9+** 에서 동작하도록 작성되어 있습니다. 가상환경 경로가 맞는지 확인하세요.
