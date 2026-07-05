# Staging-release → promote: plan implementacji

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rozciąć jednofazowe wydanie na dwie komendy CLI — `release-candidate.yml` (zbuduj RC → kanał `:staging`) i `promote.yml` (na żądanie: finalizuj wersję + przepnij `:latest` przez imagetools, bez rebuildu).

**Architecture:** `build-docker-images.yml` staje się reusable (`workflow_call`) silnikiem build (buduje 6 obrazów do podanego docker-tagu + opcjonalny kanał, brama Trivy sterowana inputem), przestaje budować/ruszać `:latest` na push mastera. `release-candidate.yml` bumpuje wersję RC na gałęzi `release/v<BASE>`, skanuje, testuje, pushuje gałąź i woła silnik build. `promote.yml` finalizuje wersję, składa towncrier, merge→master + back-merge→dev, i `imagetools`-uje immutable RC-tag → `:latest` + `:wersja`.

**Tech Stack:** GitHub Actions (workflow_call/dispatch), `gh` CLI, bumpver (CalVer `vYYYY0M.BUILD[-TAGNUM]`), towncrier, uv, `docker buildx bake` (Docker Cloud builder) + `docker buildx imagetools create`, Trivy.

## Global Constraints

- **6 obrazów** budowanych/tagowanych: `iplweb/bpp_base`, `iplweb/bpp_appserver`, `iplweb/bpp_workerserver`, `iplweb/bpp_beatserver`, `iplweb/bpp_authserver`, `iplweb/bpp_denorm_queue`.
- **Docker-tagi wersyjne = pep440 bumpvera** (bez `v`, bez myślnika): `202606.1392rc1`, `202606.1392`. Git-tagi = forma wersji-stringa z `v` (`v202606.1392`); RC nie dostaje git-tagu.
- **`bin/bpp-version.py`** wypisuje pep440 z `src/django_bpp/version.py` (np. `202606.1392rc1`), bez nowej linii.
- **Pliki wersji są własnością bumpvera** (`pyproject.toml`, `src/django_bpp/version.py`, `package.json`, `Makefile` `DOCKER_VERSION`) — nigdy nie edytować ręcznie na dev.
- **`uv run` przed każdą komendą Pythona.** Max długość linii 88 (ruff).
- **Komentarze i opisy po polsku** (zgodnie z istniejącymi workflowami).
- **Sekrety/vars:** `secrets.DOCKER_PAT`, `vars.DOCKER_USER` (login Docker Hub); builder Docker Cloud: `driver: cloud`, `endpoint: "iplweb/bpp"`.
- **Branch protection na `master`:** jeśli odrzuca push z Actions — użyć `secrets.RELEASE_PAT` (fine-grained, contents:write) w `token:` checkout/push (opisane w zadaniach jako wariant).
- Walidacja YAML w każdym zadaniu: `uv run python -c "import yaml; yaml.safe_load(open('<plik>'))"`.

## File Structure

- `.github/workflows/build-docker-images.yml` — **modyfikacja**: reusable silnik build (inputs/outputs), usunięcie `push:master` + master-`:latest`, Trivy gated inputem, promocja kanału.
- `.github/workflows/release.yml` → `.github/workflows/release-candidate.yml` — **rename + przepisanie**: cut-RC na `release/v<BASE>` → woła silnik build z `channel=staging`.
- `.github/workflows/promote.yml` — **nowy**: finalizacja + merge + imagetools rc→latest.
- `.github/workflows/tests.yml` — bez zmian (skip release-commita na master już jest).
- `docs/deweloper/wydania.md` — **nowy**: dokumentacja dwufazowego flow + przełączenie stagingu na `:staging`.
- `CLAUDE.md` — **modyfikacja**: krótka notka o nowym flow wydań.

---

### Task 1: `build-docker-images.yml` → reusable silnik build

**Files:**
- Modify: `.github/workflows/build-docker-images.yml` (`on:` blok ~63-74; `check-flag` ~107-115; `docker` checkout ~201-202; `Compute Docker tags` ~208-269; `Trivy` ~323-324, ~391; `Promote` ~453-496)

