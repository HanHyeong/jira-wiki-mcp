# 변경 이력

형식은 [Keep a Changelog](https://keepachangelog.com/ko/1.0.0/)를 따르며, 버전은 [Semantic Versioning](https://semver.org/lang/ko/)을 권장합니다.

## [Unreleased]

## [1.2.4] — 2026-04-17

- 지라: 담당자 변경·해제 `jira_set_assignee`(MCP), `jira_search.set_issue_assignee`

## [1.2.3] — 2026-04-17

- 지라: 워크플로 전이 조회 `jira_list_transitions`, 전이 실행 `jira_transition_issue`(MCP), `jira_search` 헬퍼 함수

## [1.2.2] — 2026-04-17

- 지라: 이슈 댓글 등록 `jira_add_comment`(MCP), CLI `--post-comment-on` / `--comment-body`

## [1.2.1] — 2026-04-03

- Cursor 프로젝트 규칙: 기능·동작 변경 시 `project_version.py` 패치 버전과 `CHANGELOG.md` 자동 갱신 (`.cursor/rules/version-changelog.mdc`)

## [1.2.0] — 2026-04-02

- 지라 첨부: `jira_fetch_attachments`(base64), `jira_download_attachments` 경로 검증·안내 강화
- 위키: `wiki_get_page`, CLI `--page`
- MCP 도구 확장, Claude Desktop 가이드, MIT 라이선스

## [1.1.0] — 이전

- 위키 검색 `wiki_search` 및 관련 문서

## [1.0.0] — 초기

- 지라 MCP·CLI (`jira_search`, 이슈 상세, 사용자 검색, 첨부 다운로드)
