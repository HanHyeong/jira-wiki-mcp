# Jira·Wiki MCP 사용 가이드

이 프로젝트의 `mcp_jira_server.py`는 **MCP(Model Context Protocol)** 로 **지라** 검색·이슈 조회·첨부 다운로드와 **위키(Confluence)** 검색을 **Cursor·VS Code·Claude Desktop** 등에서 AI가 도구처럼 호출할 수 있게 해 줍니다.

---

## MCP가 뭔가요?

짧게 말하면, **AI와 외부 프로그램을 연결하는 표준 “콘센트”**입니다.  
클라이언트(Cursor, VS Code, **Claude Desktop** 등)가 백그라운드에서 우리 Python 서버를 띄우고, AI가 `jira_search`·`wiki_search`·`wiki_get_page` 같은 **도구**를 호출하면 서버가 지라·위키 REST API에 요청하고 결과를 돌려줍니다.

- 사용자가 매번 터미널에서 `python jira_search.py …`를 치지 않아도 됩니다.
- 대신 **앱 설정에 MCP 서버를 한 번 등록**해 두어야 합니다.

---

## 어떻게 “구동”하나요?

**보통은 따로 구동하지 않습니다.**

1. Cursor / VS Code / Claude Desktop 등이 MCP 설정을 읽습니다.
2. 채팅이 지라·위키 도구가 필요하다고 판단하면 **자동으로**  
   `python mcp_jira_server.py` 같은 명령을 **자식 프로세스**로 실행합니다.
3. 클라이언트와 서버는 **표준 입출력(stdio)** 으로만 대화합니다. (별도 포트·URL 없음)

즉, **MCP 서버는 “앱이 필요할 때 켜는 백그라운드 프로그램”**에 가깝습니다.

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
- “CSA10-36630 이슈에 댓글로 ‘검토 완료’ 달아 줘” → **`jira_add_comment`**
- “CSA10-45980 지금 어떤 상태 전이가 가능한지 보여 줘” → **`jira_list_transitions`**
- “그 이슈 접수로 바꿔 줘” → **`jira_list_transitions`**로 후보 확인 후 **`jira_transition_issue`**
- “담당자를 ○○로 바꿔 줘” → **`jira_search_users`**로 계정 확인 후 **`jira_set_assignee`**
- “위키에서 ○○ 키워드로 페이지 검색해 줘”
- “위키에서 **P1599** 찾아 줘” → **`wiki_search`(query=`P1599`)** (문서코드·검색어)
- “그 페이지 본문 보여 줘” → 검색 JSON의 **숫자 id**로 **`wiki_get_page`**

에이전트가 **`jira_search` / `jira_search_users` / `jira_get_issue` / `jira_list_transitions` / `jira_transition_issue` / `jira_set_assignee` / `jira_add_comment` / `jira_download_attachments` / `jira_fetch_attachments`** 와 **`wiki_search` / `wiki_get_page`** 등 필요한 도구를 호출합니다.

---

## Claude Desktop에서 등록하기

**예, 사용할 수 있습니다.** Claude Desktop도 MCP를 지원하며, 이 프로젝트 서버는 **stdio** 방식이라 Cursor와 같은 형태로 넣으면 됩니다.

1. Claude Desktop을 연 뒤 **설정(Settings)** 을 엽니다. 앱 버전에 따라 **Developer**, **Desktop app** 하위의 개발자 설정, 또는 **Extensions / Connectors** 안내가 보일 수 있습니다.
2. **`claude_desktop_config.json`** 을 편집합니다. 메뉴 이름은 **Edit Config** 등으로 표시되는 경우가 많고, 채팅 입력란의 **Connectors** 에서 연결된 MCP·도구 목록을 확인할 수도 있습니다.
3. 최상위에 `mcpServers` 객체가 없으면 만들고, 아래처럼 **절대 경로**를 본인 환경에 맞게 넣습니다.

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

- **설정 파일 위치**(앱 버전에 따라 다를 수 있음): macOS는 보통 `~/Library/Application Support/Claude/claude_desktop_config.json`, Windows는 `%APPDATA%\Claude\claude_desktop_config.json` 근처입니다. 메뉴의 “Edit Config”가 가장 확실합니다.
- VS Code의 `envFile`처럼 **JSON 밖의 `.env`를 자동으로 읽어 주지는 않는 경우가 많습니다.** 자격 증명은 위처럼 `env`에 두거나, `.env`를 읽어 환경 변수를 세팅한 뒤 Python을 실행하는 **래퍼 스크립트**를 `command`로 지정하는 방식을 쓸 수 있습니다.
- JSON을 저장한 뒤 **Claude Desktop을 완전히 종료했다가 다시 실행**하면 MCP 목록에 반영되는 경우가 많습니다.
- 위키를 쓰지 않거나 기본 `WIKI_BASE_URL`을 쓰면 Cursor 절과 같이 **`WIKI_BASE_URL` 키는 생략**해도 됩니다.

