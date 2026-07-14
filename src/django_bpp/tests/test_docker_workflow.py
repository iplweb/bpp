"""Kontrakt uruchamiania workflow oficjalnych obrazów Docker."""

from pathlib import Path

WORKFLOW_PATH = (
    Path(__file__).resolve().parents[3]
    / ".github"
    / "workflows"
    / "build-docker-images.yml"
)


def test_docker_workflow_uruchamia_sie_tylko_jawnie():
    workflow = WORKFLOW_PATH.read_text(encoding="utf-8")
    triggers = workflow.split("\non:\n", maxsplit=1)[1].split(
        "\npermissions:\n", maxsplit=1
    )[0]

    assert "  workflow_dispatch:" in triggers
    assert "  workflow_call:" in triggers
    assert "  pull_request:" not in triggers
    assert "  push:" not in triggers


def test_docker_workflow_nie_ma_pustego_jobu_guard():
    workflow = WORKFLOW_PATH.read_text(encoding="utf-8")
    jobs = workflow.split("\njobs:\n", maxsplit=1)[1]

    assert jobs.startswith("  docker:\n")
    assert "\n  check-flag:" not in jobs
