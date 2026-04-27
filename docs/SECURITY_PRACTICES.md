# Security Practices — BPP

Dokument zbiera praktyki bezpieczeństwa stosowane w BPP, oparte na
[lirantal/pypi-security-best-practices](https://github.com/lirantal/pypi-security-best-practices).

Polityka zgłaszania luk bezpieczeństwa: [SECURITY.md](../SECURITY.md).

## Spis treści

- [Deterministyczne instalacje (`--frozen`)](#deterministyczne-instalacje---frozen)
- [Wheel-only policy](#wheel-only-policy)
- [Cooldown przed instalacją](#cooldown-przed-instalacją)
- [Eksplicytny indeks PyPI](#eksplicytny-indeks-pypi)
- [SHA-pinning GitHub Actions](#sha-pinning-github-actions)
- [Sekrety i `.env`](#sekrety-i-env)

---

## Deterministyczne instalacje (`--frozen`)

**Reguła**: Każda komenda instalująca pakiety w środowisku CI lub produkcji
MUSI używać `uv sync --frozen` (nigdy `uv sync` ani `uv pip install`).

**Dlaczego**: bez `--frozen` uv ponownie rozwiązuje zależności i może
wciągnąć nowsze (potencjalnie złośliwe) wersje opublikowane między
generacją lockfile a instalacją. `--frozen` instaluje WYŁĄCZNIE wersje
zapisane w `uv.lock` — z hashami SHA-256, które wykrywają tampering.

**Gdzie egzekwowane**:

| Kontekst                                  | Komenda                            |
| ----------------------------------------- | ---------------------------------- |
| `.github/workflows/tests.yml`             | `uv sync --frozen`                 |
| `.github/workflows/refresh-baseline.yml`  | `uv sync --frozen --extra ...`     |
| `docker/bpp_base/Dockerfile` (builder)    | `uv sync --frozen --no-dev ...`    |
| `docker/bpp_base/Dockerfile` (test stage) | `uv sync --frozen --all-extras`    |
| `make prepare-developer-machine-*`        | `uv sync --frozen --all-extras`    |

**Wyjątki (świadome)**:

- `make uv-sync` — luźny, bez `--frozen`, dla aktywnego dewelopmentu gdy
  dev modyfikuje `pyproject.toml` i potrzebuje refresh lockfile w jednym
  kroku. Workflow: `vim pyproject.toml; make uv-lock; make uv-sync`.
- `make live-docs` — `uv pip install --upgrade sphinx-autobuild` poza
  lockfile (świadomie, sphinx-autobuild jest dev-only narzędziem).
- `make enable-microsoft-auth` — `uv pip install django_microsoft_auth`
  (alternatywnie można `uv sync --extra office365` jeśli pakiet jest w
  lockfile).

**Generowanie lockfile**: `make uv-lock` lub `make uv-lock-cooldown`
(z 3-dniowym cooldownem — patrz [Cooldown](#cooldown-przed-instalacją)).

## Wheel-only policy

**Reguła**: Każda zewnętrzna zależność musi mieć prebuilt wheel — sdist
(source distribution) jest zabronione.

**Dlaczego**: sdist wykonuje `setup.py` przy instalacji — klasyczny
wektor wykonania złośliwego kodu (np. exfiltracja zmiennych środowiska,
backdoor w pre-install hook).

**Egzekwowane**: pre-commit hook `uv-lock-no-build` uruchamia
`uv lock --check --no-build` przy zmianach `pyproject.toml`/`uv.lock`.

**Co robić gdy nowa dep nie ma wheel**:

1. Znajdź alternatywę z wheel.
2. Zgłoś maintainerowi pakietu prośbę o wheel.
3. Jeśli krytyczne i bez alternatywy — udokumentuj wyjątek w komentarzu
   `[tool.uv.no-build-package]` z linkiem do issue maintainera.

## Cooldown przed instalacją

**Reguła**: Pakiety publikowane w ostatnich 3 dniach są wykluczane z
automatycznych aktualizacji.

**Dlaczego**: większość ataków supply-chain (np. LiteLLM 2.5h przed PyPI
quarantine, 119k pobrań) jest wykrywanych w pierwszych godzinach.
Cooldown 3-dniowy daje community czas na reakcję.

**Egzekwowane**:

- `.github/dependabot.yml` — `cooldown:` block dla wszystkich trzech
  ekosystemów (Python/uv, github-actions, docker).
- `make uv-lock-cooldown` — manual lock z dynamicznym cutoffem (3d default).
- **Aktualizacje security (CVE) automatycznie omijają cooldown** —
  Dependabot ma to wbudowane.

**Pakiety in-house (`*-iplweb`) zwolnione**: opublikowane przez ten sam
team co BPP (kompromis konta uderzyłby je tak czy tak), a świeże releasy
są często load-bearing.

## Eksplicytny indeks PyPI

**Reguła**: `pyproject.toml` deklaruje `[[tool.uv.index]]` z
`url = "https://pypi.org/simple"` i `default = true`.

**Dlaczego**: implicit default jest pułapką — gdy ktoś w przyszłości
doda prywatny indeks, łatwo o pomyłkę kolejności i dependency confusion
attack (atakujący publikuje pakiet o tej samej nazwie co wewnętrzny na
PyPI z wyższą wersją).

**Dodawanie prywatnego indeksu**: PRZED `[pypi]` z `explicit = true`,
żeby tylko wybrane pakiety były z niego pobierane.

## SHA-pinning GitHub Actions

**Reguła**: Każde `uses:` w `.github/workflows/*.yml` musi pinować
40-znakowy commit SHA, nie tag.

**Dlaczego**: tag-promotion attack — atakujący kompromituje konto
maintainera akcji (np. `actions/checkout`), przepina `@v6` na złośliwy
commit. Wszystkie runy używające `@v6` dostają kompromat natychmiast
(precedens: `tj-actions/changed-files` w marcu 2025).

**Egzekwowane**: pre-commit hook `zizmor` (security audyt workflowów).

**Update workflow**: Dependabot z `github-actions` ekosystemu
automatycznie podbija SHA gdy wyjdzie nowa wersja akcji (z 3-dniowym
cooldownem).

## Sekrety i `.env`

**Reguła**: Sekrety produkcyjne (hasła do bazy, klucze API, `SECRET_KEY`)
NIE są commitowane do repozytorium. `.env` jest w `.gitignore`. Dev-owe
`.env*` zawierają wyłącznie placeholders / non-prod credentials.

**Dlaczego**: złośliwy pakiet PyPI (lub backdoor w skompromitowanej
zależności) może łatwo eksfiltrować zmienne środowiska. Trzymanie
prawdziwych sekretów w plaintext `.env` zwiększa ich ekspozycję — przy
kompromisie konta deva atakujący dostaje wszystko za darmo.

### Lokalny dev

`.env.example` (committed) — szablon ze wszystkimi zmiennymi i
placeholder values. Dev kopiuje do `.env` (gitignored) i wypełnia
własnymi wartościami:

```sh
cp .env.example .env
$EDITOR .env  # wypełnij placeholderami z dev-owej DB / dev klucza Sentry / itp.
```

`.env.docker` — devowe ustawienia dla `docker compose up` (gitignored
output: `.env.local` jest preferowany dla overrideów).

**Nigdy** nie umieszczaj prawdziwych produkcyjnych sekretów w lokalnym
`.env` — nawet jeśli `.gitignore` chroni przed accidental commit, plik
jest read-able przez każdy proces deva (i każdą złośliwą dep).

### Rekomendowany pattern dla devów dotykających prawdziwych sekretów

Użyj secret managera (1Password, Infisical, Bitwarden, vault), który
przechowuje **referencje**, nie wartości:

```sh
# .env (committed jako .env.example, kopiowany do .env)
DATABASE_PASSWORD=op://Personal/bpp-prod/database/password
SENTRY_DSN=op://Personal/bpp-prod/sentry/dsn

# Uruchomienie:
op run -- uv run python src/manage.py shell
# (op CLI rozwija op:// referencje przed uruchomieniem komendy)
```

Korzyści:

1. Plaintext `.env` zawiera tylko **referencje**, nie wartości — exfil
   dostaje string `op://...`, niezdatny do uzytku bez sesji 1Password.
2. Audit trail w secret managerze (kto, kiedy, gdzie używał).
3. Rotacja sekretów = jedna zmiana w vault, nie deploymentowy ritual.

### Produkcja

`bpp-deploy` (orkiestracja produkcyjna) nie używa plików `.env` — sekrety
są wstrzykiwane jako env vars przez orkiestrator (k8s Secrets, Docker
Swarm secrets, `op run`-style injection). Nie ma plaintext sekretów na
dyskach produkcyjnych poza ramą tymczasową procesu.

### Audit `.env*` files

Przed commitem nowego `.env*.example` lub modyfikacją istniejącego:

```sh
# Sprawdz że nie ma prawdziwych sekretów (powinny być placeholders):
grep -E "(password|secret|key|token)" .env.example | \
    grep -vE "(YOUR_|placeholder|example|ZMIEN_|<your)"
# Output powinien być pusty lub same komentarze.
```

`SECRET_KEY` dla Django w `.env.docker`: `ZMIEN_KONIECZNIE_PRZED_URUCHOMIENIEM_PRODUKCJI`
(jawny placeholder z polskim ostrzeżeniem). Produkcyjny SECRET_KEY
generowany przez `bpp-deploy` przy pierwszym setupie.

### Co robić gdy sekret wycieknie

1. **Natychmiast** rotacja na zaatakowanym secret managerze / vault.
2. Audyt git history przez `trufflehog` (już mamy w pre-commit) i
   `gitleaks` żeby sprawdzić czy gdzieś indziej nie wyciekł:
   ```sh
   trufflehog git file://. --only-verified
   ```
3. Jeśli sekret był w commit history — `git filter-repo` (NIE `git rebase`)
   + force-push + invalidacja kluczy na poziomie usługi (klucz API,
   sesja, cache).
4. Wpis w `HISTORY.rst` jako security-relevant zmiana (bez ujawniania
   wartości oczywiście).

---

## Linki zewnętrzne

- [pypi-security-best-practices (źródłowy doc)](https://github.com/lirantal/pypi-security-best-practices)
- [uv docs — exclude-newer](https://docs.astral.sh/uv/reference/settings/#exclude-newer)
- [zizmor docs](https://docs.zizmor.sh/)
- [SECURITY.md (BPP vulnerability disclosure)](../SECURITY.md)
