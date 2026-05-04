# Opt-in Docker Builds Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement opt-in Docker builds using `[docker-build]` flag in commit messages to reduce BuildCloud costs

**Architecture:** Modify GitHub Actions workflow to check commit messages for `[docker-build]` flag before building Docker images on non-master branches

**Tech Stack:** GitHub Actions, bash scripting, git

---

## File Structure

**Files to modify:**
- `.github/workflows/build-docker-images.yml` - Main workflow file, contains trigger configuration and build logic

**No new files will be created.**

---

## Task 1: Update workflow triggers to remove automatic feature/fix/hotfix builds

**Files:**
- Modify: `.github/workflows/build-docker-images.yml:63-78`

- [ ] **Step 1: Remove feature/fix/hotfix from push triggers**

Remove the automatic triggers for feature, fix, and hotfix branches. We'll use commit message filtering instead.

Current code (lines 63-78):
```yaml
on:
  push:
    branches:
      - master
      - main
      - 'feature/**'
      - 'fix/**'
      - 'hotfix/**'
      # dev intentionally excluded — merge dev->master jest release flow,
      # nie chcemy palic Docker Cloud minutek na intermediate state dev.
  pull_request:
    # Buduje na każdy push do PR-a (oraz na otwarcie/reopen).
    types: [opened, synchronize, reopened]
  workflow_dispatch:
    # Ręczne wywołanie z GUI GitHub lub przez
    # `gh workflow run build-docker-images.yml --ref <branch>`.
```

Replace with:
```yaml
on:
  push:
    branches:
      - master
      - main
      # feature/**, fix/**, hotfix/** removed - build only on [docker-build] flag
  pull_request:
    # Buduje na każdy push do PR-a (oraz na otwarcie/reopen).
    types: [opened, synchronize, reopened]
  workflow_dispatch:
    # Ręczne wywołanie z GUI GitHub lub przez
    # `gh workflow run build-docker-images.yml --ref <branch>`.
```

- [ ] **Step 2: Verify YAML syntax**

Run: Check that YAML is valid (no trailing spaces, proper indentation)

Expected: File should be valid YAML

- [ ] **Step 3: Commit changes**

```bash
git add .github/workflows/build-docker-images.yml
git commit -m "feat: remove automatic Docker builds for feature/fix/hotfix branches

Branches will now only build when:
- Commit contains [docker-build] flag (case-insensitive)
- Actor is mpasternak
- Master/main always build (no flag needed)
- workflow_dispatch always works (manual override)

This reduces BuildCloud costs by avoiding unnecessary builds"
```

---

## Task 2: Implement commit message flag checking in check-flag job

**Files:**
- Modify: `.github/workflows/build-docker-images.yml:85-151`

- [ ] **Step 1: Add fetch-depth to checkout step**

We need full commit history to fetch commit messages. Update the checkout step in check-flag job.

Find line 104:
```yaml
- uses: actions/checkout@de0fac2e4500dabe0009e67214ff5f5447ce83dd # v6.0.2
```

Replace with:
```yaml
- uses: actions/checkout@de0fac2e4500dabe0009e67214ff5f5447ce83dd # v6.0.2
  with:
    fetch-depth: 0  # Need full history for commit messages
```

- [ ] **Step 2: Replace build decision logic**

Replace the entire script section (lines 112-151) with new logic that checks for `[docker-build]` flag.

