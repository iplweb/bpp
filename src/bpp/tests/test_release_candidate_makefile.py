import os
import subprocess
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]


def _write_executable(path, content):
    path.write_text(content)
    path.chmod(0o755)


def _run_release_candidate(tmp_path, scenario):
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    calls_path = tmp_path / "gh-calls"
    state_path = tmp_path / "gh-state"

    _write_executable(
        fake_bin / "git",
        """#!/bin/sh
printf 'dev\\n'
""",
    )
    _write_executable(
        fake_bin / "sleep",
        """#!/bin/sh
exit 0
""",
    )
    _write_executable(
        fake_bin / "gh",
        """#!/bin/sh
printf '%s\\n' "$*" >> "$GH_CALLS_PATH"

case "$1 $2" in
    "workflow run")
        if [ "$GH_SCENARIO" = "dispatch-failure" ]; then
            echo "simulated dispatch failure" >&2
            exit 1
        fi
        ;;
    "run list")
        case "$*" in
            *'.createdAt >= '*);;
            *)
                printf '111\\n'
                exit 0
                ;;
        esac
        attempt=0
        if [ -f "$GH_STATE_PATH" ]; then
            attempt=$(sed -n '1p' "$GH_STATE_PATH")
        fi
        attempt=$((attempt + 1))
        printf '%s\\n' "$attempt" > "$GH_STATE_PATH"
        if [ "$attempt" -ge 3 ]; then
            printf '222\\n'
        fi
        ;;
    "run watch")
        printf 'watched %s\\n' "$3"
        ;;
esac
""",
    )

    env = os.environ.copy()
    env.update(
        {
            "GH_CALLS_PATH": str(calls_path),
            "GH_SCENARIO": scenario,
            "GH_STATE_PATH": str(state_path),
            "PATH": f"{fake_bin}{os.pathsep}{env['PATH']}",
        }
    )
    result = subprocess.run(
        ["make", "--no-print-directory", "release-candidate", "SKIP_SCAN=1"],
        cwd=REPOSITORY_ROOT,
        env=env,
        capture_output=True,
        text=True,
    )
    calls = calls_path.read_text().splitlines()
    return result, calls


def test_release_candidate_stops_when_dispatch_fails(tmp_path):
    result, calls = _run_release_candidate(tmp_path, "dispatch-failure")

    assert result.returncode != 0
    assert "Nie udało się uruchomić workflow" in result.stdout
    assert len(calls) == 1
    assert calls[0].startswith("workflow run release-candidate.yml")


def test_release_candidate_watches_only_run_created_after_dispatch(tmp_path):
    result, calls = _run_release_candidate(tmp_path, "success")

    assert result.returncode == 0, result.stdout + result.stderr
    assert "Obserwuję run ID: 222" in result.stdout
    run_list_calls = [call for call in calls if call.startswith("run list ")]
    assert len(run_list_calls) == 3
    assert all("--branch=dev" in call for call in run_list_calls)
    assert all("--event=workflow_dispatch" in call for call in run_list_calls)
    assert all("databaseId,createdAt" in call for call in run_list_calls)
    assert calls[-1] == "run watch 222"
