"""Kontrakt uruchamiania workflow oficjalnych obrazów Docker."""

from pathlib import Path

WORKFLOW_PATH = (
    Path(__file__).resolve().parents[3]
    / ".github"
    / "workflows"
    / "build-docker-images.yml"
)
REFRESH_BASELINE_WORKFLOW_PATH = (
    Path(__file__).resolve().parents[3]
    / ".github"
    / "workflows"
    / "refresh-baseline.yml"
)
TESTS_WORKFLOW_PATH = (
    Path(__file__).resolve().parents[3] / ".github" / "workflows" / "tests.yml"
)
RELEASE_CANDIDATE_WORKFLOW_PATH = (
    Path(__file__).resolve().parents[3]
    / ".github"
    / "workflows"
    / "release-candidate.yml"
)
DOCKERFILE_PATH = (
    Path(__file__).resolve().parents[3] / "docker" / "bpp_base" / "Dockerfile"
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

    assert "\n  build:\n" in jobs
    assert "\n  dependency_scan:\n" in jobs
    assert "\n  scan:\n" in jobs
    assert "\n  promote:\n" in jobs
    assert "\n  check-flag:" not in jobs


def test_docker_workflow_promocja_czeka_na_oba_skany():
    workflow = WORKFLOW_PATH.read_text(encoding="utf-8")
    promote = workflow.split("\n  promote:\n", maxsplit=1)[1]

    assert "needs: [build, dependency_scan, scan]" in promote
    assert "needs.dependency_scan.result == 'success'" in promote
    assert "needs.scan.result == 'success'" in promote


def test_release_candidate_wlacza_oba_skany_w_reusable_workflow():
    workflow = RELEASE_CANDIDATE_WORKFLOW_PATH.read_text(encoding="utf-8")

    assert "run_trivy: ${{ !inputs.skip_scan }}" in workflow
    assert "run_dependency_scan: ${{ !inputs.skip_scan }}" in workflow


def test_refresh_baseline_uzywa_kanonicznego_targetu_make():
    workflow = REFRESH_BASELINE_WORKFLOW_PATH.read_text(encoding="utf-8")

    assert "run: make baseline-update" in workflow
    assert "run: uv run python src/manage.py baseline_rebuild" not in workflow


def test_ci_test_runner_nie_zawiera_node_ani_pelnego_chromium():
    dockerfile = DOCKERFILE_PATH.read_text(encoding="utf-8")
    test_runner = dockerfile.split(" AS test-runner\n", maxsplit=1)[1].split(
        " AS test-runner-local\n", maxsplit=1
    )[0]

    assert "playwright install --only-shell chromium" in dockerfile
    assert "node_modules" not in test_runner
    assert "npm install" not in test_runner
    assert "apt-get install -y nodejs" not in test_runner


def test_ci_test_runner_jest_pushowany_z_kompresja_zstd():
    workflow = TESTS_WORKFLOW_PATH.read_text(encoding="utf-8")

    assert "type=registry,compression=zstd,compression-level=3" in workflow