**Interfaces:**
- Produces (workflow_call): inputs `ref:string`, `version_tag:string`, `channel:string=""`, `run_trivy:boolean=true`. Buduje 6 obrazów, promuje `sha-<sha>` → `:<version_tag>` (+ `:<channel>` jeśli podany). Produkcyjny `:latest` rusza wyłącznie przez `promote.yml`.

- [ ] **Step 1: Zamień blok `on:` — usuń push:master, dodaj workflow_call**

Zastąp obecny `on:` (linie ~63-74):

```yaml
on:
  # UWAGA: push:master USUNIĘTY. Produkcyjny :latest rusza WYŁĄCZNIE promote.yml
  # (imagetools z gotowego RC) — build-once-promote, jedno źródło prawdy o prod.
  pull_request:
    types: [opened, synchronize, reopened]
  workflow_dispatch:
  workflow_call:
    inputs:
      ref:
        description: Git ref do zbudowania (np. release/v202606.1392)
        type: string
        required: true
      version_tag:
        description: Immutable docker-tag do publikacji (pep440, np. 202606.1392rc1)
        type: string
        required: true
      channel:
        description: Opcjonalny ruchomy tag-kanał (np. staging). Pusty = brak.
        type: string
        default: ""
      run_trivy:
        description: Uruchom bramę Trivy CRITICAL przed promocją
        type: boolean
        default: true
```

- [ ] **Step 2: `check-flag` — zawsze buduj gdy wywołane przez workflow_call**

W jobie `check-flag`, w stepie `- id: check`, dodaj do `env:` (po `GIT_SHA:`):

```yaml
          VERSION_TAG: ${{ inputs.version_tag }}
```

i na początku skryptu `run: |` (zaraz po `# Dedupe:` komentarzu, przed pierwszym `if`):

```bash
          # Wywołanie reusable (workflow_call): silnik buduje bezwarunkowo.
          if [ -n "${VERSION_TAG:-}" ]; then
            echo "should_build=true" >> "$GITHUB_OUTPUT"
            echo "::notice::Docker build — workflow_call (version_tag=${VERSION_TAG})"
            exit 0
          fi
```

- [ ] **Step 3: `docker` job — checkout po `inputs.ref`**

W jobie `docker`, step `Checkout code` (~201-202) zamień na:

```yaml
      - name: Checkout code
        uses: actions/checkout@df4cb1c069e1874edd31b4311f1884172cec0e10 # v6.0.3
        with:
          # Pusty ref (dispatch/PR) = domyślny ref eventu; przy workflow_call
          # budujemy dokładnie gałąź wydania.
          ref: ${{ inputs.ref }}
```

- [ ] **Step 4: `Compute Docker tags` — gałąź dla workflow_call + output `channel_tag`**

W stepie `Compute Docker tags (staging + final)` dodaj do `env:` (po `PR_NUMBER:`):

```yaml
          INPUT_VERSION_TAG: ${{ inputs.version_tag }}
          INPUT_CHANNEL: ${{ inputs.channel }}
```

W skrypcie, zaraz po wyliczeniu `STAGING_TAG` i jego echo (po linii `echo "staging_tag=${STAGING_TAG}" >> "$GITHUB_OUTPUT"`), wstaw gałąź workflow_call:

```bash
          # Wywołanie reusable: tag i kanał z inputów (omija logikę ref-based).
          if [ -n "${INPUT_VERSION_TAG:-}" ]; then
            echo "final_tag=${INPUT_VERSION_TAG}" >> "$GITHUB_OUTPUT"
            echo "channel_tag=${INPUT_CHANNEL}" >> "$GITHUB_OUTPUT"
            echo "branch_tag=" >> "$GITHUB_OUTPUT"
            exit 0
          fi
```

W każdej z gałęzi ref-based (`pull_request` / `else`) dodaj pustą linię outputu kanału, żeby step zawsze ją ustawiał. W każdej dopisz:

```bash
            echo "channel_tag=" >> "$GITHUB_OUTPUT"
```