공식·최신 절차는 [Claude Desktop용 MCP 연결 안내](https://support.anthropic.com/en/articles/10949351-getting-started-with-local-mcp-servers-on-claude-for-desktop)를 함께 확인하세요.

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

## 제공되는 도구 (11개)

| 도구 이름 | 하는 일 |
| --- | --- |
| `jira_search` | JQL 검색 → JSON 문자열로 결과 |
| `jira_search_users` | 사용자 id·이름 일부 검색(웹 자동완성과 유사) → JSON 배열 문자열 |
| `jira_get_issue` | 이슈 키로 상세(본문·첨부 메타·이력·댓글) — `text` 또는 `json` |
| `jira_list_transitions` | 이슈 **현재 상태**와 Jira가 허용하는 **워크플로 전이 목록**(`transition_id`, 전이 이름, 이동 후 상태). `output_format`: `text`(기본) 또는 `json` |
| `jira_transition_issue` | `transition_id`로 **한 단계** 상태 전이. 전이에 필수 필드가 있으면 `fields_json`(REST `fields` 객체 JSON 문자열)로 함께 전달 |
| `jira_set_assignee` | **담당자(assignee) 변경·해제**. Server/DC는 로그인 **`name`**, Jira Cloud는 **`assignee_account_id`**. 담당 해제는 `assignee`·`assignee_account_id` 모두 비우거나 `(없음)` 등 |
| `jira_add_comment` | 이슈에 **댓글 등록**(`issue_key`, `body` 플레인 텍스트) → 생성된 댓글 JSON |
| `jira_download_attachments` | 첨부를 **`dest_dir` 실제 디스크 경로**에 저장 (`~` 확장·절대 경로). 저장 후 존재·크기 검증 문자열 포함 |
| `jira_fetch_attachments` | 첨부를 **디스크 없이** JSON으로 반환(`content_base64`). Claude Desktop에서 “저장됐는데 안 보임”일 때 소용량 이미지·파일 확인용 |
| `wiki_search` | 위키 **검색어**로 페이지·블로그 CQL 검색 → **목록 JSON**(제목·id 등, 본문은 짧게만 포함될 수 있음) |
| `wiki_get_page` | **숫자 content id**로 본문·스페이스·웹 URL 조회 — `text`(기본) 또는 `json`. `P1599` 같은 코드는 `wiki_search`로 검색 |

지라 관련 도구는 CLI의 `jira_search.py`와 같은 **지라 URL·계정**을 사용합니다.

### Claude Desktop / 첨부파일

- **`jira_download_attachments`**는 MCP 서버(로컬 Python)가 **지정한 폴더에 실제로 씁니다.** 다만 AI가 `dest_dir`로 `/tmp/...`, 가상 작업 디렉터리만 넣으면 **본인 Mac의 Finder·다운로드와 다른 위치**가 되어 “완료인데 파일이 없다”처럼 느껴질 수 있습니다.
- **권장**: `dest_dir`를 **`/Users/본인계정/Downloads/jira_CSA10-36630`** 처럼 **본인 사용자 홈 아래 실제 경로**로 요청하세요. 응답에 적힌 절대 경로로 폴더를 직접 열어 확인합니다.
- **채팅 안에서 내용 보기**: **`jira_fetch_attachments`** — 첨부를 base64로 돌려줍니다(기본 파일당 2MB·전체 8MB 한도, 초과 분은 `skipped`). 이미지는 모델이 설명·표시하기 쉬워집니다.

---

## 지라: 상태 전이 (`jira_list_transitions` / `jira_transition_issue`)

프로젝트·이슈 유형마다 **워크플로가 다릅니다.** 상태를 바꿀 때는 UI의 “작업 흐름” 버튼과 같이, **지금 허용된 전이만** REST로 실행할 수 있습니다.

### 권장 흐름 (에이전트)

1. **`jira_list_transitions`**(`issue_key`)로 **현재 상태**와 **가능한 전이**를 받는다.  
   - 각 줄에 `transition_id`, 전이 이름(버튼 라벨), **이동 후 상태 이름**이 나옵니다.
2. 사용자가 말한 목표(예: “접수”, “처리완료”)와 **일치하는 전이가 하나**이면 그 `transition_id`로 **`jira_transition_issue`**를 호출한다.
3. **일치하는 전이가 없거나**, 후보가 **여러 개**이면 → 목록을 **사용자에게 그대로 보여 주고** 어떤 `transition_id`로 할지 고르게 한다.
4. **한 번의 호출로 한 단계**만 전이한다. 여러 단계가 필요하면 전이 후 **다시** `jira_list_transitions`로 갱신된 목록을 조회한다.

### `jira_list_transitions`

- **인자**: `issue_key`(필수), `output_format`(선택, `text` 기본 또는 `json`)
- **`json`**: `issueKey`, `currentStatusName`, `transitions` 배열 등을 한 번에 볼 수 있습니다.

### `jira_transition_issue`

- **인자**: `issue_key`, `transition_id`(문자열, 예 `"341"`), `fields_json`(선택)
- **필수 필드가 있는 전이**(예: “처리내용을 입력하세요”)는 Jira가 400과 메시지를 돌려줍니다. 이 경우 `fields_json`에 REST **`fields`** 객체를 JSON 문자열로 넣어 재시도합니다.  
  - 예: `{"customfield_16801": "처리 내용 텍스트"}` — 실제 필드 id·이름은 프로젝트마다 다릅니다. 오류 본문·전이 화면을 참고하세요.
- 전이 후 확인은 **`jira_get_issue`** 또는 **`jira_list_transitions`**로 합니다.

---

## 지라: 담당자 변경 (`jira_set_assignee` / `jira_search_users`)

### `jira_set_assignee`

- **인자**: `issue_key`(필수), `assignee`(선택), `assignee_account_id`(선택)
- **Server / Data Center**: `assignee`에 Jira **로그인 name**을 넣습니다. (웹에 보이는 **표시 이름만**으로는 동작하지 않을 수 있습니다.)
- **Jira Cloud**: `assignee_account_id`에 Atlassian **accountId**를 넣습니다. `assignee`와 **동시에 지정하면 안 됩니다.**
- **담당 해제**: `assignee`·`assignee_account_id`를 모두 비우거나, `assignee`를 `(없음)`, `-`, `none` 등으로 둡니다.

### 표시 이름만 들었을 때(예: “원경업으로 바꿔 줘”)

1. **`jira_search_users`**에 `query`로 이름 일부를 넣어 후보 목록을 받습니다.
2. **한 명**이고 표시 이름·메일 등으로 확실하면 → 그 사용자의 **`name`**을 `jira_set_assignee`의 `assignee`에 넣습니다.
3. **여러 명**(동명이인·유사 검색)이면 → JSON을 사용자에게 보여 주고 **어느 계정인지** 골라 달라고 한 뒤, 고른 **`name`**으로 다시 호출합니다.
4. **검색 결과가 비어 있으면** → 표시 이름만으로는 계정을 특정할 수 없으므로, 검색어 변경·로그인 id 안내 등을 하고 **확인 없이 임의의 문자열을 `assignee`에 넣지 않습니다.** 잘못된 `name`은 Jira가 400 등으로 거절할 수 있습니다.

---

## 위키(Confluence): 검색 (`wiki_search`)과 본문 (`wiki_get_page`)

- **`P1599`, `HELP-123` 같은 문자열**은 보통 **문서코드·검색어**입니다 → **`wiki_search`의 `query`**에 그대로 넣습니다. (Confluence 페이지 id가 아닙니다.)
- 검색 API는 **전체 본문**을 잘 안 줍니다. 본문을 보려면 검색 결과에 나온 **숫자 id**(또는 URL의 `pageId=`)로 **`wiki_get_page`**를 호출합니다.

### `wiki_search`

- **계정**: 지라와 동일하게 `JIRA_USER`, `JIRA_PASSWORD`(Basic 인증)를 사용합니다. 위키 전용 별도 변수는 없습니다.
- **주소**: `WIKI_BASE_URL` 환경 변수로 지정합니다. **비우거나 생략**하면 기본값 `http://wiki.example.com:8080` 이 사용됩니다.
- **인자**:
  - `query` (필수): 검색어
  - `max_results` (선택, 기본 20, 최대 100)
  - `start_at` (선택, 기본 0): 다음 페이지 조회 시 offset
- **응답**: Confluence REST API JSON 문자열입니다. 실제로 호출에 성공한 엔드포인트와 사용한 CQL은 `_wikiSearchMeta` 필드에 붙습니다.
- **id 찾기**: JSON의 `results` 항목마다 구조가 다를 수 있습니다. **`id`**가 최상위에 있거나, **`content.id`** 안에 있습니다. 그 값을 `wiki_get_page`의 `content_id`에 넣습니다.

### `wiki_get_page`

- **인자**:
  - `content_id` (필수): **숫자만** (예 `344872205`). `wiki_search` 결과의 `id` / `content.id`, 또는 웹 주소의 `pageId=`.
  - `output_format` (선택): `text`(기본, 본문은 HTML 렌더에서 태그 제거) 또는 `json`(API 원본)
- **주의**: `P1599`를 여기 넣지 마세요. 문서코드는 **`wiki_search`**로 찾은 뒤, 나온 **숫자 id**를 넣습니다.
- **동작**: `GET /rest/api/content/{id}` 를 여러 설치 경로 후보로 시도하고, `expand` 조합을 줄여 가며 호출합니다.

**위키만** 쓰고 지라 URL이 없을 때는 `wiki_search` / `wiki_get_page`만 쓰면 되며, 이때도 **`JIRA_USER` / `JIRA_PASSWORD`는 필수**입니다. (`JIRA_BASE_URL` 없이도 위키 도구는 동작합니다.)

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
| VS Code / Cursor / Claude Desktop에 등록해서 쓸 수 있나요? | **예.** 각 앱의 MCP 설정에 서버를 추가하면 됩니다. |
| 어떻게 구동하나요? | **클라이언트 앱이 자동으로** Python 서버를 subprocess로 실행합니다. |
| 매번 아이디/비밀번호를 입력하나요? | **아니요.** `.env` 또는 MCP `env` / `envFile`에 한 번 넣어 둡니다. |
| 위키도 같은 서버에서 쓰나요? | **`wiki_search`**로 검색, **`wiki_get_page`**로 id별 본문 조회. 계정은 지라와 동일, 주소는 `WIKI_BASE_URL`(선택). |
| 이슈 상태를 AI로 바꿀 수 있나요? | **`jira_list_transitions`**로 허용 전이 확인 → **`jira_transition_issue`**로 한 단계씩. 필수 필드는 `fields_json`. 프로젝트마다 워크플로가 다릅니다. |
| 담당자만 바꿀 수 있나요? | **`jira_set_assignee`**. Server/DC는 로그인 **`name`**; 표시 이름만 알면 **`jira_search_users`**로 후보를 찾고, 동명이인이면 사용자가 고릅니다. |
| 다른 사람은? | **각자 자기 계정**으로 같은 방식 설정. 비밀번호 공유·저장소 커밋은 피하세요. |
| MCP·CLI 버전은 어디에? | **`project_version.py`** 의 `__version__` 이 단일 기준입니다. `jira_search.py --version` / `wiki_search.py --version`, MCP `serverInfo.version` 과 동일합니다. |

---

## 문제가 생기면

- **설정을 못 읽는다**: `JIRA_BASE_URL` 끝 슬래시 없이, `JIRA_USER` / `JIRA_PASSWORD` 오타 확인.
- **위키 검색이 404·엔드포인트 없음**: `WIKI_BASE_URL`에 **컨텍스트 경로**(`/wiki` 등)를 포함해야 하는지 확인합니다. 에러 응답 본문과 `_wikiSearchMeta`의 `endpoint`를 보면 어떤 URL로 시도했는지 알 수 있습니다.
- **위키만 쓰는데 도구가 자격 증명 없다고 한다**: `wiki_search` / `wiki_get_page` 모두 `JIRA_USER`, `JIRA_PASSWORD`를 읽습니다. 변수 이름이 지라와 같아 헷갈릴 수 있으나, 위키 로그인에도 동일 값을 넣으면 됩니다.
- **검색만 했는데 본문이 안 보인다**: 정상입니다. `wiki_get_page`에 검색 결과의 **숫자 id**를 넣으세요. `P1599`는 검색어로만 쓰입니다.
- **도구가 안 보인다**: Cursor/VS Code에서 MCP 서버가 **Enabled** 인지, Claude Desktop은 **Developer** 설정·앱 재시작·해당 대화에서 도구 사용이 허용되는지 확인합니다. **새 도구**를 추가했다면 MCP 서버(또는 앱)를 **한 번 재시작**해야 목록에 반영되는 경우가 많습니다.
- **상태 전이가 400**: `jira_list_transitions`로 허용 목록을 다시 확인하고, 메시지에 **필수 필드**가 있으면 `jira_transition_issue`의 `fields_json`으로 채웁니다.
- **담당자 변경이 400**: `assignee`에는 **로그인 name**이 필요합니다. `jira_search_users`로 `name`을 확인하세요. Cloud는 `assignee_account_id`를 사용합니다.
- **Claude Desktop·지라 첨부 “다운로드 완료인데 파일 없음”**: 위 **「Claude Desktop / 첨부파일」** 절 참고. 실제 경로 지정 또는 `jira_fetch_attachments` 사용.
- **Python 버전**: 이 프로젝트 MCP 서버는 **Python 3.9+** 에서 동작하도록 작성되어 있습니다. 가상환경 경로가 맞는지 확인하세요.
