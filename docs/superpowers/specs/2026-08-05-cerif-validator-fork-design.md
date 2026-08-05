# Spec: fork `openaire-cris-validator` z publikacją JAR-a i obrazu Dockera

Data: 2026-08-05
Autor: sesja Claude Code (na podstawie `HANDOFF-cerif-validator-fork.md`)
Status: zatwierdzony do wdrożenia

---

## 1. Problem

Żeby zweryfikować endpoint CERIF BPP (`/cerif-oai/`) walidatorem euroCRIS,
trzeba dziś mieć lokalnie JDK (380 MB) + Maven (11 MB) + cache `~/.m2`
(52 MB) + klon walidatora (89 MB) + klon `guidelines-cris-managers` (21 MB)
— razem ~550 MB narzędzi, żeby wyprodukować **4,7 MB** samowystarczalnego
JAR-a. Target `make cerif-validate` (`Makefile:369-379`) dodatkowo robi
`mvn clean package` przy **każdym** wywołaniu, czyli kasuje gotowy artefakt,
żeby zbudować identyczny.

Upstream (`EuroCRIS/openaire-cris-validator`) nie publikuje binariów:
release'y istnieją, ale **wszystkie mają zero assetów**, projektu nie ma
na Maven Central, nie ma `Dockerfile`. Jedyna droga to zbudować raz
i rozdystrybuować samodzielnie.

## 2. Cel

Fork `iplweb/openaire-cris-validator`, który przy tagu `v*` buduje JAR-a,
publikuje go jako asset release'u **oraz** jako obraz
`iplweb/cerif-validator` na Docker Hubie. BPP-owy `make cerif-validate`
przestaje wymagać Mavena — pobiera gotowy artefakt.

### Poza zakresem (świadome decyzje, nie przeoczenia)

- **GitHub Packages / Maven registry forka** — walidator uruchamiamy jako
  CLI, nie linkujemy jako zależność. Publikacja do rejestru Mavena nie ma
  dla nas wartości.
- **Automatyczna synchronizacja z upstreamem** (`repo-sync` itp.) —
  upstream wydaje release ~raz na rok. Ręczny merge przy nowym tagu
  wystarcza i jest mniej ruchomych części.
- **Zmiany w kodzie walidatora** — fork ma być czysto dystrybucyjny.

## 3. Fakty zweryfikowane pomiarem

| Ustalenie | Wartość | Skąd |
|---|---|---|
| Wymagany JDK | **17** | `pom.xml:17` — `<maven.compiler.version>17</maven.compiler.version>`, użyte w `maven-compiler-plugin` jako `<source>`/`<target>` |
| Testy upstreamu | **43, wszystkie przechodzą, wszystkie offline** | `mvn -B clean package` → `Tests run: 43, Failures: 0, Errors: 0`; fixture'y to zapisane odpowiedzi OAI-PMH w `src/test/java/.../check_*/` |
| Czas ciepłego rebuildu | 3,5 s (`-o -DskipTests`) | pomiar w sesji źródłowej |
| Rozmiar JAR-a | 4 721 874 B (~4,7 MB) | `target/openaire-cris-validator-2.1.1-SNAPSHOT-jar-with-dependencies.jar` |
| Schematy w JAR-ze | **tak** — `schemas/original/cerif_profile_1_1/**` | `unzip -l` na zbudowanym JAR-ze |
| `NOTICE` w upstreamie | **nie istnieje** (jest tylko `LICENSE`) | `ls` w klonie |
| Tag schematów | `v1.2.0` istnieje w `openaire/guidelines-cris-managers` | `git tag` w klonie |
| Wersja w `pom.xml` | `2.1.1-SNAPSHOT` (przed ostatnim tagiem `v2.1.0`) | `pom.xml:5` |

### 3.1. Krytyczne: build NIE jest reprodukowalny

`pom.xml` używa **zakresów wersji** zależności:

```xml
<version>[1.3.1,2)</version>   <!-- linia 23 -->
<version>[4.13.1,)</version>   <!-- linia 28 -->
```

