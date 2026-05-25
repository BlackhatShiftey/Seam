from datetime import datetime, timezone

from tools.ci.github_maintenance_report import build_report, render_markdown


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
