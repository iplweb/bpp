# Security Practices — BPP

Dokument zbiera praktyki bezpieczeństwa stosowane w BPP, oparte na
[lirantal/pypi-security-best-practices](https://github.com/lirantal/pypi-security-best-practices).

Polityka zgłaszania luk bezpieczeństwa: [SECURITY.md](SECURITY.md).

## Spis treści

- [Deterministyczne instalacje (`--frozen`)](#deterministyczne-instalacje---frozen)
- [Wheel-only policy](#wheel-only-policy)
- [Cooldown przed instalacją](#cooldown-przed-instalacją)
- [Eksplicytny indeks PyPI](#eksplicytny-indeks-pypi)
- [SHA-pinning GitHub Actions](#sha-pinning-github-actions)

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

---

## Linki zewnętrzne

- [pypi-security-best-practices (źródłowy doc)](https://github.com/lirantal/pypi-security-best-practices)
- [uv docs — exclude-newer](https://docs.astral.sh/uv/reference/settings/#exclude-newer)
- [zizmor docs](https://docs.zizmor.sh/)
- [SECURITY.md (BPP vulnerability disclosure)](SECURITY.md)