Maven rozwiązuje je **w czasie builda**. Rebuild z tego samego tagu za pół
roku może wciągnąć inne wersje zależności. Konsekwencje dla designu:

1. **Asset release'u jest jedynym źródłem prawdy.** Nigdy „odtwórz artefakt
   z taga" — pobierz opublikowany plik.
2. **Obraz Dockera musi zawierać dokładnie ten sam JAR co release**, więc
   `Dockerfile` *kopiuje* artefakt z kroku Mavena, zamiast budować drugi raz.

### 3.2. Schematy muszą leżeć jako katalog-rodzeństwo, nie byle gdzie

`pom.xml:14` deklaruje `<guidelines.project.dir>../guidelines-cris-managers</guidelines.project.dir>`,
używane w liniach 162, 175, 229, 241 (m.in. `${guidelines.project.dir}/schemas/catalog.xml`).
Bez tego build pada na `That catalog does not exist`.

Property **da się** nadpisać (`-Dguidelines.project.dir=/dowolna/sciezka`)
i sam build wtedy przechodzi — ale **to nie wystarcza**. Pliki w `samples/`
są dowiązaniami symbolicznymi do `../../guidelines-cris-managers/samples/*`,
więc smoke test na `file:samples/` wymaga repo schematów pod **dokładnie tą
nazwą, jako katalogu-rodzeństwa** korzenia repo. Zweryfikowane: przy
nadpisanej property smoke test pada z
`java.io.FileNotFoundException: samples/_verb=Identify.xml`.

Dlatego CI robi to samo, co upstreamowy `maven.yml`: checkout do
`guidelines-cris-managers`, potem `mv guidelines-cris-managers ..`.
Zaspokaja to naraz symlinki i domyślną wartość property, więc żadne
`-D` nie jest potrzebne. **Nie „upraszczać" tego z powrotem do `-D`.**

## 4. Licencje

