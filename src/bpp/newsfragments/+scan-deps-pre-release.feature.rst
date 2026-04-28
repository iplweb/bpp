Pipeline release-u (``make new-release`` oraz ``make release``)
weryfikuje teraz zaleznosci pod katem znanych CVE PRZED zbumpieniem
wersji i wystartowaniem builda. Nowy target ``make scan-deps``
generuje SBOM (CycloneDX) z ``uv.lock`` przez ``uv export --no-dev``
i puszcza go przez OSV-Scanner, Grype oraz Trivy. Jezeli ktorykolwiek
skaner znajdzie HIGH/CRITICAL CVE, ``make`` zatrzyma sie z exit 1 i
release nie ruszy — zeby pominac (na wlasna odpowiedzialnosc), uzyj
``./bin/scan-deps.sh --no-gate``. Wymagane narzedzia: ``brew install
osv-scanner grype trivy``.

Workflow ``dependency-audit.yml`` rozszerzony o drugi job
``multi-scanner``, ktory na CI generuje ten sam SBOM i odpala te
same trzy skanery jako defense-in-depth obok istniejacego gate-u
``uv-secure``. Nowe skanery sa report-only (zapisuja markdown do
``GITHUB_STEP_SUMMARY``, nie blokuja merga) — chodzi o widocznosc
findings, ktorych nie wykryla baza ``uv-secure``, bez ryzyka
zablokowania PR-a falszywym pozytywem z innej bazy CVE.