- [ ] **Step 5: Trivy — brama sterowana inputem**

W obu stepach Trivy zamień warunek `if: github.ref_name == 'master'` na:

```yaml
        if: ${{ inputs.run_trivy || github.ref_name == 'master' }}
```

(Dotyczy `Trivy CRITICAL gate` i `Trivy HIGH report`. Dla dispatch/PR `inputs.run_trivy` jest puste/false → zachowanie jak dziś; dla workflow_call domyślnie true → brama działa na RC.)

- [ ] **Step 6: Promote — dodaj promocję kanału**

W stepie `Promote staging tag to canonical tag(s)` dodaj do `env:` (po `BRANCH_TAG:`):

```yaml
          CHANNEL_TAG: ${{ steps.tag.outputs.channel_tag }}
```

W pętli `for img`, zaraz po promocji `FINAL_TAG`, wstaw:

```bash
            # Kanał deployu (np. :staging) — ruchomy alias na ten sam digest.
            if [ -n "${CHANNEL_TAG:-}" ]; then
              echo "→ also tagging :${CHANNEL_TAG} (kanał)"
              docker buildx imagetools create \
                -t "${img}:${CHANNEL_TAG}" \
                "${img}:${STAGING_TAG}"
            fi
```

- [ ] **Step 7: Walidacja YAML**

Run: `uv run python -c "import yaml; yaml.safe_load(open('.github/workflows/build-docker-images.yml')); print('OK')"`
Expected: `OK`

- [ ] **Step 8: Commit**

```bash
git add .github/workflows/build-docker-images.yml
git commit -m "ci(docker): reusable silnik build (workflow_call) + kanał deployu, usuń push:master→latest"
```

---

### Task 2: `release.yml` → `release-candidate.yml` (cut RC → staging)

**Files:**
- Rename+rewrite: `.github/workflows/release.yml` → `.github/workflows/release-candidate.yml`

**Interfaces:**
- Consumes: silnik build z Task 1 (`uses: ./.github/workflows/build-docker-images.yml`, inputs `ref`/`version_tag`/`channel`/`run_trivy`).
- Produces: gałąź `release/v<BASE>` na origin; obrazy `:<BASE>rcN` + `:staging`. Job `prepare` outputs: `version_tag` (pep440 rc), `release_ref` (`release/v<BASE>`).

- [ ] **Step 1: Usuń stary `release.yml`, utwórz `release-candidate.yml`**

```bash
git rm .github/workflows/release.yml
```

Utwórz `.github/workflows/release-candidate.yml` z pełną treścią:

