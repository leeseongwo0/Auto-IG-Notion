#!/usr/bin/env python3
"""Build a private Dot setup handoff; makes no network requests."""

import json
import re
import sys
from pathlib import Path
from urllib.parse import urlsplit


ROOT = Path(__file__).resolve().parents[1]
URL_FIELDS = (
    "parent_page_url",
    "dashboard_page_url",
    "content_database_url",
    "content_metrics_database_url",
    "account_metrics_database_url",
)


class SetupError(ValueError):
    """A safe, user-facing configuration error without private input values."""


def build():
    config_path = ROOT / "config/local.json"
    if not config_path.is_file():
        raise SetupError("config/example.json을 config/local.json에 복사하고 대상 정보를 입력하세요.")
    config = json.loads(config_path.read_text(encoding="utf-8"))
    if not isinstance(config, dict) or not all(
        isinstance(config.get(key), dict) for key in ("instagram", "notion")
    ):
        raise SetupError("instagram과 notion 설정은 JSON 객체여야 합니다.")
    username = config["instagram"]["username"]
    if not isinstance(username, str) or not re.fullmatch(r"[A-Za-z0-9._]{1,30}", username) or username == "YOUR_ACCOUNT":
        raise SetupError("실제 Instagram 계정 아이디를 입력하세요.")
    notion = {key: config["notion"].get(key) for key in URL_FIELDS}
    if not notion["parent_page_url"]:
        raise SetupError("notion.parent_page_url에 생성 위치를 입력하세요.")
    for value in notion.values():
        if value is None:
            continue
        if not isinstance(value, str):
            raise SetupError("Notion 주소는 문자열 또는 null이어야 합니다.")
        url = urlsplit(value)
        hostname = url.hostname or ""
        if (
            url.scheme != "https"
            or url.username is not None
            or url.password is not None
            or not any(hostname == domain or hostname.endswith("." + domain)
                       for domain in ("notion.com", "notion.so", "notion.site"))
        ):
            raise SetupError("Notion 주소는 인증 정보가 없는 HTTPS Notion URL이어야 합니다.")
    # Only explicit non-secret fields are included, never the entire local config.
    target = {
        "instagram": {"username": username, "profile_url": f"https://www.instagram.com/{username}/"},
        "notion": notion,
        "observation_timezone": config.get("observation_timezone", "Asia/Seoul"),
    }
    if target["observation_timezone"] != "Asia/Seoul":
        raise SetupError("현재 실행 지침의 시간대는 Asia/Seoul입니다. 변경하려면 지침도 함께 갱신하세요.")
    schema = json.loads((ROOT / "notion/schema.json").read_text(encoding="utf-8"))
    handoff = (ROOT / "prompts/dot-handoff.md").read_text(encoding="utf-8")
    handoff = handoff.replace("{{INSTAGRAM_USERNAME}}", username).replace(
        "{{NOTION_PARENT_PAGE_URL}}", notion["parent_page_url"]
    )
    sections = [
        "# Dot에 전달할 Instagram 성과 구성 작업\n\n"
        "이 파일에는 비공개 대상 주소가 포함되어 있습니다. 공개 저장소에 올리지 마세요.\n"
        "다음 최초 구성 지침을 실행하고 실제 결과를 보고하세요.\n",
        handoff,
        "## 실행 대상\n\n```json\n" + json.dumps(target, ensure_ascii=False, indent=2) + "\n```\n",
        "## 최초 구성\n\n" + (ROOT / "prompts/dot-bootstrap.md").read_text(encoding="utf-8"),
        "## DB와 보기 명세\n\n```json\n" + json.dumps(schema, ensure_ascii=False, indent=2) + "\n```\n",
    ]
    for name in ("docs/notion-layout.md", "docs/workflow.md", "docs/initial-import.md", "prompts/dot-task.md"):
        sections.append(f"## 참조 문서: {name}\n\n" + (ROOT / name).read_text(encoding="utf-8"))
    output = ROOT / "runtime/dot-setup.md"
    output.parent.mkdir(exist_ok=True)
    output.write_text("\n\n".join(sections), encoding="utf-8")
    output.chmod(0o600)
    concise_output = ROOT / "runtime/dot-handoff.md"
    concise_output.write_text(handoff, encoding="utf-8")
    concise_output.chmod(0o600)
    print("생성 완료: runtime/dot-handoff.md, runtime/dot-setup.md (로컬 전달본; 외부 요청 없음)")


if __name__ == "__main__":
    try:
        build()
    except (ValueError, KeyError, TypeError, OSError) as error:
        # Never echo config contents or arbitrary parser messages with private values.
        if isinstance(error, SetupError):
            print(f"준비 실패: {error}", file=sys.stderr)
        else:
            print("준비 실패: 로컬 설정과 필수 명세 파일의 형식·존재 여부를 확인하세요.", file=sys.stderr)
        sys.exit(1)
