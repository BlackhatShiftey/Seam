from pathlib import Path


def test_ci_workflow_requires_locomo_bil2_and_chroma_smokes() -> None:
    workflow = Path(".github/workflows/ci.yml").read_text(encoding="utf-8")

    assert 'python -m pip install -e ".[server,sbert,rerank]"' in workflow
    assert "locomo-quickstart-bil2:" in workflow
    assert "python -m seam bench external --quickstart locomo" in workflow
    assert "python -m seam bench seal locomo.quickstart.json --level BIL-2 --allow-stub-seal" in workflow
    assert "python -m seam bench verify locomo.quickstart.bil2.json --format json" in workflow
    assert "python -m tools.ci.chroma_real_smoke" in workflow
    assert "Secret/session URL scan" in workflow
    assert "git diff --check" in workflow


def test_pull_request_template_keeps_repo_management_checklist_visible() -> None:
    template = Path(".github/pull_request_template.md").read_text(encoding="utf-8")

    assert "No paid benchmark/API calls" in template
    assert "BIL-2 quickstart" in template
    assert "history/stream" in template.lower()
    assert "secrets" in template.lower()