```yaml
name: Release candidate (kandydat → staging)

# Pierwsza z dwóch komend wydania (druga: promote.yml). Buduje kandydata na
# gałęzi release/v<BASE>, skanuje, testuje i publikuje obrazy :<BASE>rcN +
# :staging. NIE rusza master/dev/:latest. Wywołanie:
#   gh workflow run release-candidate.yml --ref dev
# Powtórne wywołanie (gdy gałąź release/* otwarta) → kolejne -rcN.
# Promote dopiero przez: gh workflow run promote.yml

on:
  workflow_dispatch:
    inputs:
      skip_tests:
        description: Pomiń testy (AWARYJNIE).
        type: boolean
        default: false
      skip_scan:
        description: Pomiń skan CVE (AWARYJNIE).
        type: boolean
        default: false

concurrency:
  group: release
  cancel-in-progress: false

permissions:
  contents: write

jobs:
  prepare:
    name: Zbuduj kandydata (bump RC + scan + testy)
    runs-on: ubuntu-latest
    timeout-minutes: 60
    env:
      COMPOSE_FILES: -f docker-compose.test.yml -f docker-compose.test.ci.yml
    outputs:
      version_tag: ${{ steps.bump.outputs.version_tag }}
      release_ref: ${{ steps.bump.outputs.release_ref }}
    steps:
      - name: Checkout (pełna historia + tagi)
        uses: actions/checkout@df4cb1c069e1874edd31b4311f1884172cec0e10 # v6.0.3
        with:
          fetch-depth: 0
          token: ${{ secrets.GITHUB_TOKEN }}

      - name: Konfiguracja git
        run: |
          git config user.name  "github-actions[bot]"
          git config user.email "41898282+github-actions[bot]@users.noreply.github.com"
          git fetch --tags origin dev

      - name: Install uv
        uses: astral-sh/setup-uv@fac544c07dec837d0ccb6301d7b5580bf5edae39 # v8.2.0
        with:
          enable-cache: true

      - name: Bump RC (nowy cykl lub kolejne -rcN)
        id: bump
        run: |
          set -euo pipefail
          # Wykryj otwartą gałąź wydania (origin/release/*).
          OPEN=$(git ls-remote --heads origin 'refs/heads/release/*' \
                 | sed -E 's@.*refs/heads/(release/.*)$@\1@' | head -1 || true)

          if [ -z "$OPEN" ]; then
            # Nowy cykl: gałąź z dev, bump do rc1 (inkrementuje BUILD + -rc1).
            git switch -C _rc origin/dev
            uv run bumpver update --no-fetch --commit --no-push --tag rc --tag-num
          else
            # Kontynuacja: checkout gałęzi, podbierz fixy z dev, kolejny -rcN.
            git switch -C _rc "origin/$OPEN"
            git merge --no-ff --no-edit origin/dev
            uv run bumpver update --no-fetch --commit --no-push --tag-num
          fi

          PEP=$(./bin/bpp-version.py)            # np. 202606.1392rc2
          BASE=$(echo "$PEP" | sed -E 's/rc[0-9]+$//')   # 202606.1392
          RELEASE_REF="release/v${BASE}"
          git branch -M _rc "$RELEASE_REF"
          echo "version_tag=${PEP}" >> "$GITHUB_OUTPUT"
          echo "release_ref=${RELEASE_REF}" >> "$GITHUB_OUTPUT"
          echo "::notice::Kandydat ${PEP} na gałęzi ${RELEASE_REF}"

          # Zamroź lockfile dla tego RC.
          uv lock
          git add uv.lock
          git commit -m "Aktualizacja uv.lock dla ${PEP}" || echo "uv.lock bez zmian."

      - name: Zainstaluj skanery CVE
        if: ${{ !inputs.skip_scan }}
        run: |
          curl -sSL -o /usr/local/bin/osv-scanner \
            https://github.com/google/osv-scanner/releases/latest/download/osv-scanner_linux_amd64
          chmod +x /usr/local/bin/osv-scanner
          curl -sSfL https://raw.githubusercontent.com/anchore/grype/main/install.sh \
            | sh -s -- -b /usr/local/bin
          curl -sSfL https://raw.githubusercontent.com/aquasecurity/trivy/main/contrib/install.sh \
            | sh -s -- -b /usr/local/bin

      - name: Skan CVE (bramka)
        if: ${{ !inputs.skip_scan }}
        run: ./bin/scan-deps.sh

      - name: Przygotuj ci-output
        if: ${{ !inputs.skip_tests }}
        run: mkdir -p ci-output

      - name: Zbuduj obraz test-runner
        if: ${{ !inputs.skip_tests }}
        run: docker compose $COMPOSE_FILES build test-runner

      - name: Wystartuj usługi
        if: ${{ !inputs.skip_tests }}
        run: docker compose $COMPOSE_FILES up -d db redis

      - name: Czekaj na usługi
        if: ${{ !inputs.skip_tests }}
        timeout-minutes: 2
        run: |
          until docker compose $COMPOSE_FILES exec db pg_isready -U bpp; do
            echo "Czekam na PostgreSQL..."; sleep 2
          done
          until docker compose $COMPOSE_FILES exec redis redis-cli ping; do
            echo "Czekam na Redis..."; sleep 2
          done

      - name: TESTY (pełna suita)
        if: ${{ !inputs.skip_tests }}
        timeout-minutes: 45
        run: |
          docker compose $COMPOSE_FILES run --rm \
            test-runner uv run pytest -n auto --timeout 300

      - name: Sprzątanie usług
        if: ${{ always() && !inputs.skip_tests }}
        run: docker compose $COMPOSE_FILES down -v

      - name: Push gałęzi wydania
        env:
          RELEASE_REF: ${{ steps.bump.outputs.release_ref }}
        run: git push origin "HEAD:refs/heads/${RELEASE_REF}"

  build:
    name: Build obrazów RC → :staging
    needs: prepare
    uses: ./.github/workflows/build-docker-images.yml
    with:
      ref: ${{ needs.prepare.outputs.release_ref }}
      version_tag: ${{ needs.prepare.outputs.version_tag }}
      channel: staging
      run_trivy: ${{ !inputs.skip_scan }}
    secrets: inherit
```

