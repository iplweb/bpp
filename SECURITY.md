# Polityka bezpieczeństwa BPP

*Security Policy — see English section below.*

## Wspierane wersje

Aktywnie wspierana jest najnowsza wersja z serii kalendarzowej (obecnie
`202604.x`). Łaty bezpieczeństwa wydawane są wyłącznie dla wersji aktualnie
oznaczonej jako `latest` na Docker Hub (`iplweb/bpp_appserver:latest`).

| Wersja            | Wsparcie bezpieczeństwa |
| ----------------- | ----------------------- |
| `202604.x` (latest) | Tak                   |
| starsze            | Nie — proszę zaktualizować |

## Zgłaszanie luk bezpieczeństwa

**Nie otwieraj publicznego issue ani PR-a dla luk bezpieczeństwa.** Publiczne
ujawnienie przed wydaniem łaty naraża wszystkie produkcyjne instancje BPP.

Preferowany kanał zgłoszenia (oba są prywatne):

1. **GitHub Security Advisory** — przejdź do
   [zakładki Security tego repozytorium](https://github.com/iplweb/bpp/security/advisories/new)
   i wybierz „Report a vulnerability". To najszybsza ścieżka — utrzymanie
   dostaje powiadomienie natychmiast.
2. **E-mail** — `security@iplweb.pl` (jeśli nie masz konta GitHub lub
   wolisz e-mail).

W zgłoszeniu opisz proszę:

- krok-po-kroku reprodukcję,
- wpływ (co atakujący może zrobić),
- wersję BPP (`docker image inspect` lub strona `/admin/`),
- ewentualny PoC / log / screenshot.

## SLA

| Etap                  | Czas docelowy                    |
| --------------------- | -------------------------------- |
| Potwierdzenie odbioru | 3 dni robocze                    |
| Wstępna ocena (triage)| 7 dni roboczych                  |
| Łata: krytyczne       | 14 dni od potwierdzenia          |
| Łata: wysokie         | 30 dni                           |
| Łata: średnie/niskie  | następne planowane wydanie       |

Zgłaszający otrzyma podziękowanie w wpisie do `HISTORY.md` i (na życzenie) w
opublikowanym Security Advisory, po wydaniu łaty.

## Poza zakresem

Następujące rzeczy **nie są** uznawane za luki bezpieczeństwa:

- Dane testowe i fixture'y w katalogach `src/*/tests/` — to świadomie
  publiczne dane.
- Aplikacja `test_bpp` — pozostawiona w produkcji wyłącznie dla starszych
  referencji `ContentType` (zob. `CLAUDE.md`).
- Domyślne hasła w `docker-compose.yml` — przeznaczony tylko do dewelopmentu;
  produkcyjny deployment przez `bpp-deploy` używa wstrzykniętych sekretów.
- Brak rate-limitingu na publicznych endpointach raportowych — celowo,
  obciążenie reguluje warstwa nginx/cdn deploymentu.
- Self-XSS wymagający dostępu do panelu admina — Django admin zakłada
  zaufaną rolę.

## Hardening podczas korzystania

Kilka rzeczy, których oczekujemy od deploymentu (nie są to luki BPP, ale
wpływają na bezpieczeństwo):

- **HTTPS** wymuszone na warstwie reverse-proxy (nginx/traefik).
- **`SECRET_KEY`** unikalny per instancja, trzymany poza repozytorium.
- **Backupy bazy** szyfrowane i regularnie testowane na restore.
- **PostgreSQL/Redis** dostępne wyłącznie z sieci wewnętrznej.
- Aktualizacje obrazów Docker w cyklu zgodnym z polityką organizacji
  (zob. `iplweb/bpp_appserver:latest` — Trivy gate na CRITICAL CVE).

---

# Security Policy (English)

## Supported Versions

Only the latest calendar release (`202604.x` series, tagged `latest` on
Docker Hub as `iplweb/bpp_appserver:latest`) receives security patches.

## Reporting a Vulnerability

**Do not open a public issue or PR for security vulnerabilities.** Use one of
these private channels:

1. **GitHub Security Advisory** — preferred. Go to
   [Security tab](https://github.com/iplweb/bpp/security/advisories/new) →
   "Report a vulnerability".
2. **Email** — `security@iplweb.pl`.

Please include reproduction steps, impact, BPP version, and any PoC/logs.

## SLA

- Acknowledgement: within 3 business days.
- Triage: within 7 business days.
- Patch: critical 14d, high 30d, medium/low next scheduled release.

Reporters are credited in `HISTORY.md` and (on request) in the published
Security Advisory.
