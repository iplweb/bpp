# Konfigurator wyglądu

Konfigurator wyglądu pozwala ustawić wygląd stron BPP: kolory, czcionkę,
wygląd menu i przycisków. Każdą zmianę od razu widać na podglądzie
prawdziwych stron tej bazy. Gdy wygląd odpowiada, przycisk **Zastosuj**
włącza go dla wszystkich odwiedzających, bez udziału IPLweb i bez
aktualizacji systemu.

## Gdzie go znaleźć

Konfigurator jest pod adresem `/bpp/konfigurator-wygladu/`. Linki do niego:

- na stronie: menu **redagowanie** → **Konfigurator wyglądu**,
- w module redagowania: zakładka **WWW** → **Konfigurator wyglądu**, a także
  **Uczelnia** → pole **Motyw kolorystyczny**.

Kto ma dostęp:

- Oglądać, próbować i **zapisywać** ustawienia mogą superużytkownicy oraz
  użytkownicy z dostępem do modułu redagowania w grupie **web** albo
  **administracja**. Pozostali nie widzą linków, a adres konfiguratora
  zwraca im „brak dostępu”.
- **Zastosować** wygląd (włączyć go na stronie) może tylko superużytkownik.

Ustawienia są pogrupowane w sekcje, które można zwijać i rozwijać.

## Punkt wyjścia: gotowe motywy

Lista **„Zacznij od gotowego motywu”** wczytuje ustawienia domyślne albo
odpowiednik jednego z dotychczasowych motywów BPP (niebieski, zielony,
pomarańczowy, VIZJA, MWSL, czerwono-błękitny) — potem można je dowolnie
zmieniać. Część dotychczasowych motywów ma kolor główny za jasny dla
wymogów dostępności; konfigurator zaznaczy to od razu i zaproponuje
najbliższy czytelny odcień.

## Co można ustawić

| Grupa | Ustawienie |
|-------|------------|
| Kolory | kolor paska menu, kolor główny (przyciski, linki), kolor dodatkowy, tło strony (białe albo jasnoszare) |
| Tekst | czcionka tekstu i osobno czcionka nagłówków, wielkość tekstu, nagłówki zwykłe albo pogrubione |
| Menu | ikony w menu (tak/nie), zaokrąglone rozwijane menu (tak/nie), cień pod paskiem menu, logo BPP (szare, pomarańczowe, w kolorze napisów paska albo ukryte) |
| Kształt | rogi przycisków, pól i kart: kanciaste, lekko albo mocno zaokrąglone, przyciski okrągłe („pigułki”) |
| Przyciski | styl: pełne płaskie, z obrysem, pełne z cieniem; kolory: wszystkie w kolorze głównym albo każdy rodzaj (potwierdzenie, ostrzeżenie, usuwanie) w wybranym kolorze |
| Komunikaty | kolory komunikatów: informacja, sukces, ostrzeżenie, błąd (jasne tło i czytelny tekst wyliczają się same) |
| Strona główna i wykresy | kafle „Przeglądaj bazę publikacji” (jasne z kolorowymi ikonami, z ikonami w kolorze głównym, z obrysem albo wypełnione kolorem głównym); kolor wykresów „w latach” na stronach autorów, jednostek i źródeł (domyślnie kolor główny) |
| Okruszki i stopka | pasek ścieżki pod menu i stopka: jak dotąd, w kolorze paska menu albo w wybranym kolorze (tekst i linki dobierają się same) |
| Menu — logo i napis | logo BPP (szare, pomarańczowe, w kolorze napisów, ukryte), napis „BPP”, własny skrót albo bez napisu, małe logo uczelni |
| Grafika w tle | obrazek (PNG, JPG, WebP, SVG) w wybranym rogu, na górze, na dole, na środku, powtarzany albo na cały ekran; wielkość i widoczność |
| Przycisk dostępności (UserWay) | kolor okrągłego przycisku (domyślnie jak kolor główny) i jego cień |

### Czcionki

- **Lokalne** (systemowa, Inter, Lato, Open Sans, Roboto, Source Sans Pro) są
  zapisane na serwerze BPP i nie wymagają łączenia się z zewnętrznymi
  serwisami.
- **Z internetu**: ok. 30 popularnych czcionek z polskimi znakami (np.
  Montserrat, Lora, Merriweather, Playfair Display, Roboto Slab), a także
  dowolna czcionka z Google Fonts po wpisaniu jej nazwy. Domyślnie są
  pobierane z **Bunny Fonts**, czyli europejskiej kopii Google Fonts, która
  nie zbiera danych odwiedzających. To zalecany wybór ze względu na RODO.
  Można też przełączyć źródło na Google Fonts.

Przy czcionce wpisanej ręcznie sprawdź na podglądzie polskie znaki: nie
każda czcionka z Google Fonts je ma.

### Grafika w tle

Obrazek: PNG, JPG, WebP, GIF albo SVG, do 10 MB i do 10 000 px na bok. Duże
zdjęcia konfigurator sam zmniejsza (do 1200 px). Najlepiej sprawdzają się ornamenty
i logo z przezroczystym tłem, ustawione w rogu z widocznością „słaba” albo
„ledwo widoczna”, żeby nie przeszkadzały w czytaniu. Grafika nie jest
drukowana.

### Czytelność jest pilnowana automatycznie

- Kolor napisów na pasku menu i na przyciskach dobiera się sam: biały albo
  czarny, zależnie od tego, który jest lepiej widoczny.
- Za jasny kolor główny (biały napis na przycisku byłby słabo widoczny)
  jest oznaczony jako błąd. Konfigurator od razu proponuje najbliższy
  ciemniejszy odcień, który spełnia wymagania dostępności (WCAG AA,
  kontrast 4,5:1). Wystarczy kliknąć „Użyj czytelnego odcienia”.