- [ ] **Step 2: Walidacja YAML**

Run: `uv run python -c "import yaml; yaml.safe_load(open('.github/workflows/release-candidate.yml')); print('OK')"`
Expected: `OK`

- [ ] **Step 3: Sanity — wykrycie gałęzi i ekstrakcja BASE lokalnie**

Run:
```bash
echo "202606.1392rc2" | sed -E 's/rc[0-9]+$//'
```
Expected: `202606.1392`

- [ ] **Step 4: Commit**

```bash
git add .github/workflows/release-candidate.yml
git commit -m "ci: release-candidate.yml (cut RC → staging), zastępuje release.yml"
```

---

### Task 3: `promote.yml` (RC → produkcja, imagetools)

**Files:**
- Create: `.github/workflows/promote.yml`

**Interfaces:**
- Consumes: gałąź `release/v<BASE>` + immutable obrazy `:<BASE>rcN` z Task 2.
- Produces: final wersja `<BASE>`, git-tag `v<BASE>`, merge→master + back-merge→dev, obrazy `:<BASE>` + `:latest` (imagetools).

- [ ] **Step 1: Utwórz `.github/workflows/promote.yml`**

```yaml
name: Promote (RC → produkcja)

# Druga komenda wydania. Finalizuje otwarte wydanie i przepina :latest na
# zatwierdzony obraz RC — BEZ rebuildu (imagetools). Wywołanie:
#   gh workflow run promote.yml
# Gdy otwartych jest >1 gałęzi release/* — podaj którą:
#   gh workflow run promote.yml -f version=v202606.1392

on:
  workflow_dispatch:
    inputs:
      version:
        description: "Wersja do promocji (np. v202606.1392). Puste = jedyna otwarta release/*."
        type: string
        default: ""

concurrency:
  group: release
  cancel-in-progress: false

permissions:
  contents: write

jobs:
  promote:
    name: Finalizuj + przepnij :latest
    runs-on: ubuntu-latest
    timeout-minutes: 20
    steps:
      - name: Checkout (pełna historia + tagi)
        uses: actions/checkout@df4cb1c069e1874edd31b4311f1884172cec0e10 # v6.0.3
        with:
          fetch-depth: 0
          token: ${{ secrets.GITHUB_TOKEN }}

      - name: Konfiguracja git
        run: |
          git config user.name  "github-actions[bot]"
          git config user.email "41898282+github-actions[bot]@users.noreply.github.com"
          git fetch --tags origin master dev '+refs/heads/release/*:refs/remotes/origin/release/*'

      - name: Install uv
        uses: astral-sh/setup-uv@fac544c07dec837d0ccb6301d7b5580bf5edae39 # v8.2.0
        with:
          enable-cache: true

      - name: Wykryj gałąź wydania + odczytaj RC
        id: detect
        env:
          INPUT_VERSION: ${{ inputs.version }}
        run: |
          set -euo pipefail
          if [ -n "${INPUT_VERSION:-}" ]; then
            BASE="${INPUT_VERSION#v}"
            RELEASE_REF="release/v${BASE}"
            git rev-parse --verify "origin/${RELEASE_REF}" >/dev/null 2>&1 \
              || { echo "::error::Brak gałęzi origin/${RELEASE_REF}"; exit 1; }
          else
            mapfile -t BRANCHES < <(git ls-remote --heads origin 'refs/heads/release/*' \
              | sed -E 's@.*refs/heads/(release/.*)$@\1@')
            if [ "${#BRANCHES[@]}" -eq 0 ]; then
              echo "::error::Brak otwartego wydania do promocji."; exit 1
            fi
            if [ "${#BRANCHES[@]}" -gt 1 ]; then
              echo "::error::Otwartych >1 wydań: ${BRANCHES[*]}. Podaj -f version=vXXX."; exit 1
            fi
            RELEASE_REF="${BRANCHES[0]}"
            BASE="${RELEASE_REF#release/v}"
          fi

          git switch -C "$RELEASE_REF" "origin/$RELEASE_REF"
          RC_TAG=$(./bin/bpp-version.py)        # np. 202606.1392rc2 (immutable docker-tag źródłowy)
          echo "release_ref=${RELEASE_REF}" >> "$GITHUB_OUTPUT"
          echo "base=${BASE}" >> "$GITHUB_OUTPUT"
          echo "rc_tag=${RC_TAG}" >> "$GITHUB_OUTPUT"
          echo "::notice::Promuję ${RELEASE_REF}: obraz :${RC_TAG} → :${BASE} + :latest"

      - name: Finalizuj wersję + towncrier
        env:
          BASE: ${{ steps.detect.outputs.base }}
        run: |
          set -euo pipefail
          uv run bumpver update --no-fetch --commit --no-push \
            --set-version "v${BASE}"
          uv run towncrier build --yes || echo "towncrier: brak newsfragmentów."
          git add -A
          git commit -m "Changelog dla v${BASE}" || echo "Brak zmian changelogu."

      - name: Przygotuj master/dev/tag lokalnie
        env:
          BASE: ${{ steps.detect.outputs.base }}
          RELEASE_REF: ${{ steps.detect.outputs.release_ref }}
        run: |
          set -euo pipefail
          git switch -C _master origin/master
          git merge --no-ff "$RELEASE_REF" -m "Release v${BASE}"
          git tag -a "v${BASE}" -m "Release v${BASE}"

          git switch -C _dev origin/dev
          git merge --no-ff "v${BASE}" -m "Merge tag 'v${BASE}' into dev"

      - name: Pre-flight — atomic git push będzie możliwy
        env:
          BASE: ${{ steps.detect.outputs.base }}
          RELEASE_REF: ${{ steps.detect.outputs.release_ref }}
        run: |
          set -euo pipefail
          git push --atomic --dry-run origin \
            _master:refs/heads/master \
            _dev:refs/heads/dev \
            "refs/tags/v${BASE}" \
            ":refs/heads/${RELEASE_REF}"

      - name: Log in to Docker Hub
        uses: docker/login-action@650006c6eb7dba73a995cc03b0b2d7f5ca915bee # v4.2.0
        with:
          username: ${{ vars.DOCKER_USER }}
          password: ${{ secrets.DOCKER_PAT }}

      - name: Set up Docker Buildx
        uses: docker/setup-buildx-action@d7f5e7f509e45cec5c76c4d5afdd7de93d0b3df5 # v4.1.0

      - name: Promote obrazów :rc → :wersja + :latest (imagetools)
        env:
          BASE: ${{ steps.detect.outputs.base }}
          RC_TAG: ${{ steps.detect.outputs.rc_tag }}
        run: |
          set -eu
          images=(
            iplweb/bpp_base
            iplweb/bpp_appserver
            iplweb/bpp_workerserver
            iplweb/bpp_beatserver
            iplweb/bpp_authserver
            iplweb/bpp_denorm_queue
          )
          for img in "${images[@]}"; do
            echo "::group::Promote ${img}: ${RC_TAG} → ${BASE} + latest"
            docker buildx imagetools create \
              -t "${img}:${BASE}" \
              -t "${img}:latest" \
              "${img}:${RC_TAG}"
            echo "::endgroup::"
          done
          {
            echo "## ✅ Promoted v${BASE}"
            echo ""
            echo "Źródło RC: \`:${RC_TAG}\` → \`:${BASE}\` + \`:latest\` (bez rebuildu)"
          } >> "$GITHUB_STEP_SUMMARY"

      - name: Push master/dev/tag i usuń release branch
        env:
          BASE: ${{ steps.detect.outputs.base }}
          RELEASE_REF: ${{ steps.detect.outputs.release_ref }}
        run: |
          set -euo pipefail
          git push --atomic origin \
            _master:refs/heads/master \
            _dev:refs/heads/dev \
            "refs/tags/v${BASE}" \
            ":refs/heads/${RELEASE_REF}"
```

