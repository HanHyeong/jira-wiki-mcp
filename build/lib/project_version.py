"""
프로젝트 버전 단일 정의.

릴리스 절차:
  1. 여기의 __version__ 을 올린다 (예: 1.2.0 → 1.3.0).
  2. CHANGELOG.md 에 해당 버전 섹션을 적는다.
  3. git commit 후 선택적으로 태그: git tag v1.3.0 && git push origin v1.3.0

MCP serverInfo.version · CLI --version 이 모두 이 값을 쓴다.
"""

__version__ = "1.2.0"