- Przyciski usuwania i operacji nieodwracalnych zawsze zostają czerwone.

## Podgląd

Po prawej stronie widać strony tej bazy: stronę główną, wyszukiwarkę,
listę autorów, stronę autora, publikacji, jednostki, raporty, stronę
przykładową ze wszystkimi rodzajami komunikatów, przycisków i pól
formularza, a także trzy widoki telefonu. Podglądy są „żywe”: można w nie
klikać, a przycisk **Powiększ** pokazuje stronę w pełnym rozmiarze.
Przełącznik **Układ** (1, 2 albo 3 kolumny, auto) zmienia wielkość
miniatur.

Podgląd przebudowuje się po każdej zmianie, zwykle w ciągu 1–2 sekund.
Ustawienia, które nie zostały jeszcze zastosowane, przeglądarka pamięta
także po zamknięciu karty.

## Ikona strony (favicon)

W sekcji **Ikona strony** można wgrać ikonę PNG (najlepiej kwadrat, co
najmniej 64×64 px) albo ICO, do 1 MB, i zobaczyć ją na makiecie karty
przeglądarki. Ikona zapisuje się razem z „Zastosuj dla wszystkich” — w ustawieniach
uczelni i w ikonach strony.

## Zapisanie motywu bez stosowania

**Zapisz w bazie (bez stosowania)** zachowuje ustawienia, ale nie zmienia
strony. Konfigurator wczyta je przy następnym otwarciu, a superużytkownik
może je potem zastosować. Przycisk jest zawsze dostępny; staje się głównym,
gdy kompilator motywów jest chwilowo niedostępny albo ustawienia przygotowuje
osoba bez prawa „Zastosuj dla wszystkich”.

## Przymiarka na całej stronie

**Przymierz na całej stronie (tylko ja)** włącza ustawienia z edytora na
wszystkich stronach BPP — ale **tylko dla Ciebie**. Odwiedzający dalej widzą
obecny wygląd. Na górze każdej strony pojawia się pasek „Przymierzasz motyw”
z przyciskami **Wróć do konfiguratora** i **Zakończ przymiarkę**. Przymiarka
kończy się sama po dobie. Panel administracyjny nie jest objęty motywem.

## Historia i cofanie zmian

Sekcja **Historia i cofanie zmian** pokazuje 10 ostatnich zastosowanych
motywów (kiedy i kto). **Wczytaj** wstawia wybraną wersję do edytora —
żeby przywrócić ją na stronie, kliknij **Zastosuj**.

Jeśli uczelnia przed konfiguratorem miała jeden z gotowych motywów BPP
(np. zielony), pojawia się przycisk **Wróć do motywu sprzed konfiguratora** —
działa od razu, bez budowania motywu.

## Strona błędu

Gdy BPP chwilowo nie działa, serwer pokazuje statyczną stronę błędu.
Po każdym „Zastosuj dla wszystkich” jest ona przebudowywana w nowym motywie, więc także
wtedy odwiedzający widzą wygląd uczelni.

## Zastosowanie i powrót

**Zastosuj dla wszystkich** zapisuje ustawienia i przełącza uczelnię na
motyw „Własny (z konfiguratora wyglądu)”. Zmianę widzą od razu wszyscy
odwiedzający.

Żeby wrócić do jednego z gotowych motywów, wybierz go w module redagowania:
**Uczelnia** → **Motyw kolorystyczny**. Zapisany własny motyw zostaje na
liście i można do niego wrócić w każdej chwili.

!!! note "Po aktualizacji BPP"
    Przy aktualizacji BPP motyw przebudowuje się sam z zapisanych ustawień,
    więc obejmuje także nowe strony i elementy. Gdyby to się nie udało,
    konfigurator wyświetli przypomnienie — wystarczy wtedy kliknąć
    **Zastosuj** jeszcze raz.

### Tryb jasny i ciemny

Domyślnie strona ma **wersję jasną i ciemną**: przeglądarka sama wybiera tę,
którą odwiedzający ustawił w systemie (tryb „Automatyczny”). Na podglądzie
można przełączać „jasny / ciemny”. Wysoki kontrast zapewnia przycisk
dostępności UserWay.

Wersja ciemna **powstaje automatycznie** z ustawień wersji jasnej: jasne
tła zamieniają się w ciemne (z zachowaniem odcienia), ciemny tekst w jasny,
a kolory przycisków, paska menu i wykresów zostają. Nie ma osobnych
ustawień dla wersji ciemnej.

W trybie „Automatyczny” na pasku menu pojawia się przełącznik **kolory**
(Automatyczny / Jasny / Ciemny): odwiedzający może wybrać wersję niezależnie
od ustawień systemu. Wybór pamięta przeglądarka (bez logowania). Ten sam
przełącznik mają motywy wbudowane z dopiskiem „jasny lub ciemny wg ustawień
systemu” (np. „Niebieski (jasny lub ciemny wg ustawień systemu)”). Przy
motywach tylko jasnych albo tylko ciemnych przełącznika nie ma.

## Zapis do pliku

Sekcja **Zapisz do pliku / wczytaj z pliku** zapisuje bieżące ustawienia jako
plik `.json` (do katalogu pobranych plików przeglądarki), wczytuje je z
powrotem albo kopiuje do schowka — np. żeby przenieść motyw do innej bazy
BPP albo wysłać go do IPLweb. Opis i nazwa pliku są opcjonalne. Z takiego
pliku IPLweb może też przygotować motyw wbudowany w system (opis dla
programistów: [Budowanie CSS](../deweloper/budowanie-css.md#motywy-z-konfiguracji)).