Current code (lines 112-151):
```bash
run: |
  # Dedupe: push event na branchu z otwartym PR-em jest duplikatem
  # pull_request eventu dla tego samego commita. Pomijamy push run,
  # zeby nie budowac i nie pushowac tego samego SHA dwa razy do
  # Docker Cloud (~7 min build + transfer do rejestru kazdorazowo).
  # pull_request event bedzie tagowac obraz <PR#>-merge.
  if [ "$EVENT_NAME" = "push" ] \
     && [ "$REF_NAME" != "master" ] \
     && [ "$REF_NAME" != "main" ]; then
    PR=$(gh pr list --head "$REF_NAME" --state open \
         --repo "$REPO" \
         --json number --jq '.[0].number // empty')
    if [ -n "$PR" ]; then
      echo "should_build=false" >> "$GITHUB_OUTPUT"
      echo "::notice::Pomijam push run — PR #${PR} obsluzy ten commit (tag ${PR}-merge)"
      exit 0
    fi
  fi

  # Zawsze: master/main push (release) i workflow_dispatch (manual)
  if [ "$EVENT_NAME" = "push" ] \
     && { [ "$REF_NAME" = "master" ] || [ "$REF_NAME" = "main" ]; }; then
    echo "should_build=true" >> "$GITHUB_OUTPUT"
    echo "::notice::Docker build — push na ${REF_NAME} (release flow)"
    exit 0
  fi
  if [ "$EVENT_NAME" = "workflow_dispatch" ]; then
    echo "should_build=true" >> "$GITHUB_OUTPUT"
    echo "::notice::Docker build — workflow_dispatch (manual override)"
    exit 0
  fi

  # Pozostale (PR event, feature push bez PR) — tylko mpasternak.
  if [ "$ACTOR" = "mpasternak" ]; then
    echo "should_build=true" >> "$GITHUB_OUTPUT"
    echo "::notice::Docker build — actor=mpasternak, event=${EVENT_NAME}"
  else
    echo "should_build=false" >> "$GITHUB_OUTPUT"
    echo "::notice::Pomijam Docker build — actor=${ACTOR} != mpasternak"
  fi
```

Replace with:
```bash
run: |
  # Dedupe: push event na branchu z otwartym PR-em jest duplikatem
  # pull_request eventu dla tego samego commita. Pomijamy push run,
  # zeby nie budowac i nie pushowac tego samego SHA dwa razy do
  # Docker Cloud (~7 min build + transfer do rejestru kazdorazowo).
  # pull_request event bedzie tagowac obraz <PR#>-merge.
  if [ "$EVENT_NAME" = "push" ] \
     && [ "$REF_NAME" != "master" ] \
     && [ "$REF_NAME" != "main" ]; then
    PR=$(gh pr list --head "$REF_NAME" --state open \
         --repo "$REPO" \
         --json number --jq '.[0].number // empty')
    if [ -n "$PR" ]; then
      echo "should_build=false" >> "$GITHUB_OUTPUT"
      echo "::notice::Pomijam push run — PR #${PR} obsluzy ten commit (tag ${PR}-merge)"
      exit 0
    fi
  fi

  # Zawsze: master/main push (release) i workflow_dispatch (manual)
  if [ "$EVENT_NAME" = "push" ] \
     && { [ "$REF_NAME" = "master" ] || [ "$REF_NAME" = "main" ]; }; then
    echo "should_build=true" >> "$GITHUB_OUTPUT"
    echo "::notice::Docker build — push na ${REF_NAME} (release flow)"
    exit 0
  fi
  if [ "$EVENT_NAME" = "workflow_dispatch" ]; then
    echo "should_build=true" >> "$GITHUB_OUTPUT"
    echo "::notice::Docker build — workflow_dispatch (manual override)"
    exit 0
  fi

  # Pozostale (PR event, feature push bez PR) — sprawdzamy flage
  # [docker-build] w commit message (case-insensitive).
  # Budujemy tylko gdy:
  #   - actor to mpasternak
  #   - ORAZ commit message zawiera [docker-build]
  if [ "$ACTOR" != "mpasternak" ]; then
    echo "should_build=false" >> "$GITHUB_OUTPUT"
    echo "::notice::Pomijam Docker build — actor=${ACTOR} != mpasternak (flag check skipped)"
    exit 0
  fi

  # Pobierz pelny commit message (subject + body)
  COMMIT_MSG=$(git log -1 --format=%B "$GIT_SHA")

  # Sprawdz flage [docker-build] (case-insensitive)
  if echo "$COMMIT_MSG" | grep -qi "\[docker-build\]"; then
    echo "should_build=true" >> "$GITHUB_OUTPUT"
    echo "::notice::Docker build — znaleziono flage [docker-build] w commit message"
  else
    echo "should_build=false" >> "$GITHUB_OUTPUT"
    echo "::notice::Pomijam Docker build — brak flagi [docker-build] w commit message"
    echo "::notice::Aby wymusic build, dodaj [docker-build] do commit message lub uruchom: gh workflow run build-docker-images.yml --ref ${REF_NAME}"
  fi
```

