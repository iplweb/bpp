# Opt-in Docker Builds with Commit Message Flag

**Date:** 2026-05-04
**Author:** Claude (with mpasternak)
**Status:** Design approved, awaiting implementation

## Problem Statement

Docker Cloud builds are triggered on every push to `feature/**`, `fix/**`, and `hotfix/**` branches, consuming paid BuildCloud minutes unnecessarily. These builds are rarely used - only needed when testing Docker-specific changes before merging to master.

Current workflow costs money without providing value for most feature branches.

## Requirements

### Functional Requirements

1. **Master/main branches:** Always build Docker images automatically (release flow)
2. **Feature/fix/hotfix branches:** Build ONLY when:
   - Commit message (subject OR body) contains `[docker-build]` flag (case-insensitive)
   - AND the actor is `mpasternak`
3. **Manual override:** `workflow_dispatch` always builds regardless of branch or flags
4. **Pull requests:** Should follow same logic as feature/fix branches (flag + actor check)

### Non-Functional Requirements

- No accidental builds from contributor branches
- Easy to opt-in when Docker testing is needed
- Full audit trail of why a build was triggered (visible in workflow logs)
- Backwards compatible with existing workflow_dispatch usage

## Proposed Solution

### Workflow Trigger Changes

**Remove automatic triggers for non-master branches:**
```yaml
on:
  push:
    branches:
      - master
      - main
      # Removed: feature/**, fix/**, hotfix/** (will use filter instead)
  pull_request:
    types: [opened, synchronize, reopened]
  workflow_dispatch:
    # Manual override - always builds
```

### Build Logic in `check-flag` Job

Replace existing actor-based logic with:

```python
# Pseudo-code for check-flag job
should_build = false

if event == "workflow_dispatch":
    should_build = true  # Manual override
elif event == "push" and branch in ["master", "main"]:
    should_build = true  # Always build master/main
elif event == "pull_request" or (event == "push" and branch not in ["master", "main"]):
    # Check if mpasternak AND commit contains [docker-build]
    if actor == "mpasternak":
        commit_message = get_commit_message(github.sha)
        if "[docker-build]" in commit_message.lower():
            should_build = true

if should_build:
    echo "should_build=true" >> $GITHUB_OUTPUT
else:
    echo "should_build=false" >> $GITHUB_OUTPUT
```

### Implementation Details

**Fetch commit message:**
```bash
# Get full commit message (subject + body)
COMMIT_MSG=$(git log -1 --format=%B ${{ github.sha }})
```

**Case-insensitive search:**
```bash
if echo "$COMMIT_MSG" | grep -qi "\[docker-build\]"; then
  echo "should_build=true"
fi
```

**Preserve existing PR dedupe logic:** Keep the existing check that skips push events when a PR is open for the same branch (avoids duplicate builds).

### Example Usage

**Feature branch that should NOT build:**
```bash
git commit -m "Add new feature"
git push origin feature/my-feature
# Result: NO Docker build
```

**Feature branch that SHOULD build:**
```bash
git commit -m "[docker-build] Update base image to Ubuntu 24.04"
git push origin feature/docker-upgrade
# Result: Docker build triggered
```

**Manual override (any branch):**
```bash
gh workflow run build-docker-images.yml --ref feature/some-branch
# Result: Docker build triggered (no flag needed)
```

## Migration Path

1. Update `.github/workflows/build-docker-images.yml` with new logic
2. Test on feature branch without flag (should NOT build)
3. Test on feature branch with `[docker-build]` flag (SHOULD build)
4. Verify workflow_dispatch still works
5. Merge to master

## Testing Strategy

- **No flag test:** Push to feature branch without `[docker-build]` → verify build is skipped
- **With flag test:** Push to feature branch with `[docker-build]` → verify build runs
- **Case insensitivity:** Test `[DOCKER-BUILD]`, `[Docker-Build]`, etc.
- **Flag in body:** Test with flag only in commit body (not subject)
- **Actor check:** Verify non-mpasternak pushes don't build even with flag
- **Master always builds:** Push to master → verify build runs without flag
- **Manual override:** Test workflow_dispatch on random branch
- **PR dedupe:** Verify push event is skipped when PR is open

## Rollback Plan

If issues arise, revert to previous workflow logic:
- Restore `feature/**`, `fix/**`, `hotfix/**` in push triggers
- Restore simple actor-based check (mpasternak builds, others skip)

## Success Criteria

- BuildCloud minutes reduced by ~80% (estimated based on current usage)
- No accidental builds from non-mpasternak contributors
- Easy opt-in when Docker testing is genuinely needed
- Zero disruption to master/main release flow
