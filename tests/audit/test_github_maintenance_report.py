from datetime import datetime, timezone

from tools.ci.github_maintenance_report import build_report, render_markdown, resolve_github_token


def test_maintenance_report_flags_stale_prs_and_unowned_branches() -> None:
    now = datetime(2026, 5, 25, tzinfo=timezone.utc)
    prs = [
        {
            "number": 31,
            "title": "Add Track M",
            "html_url": "https://github.example/pr/31",
            "draft": True,
            "head": {"ref": "claude/remote-control-AD6Di"},
            "created_at": "2026-05-10T00:00:00Z",
            "updated_at": "2026-05-12T00:00:00Z",
        },
        {
            "number": 32,
            "title": "Fresh branch",
            "html_url": "https://github.example/pr/32",
            "draft": False,
            "head": {"ref": "fresh/pr"},
            "created_at": "2026-05-25T00:00:00Z",
            "updated_at": "2026-05-25T00:00:00Z",
        },
    ]
    branches = [
        {"name": "origin/main", "sha": "aaa", "committed_at": "2026-05-25T00:00:00Z"},
        {"name": "origin/claude/remote-control-AD6Di", "sha": "bbb", "committed_at": "2026-05-10T00:00:00Z"},
        {"name": "origin/old/no-pr", "sha": "ccc", "committed_at": "2026-05-01T00:00:00Z"},
        {"name": "origin/backup/local-pgvector-bootstrap", "sha": "ddd", "committed_at": "2026-04-01T00:00:00Z"},
    ]

    report = build_report(prs=prs, branches=branches, now=now, stale_days=7)

    assert report["status"] == "ACTION_REQUIRED"
    assert report["summary"]["open_pr_count"] == 2
    assert [item["number"] for item in report["stale_prs"]] == [31]
    assert [item["name"] for item in report["stale_branches_without_pr"]] == ["origin/old/no-pr"]
    assert "origin/claude/remote-control-AD6Di" not in [
        item["name"] for item in report["stale_branches_without_pr"]
    ]


def test_maintenance_report_markdown_is_actionable_without_secrets() -> None:
    now = datetime(2026, 5, 25, tzinfo=timezone.utc)
    report = build_report(
        prs=[
            {
                "number": 31,
                "title": "Add Track M",
                "html_url": "https://github.example/pr/31",
                "draft": True,
                "head": {"ref": "claude/remote-control-AD6Di"},
                "created_at": "2026-05-10T00:00:00Z",
                "updated_at": "2026-05-12T00:00:00Z",
            }
        ],
        branches=[],
        now=now,
        stale_days=7,
    )

    markdown = render_markdown(report)

    assert "ACTION_REQUIRED" in markdown
    assert "#31" in markdown
    assert "https://github.example/pr/31" in markdown
    assert "updated 13d ago" in markdown


def test_maintenance_report_lists_stale_prs_separately() -> None:
    now = datetime(2026, 5, 25, tzinfo=timezone.utc)
    report = build_report(
        prs=[
            {
                "number": 31,
                "title": "Old draft",
                "html_url": "https://github.example/pr/31",
                "draft": True,
                "head": {"ref": "old/draft"},
                "created_at": "2026-05-01T00:00:00Z",
                "updated_at": "2026-05-10T00:00:00Z",
            },
            {
                "number": 32,
                "title": "Fresh draft",
                "html_url": "https://github.example/pr/32",
                "draft": True,
                "head": {"ref": "fresh/draft"},
                "created_at": "2026-05-24T00:00:00Z",
                "updated_at": "2026-05-24T00:00:00Z",
            },
        ],
        branches=[],
        now=now,
        stale_days=7,
    )

    markdown = render_markdown(report)

    assert "## Stale PRs" in markdown
    stale_section = markdown.split("## Stale PRs", 1)[1].split("## Stale Branches Without PR", 1)[0]
    assert "#31 draft: Old draft" in stale_section
    assert "#32" not in stale_section


def test_maintenance_report_redacts_session_links_from_rendered_fields() -> None:
    now = datetime(2026, 5, 25, tzinfo=timezone.utc)
    claude_session_url = "https://claude." "ai/chat/session-local"
    chatgpt_session_url = "https://chatgpt." "com/share/local"
    openai_session_url = "https://chat.openai." "com/c/local"
    report = build_report(
        prs=[
            {
                "number": 31,
                "title": f"Contains {claude_session_url}",
                "html_url": "https://github.example/pr/31",
                "draft": True,
                "head": {"ref": f"branch/{chatgpt_session_url}"},
                "created_at": "2026-05-01T00:00:00Z",
                "updated_at": "2026-05-10T00:00:00Z",
            }
        ],
        branches=[
            {
                "name": f"origin/branch/{openai_session_url}",
                "sha": "abc",
                "committed_at": "2026-05-01T00:00:00Z",
            }
        ],
        now=now,
        stale_days=7,
    )

    markdown = render_markdown(report)

    assert "claude.ai" not in markdown
    assert "chatgpt.com" not in markdown
    assert "chat.openai.com" not in markdown
    assert "<redacted-session-url>" in markdown


def test_resolve_github_token_prefers_github_token_env(monkeypatch) -> None:
    monkeypatch.setenv("GITHUB_TOKEN", "env-token")
    monkeypatch.setenv("GH_TOKEN", "gh-env-token")

    def fail_run(*_args, **_kwargs):
        raise AssertionError("gh auth token should not run when env token exists")

    monkeypatch.setattr("tools.ci.github_maintenance_report.subprocess.run", fail_run)

    assert resolve_github_token() == "env-token"


def test_resolve_github_token_uses_gh_token_env(monkeypatch) -> None:
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    monkeypatch.setenv("GH_TOKEN", "gh-env-token")

    def fail_run(*_args, **_kwargs):
        raise AssertionError("gh auth token should not run when GH_TOKEN exists")

    monkeypatch.setattr("tools.ci.github_maintenance_report.subprocess.run", fail_run)

    assert resolve_github_token() == "gh-env-token"


def test_resolve_github_token_falls_back_to_gh_auth_token(monkeypatch) -> None:
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    monkeypatch.delenv("GH_TOKEN", raising=False)
    calls = []

    class Completed:
        stdout = "keyring-token\n"

    def fake_run(args, **kwargs):
        calls.append((args, kwargs))
        return Completed()

    monkeypatch.setattr("tools.ci.github_maintenance_report.subprocess.run", fake_run)

    assert resolve_github_token() == "keyring-token"
    assert calls == [
        (
            ["gh", "auth", "token"],
            {"check": True, "capture_output": True, "text": True},
        )
    ]


def test_resolve_github_token_returns_empty_when_gh_auth_unavailable(monkeypatch) -> None:
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    monkeypatch.delenv("GH_TOKEN", raising=False)

    def fake_run(*_args, **_kwargs):
        raise FileNotFoundError("gh not installed")

    monkeypatch.setattr("tools.ci.github_maintenance_report.subprocess.run", fake_run)

    assert resolve_github_token() == ""
