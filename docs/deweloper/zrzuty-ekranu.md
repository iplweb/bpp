# Zrzuty ekranu do dokumentacji i bazy wiedzy

Zrzuty z oznaczeniami (ramki, strzałki, podpisy) do instrukcji w `docs/`
i do artykułów bazy wiedzy Freshdesk robi skrypt
`bin/docs-screenshots.py`. Zrzutów **nie robimy ręcznie** — skrypt odtwarza
je jednym poleceniem, więc po zmianie interfejsu wystarczy go uruchomić
ponownie.

## Gdzie co leży

| Co | Gdzie |
|---|---|
| Pliki PNG | `docs/images/<sekcja>/<scenariusz>/NN-opis.png`, np. `docs/images/uzytkownik/moj-profil-autora/01-menu-konto.png` |
| Scenariusze (co klikamy, co oznaczamy) | funkcje w `bin/docs-screenshots.py`, słownik `SCENARIOS` |
| Publiczny adres obrazka | `https://iplweb.github.io/bpp/images/<sekcja>/<scenariusz>/NN-opis.png` |

Obrazki są **jedno źródło** dla dokumentacji i bazy wiedzy: strona w
`docs/` osadza je ścieżką względną, a artykuł we Freshdesku linkuje ten sam
plik z GitHub Pages (`<img src="https://iplweb.github.io/bpp/images/…">`).

!!! warning "Nie przenoś i nie zmieniaj nazw plików bez sprawdzenia Freshdesku"
    Artykuły bazy wiedzy linkują obrazki po pełnym adresie. Po zmianie
    ścieżki obrazek w artykule **po cichu przestaje się wyświetlać**.
    Nowa wersja zrzutu = nadpisanie pliku pod tą samą nazwą.

## Reguły

**Dane.** Wyłącznie dane demo (`create_demo_data`), nigdy zrzut bazy
klienta — na obrazku nie może się znaleźć prawdziwe nazwisko, uczelnia ani
adres. Domyślnie motyw **Wiedźmin** (`--motyw wiedzmin`) z flagą
**`--bez-prefiksu`** — bez niej nazwy mają przedrostek „Demo —”, który na
zrzucie wygląda jak błąd.

**Konto.** Zrzuty z punktu widzenia użytkownika robimy na **zwykłym**
koncie demo `yennefer` (bez `is_staff`/`is_superuser`), powiązanym z
autorem. Konto admina pokazuje pozycje menu, których zwykły użytkownik nie
ma (np. „zaloguj jako inny użytkownik”). Zrzuty dla redaktora/administratora
— na koncie z odpowiednią grupą, nie na superuserze, chyba że opisujemy
funkcję wyłącznie dla superusera.

**Przeglądarka.** Okno 1280×800, `device_scale_factor=2` (ostre na
ekranach HiDPI), język polski. Pełny Chromium (`channel="chromium"`), nie
„headless shell” — tylko on respektuje `--lang=pl`, inaczej natywne
kontrolki mówią „Choose File” zamiast „Wybierz plik”. Baner ciasteczek
zamykamy przed zrzutem.

**Oznaczenia** — jeden styl na wszystkich zrzutach:

- kolor `#e8173c`; ramka 4 px z zaokrągleniem wokół elementu,
- zakrzywiona strzałka 5 px z grotem, **z cieniem**,
- podpis pogrubiony, w **białej ramce z cieniem** — czytelny na każdym tle,
- kroki numerujemy w podpisach („1. konto”, „2. mój profil”), gdy kolejność
  ma znaczenie,
- oznaczenia są rysowane **w stronie** (nakładka SVG) i przypięte do
  selektorów CSS elementów — nie do współrzędnych. Po zmianie układu strony
  same trafiają we właściwe miejsce,
- podpis nie może zasłaniać tekstu ani innej ramki. Kierunek strzałki
  (`arrow`: `left`/`right`/`above`/`below`) i przesunięcie podpisu
  (`dx`/`dy`) dobieramy tak, żeby podpis stał w pustym miejscu.

**Adresy.** Na zrzutach nie może być `localhost:PORT`. Skrypt podstawia
lokalny BPP pod adres `https://bpp.twoja-uczelnia.pl` (`PUBLIC_BPP`,
funkcja `proxy_public_bpp`) wszędzie tam, gdzie adres serwera widać na
ekranie — np. w kodzie do wklejenia.

**Strona „u klienta”.** Gdy trzeba pokazać efekt na zewnętrznej stronie
(np. widget publikacji), używamy wymyślonej strony z motywu demo
(`EXAMPLE_PAGE` w skrypcie, adres `https://katedra.example`), nigdy strony
prawdziwej uczelni.

**Element daleko na stronie.** Gdy klikany element jest np. na samym dole
długiej strony, sam wycinek nie mówi, *gdzie* go szukać. Robimy wtedy jeden
obrazek z dwóch kadrów — góra strony (żeby było wiadomo, jaka to strona),
„rozdarcie” z podpisem (np. „przewiń na sam dół strony”), potem fragment
z oznaczonym elementem. Służy do tego funkcja `stitch()` w skrypcie.

**Kadr.** Tylko fragment, o którym mowa w tekście (`clip=`), chyba że zrzut
pokazuje cały formularz. Każdy zrzut **obejrzyj** po wygenerowaniu —
nakładające się podpisy i niedokończone animacje (rozwijane menu) widać
dopiero na obrazku.

## Artykuły w bazie wiedzy (Freshdesk)