- **Walidator: Apache License 2.0.** Redystrybucja binariów wprost dozwolona.
  Warunki, które nas dotyczą: zachować `LICENSE`, dołączyć `NOTICE`
  i **zaznaczyć, że wprowadzono zmiany** (§4b — fork dokłada CI i Dockerfile,
  więc jest to „modified work").
- **`guidelines-cris-managers` nie ma pliku `LICENSE`**, ale same wytyczne są
  **CC BY 4.0** (nagłówek `schemas/openaire-cerif-profile.xsd`). Schematy
  **fizycznie trafiają do JAR-a** (potwierdzone `unzip -l`), więc atrybucja
  OpenAIRE/euroCRIS w `NOTICE` jest obowiązkowa, nie kurtuazyjna.

## 5. Architektura

### 5.1. Wersjonowanie

Schemat tagów forka: **`v2.1.1-iplweb.N`**.

- `2.1.1` — wersja z `pom.xml` upstreamu (baza forka to `main`, który jest
  przed ostatnim releasem `v2.1.0`)
- `iplweb.N` — inkrementowane przy zmianach **w samym forku** (CI, Dockerfile,
  NOTICE), bez ruchu upstreamu

Pierwszy tag: `v2.1.1-iplweb.1`.

`N` liczy się **w obrębie danej bazy upstreamu** i resetuje do 1, gdy baza
się zmienia. Tag wydajemy tylko wtedy, gdy zmienia się publikowany artefakt
albo obraz — sama poprawka w `README.md` nowego tagu nie wymaga.

**Gdy upstream wyda `v2.1.1`** i przestawi `pom.xml` na `2.1.2-SNAPSHOT`,
nasze tagi `v2.1.1-iplweb.N` zaczęłyby kłamać (wskazywałyby na kod już po
2.1.1). Procedura synchronizacji: `git fetch upstream && git merge
upstream/main`, odczytaj `pom.xml:5`, nowy tag =
`v<wersja-z-pom-bez-SNAPSHOT>-iplweb.1`, podbij `CERIF_VALIDATOR_VERSION`
w BPP.

**`pom.xml` pozostaje NIETKNIĘTY.** Nie podbijamy w nim wersji na
`2.1.1-iplweb.1`, bo każdy diff w `pom.xml` to konflikt przy każdej
synchronizacji z upstreamem. Artefakt buduje się pod nazwą
`openaire-cris-validator-2.1.1-SNAPSHOT-jar-with-dependencies.jar`,
a workflow przemianowuje go przy publikacji.

### 5.2. Pliki dodane w forku

Fork **dodaje** pliki, których upstream nie ma; jedyny plik współdzielony
to `README.md`:

| Plik | Rola |
|---|---|
| `.github/workflows/release.yml` | build + testy + release + obraz |
| `Dockerfile` | runtime na JRE, kopiuje gotowy JAR |
| `.dockerignore` | kontekst budowy = `dist/validator.jar` + `LICENSE` + `NOTICE` |
| `NOTICE` | Apache §4b + atrybucja CC BY 4.0 dla schematów |
| `README.md` (sekcja „Changes in this fork") | Apache §4b — jawna nota o modyfikacji |

Sekcja w `README.md` dopisywana na końcu, żeby minimalizować ryzyko
konfliktu przy synchronizacji.

**Upstreamowy `.github/workflows/maven.yml` zostaje nietknięty.** Odpala się
na push do `main` i na PR-y, przypina schematy do `ref: main` (niepinowane),
więc może się kiedyś zaczerwienić z powodów niezależnych od nas. Zostawiamy
go świadomie: to niezależny build check, minuty na repo publicznym są
darmowe, a każda zmiana w nim to niepotrzebny konflikt przy merge'u
upstreamu. To z niego pochodzi smoke test `java -jar … file:samples/`,
przeniesiony do `release.yml`.

### 5.3. Workflow `release.yml`

Wyzwalacze: `push: tags: ['v*']` oraz `workflow_dispatch`.
Uprawnienia: `contents: write` (tworzenie release'u).

`concurrency: release-${{ github.ref }}` z `cancel-in-progress: false` —
półopublikowane wydanie (asset jest, obrazu nie ma) jest gorsze niż
zakolejkowane.

Jeden job na `ubuntu-latest`:

1. **Ustal tag.** Wartość wchodzi do shella przez `env:`, **nigdy** przez
   bezpośrednią interpolację `${{ }}` do `run:` — inaczej spreparowany input
   `workflow_dispatch` wykonałby się jako polecenie. Druga linia obrony:
   wzorzec `^v[0-9]+\.[0-9]+\.[0-9]+(-[A-Za-z0-9][A-Za-z0-9.]*)?$`, bo ta
   sama wartość trafia potem do `actions/checkout` jako `ref:`.
   Bez tego kroku `workflow_dispatch` nie miałby skąd wziąć tagu
   (`github.ref_name` na gałęzi = `main`, a `action-gh-release` bez tagu
   kończy się błędem).
2. **Odmów nadpisania.** `gh release view "$TAG"` → jeśli istnieje, twardy
   fail. Uzasadnienie w §3.1: re-run wyprodukowałby inny artefakt pod
   opublikowanym tagiem. Poprawki dostają nowe `iplweb.N`.
3. `actions/checkout` forka na `ref: <TAG>`
4. `actions/checkout` `openaire/guidelines-cris-managers` @ `v1.2.0` →
   `path: guidelines-cris-managers`, potem `mv guidelines-cris-managers ..`
   (uzasadnienie: §3.2 — symlinki w `samples/`)
5. `actions/setup-java` — `distribution: temurin`, `java-version: 17`,
   `cache: maven` (wbudowany cache `~/.m2`; osobny `actions/cache` zbędny)
6. `mvn -B -V clean package -Dmaven.javadoc.skip=true` — **bez
   `-DskipTests`**. 43 testy są offline i przechodzą, więc są darmowym
   sanity checkiem na sensowność builda.
7. **Smoke test:** `java -jar target/…-jar-with-dependencies.jar file:samples/`
   → oczekiwane `OK (13 tests)`. Dowodzi, że złożony JAR faktycznie startuje
   i waliduje, a nie tylko że się skompilował.
8. Staging artefaktu do `dist/`: `validator.jar` (nazwa stała — dla `COPY`
   w `Dockerfile`), `openaire-cris-validator-<TAG>-jar-with-dependencies.jar`
   (nazwa z wersją — asset) oraz `<…>.sha256`. Oba JAR-y to **ta sama**
   kopia jednego builda.
9. `softprops/action-gh-release` — **jawnie wymienione** dwa pliki (asset
   + `.sha256`), nie `dist/*`; `dist/validator.jar` nie jest publikowany.
   Release idzie **przed** obrazem, żeby problem z poświadczeniami Docker
   Huba nie kosztował JAR-a.
10. `docker/setup-buildx-action` + `docker/login-action` +
    `docker/build-push-action` z **`context: .`** → `iplweb/cerif-validator:<TAG-bez-v>`
    oraz `:latest`, platformy `linux/amd64,linux/arm64`

**`context: .` jest wymagane, nie domyślne.** `docker/build-push-action` bez
niego używa kontekstu **gitowego** (pobiera repo z GitHuba), a `dist/` powstaje
dopiero w kroku 8 i jest w `.gitignore` — build padłby na
`COPY dist/validator.jar: not found`.

Multi-arch jest tani, bo obraz nic nie kompiluje — to JRE + `COPY`.

Akcje trzecich stron (`softprops/*`, `docker/*`) przypięte do SHA. Repo
publikuje binarium uruchamiane u odbiorców; przejęty ruchomy tag akcji
oznaczałby podmieniony artefakt. `actions/*` zostają na tagach głównych,
zgodnie z konwencją `iplweb/bpp`.

**Poświadczenia Docker Huba:** `vars.DOCKER_USER` (zmienna) +
`secrets.DOCKER_PAT` (sekret) — te same nazwy, co w `iplweb/bpp`. Zmienna
jest ustawiona; sekret trzeba dodać temu repo osobno (nie da się go odczytać
z innego repo).

### 5.4. `Dockerfile`

```dockerfile
FROM eclipse-temurin:17-jre
LABEL org.opencontainers.image.* ...
COPY LICENSE NOTICE /opt/
COPY dist/validator.jar /opt/validator.jar
WORKDIR /work
ENTRYPOINT ["java", "-jar", "/opt/validator.jar"]
```

Świadomie **nie** multi-stage: build ma się zdarzyć raz, w kroku 6 workflow.
Drugi przebieg Mavena wewnątrz obrazu mógłby — przez zakresy wersji z §3.1 —
dać inny artefakt niż ten w release'ie.

`COPY` używa stałej nazwy `dist/validator.jar` zamiast glob-a
`target/*-jar-with-dependencies.jar`, bo `COPY` z wildcardem do ścieżki
nie-katalogowej jest kruchy (w `target/` leżą dwa JAR-y).

**`LICENSE` i `NOTICE` jadą razem z binarium**, bo obraz jest redystrybucją
w rozumieniu Apache-2.0 §4. Sam JAR ma `META-INF/NOTICE`, ale to zmerdżowane
NOTICE **zależności** — nie ma tam ani noty o modyfikacji, ani atrybucji
CC BY 4.0 dla schematów, które fizycznie są w obrazie.

**`WORKDIR /work`**, bo walidator zapisuje pobrane odpowiedzi OAI-PMH do
**względnego** katalogu `data/` (`CRISValidator.java`:
`new FileLoggingConnectionStreamFactory("data")`). Bez `WORKDIR` trafiałoby
to do `/` i ginęło po `--rm`, czyli ścieżka dockerowa po cichu gubiłaby
materiał diagnostyczny, który ścieżka javowa zostawia w katalogu roboczym.

**`Dockerfile` nie może zawierać `RUN`.** Multi-arch działa bez
`docker/setup-qemu-action` wyłącznie dlatego, że sam `FROM` + `COPY` +
`WORKDIR` nie wykonuje kodu. Pierwsze `RUN apt-get …` da `exec format error`
na obcej architekturze.

`.dockerignore` (negacja zweryfikowana empirycznie — BuildKit schodzi do
wykluczonego katalogu, gdy istnieją wyjątki):

```
*
!dist/validator.jar
!LICENSE
!NOTICE
```

### 5.5. Zmiana w `iplweb/bpp`

Osobny, mały PR. `Makefile:358-379` zastąpione w całości — **łącznie
z blokiem komentarza**, który dziś mówi „wymaga JVM, Mavena i DZIAŁAJĄCEGO
endpointu" i po zmianie kłamałby dokładnie w tym, czego dotyczy PR.

Zmienne:

```make
CERIF_VALIDATOR_VERSION ?= v2.1.1-iplweb.1
CERIF_VALIDATOR_CACHE   ?= $(HOME)/.cache/bpp/cerif-validator
CERIF_VALIDATOR_IMAGE   ?= iplweb/cerif-validator
CERIF_VALIDATOR_SHA256  ?=
```

Cache **poza drzewem repo**: `make clean` zależy od `clean-pycache`, który
robi `rm -rf .cache` (`Makefile:206-209`), więc artefakt znikałby przy każdym
sprzątaniu. W `$(HOME)` przeżywa `clean` i jest współdzielony między worktree
— na tym hoście zwykle biega ich kilka naraz.

Nazwa pliku w cache **zawiera wersję**, więc podbicie
`CERIF_VALIDATOR_VERSION` wymusza pobranie; stały `validator.jar`
w nieskończoność serwowałby starą wersję.

Logika targetu `cerif-validate`:

1. Brak `URL=` → komunikat z przykładem, `exit 1` (zachowanie jak dziś)
2. JAR-a nie ma w cache → `curl -fL --retry 3 --proto '=https' --tlsv1.2`
   do pliku tymczasowego, weryfikacja SHA-256, potem `mv` na docelowy
   (atomowo — przerwany download nie zostawia uszkodzonego cache'u).
   Błąd `curl` → komunikat z wersją, URL-em i linkiem do listy wydań.
3. Jest `java` **w wersji ≥ 17** → `java -jar <cache>/… "$(URL)"`
4. Brak javy albo za stara, jest `docker` → `docker run --rm` z obrazem
   `iplweb/cerif-validator:<wersja-bez-v>`
5. Nie ma ani `java`, ani `docker` → błąd z konkretnymi poleceniami
   instalacji (`brew install openjdk@17`, `brew install --cask docker`,
   `apt install openjdk-17-jre`)

Znika: `mvn`, `git clone`, `mvn clean`, zmienna `CERIF_VALIDATOR_DIR`.

#### Wersja javy, nie sama jej obecność

JAR ma target 17. Na JRE 8/11 (wciąż typowe na macOS i w korporacyjnych
Linuksach) `java -jar` wywala `UnsupportedClassVersionError` — komunikat,
którego odbiorca nie zmapuje na „zainstaluj nowszą Javę". Target parsuje
`java -version`; za stara albo niedziałająca java (macOS-owy stub w
`/usr/bin/java`) jest traktowana jak jej brak i spada na Dockera.

#### Weryfikacja integralności

Suma pobierana z tego samego release'u co JAR **nie jest kotwicą zaufania**
— łapie obcięty transfer i przypadkowo podmieniony asset, nie skompromitowane
wydanie. Realnym gatem jest `CERIF_VALIDATOR_SHA256` przypięte w gicie
(przechodzi przez code review); gdy ustawione, ma pierwszeństwo. Do
uzupełnienia po opublikowaniu pierwszego release'u.

Ma to znaczenie właśnie dlatego, że §3.1 wyklucza odtworzenie artefaktu:
sumy nie da się zweryfikować przez rebuild, więc musi być zapisana.

#### Pułapka: `docker run` + adres lokalny

Kontener ma własny network namespace, więc lokalny endpoint jest z niego
niedostępny. Detekcja **nie może** opierać się na samym `localhost`:
`run-site` binduje się na **nazwę hosta** (`mac-mini`), więc typowy lokalny
przepływ nie zawiera wcale słowa „localhost" — dokładnie ten przypadek
umknąłby heurystyce. Target wyciąga host z URL-a i porównuje z:
`localhost`, `127.0.0.1`, `0.0.0.0`, `::1`, `$(hostname)`, `$(hostname -s)`.

Przy trafieniu: `--add-host=host.docker.internal:host-gateway` i podmiana
hosta w URL-u, plus ostrzeżenie o dwóch warunkach, bez których i tak nie
zadziała:

- **`ALLOWED_HOSTS`** — kontener wyśle `Host: host.docker.internal`, a Django
  odrzuci to `DisallowedHost` (HTTP 400). Walidator zobaczy 400 zamiast
  OAI-PMH i wypluje mylący błąd protokołu.
- **bind na Linuksie** — `host-gateway` mapuje na IP bridge'a (`172.17.0.1`),
  więc serwer słuchający tylko na `127.0.0.1` odrzuci połączenie mimo
  poprawnego DNS-u. Na Docker Desktop (macOS) ruch idzie przez VM i działa
  niezależnie od bindu — stąd klasyczne „u mnie działa".

Katalog `data/` z kontenera montowany do cache'u, żeby ścieżka dockerowa
zostawiała ten sam materiał diagnostyczny, co javowa (patrz §5.4).

#### Dokumentacja i newsfragment

- `src/bpp/newsfragments/cerif-validator-artefakt.doc.rst`
- `docs/deweloper/eurocris-co-jeszcze.md:116` — wymienia `make cerif-validate`
  w kroku rejestracyjnym; dopisać, że wymaga JRE 17+ **albo** Dockera

## 6. Kolejność wdrożenia

1. ✅ **Fork** — `gh repo fork EuroCRIS/openaire-cris-validator --org iplweb
   --clone=false`, potem osobny `git clone` po SSH do
   `~/Programowanie/openaire-cris-validator-iplweb`. Osobny klon, bo
   `gh repo fork --clone` nie przyjmuje ścieżki docelowej — sklonowałby do
   `./openaire-cris-validator` i zderzył się z istniejącym klonem upstreamu.
2. ✅ **`NOTICE` + sekcja w `README.md`** — commit, push
3. ✅ **`Dockerfile` + `.dockerignore`** — commit, push
4. ✅ **`.github/workflows/release.yml`** — commit, push. Hipoteza o SSH
   potwierdzona (§7)
5. ✅ **Merge do `main`** — workflow rejestruje się dopiero z gałęzi
   domyślnej; oba workflow mają stan `active` (nie `disabled_fork`)
6. ⏳ **Sekret `DOCKER_PAT`** w repo forka — wymaga człowieka, wartości
   sekretu nie da się odczytać z `iplweb/bpp`. Zmienna `DOCKER_USER`
   ustawiona.
7. ⏳ **Tag `v2.1.1-iplweb.1`** + push → workflow buduje i publikuje.
   **Dopiero po kroku 6** — release powstaje przed logowaniem do Docker
   Huba, więc przy braku sekretu zostałby opublikowany JAR bez obrazu,
   a blokada z §5.3 krok 2 uniemożliwiłaby poprawkę bez podbicia `iplweb.N`.
8. ⏳ **Weryfikacja artefaktów** — pobrany JAR i obraz dają ten sam wynik;
   uzupełnić `CERIF_VALIDATOR_SHA256` w BPP
9. ⏳ **PR do `iplweb/bpp`** — `Makefile` + newsfragment + `eurocris-co-jeszcze.md`

## 7. Scope `workflow` tokena `gh` — hipoteza POTWIERDZONA

Token `gh` na hoście `mac-mini` ma scope'y `admin:public_key`, `gist`,
`read:org`, `repo` — **bez `workflow`** (zweryfikowane przez
`gh api -i user` → `X-Oauth-Scopes`, nie tylko przez odczyt konfiguracji).

Handoff zakładał, że to twardy blocker. **Nie jest** — zweryfikowane
empirycznie w kroku 4: commit z `.github/workflows/release.yml` przeszedł
po SSH bez odświeżania tokena.

Mechanizm: ograniczenie „refusing to allow an OAuth App to create or update
workflow" jest przypięte do **uwierzytelnienia tokenem** (Contents API oraz
push po HTTPS z `gho_*`/PAT). Push po SSH uwierzytelnia się kluczem, żaden
token OAuth nie bierze udziału, więc nie ma czego sprawdzać pod kątem
scope'ów.

⚠️ **Pułapka przy weryfikacji:** `gh config get git_protocol` (bez `--host`)
zwraca `https`, a `gh config get git_protocol --host github.com` zwraca `ssh`
— i to ta druga wartość obowiązuje. Kto sprawdzi tę pierwszą, wyciągnie
odwrotny wniosek. Twardy warunek jest inny i deterministyczny: po klonie
`git remote get-url origin` musi zwracać `git@github.com:…`. Jeśli zwraca
`https://` — `git remote set-url origin git@github.com:iplweb/openaire-cris-validator.git`
przed pushem workflow.

Gdyby mimo wszystko odbiło: `gh auth refresh -s workflow` **na tym hoście**
(interaktywne, otwiera przeglądarkę).

## 8. Kryteria akceptacji

1. Release `v2.1.1-iplweb.1` w `iplweb/openaire-cris-validator` ma dwa assety:
   `openaire-cris-validator-v2.1.1-iplweb.1-jar-with-dependencies.jar`
   (~4,7 MB) oraz `<…>.sha256`
2. `docker run --rm iplweb/cerif-validator:2.1.1-iplweb.1 <URL>` uruchamia
   walidację i kończy się kodem 0. **Wywołanie bez argumentu kończy się
   kodem niezerowym, nie komunikatem usage** — `CRISValidator.main()` robi
   `args.length > 0 ? args[0] : null`, a potem bezwarunkowo
   `URI.create(...)`, więc leci `NullPointerException`. Usage istnieje tylko
   w konstruktorze, do którego `main` nigdy nie dochodzi. Zmiana tego
   wymagałaby patcha w kodzie walidatora, co §2 wyklucza.
3. Workflow przechodzi z **43 testami** (nie `-DskipTests`) **i** smoke
   testem `file:samples/` → `OK (13 tests)`
4. `docker run --rm --entrypoint ls iplweb/cerif-validator:… /opt` pokazuje
   `LICENSE` i `NOTICE`
5. Obraz zawiera JAR o **tym samym SHA-256**, co asset release'u
6. `make cerif-validate URL=…` działa na maszynie **bez Mavena**
7. `make cerif-validate URL=…` na maszynie **bez `java` w PATH** kończy się
   tym samym wynikiem, przez ścieżkę dockerową
8. Wynik walidacji tego samego endpointu przez stary tor (`mvn`) i nowy
   (pobrany asset) jest **identyczny** — sprawdzalne, dopóki Maven jest
   jeszcze na hoście
9. `NOTICE` zawiera notę o modyfikacji (Apache §4b) i atrybucję CC BY 4.0
   dla schematów

## 9. Weryfikacja końcowa

```bash
# .dump, NIE .pg_dump — run-site rozpoznaje .sql/.sql.gz/.dump, a obok
# leży identyczny plik (ten sam rozmiar) z akceptowanym rozszerzeniem
uv run run-site run --from-dump /Volumes/SSD/db-backup-20260428-093811.dump \
    --no-browser --no-celery
# adres z bannera "run-site is running" — run-site bindował się na hostname
# (mac-mini), NIE na localhost; nie bierz portu z .dev_helpers_port w oderwaniu
make cerif-validate URL=http://<host>:<port>/cerif-oai/
```

Oczekiwane: `OK (13 tests)`. Powtórzyć z wymuszoną ścieżką dockerową
(np. tymczasowo ukrywając `java` w `PATH`), żeby sprawdzić oba warianty.