- [ ] **Step 2: Walidacja YAML**

Run: `uv run python -c "import yaml; yaml.safe_load(open('.github/workflows/promote.yml')); print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add .github/workflows/promote.yml
git commit -m "ci: promote.yml (RC → produkcja przez imagetools, bez rebuildu)"
```

---

### Task 4: Dokumentacja flow + przełączenie stagingu

**Files:**
- Create: `docs/deweloper/wydania.md`
- Modify: `CLAUDE.md` (sekcja po „Key Commands")

- [ ] **Step 1: Utwórz `docs/deweloper/wydania.md`**

```markdown
# Wydania (staging-release → promote)

Wydanie jest dwufazowe i sterowane z CLI (`gh`). Build raz, promocja przepina
metadane tagu — produkcja dostaje DOKŁADNIE obraz przetestowany na stagingu.

## Wymóg jednorazowy: staging pulluje `:staging`

Serwer staging musi ciągnąć tag `:staging` (NIE `:latest`) wszystkich 6 obrazów:
`bpp_base`, `bpp_appserver`, `bpp_workerserver`, `bpp_beatserver`,
`bpp_authserver`, `bpp_denorm_queue`. Produkcja zostaje na `:latest`.

## Cykl

```bash
# 1) Utnij kandydata → buduje obrazy, przesuwa :staging
gh workflow run release-candidate.yml --ref dev

# … staging pulluje :staging, testujesz …

# 2a) OK → promuj (finalizacja + :latest, bez rebuildu)
gh workflow run promote.yml

# 2b) „kupa" → fix na dev, ponów cut-RC (kolejny -rcN, numer finalny niespalony)
gh workflow run release-candidate.yml --ref dev
```

Podgląd: `gh run watch $(gh run list --workflow=promote.yml -L1 --json databaseId --jq '.[0].databaseId')`.

## Dowód build-once-promote

Po promote `:latest` ma ten sam digest co przetestowany RC:

```bash
docker buildx imagetools inspect iplweb/bpp_appserver:latest
docker buildx imagetools inspect iplweb/bpp_appserver:202606.1392rc1   # ten sam digest
```

## Uwagi

- Gałąź `release/v<BASE>` żyje od cut-RC do promote (stan numeru RC); promote ją kasuje.
- `push:master` NIE przebudowuje już obrazów — każda zmiana prod idzie przez promote.
- Awaryjny build ad-hoc: `gh workflow run build-docker-images.yml --ref <branch>`.
```

- [ ] **Step 2: Dodaj notkę do `CLAUDE.md`**

Po sekcji „## Key Commands (Quick Reference)" dodaj:

```markdown
## Wydania (dwufazowe, CLI)

Wydanie = dwie komendy `gh` (szczegóły: docs/deweloper/wydania.md):

```bash
gh workflow run release-candidate.yml --ref dev   # zbuduj RC → :staging
gh workflow run promote.yml                        # RC → :latest (bez rebuildu)
```

`push:master` NIE buduje już obrazów produkcyjnych — robi to promote (imagetools).
```

- [ ] **Step 3: Commit**

```bash
git add docs/deweloper/wydania.md CLAUDE.md
git commit -m "docs: dwufazowy flow wydań (release-candidate + promote)"
```

---

### Task 5: Walidacja całości + pierwszy realny przebieg

**Files:** (brak zmian kodu — walidacja end-to-end)

- [ ] **Step 1: Walidacja wszystkich workflowów naraz**

Run:
```bash
uv run python - <<'PY'
import yaml, glob
for f in sorted(glob.glob('.github/workflows/*.yml')):
    yaml.safe_load(open(f)); print(f, "OK")
PY
```
Expected: każdy plik `OK`; brak `release.yml` na liście.

- [ ] **Step 2: (opcjonalnie) actionlint, jeśli dostępny**

Run: `command -v actionlint >/dev/null && actionlint .github/workflows/*.yml || echo "actionlint brak — pomijam"`
Expected: brak błędów albo „actionlint brak".

- [ ] **Step 3: Merge gałęzi feature na `dev` (rejestracja workflow_dispatch)**

Workflowy `workflow_dispatch` stają się uruchamialne dopiero z domyślnej gałęzi.
Otwórz PR feature→dev, scal (testy zielone), upewnij się że `dev` ma nowe pliki.

- [ ] **Step 4: Przełącz staging na `:staging`**

W konfiguracji deployu stagingu zmień pull obrazów z `:latest` na `:staging`
(6 obrazów). Bez tego pierwszy promote nie da się odróżnić od starego flow.

- [ ] **Step 5: Pierwszy cut-RC**

Run: `gh workflow run release-candidate.yml --ref dev`
Then: `gh run watch $(gh run list --workflow=release-candidate.yml -L1 --json databaseId --jq '.[0].databaseId')`
Expected: zielono; powstaje gałąź `release/vYYYYMM.N`, obrazy `:YYYYMM.Nrc1` + `:staging`.

- [ ] **Step 6: Test na stagingu, potem promote**

Po teście stagingu:
Run: `gh workflow run promote.yml`
Then: `gh run watch $(gh run list --workflow=promote.yml -L1 --json databaseId --jq '.[0].databaseId')`
Expected: master + dev zaktualizowane, git-tag `vYYYYMM.N`, gałąź `release/*` skasowana.

- [ ] **Step 7: Dowód build-once-promote**

Run:
```bash
docker buildx imagetools inspect iplweb/bpp_appserver:latest --format '{{.Manifest.Digest}}'
docker buildx imagetools inspect iplweb/bpp_appserver:$(gh ... rc_tag) --format '{{.Manifest.Digest}}'
```
Expected: **identyczny digest** (te same bajty co staging).

---

## Self-Review

**Spec coverage:**
- §2 build-once-promote → Task 3 imagetools (rc→latest), Task 5 step 7 dowód. ✓
- §2 rozdzielenie kanałów → Task 1 step 6 (channel), Task 4 (staging→:staging). ✓
- §3 dwie komendy CLI → Task 2 (release-candidate), Task 3 (promote), Task 4 docs. ✓
- §4 taksonomia (pep440 docker-tagi, :staging, :latest) → Task 1/2/3 spójnie pep440. ✓
- §5 git/wersje (release/v<BASE>, rc→final, back-merge "Merge tag") → Task 2 bump, Task 3 finalize+merge. ✓
- §6.1 reusable silnik (inputs/outputs, usuń push:master, Trivy gated) → Task 1. ✓
- §6.2 release-candidate (rc bump, no-towncrier, scan, test, call build) → Task 2. ✓
- §6.3 promote (finalize, towncrier, merge, imagetools) → Task 3. ✓
- §8 pliki wersji = bumpver-owned → Global Constraints + Task 2 (brak ręcznej edycji). ✓
- §9 staging→:staging → Task 4 step 1, Task 5 step 4. ✓
- §10 plan wdrożenia → Task 5. ✓

**Placeholder scan:** brak TBD/TODO; każdy step ma realny kod/komendę. ✓

**Type/nazwa consistency:**
- Outputy `prepare`: `version_tag`, `release_ref` ↔ użyte w `build.with` (Task 2). ✓
- `inputs` silnika: `ref/version_tag/channel/run_trivy` ↔ `build.with` (Task 2) + obsługa w Task 1 (steps 1,4,5,6). ✓
- `steps.detect.outputs`: `release_ref/base/rc_tag` ↔ użyte w kolejnych stepach promote (Task 3). ✓
- Docker-tag pep440 (`./bin/bpp-version.py`) konsekwentnie jako źródło RC (Task 2 bump, Task 3 detect). ✓
```