- [ ] **Step 3: Verify bash syntax**

Check for common syntax errors: unmatched quotes, missing `then`/`fi`, incorrect variable expansion

Expected: All syntax should be valid bash

- [ ] **Step 4: Commit changes**

```bash
git add .github/workflows/build-docker-images.yml
git commit -m "feat: add [docker-build] flag check for opt-in Docker builds

Feature/fix/hotfix branches now require [docker-build] flag in commit
message (case-insensitive, in subject or body) to trigger Docker builds.

Changes:
- Add fetch-depth: 0 to checkout step (need full history for messages)
- Check commit message for [docker-build] flag
- Case-insensitive grep search
- Maintains mpasternak actor check
- Maintains PR dedupe logic
- Maintains master/main always-build
- Maintains workflow_dispatch manual override

Usage:
  git commit -m '[docker-build] update base image'
  git push origin feature/my-feature"
```

---

## Task 3: Update workflow documentation comments

**Files:**
- Modify: `.github/workflows/build-docker-images.yml:3-61`

- [ ] **Step 1: Update header comment to reflect new behavior**

The workflow header (lines 3-61) has extensive documentation. Update the check-flag job section to document the new behavior.

Find the section starting at line 85:
```yaml
  check-flag:
    # Guard job decyduje czy budowac obraz Docker.
    # - master/main push:           buduj zawsze (release flow, dowolny actor)
    # - workflow_dispatch:           buduj zawsze (manual override, dowolny actor)
    # - PR push / feature push:      buduj tylko gdy actor=mpasternak
    #                                (aby nie palic Docker Cloud minutek na PR-y
    #                                contributorow — manualnie odpalisz przez
    #                                `gh workflow run` jesli trzeba)
    # Plus dedupe: push do branchu z otwartym PR-em → skip (PR run obsluzy).
```

Replace with:
```yaml
  check-flag:
    # Guard job decyduje czy budowac obraz Docker.
    # - master/main push:           buduj zawsze (release flow, dowolny actor)
    # - workflow_dispatch:           buduj zawsze (manual override, dowolny actor)
    # - PR push / feature push:      buduj tylko gdy:
    #                                 • actor=mpasternak
    #                                 • ORAZ commit message zawiera [docker-build]
    #                                   (case-insensitive, w subject lub body)
    #                               W przeciwnym razie skip — aby nie palic
    #                               Docker Cloud minutek na kazdy feature/fix
    #                               branch. Mozna wymusic build recznie przez
    #                               `gh workflow run build-docker-images.yml`.
    # Plus dedupe: push do branchu z otwartym PR-em → skip (PR run obsluzy).
```

- [ ] **Step 2: Commit documentation update**

```bash
git add .github/workflows/build-docker-images.yml
git commit -m "docs: update workflow comments for [docker-build] flag

Document the new opt-in build behavior in workflow header comments."
```

---

## Task 4: Create test branch to verify implementation

**Files:**
- No files modified (git operations only)

- [ ] **Step 1: Create test feature branch**

```bash
git checkout -b test/docker-build-flag
```

- [ ] **Step 2: Create test commit WITHOUT flag**