Artykuł we Freshdesku to **zajawka** strony z `docs/`, nie jej kopia. Widżet
pomocy wyświetla go w małym okienku, więc:

- początek instrukcji — **gdzie kliknąć**, **skąd skopiować** — do
  pierwszego istotnego momentu; resztę zostawiamy dokumentacji,
- obrazki te same co w `docs/` (adres z GitHub Pages), w krokach, których
  dotyczą; każdy owinięty w `<a href="…png" target="_blank" rel="noopener">`,
  żeby klik otwierał pełny rozmiar w nowym oknie,
- **bez uwag technicznych** — parametrów, klas CSS, stylów, szczegółów
  konfiguracji; te zostają w `docs/`,
- na końcu, pogrubiony, zawsze ten sam odnośnik do strony w dokumentacji
  (`target="_blank"`): **„Ciąg dalszy w dokumentacji systemu. Kliknij
  tutaj”**,
- bez emoji — Freshdesk zamienia je na „?”,
- przy zapisie przez API zawsze `status: 2` (inaczej zmiana zostaje
  szkicem), a potem sprawdzenie na publicznym portalu.

## Jak wygenerować

1. Postaw stack i bazę demo (szczegóły: [Dane demo](dane-demo.md)):

    ```bash
    uv run run-site run --no-browser --no-celery    # w tle; port z bannera
    source .run-site-env.sh
    export DJANGO_BPP_SKIP_DOTENV=1 DJANGO_BPP_DB_HOST=localhost \
           DJANGO_BPP_DB_PORT=$PGPORT DJANGO_BPP_DB_NAME=bpp \
           DJANGO_BPP_DB_USER=bpp DJANGO_BPP_DB_PASSWORD=password
    uv run python src/manage.py seed_default_dyscypliny
    uv run python src/manage.py create_demo_data --motyw wiedzmin --bez-prefiksu \
        --wydzialow 4 --jednostek-na-wydzial 3 --autorow 120 \
        --ile-ciaglych 600 --ile-zwartych 300 --zrodel 20 --wydawcow 8 \
        --seed 42 --yes-i-am-sure --confirm-db bpp
    uv run python src/manage.py denorm_flush
    ```

    `.run-site-env.sh` eksportuje tylko `DATABASE_URL`/`PG*`, a ustawienia
    BPP czytają `DJANGO_BPP_DB_*` — stąd drugi `export`.

2. Załóż konto demo powiązane z autorem:

    ```bash
    uv run python src/manage.py shell -c "
    from bpp.models import Autor, BppUser
    from password_policies.models import PasswordHistory
    a = Autor.objects.filter(imiona='Yennefer', nazwisko='Merigold').first()
    u, _ = BppUser.objects.get_or_create(username='yennefer', defaults=dict(
        email='yennefer@example.com', first_name='Yennefer', last_name='z Vengerbergu'))
    u.set_password('yennefer'); u.autor = a; u.save()
    PasswordHistory.objects.create(user=u, password=u.password)
    "
    ```

    Hasło = login (`yennefer`) — to lokalna baza demo, a hasło o wyglądzie
    „prawdziwego” zatrzymuje PR na skanerze sekretów (GitGuardian).
    Wpis w `PasswordHistory` jest potrzebny, inaczej polityka haseł
    przekierowuje świeże konto na zmianę hasła i zrzut pokazuje zły ekran.

    Dwa kolejne konta tak samo (hasło = login, wpis w `PasswordHistory`):
    **`jaskier`** — bez powiązanego autora (zrzut „Brak powiązania
    z autorem”), **`filippa`** — w grupie **„generowanie raportów”**
    (menu raporty/ewaluacja, raporty slotów).

3. Sloty. Generator danych demo nie wpisuje dyscyplin przy autorach prac,
   więc raporty slotów byłyby puste. Uzupełnia to skrypt:

    ```bash
    uv run python src/manage.py shell < bin/docs-demo-sloty.py
    uv run python src/manage.py denorm_flush
    ```

4. Gotową bazę warto zrzucić (`pg_dump -Fc`) i następnym razem startować z
   niej: `uv run run-site run --from-dump <plik>` — kroki 1–3 odpadają.

5. Raz na maszynie: `uv run playwright install chromium`.
   Scenariusze, które przechodzą na stronę dokumentacji (np.
   `widget-publikacji` — generator kodu mieszka na GitHub Pages), wymagają
   zbudowanej dokumentacji: `mkdocs build` (katalog `site/`). Skrypt podstawia
   ją pod adres `https://iplweb.github.io/bpp/`, bo z prawdziwej strony HTTPS
   przeglądarka nie pozwoliłaby wczytać widgetu z lokalnego BPP po `http`.

6. Wygeneruj i obejrzyj:

    ```bash
    uv run python bin/docs-screenshots.py --list
    uv run python bin/docs-screenshots.py --base http://localhost:PORT moj-profil-autora
    ```

## Nowy scenariusz

Dopisz funkcję `def nazwa(page, base, out)` w `bin/docs-screenshots.py`
(wzór: `moj_profil_autora`) i wpis w `SCENARIOS`. W funkcji: przejdź na
stronę, poczekaj na `networkidle` (i na koniec animacji, jeśli coś się
rozwija), wywołaj `mark(page, [...])`, zrób `page.screenshot(...)`.
Następnie osadź obrazki na stronie w `docs/` i — jeśli jest artykuł
w bazie wiedzy — podlinkuj je tam adresem z GitHub Pages **po** opublikowaniu
dokumentacji (budowa po pushu do `dev`).