```bash
echo "test" > test_file.txt
git add test_file.txt
git commit -m "Test commit without docker flag"
```

- [ ] **Step 3: Push test branch**

```bash
git push origin test/docker-build-flag
```

- [ ] **Step 4: Check GitHub Actions - verify build was skipped**

Visit: `https://github.com/mpasternak/bpp/actions`

Expected: Workflow should be triggered but should skip at check-flag job with message "Pomijam Docker build — brak flagi [docker-build] w commit message"

- [ ] **Step 5: Create test commit WITH flag**

```bash
echo "test2" > test_file2.txt
git add test_file2.txt
git commit -m "[docker-build] Test commit with flag"
```

- [ ] **Step 6: Push test commit**

```bash
git push origin test/docker-build-flag
```

- [ ] **Step 7: Check GitHub Actions - verify build ran**

Expected: Workflow should run full Docker build with message "Docker build — znaleziono flage [docker-build] w commit message"

- [ ] **Step 8: Test case-insensitivity**

```bash
echo "test3" > test_file3.txt
git add test_file3.txt
git commit -m "[DOCKER-BUILD] Test uppercase flag"
git push origin test/docker-build-flag
```

Expected: Build should run (case-insensitive)

- [ ] **Step 9: Test flag in commit body**

```bash
echo "test4" > test_file4.txt
git add test_file4.txt
git commit -m "Test flag in body

[docker-build] This flag is in the body, not subject"
git push origin test/docker-build-flag
```

Expected: Build should run (flag in body)

- [ ] **Step 10: Test workflow_dispatch manual override**

```bash
gh workflow run build-docker-images.yml --ref test/docker-build-flag
```

Expected: Workflow should run (manual override, no flag needed)

- [ ] **Step 11: Clean up test branch**

```bash
git checkout dev
git branch -D test/docker-build-flag
git push origin --delete test/docker-build-flag
```

---

## Task 5: Verify master/main still always build

**Files:**
- No files modified (verification only)

- [ ] **Step 1: Ensure you're on dev branch**

```bash
git checkout dev
git pull origin dev
```

- [ ] **Step 2: Verify behavior matches spec**

Check the following:
- Master/main builds should work without any flag ✓
- workflow_dispatch should work on any branch ✓
- PR dedupe logic should still work ✓
- Actor check should still prevent non-mpasternak builds ✓

Expected: All behaviors match the design spec

---

## Task 6: Merge to dev and push

**Files:**
- No files modified (git operations only)

- [ ] **Step 1: Push implementation branch to remote**

```bash
git push origin <your-implementation-branch>
```

- [ ] **Step 2: Create pull request to dev**

```bash
gh pr create --title "feat: opt-in Docker builds with [docker-build] flag" \
  --body "Implements opt-in Docker builds to reduce BuildCloud costs.

See design spec: docs/superpowers/specs/2026-05-04-docker-build-opt-in-design.md

- Feature/fix/hotfix branches now require [docker-build] flag
- Master/main always build automatically
- Manual override via workflow_dispatch preserved
- Case-insensitive flag in commit subject or body
- Actor check (mpasternak only) for non-master branches

Tested on test/docker-build-flag branch with:
- Commit without flag → build skipped ✓
- Commit with [docker-build] → build ran ✓
- Commit with [DOCKER-BUILD] → build ran (case-insensitive) ✓
- Flag in commit body → build ran ✓
- workflow_dispatch → build ran (no flag needed) ✓"
```

---

## Summary

This implementation changes Docker build behavior from automatic (for all mpasternak branches) to opt-in (via `[docker-build]` flag), significantly reducing BuildCloud costs while maintaining flexibility when Docker testing is needed.

**Key changes:**
1. Removed automatic triggers for feature/fix/hotfix branches
2. Added commit message flag checking (case-insensitive)
3. Preserved all existing safety checks (actor, PR dedupe, etc.)
4. Maintained backward compatibility for master/main and manual dispatch
