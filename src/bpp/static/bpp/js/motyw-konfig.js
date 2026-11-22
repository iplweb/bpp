/*
 * Motywy BPP z konfiguracji (konfigurator wyglądu).
 *
 * Jeden moduł używany w trzech miejscach, żeby podgląd i produkcja były
 * identyczne:
 *   - konfigurator wyglądu w przeglądarce (kompilacja w web workerze),
 *   - Gruntfile.js (task `motywy`) — kompiluje src/bpp/static/scss/motywy/*.json
 *     do src/bpp/static/scss/app-<nazwa>.css,
 *   - testy vitest (tests/js/motyw-konfig.test.js).
 *
 * Konfig to płaski obiekt JSON (patrz SCHEMAT). `doScss(konfig)` zwraca
 * punkt wejścia SCSS: zmienne + `@import "app-konfig"`. Kolory, których
 * kontrast z tłem byłby za mały (WCAG AA), są odrzucane przez `waliduj()`
 * razem z gotową poprawką, a kolory tekstu na kolorowym tle wylicza moduł —
 * klient nie wybiera ich sam, więc nie zepsuje czytelności.
 */
(function (root, fabryka) {
    if (typeof module === "object" && module.exports) {
        module.exports = fabryka();
    } else {
        root.BppMotywKonfig = fabryka();
    }
})(typeof self !== "undefined" ? self : this, function () {
    "use strict";

    var WERSJA = 1;

    // Kolory Foundation spoza konfiguracji (jak w _settings.scss).
    var BIALY = "#fefefe";
    var CZARNY = "#0a0a0a";
    var SUKCES = "#3adb76";
    var OSTRZEZENIE = "#ffae00";
    var ALERT = "#cc4b37";

    var PROG_KONTRASTU = 4.5;
    // Elementy graficzne (ikona UserWay: biały symbol na kolorowym kole).
    var PROG_KONTRASTU_GRAFIKI = 3;

    // Obrazek tła trafia do CSS-a jako data URL — limit trzyma wielkość
    // zapisu (konfig + CSS w jednym żądaniu) daleko od limitów Django.
    var MAKS_DLUGOSC_OBRAZU = 700 * 1024;

    // --- Czcionki --------------------------------------------------------------

    var ZAPAS = {
        bezszeryfowa: "system-ui, -apple-system, 'Segoe UI', Roboto, Arial, sans-serif",
        szeryfowa: "Georgia, 'Times New Roman', serif",
    };

    // Lokalne: self-hostowane z src/bpp/static/bpp/fonts/ (latin + latin-ext),
    // bez żadnego zapytania na zewnątrz.
    // Z internetu: Bunny Fonts albo Google Fonts (pole `zrodlo_czcionek`);
    // wszystkie z listy mają polskie znaki.
    var CZCIONKI = {
        systemowa: {
            etykieta: "Systemowa (Helvetica, Arial)",
            rodzina: "'Helvetica Neue', Helvetica, Roboto, Arial, sans-serif",
        },
        inter: { nazwa: "Inter", katalog: "inter", wagi: [400, 500, 600, 700] },
        lato: { nazwa: "Lato", katalog: "lato", wagi: [400, 700] },
        "open-sans": { nazwa: "Open Sans", katalog: "open-sans", wagi: [400, 500, 600, 700] },
        roboto: { nazwa: "Roboto", katalog: "roboto", wagi: [400, 500, 700] },
        "source-sans-pro": {
            nazwa: "Source Sans Pro",
            katalog: "source-sans-pro",
            wagi: [400, 600, 700],
        },
    };

    var CZCIONKI_WEB = [
        ["Archivo", "bezszeryfowa"],
        ["Barlow", "bezszeryfowa"],
        ["Cabin", "bezszeryfowa"],
        ["DM Sans", "bezszeryfowa"],
        ["Exo 2", "bezszeryfowa"],
        ["Fira Sans", "bezszeryfowa"],
        ["IBM Plex Sans", "bezszeryfowa"],
        ["Josefin Sans", "bezszeryfowa"],
        ["Manrope", "bezszeryfowa"],
        ["Montserrat", "bezszeryfowa"],
        ["Noto Sans", "bezszeryfowa"],
        ["Nunito", "bezszeryfowa"],
        ["Nunito Sans", "bezszeryfowa"],
        ["Poppins", "bezszeryfowa"],
        ["PT Sans", "bezszeryfowa"],
        ["Raleway", "bezszeryfowa"],
        ["Rubik", "bezszeryfowa"],
        ["Titillium Web", "bezszeryfowa"],
        ["Ubuntu", "bezszeryfowa"],
        ["Work Sans", "bezszeryfowa"],
        ["Crimson Pro", "szeryfowa"],
        ["EB Garamond", "szeryfowa"],
        ["Libre Baskerville", "szeryfowa"],
        ["Lora", "szeryfowa"],
        ["Merriweather", "szeryfowa"],
        ["Noto Serif", "szeryfowa"],
        ["Playfair Display", "szeryfowa"],
        ["PT Serif", "szeryfowa"],
        ["Roboto Slab", "szeryfowa"],
        ["Source Serif 4", "szeryfowa"],
    ];

    function kluczWeb(nazwa) {
        return "web:" + nazwa;
    }

    CZCIONKI_WEB.forEach(function (c) {
        CZCIONKI[kluczWeb(c[0])] = { nazwa: c[0], web: true, kategoria: c[1] };
    });

    var WLASNA = "wlasna";
    var RE_WLASNA_CZCIONKA = /^[A-Za-z0-9][A-Za-z0-9 ]{1,40}$/;

    function opcjeCzcionek(zJakTekst) {
        var opcje = zJakTekst ? [["jak_tekst", "Taka sama jak tekst"]] : [];
        Object.keys(CZCIONKI).forEach(function (k) {
            var c = CZCIONKI[k];
            var etykieta = c.etykieta || c.nazwa;
            if (c.web) etykieta += " (z internetu)";
            opcje.push([k, etykieta]);
        });
        opcje.push([WLASNA, "Inna z Google Fonts (wpisz nazwę niżej)"]);
        return opcje;
    }

    // --- Schemat -----------------------------------------------------------------

    // Kolejność = kolejność pól w konfiguratorze. `pokaz` — pole widoczne
    // tylko przy danej wartości innego pola.
    var SCHEMAT = [
        {
            klucz: "tryb_kolorow",
            typ: "wybor",
            grupa: "Kolory",
            etykieta: "Tryb kolorów",
            opis:
                "Automatyczny: strona ma wersję jasną i ciemną, a przeglądarka " +
                "wybiera tę, którą odwiedzający ustawił w systemie. Wersja " +
                "ciemna powstaje sama z wybranych kolorów. Wysoki kontrast " +
                "zapewnia przycisk dostępności UserWay.",
            opcje: [
                ["jasny", "Jasny"],
                ["ciemny", "Ciemny"],
                ["automatyczny", "Automatyczny (jak w systemie odwiedzającego)"],
            ],
            domyslnie: "automatyczny",
        },
        {
            klucz: "kolor_naglowka",
            typ: "kolor",
            grupa: "Kolory",
            etykieta: "Kolor paska menu",
            opis:
                "Tło górnego paska z menu. Kolor napisów na pasku dobierany " +
                "jest automatycznie, żeby zawsze były czytelne.",
            domyslnie: "#e6e6e6",
        },
        {
            klucz: "kolor_glowny",
            typ: "kolor",
            grupa: "Kolory",
            etykieta: "Kolor główny",
            opis: "Przyciski, linki i wyróżnienia.",
            domyslnie: "#1779ba",
        },
        {
            klucz: "kolor_dodatkowy",
            typ: "kolor",
            grupa: "Kolory",
            etykieta: "Kolor dodatkowy",
            opis: "Przyciski drugorzędne, np. „Pokaż wszystkie”.",
            domyslnie: "#767676",
        },
        {
            klucz: "tlo_strony",
            typ: "wybor",
            grupa: "Kolory",
            etykieta: "Tło strony",
            opcje: [
                ["biale", "Białe"],
                ["szare", "Jasnoszare (białe karty na szarym tle)"],
                ["wlasne", "Własny kolor (białe karty na kolorowym tle)"],
            ],
            domyslnie: "biale",
        },
        {
            klucz: "kolor_tla_strony",
            typ: "kolor",
            grupa: "Kolory",
            etykieta: "Kolor tła strony",
            opis:
                "Jasny odcień — tekst na stronie jest ciemny. Ciemną stronę " +
                "daje „Tryb kolorów”: wersja ciemna powstaje z tego koloru sama.",
            pokaz: function (k) {
                return k.tlo_strony === "wlasne";
            },
            domyslnie: "#f5f1e8",
        },
        {
            klucz: "tlo_tresci",
            typ: "wybor",
            grupa: "Kolory",
            etykieta: "Tło treści",
            opis:
                "Białe (w trybie ciemnym ciemne) pola pod treścią stron. " +
                "Półprzezroczyste albo przezroczyste odsłaniają tło strony " +
                "i grafikę w tle. Menu, okienka i pola formularzy zawsze " +
                "zostają pełne, żeby dało się je czytać.",
            opcje: [
                ["pelne", "Pełne"],
                ["polprzezroczyste", "Półprzezroczyste"],
                ["przezroczyste", "Przezroczyste"],
            ],
            domyslnie: "pelne",
        },
        {
            klucz: "czcionka",
            typ: "lista",
            grupa: "Tekst",
            etykieta: "Czcionka tekstu",
            opcje: opcjeCzcionek(false),
            domyslnie: "systemowa",
        },
        {
            klucz: "czcionka_naglowkow",
            typ: "lista",
            grupa: "Tekst",
            etykieta: "Czcionka nagłówków",
            opcje: opcjeCzcionek(true),
            domyslnie: "jak_tekst",
        },
        {
            klucz: "czcionka_wlasna",
            typ: "tekst",
            grupa: "Tekst",
            etykieta: "Nazwa czcionki z Google Fonts",
            opis:
                "Dokładnie tak, jak na fonts.google.com, np. „Lexend” albo " +
                "„Red Hat Display”. Sprawdź na podglądzie polskie znaki.",
            pokaz: function (k) {
                return k.czcionka === WLASNA || k.czcionka_naglowkow === WLASNA;
            },
            domyslnie: "",
        },
        {
            klucz: "zrodlo_czcionek",
            typ: "wybor",
            grupa: "Tekst",
            etykieta: "Skąd pobierać czcionki z internetu",
            opis:
                "Bunny Fonts to europejska kopia Google Fonts, która nie " +
                "zbiera danych odwiedzających (zalecane ze względu na RODO).",
            opcje: [
                ["bunny", "Bunny Fonts (zalecane)"],
                ["google", "Google Fonts"],
            ],
            pokaz: function (k) {
                return czyCzcionkaWeb(k.czcionka) || czyCzcionkaWeb(k.czcionka_naglowkow);
            },
            domyslnie: "bunny",
        },
        {
            klucz: "rozmiar_tekstu",
            typ: "wybor",
            grupa: "Tekst",
            etykieta: "Wielkość tekstu",
            opcje: [
                ["standardowy", "Standardowa"],
                ["wiekszy", "Większa"],
            ],
            domyslnie: "standardowy",
        },
        {
            klucz: "naglowki",
            typ: "wybor",
            grupa: "Tekst",
            etykieta: "Nagłówki",
            opcje: [
                ["normalne", "Zwykłe"],
                ["pogrubione", "Pogrubione"],
            ],
            domyslnie: "normalne",
        },
        {
            klucz: "ikony_w_menu",
            typ: "tak_nie",
            grupa: "Menu",
            etykieta: "Ikony w menu",
            opis: "Małe ikonki obok pozycji menu. Bez nich menu to sam tekst.",
            domyslnie: true,
        },
        {
            klucz: "menu_zaokraglone",
            typ: "tak_nie",
            grupa: "Menu",
            etykieta: "Zaokrąglone rozwijane menu",
            domyslnie: true,
        },
        {
            klucz: "cien_menu",
            typ: "wybor",
            grupa: "Menu",
            etykieta: "Cień pod paskiem menu",
            opcje: [
                ["brak", "Brak"],
                ["delikatny", "Delikatny"],
                ["wyrazny", "Wyraźny"],
                ["mocny", "Mocny"],
            ],
            domyslnie: "brak",
        },
        {
            klucz: "logo_bpp",
            typ: "wybor",
            grupa: "Menu",
            etykieta: "Logo BPP na pasku menu",
            opcje: [
                ["auto", "Szare, kolorowe po najechaniu (na ciemnym pasku zawsze kolorowe)"],
                ["kolorowe", "Zawsze pomarańczowe"],
                ["jak_napisy", "W kolorze napisów paska (białe albo czarne)"],
                ["ukryte", "Ukryte"],
            ],
            domyslnie: "auto",
        },
        {
            klucz: "napis_w_pasku",
            typ: "wybor",
            grupa: "Menu",
            etykieta: "Napis obok logo",
            opcje: [
                ["bpp", "„BPP”"],
                ["wlasny", "Własny skrót"],
                ["brak", "Bez napisu"],
            ],
            domyslnie: "bpp",
        },
        {
            klucz: "napis_wlasny",
            typ: "tekst",
            grupa: "Menu",
            etykieta: "Własny skrót",
            opis: "Do 20 znaków, np. skrót nazwy uczelni.",
            pokaz: function (k) {
                return k.napis_w_pasku === "wlasny";
            },
            domyslnie: "",
        },
        {
            klucz: "ikona_menu",
            typ: "wybor",
            grupa: "Menu",
            etykieta: "Ikona menu na telefonie",
            opcje: [
                ["trzy", "Trzy paski"],
                ["dwa", "Dwa paski"],
                ["rozne", "Trzy paski różnej długości"],
                ["kropki", "Trzy kropki"],
            ],
            domyslnie: "trzy",
        },
        {
            klucz: "ikona_menu_animacja",
            typ: "wybor",
            grupa: "Menu",
            etykieta: "Po otwarciu menu na telefonie",
            opcje: [
                ["x", "Ikona zmienia się w „X”"],
                ["brak", "Ikona bez zmian"],
            ],
            domyslnie: "x",
        },
        {
            klucz: "napis_menu",
            typ: "wybor",
            grupa: "Menu",
            etykieta: "Napis przy ikonie menu",
            opcje: [
                ["menu", "„Menu”"],
                ["wlasny", "Własny"],
                ["brak", "Bez napisu"],
            ],
            domyslnie: "menu",
        },
        {
            klucz: "napis_menu_wlasny",
            typ: "tekst",
            grupa: "Menu",
            etykieta: "Własny napis przy ikonie menu",
            opis: "Do 20 znaków, np. „Nawigacja” albo skrót uczelni.",
            pokaz: function (k) {
                return k.napis_menu === "wlasny";
            },
            domyslnie: "",
        },
        {
            klucz: "logo_uczelni",
            typ: "obraz",
            grupa: "Menu",
            etykieta: "Logo uczelni na pasku menu",
            opis:
                "Małe logo przed napisem (zmniejszane do wysokości paska). Żeby " +
                "pokazać je ZAMIAST logo BPP, ustaw wyżej „Logo BPP: ukryte”.",
            wysokoscPx: 56,
            szerokoscKlucz: "logo_uczelni_szerokosc",
            maksDlugosc: 200 * 1024,
            domyslnie: "",
        },
        {
            klucz: "logo_uczelni_szerokosc",
            typ: "liczba",
            ukryte: true,
            grupa: "Menu",
            etykieta: "Szerokość logo uczelni (px przy wysokości 28 px)",
            domyslnie: 0,
        },
        {
            klucz: "zaokraglenia",
            typ: "wybor",
            grupa: "Kształt",
            etykieta: "Rogi przycisków, pól i kart",
            opcje: [
                ["brak", "Kanciaste"],
                ["male", "Lekko zaokrąglone"],
                ["duze", "Mocno zaokrąglone"],
                ["pigulka", "Przyciski okrągłe („pigułki”)"],
            ],
            domyslnie: "brak",
        },
        {
            klucz: "przyciski_styl",
            typ: "wybor",
            grupa: "Przyciski",
            etykieta: "Styl przycisków",
            opcje: [
                ["pelne", "Pełne, płaskie"],
                ["obrys", "Z obrysem (wypełniają się po najechaniu)"],
                ["cien", "Pełne z cieniem"],
            ],
            domyslnie: "pelne",
        },
        {
            klucz: "przyciski_kolory",
            typ: "wybor",
            grupa: "Przyciski",
            etykieta: "Kolory przycisków",
            opis:
                "Przyciski usuwania i operacji nieodwracalnych zawsze " +
                "zostają czerwone.",
            opcje: [
                ["kolorowe", "Różne kolory (zależnie od rodzaju przycisku)"],
                ["jednolite", "Wszystkie w kolorze głównym"],
            ],
            domyslnie: "kolorowe",
        },
        {
            klucz: "kolor_przycisku_sukces",
            typ: "kolor",
            grupa: "Przyciski",
            etykieta: "Przyciski potwierdzenia (np. „Zapisz”, „Wyświetl wyniki”)",
            opis:
                "Przycisk główny ma kolor główny, a drugorzędny — kolor " +
                "dodatkowy (sekcja „Kolory”). Napisy na przyciskach dobierają się same.",
            pokaz: kolorowePrzyciski,
            domyslnie: SUKCES,
        },
        {
            klucz: "kolor_przycisku_ostrzezenie",
            typ: "kolor",
            grupa: "Przyciski",
            etykieta: "Przyciski ostrzegawcze (np. „Zapisz formularz”)",
            pokaz: kolorowePrzyciski,
            domyslnie: OSTRZEZENIE,
        },
        {
            klucz: "kolor_przycisku_alert",
            typ: "kolor",
            grupa: "Przyciski",
            etykieta: "Przyciski usuwania i operacji nieodwracalnych",
            opis: "Zalecany czerwony — użytkownicy kojarzą go z niebezpieczeństwem.",
            pokaz: kolorowePrzyciski,
            domyslnie: ALERT,
        },
        {
            klucz: "kolor_komunikatu_info",
            typ: "kolor",
            grupa: "Komunikaty",
            etykieta: "Informacja",
            opis:
                "Komunikaty u góry strony (np. „Zapisano zmiany”). Jasne tło " +
                "i ciemny tekst wyliczają się z wybranego koloru.",
            domyslnie: "#0284c7",
        },
        {
            klucz: "kolor_komunikatu_sukces",
            typ: "kolor",
            grupa: "Komunikaty",
            etykieta: "Sukces",
            domyslnie: "#16a34a",
        },
        {
            klucz: "kolor_komunikatu_ostrzezenie",
            typ: "kolor",
            grupa: "Komunikaty",
            etykieta: "Ostrzeżenie",
            domyslnie: "#d97706",
        },
        {
            klucz: "kolor_komunikatu_blad",
            typ: "kolor",
            grupa: "Komunikaty",
            etykieta: "Błąd",
            domyslnie: "#dc2626",
        },
        {
            klucz: "okruszki_tlo",
            typ: "wybor",
            grupa: "Okruszki i stopka",
            etykieta: "Pasek ścieżki (okruszki) pod menu",
            opis: "Np. „Uczelnia / Autorzy / Jan Kowalski”. Kolor tekstu i linków dobiera się sam.",
            opcje: [
                ["jasne", "Jasnoszary"],
                ["jak_pasek", "W kolorze paska menu"],
                ["wlasny", "Własny kolor"],
            ],
            domyslnie: "jasne",
        },
        {
            klucz: "okruszki_kolor",
            typ: "kolor",
            grupa: "Okruszki i stopka",
            etykieta: "Kolor paska ścieżki",
            pokaz: function (k) {
                return k.okruszki_tlo === "wlasny";
            },
            domyslnie: "#f0f0f0",
        },
        {
            klucz: "stopka_tlo",
            typ: "wybor",
            grupa: "Okruszki i stopka",
            etykieta: "Stopka",
            opcje: [
                ["jasna", "Jasnoszara"],
                ["jak_pasek", "W kolorze paska menu"],
                ["wlasny", "Własny kolor"],
            ],
            domyslnie: "jasna",
        },
        {
            klucz: "stopka_kolor",
            typ: "kolor",
            grupa: "Okruszki i stopka",
            etykieta: "Kolor stopki",
            pokaz: function (k) {
                return k.stopka_tlo === "wlasny";
            },
            domyslnie: "#f8f8f8",
        },
        {
            klucz: "kolor_wykresow",
            typ: "kolor_auto",
            grupa: "Strona główna i wykresy",
            etykieta: "Kolor wykresów",
            opis: "Słupki i linie wykresów „w latach” na stronach autorów, jednostek i źródeł.",
            auto: "Taki sam jak kolor główny",
            domyslnie: "",
        },
        {
            klucz: "kafle_styl",
            typ: "wybor",
            grupa: "Strona główna i wykresy",
            etykieta: "Kafle „Przeglądaj bazę publikacji”",
            opcje: [
                ["kolorowe", "Jasne, kolorowe ikony"],
                ["ikony_glowny", "Jasne, ikony w kolorze głównym"],
                ["obrys", "Przezroczyste z obrysem w kolorze głównym"],
                ["wypelnione", "Wypełnione kolorem głównym"],
            ],
            domyslnie: "kolorowe",
        },
        {
            klucz: "tlo_obraz",
            typ: "obraz",
            grupa: "Grafika w tle",
            etykieta: "Obrazek",
            opis:
                "PNG, JPG, WebP, GIF albo SVG, do 10 MB. Duże zdjęcia są " +
                "automatycznie zmniejszane (do 1200 px). Najlepiej wyglądają " +
                "ornamenty i logo z przezroczystym tłem.",
            domyslnie: "",
        },
        {
            klucz: "tlo_pozycja",
            typ: "wybor",
            grupa: "Grafika w tle",
            etykieta: "Położenie",
            opcje: [
                ["lewy-gorny", "Lewy górny róg"],
                ["prawy-gorny", "Prawy górny róg"],
                ["lewy-dolny", "Lewy dolny róg"],
                ["prawy-dolny", "Prawy dolny róg"],
                ["gora", "Góra, środek"],
                ["dol", "Dół, środek"],
                ["srodek", "Środek ekranu"],
                ["kafelki", "Powtarzany (kafelki)"],
                ["caly", "Cały ekran"],
            ],
            pokaz: maObraz,
            domyslnie: "prawy-dolny",
        },
        {
            klucz: "tlo_rozmiar",
            typ: "wybor",
            grupa: "Grafika w tle",
            etykieta: "Wielkość",
            opcje: [
                ["maly", "Mały"],
                ["sredni", "Średni"],
                ["duzy", "Duży"],
            ],
            pokaz: function (k) {
                return maObraz(k) && k.tlo_pozycja !== "caly";
            },
            domyslnie: "sredni",
        },
        {
            klucz: "tlo_widocznosc",
            typ: "wybor",
            grupa: "Grafika w tle",
            etykieta: "Widoczność",
            opis: "Przy słabszej widoczności grafika nie przeszkadza w czytaniu.",
            opcje: [
                ["100", "Pełna"],
                ["60", "Wyraźna"],
                ["30", "Słaba"],
                ["12", "Ledwo widoczna"],
            ],
            pokaz: maObraz,
            domyslnie: "30",
        },
        {
            klucz: "kolor_userway",
            typ: "kolor_auto",
            grupa: "Przycisk dostępności (UserWay)",
            etykieta: "Kolor przycisku",
            opis: "Okrągły przycisk z ludzikiem, który otwiera ustawienia dostępności.",
            auto: "Taki sam jak kolor główny",
            domyslnie: "",
        },
        {
            klucz: "cien_userway",
            typ: "wybor",
            grupa: "Przycisk dostępności (UserWay)",
            etykieta: "Cień przycisku",
            opcje: [
                ["brak", "Brak"],
                ["delikatny", "Delikatny"],
                ["wyrazny", "Wyraźny"],
                ["mocny", "Mocny"],
            ],
            domyslnie: "brak",
        },
    ];

    function kolorowePrzyciski(k) {
        return k.przyciski_kolory === "kolorowe";
    }

    function maObraz(k) {
        return !!k.tlo_obraz;
    }

    function czyCzcionkaWeb(klucz) {
        return klucz === WLASNA || !!(CZCIONKI[klucz] && CZCIONKI[klucz].web);
    }

    // Gotowe punkty wyjścia: domyślny i dotychczasowe motywy BPP (app-*.scss,
    // kolory z _settings_*.scss). Uwaga: część z nich nie spełnia wymogu
    // kontrastu — konfigurator pokaże to po wczytaniu, z gotową poprawką.
    var GOTOWE = [
        { klucz: "domyslny", etykieta: "Domyślny konfiguratora", konfig: {} },
        {
            klucz: "app-blue",
            etykieta: "Niebieski (app-blue)",
            konfig: { kolor_glowny: "#1779ba", kolor_dodatkowy: "#767676" },
        },
        {
            klucz: "app-green",
            etykieta: "Zielony (app-green)",
            konfig: { kolor_glowny: "#008000", kolor_dodatkowy: "#767676" },
        },
        {
            klucz: "app-orange",
            etykieta: "Pomarańczowy (app-orange)",
            konfig: { kolor_glowny: "#f26621", kolor_dodatkowy: "#eb9626" },
        },
        {
            klucz: "app-vizja",
            etykieta: "Bursztynowo-granatowy (app-vizja)",
            konfig: { kolor_glowny: "#efa402", kolor_dodatkowy: "#01608c" },
        },
        {
            klucz: "app-mwsl",
            etykieta: "Pomarańczowo-granatowy (app-mwsl)",
            konfig: { kolor_glowny: "#e35b00", kolor_dodatkowy: "#002b53" },
        },
        {
            klucz: "app-uafm",
            etykieta: "Czerwono-błękitny (app-uafm)",
            konfig: { kolor_glowny: "#b41906", kolor_dodatkowy: "#045595" },
        },

        // Motywy o różnym charakterze: poza kolorami różnią się czcionkami,
        // kształtem przycisków i kart, paskiem menu, kaflami, okruszkami
        // i stopką. Wszystkie spełniają wymogi kontrastu (sprawdza to test).
        {
            klucz: "klasyczny-akademicki",
            etykieta: "Klasyczny akademicki (szeryfowe nagłówki)",
            konfig: {
                // Granatowy pasek, bordowe akcenty, Playfair Display w nagłówkach.
                kolor_naglowka: "#1f2a44",
                kolor_glowny: "#8b1e2d",
                kolor_dodatkowy: "#5b6472",
                tlo_strony: "biale",
                tryb_kolorow: "jasny",
                czcionka: "source-sans-pro",
                czcionka_naglowkow: "web:Playfair Display",
                naglowki: "normalne",
                zaokraglenia: "male",
                przyciski_styl: "pelne",
                przyciski_kolory: "kolorowe",
                kolor_przycisku_sukces: "#2f6b3a",
                kolor_przycisku_ostrzezenie: "#b7791f",
                cien_menu: "delikatny",
                logo_bpp: "jak_napisy",
                kafle_styl: "obrys",
                okruszki_tlo: "wlasny",
                okruszki_kolor: "#f3efe6",
                stopka_tlo: "jak_pasek",
            },
        },
        {
            klucz: "nowoczesny-minimalistyczny",
            etykieta: "Nowoczesny minimalistyczny (Inter, zaokrąglony)",
            konfig: {
                // Biały pasek, indygo, białe karty na jasnoszarym tle, bez ikon.
                kolor_naglowka: "#ffffff",
                kolor_glowny: "#4f46e5",
                kolor_dodatkowy: "#64748b",
                tlo_strony: "szare",
                tryb_kolorow: "automatyczny",
                czcionka: "inter",
                czcionka_naglowkow: "jak_tekst",
                naglowki: "pogrubione",
                ikony_w_menu: false,
                menu_zaokraglone: true,
                zaokraglenia: "duze",
                przyciski_styl: "pelne",
                przyciski_kolory: "jednolite",
                cien_menu: "delikatny",
                logo_bpp: "kolorowe",
                kafle_styl: "ikony_glowny",
                okruszki_tlo: "wlasny",
                okruszki_kolor: "#ffffff",
                stopka_tlo: "wlasny",
                stopka_kolor: "#ffffff",
            },
        },
        {
            klucz: "nocny",
            etykieta: "Nocny (ciemny, chłodny błękit)",
            konfig: {
                // Zawsze ciemny; ciemnogranatowy pasek przechodzi w okruszki
                // i stopkę, kafle wypełnione kolorem.
                kolor_naglowka: "#0f172a",
                kolor_glowny: "#2563eb",
                kolor_dodatkowy: "#475569",
                tlo_strony: "biale",
                tryb_kolorow: "ciemny",
                czcionka: "web:Nunito Sans",
                czcionka_naglowkow: "jak_tekst",
                naglowki: "pogrubione",
                zaokraglenia: "male",
                przyciski_styl: "cien",
                przyciski_kolory: "kolorowe",
                cien_menu: "mocny",
                logo_bpp: "kolorowe",
                kafle_styl: "wypelnione",
                okruszki_tlo: "jak_pasek",
                stopka_tlo: "jak_pasek",
                cien_userway: "wyrazny",
            },
        },
        {
            klucz: "medyczny-turkusowy",
            etykieta: "Medyczny (chłodne turkusy, łagodne kształty)",
            konfig: {
                // Turkusowy pasek, morska zieleń, Open Sans + Nunito w nagłówkach.
                kolor_naglowka: "#0e7490",
                kolor_glowny: "#0f766e",
                kolor_dodatkowy: "#64748b",
                tlo_strony: "szare",
                tryb_kolorow: "automatyczny",
                czcionka: "open-sans",
                czcionka_naglowkow: "web:Nunito",
                naglowki: "pogrubione",
                zaokraglenia: "duze",
                przyciski_styl: "pelne",
                przyciski_kolory: "kolorowe",
                kolor_przycisku_sukces: "#0f766e",
                cien_menu: "delikatny",
                logo_bpp: "jak_napisy",
                kafle_styl: "ikony_glowny",
                okruszki_tlo: "wlasny",
                okruszki_kolor: "#e6f6f7",
                stopka_tlo: "wlasny",
                stopka_kolor: "#eef8f7",
                kolor_wykresow: "#0891b2",
            },
        },
        {
            klucz: "techniczny",
            etykieta: "Techniczny (IBM Plex Sans, kanciasty)",
            konfig: {
                // Grafitowy pasek, przyciski z obrysem, zero zaokrągleń i cieni.
                kolor_naglowka: "#161616",
                kolor_glowny: "#0b5cad",
                kolor_dodatkowy: "#525252",
                tlo_strony: "biale",
                tryb_kolorow: "automatyczny",
                czcionka: "web:IBM Plex Sans",
                czcionka_naglowkow: "jak_tekst",
                naglowki: "pogrubione",
                ikony_w_menu: true,
                menu_zaokraglone: false,
                zaokraglenia: "brak",
                przyciski_styl: "obrys",
                przyciski_kolory: "jednolite",
                cien_menu: "brak",
                logo_bpp: "jak_napisy",
                kafle_styl: "obrys",
                okruszki_tlo: "wlasny",
                okruszki_kolor: "#f4f4f4",
                stopka_tlo: "jak_pasek",
            },
        },
        {
            klucz: "humanistyczny-cieply",
            etykieta: "Humanistyczny ciepły (Merriweather, kremowe akcenty)",
            konfig: {
                // Szeryfowy tekst do długiego czytania, rdzawe akcenty, brązowy
                // pasek, kremowe okruszki i stopka.
                kolor_naglowka: "#4a2e22",
                kolor_glowny: "#9a3412",
                kolor_dodatkowy: "#78716c",
                tlo_strony: "biale",
                tryb_kolorow: "jasny",
                czcionka: "web:Merriweather",
                czcionka_naglowkow: "web:Lora",
                rozmiar_tekstu: "wiekszy",
                naglowki: "pogrubione",
                zaokraglenia: "male",
                przyciski_styl: "pelne",
                przyciski_kolory: "kolorowe",
                kolor_przycisku_sukces: "#4d7c0f",
                kolor_przycisku_ostrzezenie: "#d97706",
                cien_menu: "delikatny",
                logo_bpp: "kolorowe",
                kafle_styl: "kolorowe",
                okruszki_tlo: "wlasny",
                okruszki_kolor: "#f5ede0",
                stopka_tlo: "wlasny",
                stopka_kolor: "#efe4d2",
                kolor_wykresow: "#b45309",
            },
        },
        {
            klucz: "wysoki-kontrast",
            etykieta: "Wysoki kontrast (czarny pasek, większy tekst)",
            konfig: {
                // Czerń i mocny błękit, większy pogrubiony tekst, ostre kształty,
                // ciemne kolory przycisków.
                kolor_naglowka: "#000000",
                kolor_glowny: "#0033cc",
                kolor_dodatkowy: "#333333",
                tlo_strony: "biale",
                tryb_kolorow: "jasny",
                czcionka: "web:Noto Sans",
                czcionka_naglowkow: "jak_tekst",
                rozmiar_tekstu: "wiekszy",
                naglowki: "pogrubione",
                menu_zaokraglone: false,
                zaokraglenia: "brak",
                przyciski_styl: "pelne",
                przyciski_kolory: "kolorowe",
                kolor_przycisku_sukces: "#146c2e",
                kolor_przycisku_ostrzezenie: "#8a4b00",
                kolor_przycisku_alert: "#b00020",
                cien_menu: "brak",
                logo_bpp: "jak_napisy",
                kafle_styl: "wypelnione",
                okruszki_tlo: "jak_pasek",
                stopka_tlo: "jak_pasek",
                kolor_komunikatu_info: "#0033cc",
                kolor_komunikatu_sukces: "#146c2e",
                kolor_komunikatu_ostrzezenie: "#8a4b00",
                kolor_komunikatu_blad: "#b00020",
                kolor_wykresow: "#0033cc",
                cien_userway: "wyrazny",
            },
        },
        {
            klucz: "pastelowy",
            etykieta: "Pastelowy (lawenda, przyciski-pigułki)",
            konfig: {
                // Lawendowy pasek z ciemnym napisem, fiolet w roli głównej,
                // Nunito i okrągłe przyciski — miękko, ale czytelnie.
                kolor_naglowka: "#e9d5ff",
                kolor_glowny: "#6d28d9",
                kolor_dodatkowy: "#64748b",
                tlo_strony: "biale",
                tryb_kolorow: "jasny",
                czcionka: "web:Nunito",
                czcionka_naglowkow: "jak_tekst",
                naglowki: "pogrubione",
                zaokraglenia: "pigulka",
                przyciski_styl: "pelne",
                przyciski_kolory: "kolorowe",
                kolor_przycisku_sukces: "#86efac",
                kolor_przycisku_ostrzezenie: "#fcd34d",
                kolor_przycisku_alert: "#be123c",
                cien_menu: "delikatny",
                logo_bpp: "kolorowe",
                kafle_styl: "kolorowe",
                okruszki_tlo: "wlasny",
                okruszki_kolor: "#faf5ff",
                stopka_tlo: "wlasny",
                stopka_kolor: "#f3e8ff",
                kolor_wykresow: "#a855f7",
                kolor_userway: "#db2777",
                cien_userway: "delikatny",
            },
        },
        {
            klucz: "granatowo-zloty",
            etykieta: "Uczelniany granatowo-złoty (EB Garamond)",
            konfig: {
                // Ciemny granat i stare złoto, klasyczna antykwa w nagłówkach,
                // przyciski z cieniem, wyraźny cień pod menu.
                kolor_naglowka: "#14213d",
                kolor_glowny: "#1d3a7a",
                kolor_dodatkowy: "#8a6d1f",
                tlo_strony: "biale",
                tryb_kolorow: "jasny",
                czcionka: "web:PT Sans",
                czcionka_naglowkow: "web:EB Garamond",
                naglowki: "pogrubione",
                zaokraglenia: "male",
                przyciski_styl: "cien",
                przyciski_kolory: "kolorowe",
                kolor_przycisku_ostrzezenie: "#c9a227",
                cien_menu: "wyrazny",
                logo_bpp: "kolorowe",
                kafle_styl: "wypelnione",
                okruszki_tlo: "wlasny",
                okruszki_kolor: "#f4efe1",
                stopka_tlo: "jak_pasek",
                kolor_wykresow: "#8a6d1f",
                kolor_userway: "#8a6d1f",
            },
        },
        {
            klucz: "przyrodniczy",
            etykieta: "Przyrodniczy (zielenie i ziemia, Roboto Slab)",
            konfig: {
                // Leśna zieleń i brąz, bezszeryfowy Cabin z nagłówkami
                // w Roboto Slab, mocne zaokrąglenia.
                kolor_naglowka: "#1f4529",
                kolor_glowny: "#2f6b3a",
                kolor_dodatkowy: "#7c6342",
                tlo_strony: "szare",
                tryb_kolorow: "automatyczny",
                czcionka: "web:Cabin",
                czcionka_naglowkow: "web:Roboto Slab",
                naglowki: "normalne",
                zaokraglenia: "duze",
                przyciski_styl: "pelne",
                przyciski_kolory: "kolorowe",
                kolor_przycisku_sukces: "#4d7c0f",
                kolor_przycisku_ostrzezenie: "#ca8a04",
                cien_menu: "delikatny",
                logo_bpp: "jak_napisy",
                kafle_styl: "ikony_glowny",
                okruszki_tlo: "wlasny",
                okruszki_kolor: "#eef5e9",
                stopka_tlo: "wlasny",
                stopka_kolor: "#e3eddb",
                kolor_wykresow: "#4d7c0f",
            },
        },
        {
            klucz: "redakcyjny",
            etykieta: "Redakcyjny (szeryfowy tekst, jak czasopismo)",
            konfig: {
                // Czarno-biały jak łamy czasopisma: Source Serif 4 w tekście,
                // Work Sans w nagłówkach, karmazynowe linki, bez ikon i cieni.
                kolor_naglowka: "#111111",
                kolor_glowny: "#9f1239",
                kolor_dodatkowy: "#4b5563",
                tlo_strony: "biale",
                tryb_kolorow: "automatyczny",
                czcionka: "web:Source Serif 4",
                czcionka_naglowkow: "web:Work Sans",
                naglowki: "pogrubione",
                ikony_w_menu: false,
                menu_zaokraglone: false,
                zaokraglenia: "brak",
                przyciski_styl: "obrys",
                przyciski_kolory: "jednolite",
                cien_menu: "brak",
                logo_bpp: "jak_napisy",
                kafle_styl: "obrys",
                okruszki_tlo: "jasne",
                stopka_tlo: "jasna",
                kolor_wykresow: "#111111",
            },
        },
        {
            klucz: "energiczny-pomaranczowy",
            etykieta: "Energiczny (pomarańcz i morska zieleń, Poppins)",
            konfig: {
                // Ciepły pomarańczowy pasek, przyciski-pigułki z cieniem,
                // geometryczny Poppins i kafle wypełnione kolorem.
                kolor_naglowka: "#ea580c",
                kolor_glowny: "#c2410c",
                kolor_dodatkowy: "#0f766e",
                tlo_strony: "biale",
                tryb_kolorow: "automatyczny",
                czcionka: "web:Poppins",
                czcionka_naglowkow: "jak_tekst",
                naglowki: "pogrubione",
                zaokraglenia: "pigulka",
                przyciski_styl: "cien",
                przyciski_kolory: "kolorowe",
                kolor_przycisku_sukces: "#0f766e",
                cien_menu: "wyrazny",
                logo_bpp: "jak_napisy",
                kafle_styl: "wypelnione",
                okruszki_tlo: "wlasny",
                okruszki_kolor: "#fff4ec",
                stopka_tlo: "wlasny",
                stopka_kolor: "#1f2937",
                kolor_userway: "#0f766e",
                cien_userway: "wyrazny",
            },
        },
    ];
    // Dotychczasowe motywy: jasne, kanciaste, tekst 92%, jak w app-*.scss.
    var STYL_DOTYCHCZASOWY = {
        tryb_kolorow: "jasny",
        zaokraglenia: "brak",
        rozmiar_tekstu: "standardowy",
        kolor_naglowka: "#e6e6e6",
    };
    GOTOWE.forEach(function (g) {
        if (g.klucz.indexOf("app-") === 0) {
            Object.keys(STYL_DOTYCHCZASOWY).forEach(function (k) {
                if (!(k in g.konfig)) g.konfig[k] = STYL_DOTYCHCZASOWY[k];
            });
        }
    });

    var DOMYSLNE = (function () {
        var d = { wersja: WERSJA, nazwa: "", opis: "" };
        SCHEMAT.forEach(function (p) {
            d[p.klucz] = p.domyslnie;
        });
        return d;
    })();

    // --- Kolory i kontrast (WCAG 2.x) ------------------------------------

    var RE_KOLOR = /^#[0-9a-fA-F]{6}$/;
    var RE_OBRAZ = /^data:image\/(png|jpeg|webp|gif|svg\+xml);base64,[A-Za-z0-9+/=]+$/;

    function hexNaRgb(hex) {
        return [1, 3, 5].map(function (i) {
            return parseInt(hex.slice(i, i + 2), 16);
        });
    }

    function rgbNaHex(rgb) {
        return (
            "#" +
            rgb
                .map(function (c) {
                    var h = Math.round(Math.max(0, Math.min(255, c))).toString(16);
                    return h.length === 1 ? "0" + h : h;
                })
                .join("")
        );
    }

    function luminancja(hex) {
        var rgb = hexNaRgb(hex).map(function (c) {
            c = c / 255;
            return c <= 0.03928 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4);
        });
        return 0.2126 * rgb[0] + 0.7152 * rgb[1] + 0.0722 * rgb[2];
    }

    function kontrast(a, b) {
        var la = luminancja(a);
        var lb = luminancja(b);
        return (Math.max(la, lb) + 0.05) / (Math.min(la, lb) + 0.05);
    }

    // Czytelny tekst na danym tle: biały albo czarny (jak color-pick-contrast
    // w Foundation).
    function tekstNaTle(tlo) {
        return kontrast(BIALY, tlo) >= kontrast(CZARNY, tlo) ? BIALY : CZARNY;
    }

    // Przyciemnia kolor (mnożąc RGB, odcień zostaje) do pierwszego, który
    // ma kontrast >= progu z KAŻDYM z podanych teł.
    function przyciemnijDoKontrastu(kolor, tla, prog) {
        prog = prog || PROG_KONTRASTU;
        var rgb = hexNaRgb(kolor);
        for (var krok = 0; krok <= 100; krok++) {
            var k = 1 - krok / 100;
            var kandydat = rgbNaHex(
                rgb.map(function (c) {
                    return c * k;
                }),
            );
            var ok = tla.every(function (t) {
                return kontrast(kandydat, t) >= prog;
            });
            if (ok) return kandydat;
        }
        return CZARNY;
    }

    // Mieszanka kolorów: `udzial` koloru `a`, reszta `b`.
    function wymieszaj(a, b, udzial) {
        var ra = hexNaRgb(a);
        var rb = hexNaRgb(b);
        return rgbNaHex(
            ra.map(function (c, i) {
                return c * udzial + rb[i] * (1 - udzial);
            }),
        );
    }

    // --- Konfig ------------------------------------------------------------

    function normalizuj(konfig) {
        var wynik = {};
        Object.keys(DOMYSLNE).forEach(function (k) {
            wynik[k] = konfig && konfig[k] !== undefined ? konfig[k] : DOMYSLNE[k];
        });
        SCHEMAT.forEach(function (p) {
            if (
                (p.typ === "kolor" || p.typ === "kolor_auto") &&
                typeof wynik[p.klucz] === "string"
            ) {
                wynik[p.klucz] = wynik[p.klucz].toLowerCase();
            }
        });
        return wynik;
    }

    function tloStrony(k) {
        if (k.tlo_strony === "wlasne" && RE_KOLOR.test(k.kolor_tla_strony || "")) {
            return k.kolor_tla_strony;
        }
        return k.tlo_strony === "szare" ? "#f1f5f9" : BIALY;
    }

    // Tekst strony (#0a0a0a) i szare opisy (#6c757d) muszą być czytelne na tle.
    var TEKST_STRONY = "#0a0a0a";
    var TEKST_SZARY = "#6c757d";

    function rozjasnijDoKontrastu(kolor) {
        for (var krok = 0; krok <= 100; krok++) {
            var kandydat = wymieszaj("#ffffff", kolor, krok / 100);
            if (
                kontrast(TEKST_STRONY, kandydat) >= PROG_KONTRASTU &&
                kontrast(TEKST_SZARY, kandydat) >= PROG_KONTRASTU_GRAFIKI
            ) {
                return kandydat;
            }
        }
        return BIALY;
    }

    function kolorUserway(k) {
        return k.kolor_userway || k.kolor_glowny;
    }

    var RE_NAZWA = /^[a-z0-9][a-z0-9-]{1,40}$/;
    // Napis trafia do CSS (`content: "…"`), więc bez cudzysłowów i ukośników.
    var RE_NAPIS = /^[A-Za-z0-9ĄĆĘŁŃÓŚŹŻąćęłńóśźż .&-]{1,20}$/;

    // Zwraca listę błędów [{pole, komunikat, poprawka?}]. Pusta = konfig OK.
    // `poprawka` to wartość, którą konfigurator może podstawić jednym
    // kliknięciem.
    function waliduj(konfig, opcje) {
        opcje = opcje || {};
        var k = normalizuj(konfig);
        var bledy = [];

        if (k.wersja !== WERSJA) {
            bledy.push({
                pole: "wersja",
                komunikat: "Nieobsługiwana wersja konfiguracji: " + k.wersja + ".",
            });
        }

        if (!opcje.bezNazwy && !RE_NAZWA.test(k.nazwa || "")) {
            bledy.push({
                pole: "nazwa",
                komunikat:
                    "Nazwa motywu: 2–41 znaków, małe litery bez polskich znaków, " +
                    "cyfry i myślniki (np. „uczelnia-xyz”).",
            });
        }

        if (konfig) {
            Object.keys(konfig).forEach(function (klucz) {
                if (!(klucz in DOMYSLNE)) {
                    bledy.push({
                        pole: klucz,
                        komunikat: "Nieznane pole konfiguracji: " + klucz + ".",
                    });
                }
            });
        }

        SCHEMAT.forEach(function (p) {
            var v = k[p.klucz];
            var zle = false;
            var opis = "";
            if (p.typ === "kolor") {
                zle = !(typeof v === "string" && RE_KOLOR.test(v));
                opis = "oczekiwany kolor w formacie #rrggbb.";
            } else if (p.typ === "kolor_auto") {
                zle = !(v === "" || (typeof v === "string" && RE_KOLOR.test(v)));
                opis = "oczekiwany kolor w formacie #rrggbb albo pusty.";
            } else if (p.typ === "tak_nie") {
                zle = typeof v !== "boolean";
                opis = "oczekiwane true albo false.";
            } else if (p.typ === "wybor" || p.typ === "lista") {
                var dozwolone = p.opcje.map(function (o) {
                    return o[0];
                });
                zle = dozwolone.indexOf(v) === -1;
                opis = "niedozwolona wartość „" + v + "”.";
            } else if (p.typ === "liczba") {
                zle = typeof v !== "number" || !(v >= 0 && v <= 400);
                opis = "oczekiwana liczba 0–400.";
            } else if (p.typ === "obraz") {
                zle = !(v === "" || (typeof v === "string" && RE_OBRAZ.test(v)));
                opis = "oczekiwany obrazek PNG, JPG, WebP, GIF albo SVG.";
                if (!zle && v.length > (p.maksDlugosc || MAKS_DLUGOSC_OBRAZU)) {
                    zle = true;
                    opis = "obrazek jest za duży.";
                }
            } else if (p.typ === "tekst") {
                zle = typeof v !== "string";
                opis = "oczekiwany tekst.";
            }
            if (zle) bledy.push({ pole: p.klucz, komunikat: p.etykieta + ": " + opis });
        });

        if (k.napis_w_pasku === "wlasny" && !RE_NAPIS.test(k.napis_wlasny || "")) {
            bledy.push({
                pole: "napis_wlasny",
                komunikat:
                    "Własny skrót: 1–20 znaków — litery, cyfry, spacje, kropka, " +
                    "myślnik albo „&”.",
            });
        }

        if (k.napis_menu === "wlasny" && !RE_NAPIS.test(k.napis_menu_wlasny || "")) {
            bledy.push({
                pole: "napis_menu_wlasny",
                komunikat:
                    "Napis przy ikonie menu: 1–20 znaków — litery, cyfry, spacje, " +
                    "kropka, myślnik albo „&”.",
            });
        }

        var wlasnaUzywana = k.czcionka === WLASNA || k.czcionka_naglowkow === WLASNA;
        if (wlasnaUzywana && !RE_WLASNA_CZCIONKA.test(k.czcionka_wlasna || "")) {
            bledy.push({
                pole: "czcionka_wlasna",
                komunikat:
                    "Wpisz nazwę czcionki z Google Fonts (litery, cyfry i spacje, " +
                    "np. „Red Hat Display”).",
            });
        }

        if (k.tlo_strony === "wlasne" && RE_KOLOR.test(k.kolor_tla_strony || "")) {
            var kt = kontrast(TEKST_STRONY, k.kolor_tla_strony);
            var ks = kontrast(TEKST_SZARY, k.kolor_tla_strony);
            if (kt < PROG_KONTRASTU || ks < PROG_KONTRASTU_GRAFIKI) {
                bledy.push({
                    pole: "kolor_tla_strony",
                    komunikat:
                        "Tło strony jest za ciemne — tekst i szare opisy byłyby słabo " +
                        "czytelne. Wybierz jaśniejszy odcień; ciemną stronę daje " +
                        "„Tryb kolorów”.",
                    poprawka: rozjasnijDoKontrastu(k.kolor_tla_strony),
                });
            }
        }

        // Kolor główny: biały tekst na przyciskach i kolor linków na tle
        // strony — oba muszą być czytelne.
        if (RE_KOLOR.test(k.kolor_glowny || "")) {
            var tla = [BIALY, tloStrony(k)];
            var najgorszy = Math.min.apply(
                null,
                tla.map(function (t) {
                    return kontrast(k.kolor_glowny, t);
                }),
            );
            if (najgorszy < PROG_KONTRASTU) {
                bledy.push({
                    pole: "kolor_glowny",
                    komunikat:
                        "Kolor główny jest za jasny: biały napis na przycisku i " +
                        "linki na tle strony byłyby słabo czytelne (kontrast " +
                        najgorszy.toFixed(1) +
                        ":1, wymagane 4.5:1).",
                    poprawka: przyciemnijDoKontrastu(k.kolor_glowny, tla),
                });
            }
        }

        // Słupki wykresów na tle strony — element graficzny, 3:1.
        if (k.kolor_wykresow && RE_KOLOR.test(k.kolor_wykresow)) {
            var tloW = tloStrony(k);
            var kw = kontrast(k.kolor_wykresow, tloW);
            if (kw < PROG_KONTRASTU_GRAFIKI) {
                bledy.push({
                    pole: "kolor_wykresow",
                    komunikat:
                        "Kolor wykresów jest za jasny — słupki zlewałyby się z tłem " +
                        "(kontrast " + kw.toFixed(1) + ":1, wymagane 3:1).",
                    poprawka: przyciemnijDoKontrastu(
                        k.kolor_wykresow,
                        [BIALY, tloW],
                        PROG_KONTRASTU_GRAFIKI,
                    ),
                });
            }
        }

        // Ikona UserWay: biały symbol na kolorowym kole (element graficzny, 3:1).
        // Gdy kolor „jak główny”, sprawdza go już reguła wyżej (4.5:1).
        if (k.kolor_userway && RE_KOLOR.test(k.kolor_userway)) {
            var ku = kontrast(BIALY, k.kolor_userway);
            if (ku < PROG_KONTRASTU_GRAFIKI) {
                bledy.push({
                    pole: "kolor_userway",
                    komunikat:
                        "Kolor przycisku dostępności jest za jasny — biały ludzik " +
                        "byłby słabo widoczny (kontrast " +
                        ku.toFixed(1) +
                        ":1, wymagane 3:1).",
                    poprawka: przyciemnijDoKontrastu(
                        k.kolor_userway,
                        [BIALY],
                        PROG_KONTRASTU_GRAFIKI,
                    ),
                });
            }
        }

        return bledy;
    }

    // --- SCSS ----------------------------------------------------------------

    function mapaScss(obj) {
        return (
            "(" +
            Object.keys(obj)
                .map(function (k) {
                    return k + ": " + obj[k];
                })
                .join(", ") +
            ")"
        );
    }

    // Opis wybranej czcionki: {nazwa, rodzina (CSS font-family), katalog?,
    // wagi?, web?}.
    function opisCzcionki(klucz, k) {
        if (klucz === WLASNA) {
            var nazwa = (k.czcionka_wlasna || "").trim();
            return {
                nazwa: nazwa,
                web: true,
                rodzina: "'" + nazwa + "', " + ZAPAS.bezszeryfowa,
            };
        }
        var c = CZCIONKI[klucz] || CZCIONKI.systemowa;
        if (!c.nazwa) return { rodzina: c.rodzina };
        return {
            nazwa: c.nazwa,
            katalog: c.katalog,
            wagi: c.wagi,
            web: !!c.web,
            rodzina:
                "'" + c.nazwa + "', " + ZAPAS[c.kategoria || "bezszeryfowa"],
        };
    }

    // Arkusz z czcionkami z internetu (API v1 — toleruje brak niektórych
    // grubości, w przeciwieństwie do css2).
    function adresCzcionekWeb(nazwy, zrodlo) {
        var wagi = "400,600,700";
        if (zrodlo === "google") {
            return (
                "https://fonts.googleapis.com/css?family=" +
                nazwy
                    .map(function (n) {
                        return n.replace(/ /g, "+") + ":" + wagi;
                    })
                    .join("|") +
                "&display=swap"
            );
        }
        return (
            "https://fonts.bunny.net/css?family=" +
            nazwy
                .map(function (n) {
                    return n.toLowerCase().replace(/ /g, "-") + ":" + wagi;
                })
                .join("|") +
            "&display=swap"
        );
    }

    var CIENIE = {
        brak: "none",
        delikatny: "0 1px 3px rgba(0, 0, 0, 0.12)",
        wyrazny: "0 3px 10px rgba(0, 0, 0, 0.2)",
        mocny: "0 6px 20px rgba(0, 0, 0, 0.35)",
    };

    var TLO_POZYCJE = {
        "lewy-gorny": "left top",
        "prawy-gorny": "right top",
        "lewy-dolny": "left bottom",
        "prawy-dolny": "right bottom",
        gora: "center top",
        dol: "center bottom",
        srodek: "center center",
        kafelki: "left top",
        caly: "center center",
    };

    var TLO_ROZMIARY = { maly: "120px", sredni: "240px", duzy: "420px" };

    // Wyliczone wartości pochodne (kolory tekstu, paleta przycisków, czcionki).
    function wylicz(konfig) {
        var k = normalizuj(konfig);
        var tlo = tloStrony(k);
        // Paleta Foundation (etykiety, odznaki, paski postępu) — kolory
        // komunikatów; przyciski mają własną paletę.
        var paleta = {
            primary: k.kolor_glowny,
            secondary: k.kolor_dodatkowy,
            success: k.kolor_komunikatu_sukces,
            warning: k.kolor_komunikatu_ostrzezenie,
            alert: k.kolor_komunikatu_blad,
        };
        var przyciski =
            k.przyciski_kolory === "jednolite"
                ? {
                      primary: k.kolor_glowny,
                      secondary: k.kolor_glowny,
                      success: k.kolor_glowny,
                      warning: k.kolor_glowny,
                      alert: ALERT,
                  }
                : {
                      primary: k.kolor_glowny,
                      secondary: k.kolor_dodatkowy,
                      success: k.kolor_przycisku_sukces,
                      warning: k.kolor_przycisku_ostrzezenie,
                      alert: k.kolor_przycisku_alert,
                  };

        // Komunikaty: jasne tło z koloru, ramka w kolorze, tekst przyciemniony
        // do czytelności na tym tle.
        var komunikaty = {};
        [
            ["primary", k.kolor_glowny],
            ["info", k.kolor_komunikatu_info],
            ["success", k.kolor_komunikatu_sukces],
            ["warning", k.kolor_komunikatu_ostrzezenie],
            ["alert", k.kolor_komunikatu_blad],
            ["error", k.kolor_komunikatu_blad],
        ].forEach(function (para) {
            var tloKomunikatu = wymieszaj(para[1], BIALY, 0.1);
            komunikaty[para[0]] = {
                tlo: tloKomunikatu,
                ramka: para[1],
                tekst: przyciemnijDoKontrastu(para[1], [tloKomunikatu]),
            };
        });
        // Kolor napisu na przycisku z obrysem (kolor palety jako tekst na
        // tle strony) — przyciemniony do czytelności.
        var tekstyPrzyciskow = {};
        Object.keys(przyciski).forEach(function (n) {
            tekstyPrzyciskow[n] = przyciemnijDoKontrastu(przyciski[n], [BIALY, tlo]);
        });

        var czcionka = opisCzcionki(k.czcionka, k);
        var czcionkaNaglowkow =
            k.czcionka_naglowkow === "jak_tekst"
                ? czcionka
                : opisCzcionki(k.czcionka_naglowkow, k);
        var nazwyWeb = [];
        [czcionka, czcionkaNaglowkow].forEach(function (c) {
            if (c.web && nazwyWeb.indexOf(c.nazwa) === -1) nazwyWeb.push(c.nazwa);
        });
        var lokalne = [];
        [czcionka, czcionkaNaglowkow].forEach(function (c) {
            var juz = lokalne.some(function (l) {
                return l.katalog === c.katalog;
            });
            if (c.katalog && !juz) lokalne.push(c);
        });

        return {
            konfig: k,
            tlo: tlo,
            paleta: paleta,
            przyciski: przyciski,
            tekstyPrzyciskow: tekstyPrzyciskow,
            naglowekTekst: tekstNaTle(k.kolor_naglowka),
            naglowekCiemny: tekstNaTle(k.kolor_naglowka) === BIALY,
            czcionka: czcionka,
            czcionkaNaglowkow: czcionkaNaglowkow,
            czcionkiLokalne: lokalne,
            czcionkiWebUrl: nazwyWeb.length
                ? adresCzcionekWeb(nazwyWeb, k.zrodlo_czcionek)
                : null,
            kolorUserway: kolorUserway(k),
            komunikaty: komunikaty,
            kafleTekst: tekstNaTle(k.kolor_glowny),
            okruszki: pasekZTlem(k, k.okruszki_tlo, k.okruszki_kolor),
            stopka: pasekZTlem(k, k.stopka_tlo, k.stopka_kolor),
        };
    }

    // Okruszki / stopka: tło z wyboru + czytelny tekst i linki (albo null =
    // bez zmian względem dotychczasowego wyglądu).
    function pasekZTlem(k, wybor, kolor) {
        var tlo = wybor === "jak_pasek" ? k.kolor_naglowka : wybor === "wlasny" ? kolor : null;
        if (!tlo || !RE_KOLOR.test(tlo)) return null;
        var tekst = tekstNaTle(tlo);
        return {
            tlo: tlo,
            tekst: tekst,
            link: tekst === BIALY ? BIALY : przyciemnijDoKontrastu(k.kolor_glowny, [tlo]),
        };
    }

    function mapaPaska(p) {
        return p ? "(tlo: " + p.tlo + ", tekst: " + p.tekst + ", link: " + p.link + ")" : "null";
    }

    function str(s) {
        return '"' + s + '"';
    }

    // Punkt wejścia SCSS dla danego konfiga. Kompilować z loadPaths:
    // src/bpp/static/scss + node_modules/foundation-sites/scss.
    // `opcje.czcionkiUrl` — adres katalogu czcionek, gdy CSS nie leży
    // w src/bpp/static/scss (konfigurator wstawia go w <style>).
    function doScss(konfig, opcje) {
        opcje = opcje || {};
        var w = wylicz(konfig);
        var k = w.konfig;
        var promien = {
            brak: "0",
            male: "0.375rem",
            duze: "0.75rem",
            pigulka: "0.75rem",
        }[k.zaokraglenia];
        var promienPrzyciskow = k.zaokraglenia === "pigulka" ? "999px" : promien;

        var lokalne = w.czcionkiLokalne.map(function (c) {
            return "(" + str(c.nazwa) + ", " + str(c.katalog) + ", (" + c.wagi.join(", ") + "))";
        });

        var linie = [
            "// WYGENEROWANE z konfiguracji motywu przez motyw-konfig.js —",
            "// nie edytuj, zmień konfigurację.",
            // Zwykły CSS @import musi być pierwszą regułą arkusza.
            w.czcionkiWebUrl ? "@import url(" + str(w.czcionkiWebUrl) + ");" : "",
            "$global-font-size: " + (k.rozmiar_tekstu === "wiekszy" ? "100%" : "92%") + ";",
            "$foundation-palette: " + mapaScss(w.paleta) + ";",
            "$button-palette: " + mapaScss(w.przyciski) + ";",
            "$body-background: " + w.tlo + ";",
            "$body-font-family: " + w.czcionka.rodzina + ";",
            "$header-font-family: " + w.czcionkaNaglowkow.rodzina + ";",
            "$global-radius: " + promien + ";",
            "$header-font-weight: " + (k.naglowki === "pogrubione" ? "600" : "normal") + ";",
            "",
            "$cfg-czcionki-lokalne: (" + lokalne.join(", ") + (lokalne.length === 1 ? "," : "") + ");",
            "$cfg-naglowek: " + k.kolor_naglowka + ";",
            "$cfg-naglowek-tekst: " + w.naglowekTekst + ";",
            "$cfg-naglowek-ciemny: " + w.naglowekCiemny + ";",
            "$cfg-ikony-w-menu: " + k.ikony_w_menu + ";",
            "$cfg-menu-zaokraglone: " + k.menu_zaokraglone + ";",
            "$cfg-cien-menu: " + CIENIE[k.cien_menu] + ";",
            "$cfg-promien-przyciskow: " + promienPrzyciskow + ";",
            '$cfg-przyciski-styl: "' + k.przyciski_styl + '";',
            "$cfg-teksty-przyciskow: " + mapaScss(w.tekstyPrzyciskow) + ";",
            "$cfg-tlo-szare: " + (k.tlo_strony === "szare" || k.tlo_strony === "wlasne") + ";",
            "$cfg-userway-kolor: " + w.kolorUserway + ";",
            "$cfg-userway-cien: " + CIENIE[k.cien_userway] + ";",
            "$cfg-tlo-obraz: " + (k.tlo_obraz ? str(k.tlo_obraz) : "null") + ";",
            "$cfg-tlo-pozycja: " + TLO_POZYCJE[k.tlo_pozycja] + ";",
            '$cfg-tlo-tryb: "' + k.tlo_pozycja + '";',
            "$cfg-tlo-rozmiar: " + TLO_ROZMIARY[k.tlo_rozmiar] + ";",
            "$cfg-tlo-widocznosc: " + Number(k.tlo_widocznosc) / 100 + ";",
            '$cfg-logo-bpp: "' + k.logo_bpp + '";',
            '$cfg-napis: "' + k.napis_w_pasku + '";',
            '$cfg-ikona-menu: "' + k.ikona_menu + '";',
            '$cfg-ikona-menu-animacja: "' + k.ikona_menu_animacja + '";',
            '$cfg-napis-menu: "' + k.napis_menu + '";',
            "$cfg-napis-menu-wlasny: " + str(k.napis_menu === "wlasny" ? k.napis_menu_wlasny : "") + ";",
            "$cfg-napis-wlasny: " + str(k.napis_w_pasku === "wlasny" ? k.napis_wlasny : "") + ";",
            "$cfg-logo-uczelni: " + (k.logo_uczelni ? str(k.logo_uczelni) : "null") + ";",
            "$cfg-logo-uczelni-szerokosc: " + Math.round(k.logo_uczelni_szerokosc || 28) + "px;",
            '$cfg-kafle-styl: "' + k.kafle_styl + '";',
            "$cfg-kolor-wykresow: " + (k.kolor_wykresow || k.kolor_glowny) + ";",
            "$cfg-okruszki: " + mapaPaska(w.okruszki) + ";",
            "$cfg-stopka: " + mapaPaska(w.stopka) + ";",
            "$cfg-kafle-tekst: " + w.kafleTekst + ";",
            "$cfg-komunikaty: (" +
                Object.keys(w.komunikaty)
                    .map(function (typ) {
                        var c = w.komunikaty[typ];
                        return typ + ": (tlo: " + c.tlo + ", ramka: " + c.ramka + ", tekst: " + c.tekst + ")";
                    })
                    .join(", ") +
                ");",
            "",
            opcje.czcionkiUrl ? "$cfg-czcionki-url: " + str(opcje.czcionkiUrl) + ";" : "",
            '@import "app-konfig";',
            "",
        ];
        return linie.join("\n");
    }

    // --- Przetwarzanie skompilowanego CSS: tryb ciemny i tło treści ------------
    //
    // Style BPP mają setki kolorów wpisanych na sztywno (białe tła, ciemny
    // tekst), więc tryb ciemny i przezroczyste tło treści robimy na gotowym
    // CSS-ie: przechodzimy przez reguły i przeliczamy kolory w deklaracjach.

    var NAZWANE = {
        white: [255, 255, 255],
        black: [0, 0, 0],
        gray: [128, 128, 128],
        grey: [128, 128, 128],
        silver: [192, 192, 192],
        whitesmoke: [245, 245, 245],
        gainsboro: [220, 220, 220],
        lightgray: [211, 211, 211],
        lightgrey: [211, 211, 211],
        darkgray: [169, 169, 169],
        darkgrey: [169, 169, 169],
        dimgray: [105, 105, 105],
        dimgrey: [105, 105, 105],
    };

    var RE_KOLOR_W_CSS = new RegExp(
        "#[0-9a-fA-F]{3,8}\\b|rgba?\\([^)]*\\)|hsla?\\([^)]*\\)|\\b(?:" +
            Object.keys(NAZWANE).join("|") +
            ")\\b",
        "g",
    );

    function liczbaLubProcent(t, skala) {
        t = t.trim();
        if (t.slice(-1) === "%") return (parseFloat(t) / 100) * skala;
        return parseFloat(t);
    }

    function hslNaRgb(h, s, l) {
        h = (((h % 360) + 360) % 360) / 360;
        if (s === 0) return [l * 255, l * 255, l * 255];
        var q = l < 0.5 ? l * (1 + s) : l + s - l * s;
        var p = 2 * l - q;
        return [h + 1 / 3, h, h - 1 / 3].map(function (t) {
            if (t < 0) t += 1;
            if (t > 1) t -= 1;
            var v;
            if (t < 1 / 6) v = p + (q - p) * 6 * t;
            else if (t < 1 / 2) v = q;
            else if (t < 2 / 3) v = p + (q - p) * (2 / 3 - t) * 6;
            else v = p;
            return v * 255;
        });
    }

    function rgbNaHsl(rgb) {
        var r = rgb[0] / 255;
        var g = rgb[1] / 255;
        var b = rgb[2] / 255;
        var max = Math.max(r, g, b);
        var min = Math.min(r, g, b);
        var l = (max + min) / 2;
        var h = 0;
        var s = 0;
        if (max !== min) {
            var d = max - min;
            s = l > 0.5 ? d / (2 - max - min) : d / (max + min);
            if (max === r) h = (g - b) / d + (g < b ? 6 : 0);
            else if (max === g) h = (b - r) / d + 2;
            else h = (r - g) / d + 4;
            h *= 60;
        }
        return [h, s, l];
    }

    // Kolor z CSS → {rgb: [r, g, b], a} albo null (np. var(), currentColor).
    function czytajKolor(t) {
        var m;
        if (t.charAt(0) === "#") {
            var hex = t.slice(1);
            if (hex.length === 3 || hex.length === 4) {
                hex = hex
                    .split("")
                    .map(function (c) {
                        return c + c;
                    })
                    .join("");
            }
            if (hex.length !== 6 && hex.length !== 8) return null;
            return {
                rgb: [0, 2, 4].map(function (i) {
                    return parseInt(hex.slice(i, i + 2), 16);
                }),
                a: hex.length === 8 ? parseInt(hex.slice(6, 8), 16) / 255 : 1,
            };
        }
        if ((m = /^(rgba?|hsla?)\(([^)]*)\)$/i.exec(t))) {
            if (m[2].indexOf("var(") !== -1) return null;
            var czesci = m[2].replace(/\//g, " ").split(/[\s,]+/).filter(Boolean);
            if (czesci.length < 3) return null;
            var a = czesci.length > 3 ? liczbaLubProcent(czesci[3], 1) : 1;
            if (m[1].toLowerCase().indexOf("hsl") === 0) {
                return {
                    rgb: hslNaRgb(
                        parseFloat(czesci[0]),
                        liczbaLubProcent(czesci[1], 1),
                        liczbaLubProcent(czesci[2], 1),
                    ),
                    a: a,
                };
            }
            return {
                rgb: czesci.slice(0, 3).map(function (c) {
                    return liczbaLubProcent(c, 255);
                }),
                a: a,
            };
        }
        var nazwany = NAZWANE[t.toLowerCase()];
        return nazwany ? { rgb: nazwany.slice(), a: 1 } : null;
    }

    function piszKolor(k) {
        var rgb = k.rgb.map(function (c) {
            return Math.round(Math.max(0, Math.min(255, c)));
        });
        if (k.a >= 1) return rgbNaHex(rgb);
        return "rgba(" + rgb.join(",") + "," + Math.round(k.a * 1000) / 1000 + ")";
    }

    // Próg jak w color-pick-contrast Foundation: powyżej czarny tekst czytelniejszy.
    function jasny(k) {
        return luminancja(rgbNaHex(k.rgb)) > 0.179;
    }

    function zmienJasnosc(k, nowaL, mnoznikNasycenia) {
        var hsl = rgbNaHsl(k.rgb);
        return {
            rgb: hslNaRgb(hsl[0], hsl[1] * mnoznikNasycenia, Math.max(0, Math.min(1, nowaL))),
            a: k.a,
        };
    }

    // Tryb ciemny dla jednego koloru w danej roli; null = bez zmian.
    function naCiemny(k, rola) {
        var l = rgbNaHsl(k.rgb)[2];
        if (rola === "tekst") {
            return jasny(k) ? null : zmienJasnosc(k, 0.95 - l * 0.6, 0.85);
        }
        if (!jasny(k)) return null;
        if (rola === "ramka") return zmienJasnosc(k, 0.22 + (1 - l) * 0.6, 0.6);
        return zmienJasnosc(k, 0.1 + (1 - l) * 0.8, 0.6);
    }

    var ROLE = {
        color: "tekst",
        fill: "tekst",
        stroke: "tekst",
        "caret-color": "tekst",
        "text-decoration-color": "tekst",
        "-webkit-text-fill-color": "tekst",
        background: "tlo",
        "background-color": "tlo",
        "background-image": "tlo",
    };

    function rolaWlasciwosci(prop) {
        if (ROLE[prop]) return ROLE[prop];
        if (prop.indexOf("border") === 0 || prop.indexOf("outline") === 0) return "ramka";
        return null; // m.in. cienie — zostają
    }

    // Elementy, które muszą zostać nieprzezroczyste (nakładają się na treść
    // albo służą do wpisywania).
    var RE_ZAWSZE_PELNE = new RegExp(
        "menu|dropdown|select2|modal|reveal|tooltip|popup|popover|autocomplete|" +
            "\\.ui-|dialog|overlay|cookie|toast|button|input|select|textarea|" +
            "option|tabs|accordion|nav|bar\\b|-bar|search|calendar|picker|" +
            "lightbox|notification|badge|label|kbd|code|pre\\b|sticky|callout",
        "i",
    );

    function tylkoHtmlBody(selektor) {
        return selektor.split(",").every(function (s) {
            return /^\s*(html|body)\b/.test(s);
        });
    }

    // Prosty parser CSS-a z dart-sassa (compressed): reguły, @media/@supports
    // (rekurencyjnie), reszta (np. @font-face, @keyframes, @import) bez zmian.
    function konczyBlok(css, i) {
        // Zwraca indeks zamykającego `}` dla `{` na pozycji i.
        var glebokosc = 0;
        var cudzyslow = null;
        for (var j = i; j < css.length; j++) {
            var c = css.charAt(j);
            if (cudzyslow) {
                if (c === "\\") j++;
                else if (c === cudzyslow) cudzyslow = null;
            } else if (c === '"' || c === "'") cudzyslow = c;
            else if (c === "{") glebokosc++;
            else if (c === "}") {
                glebokosc--;
                if (glebokosc === 0) return j;
            }
        }
        return css.length - 1;
    }

    function parsujCss(css) {
        var wezly = [];
        var i = 0;
        while (i < css.length) {
            var start = i;
            var cudzyslow = null;
            var nawias = 0;
            while (i < css.length) {
                var c = css.charAt(i);
                if (cudzyslow) {
                    if (c === "\\") i++;
                    else if (c === cudzyslow) cudzyslow = null;
                } else if (c === '"' || c === "'") cudzyslow = c;
                else if (c === "(") nawias++;
                else if (c === ")") nawias--;
                else if (nawias === 0 && (c === "{" || c === ";" || c === "}")) break;
                i++;
            }
            var prelude = css.slice(start, i).trim();
            if (i >= css.length) {
                if (prelude) wezly.push({ surowy: prelude });
                break;
            }
            if (css.charAt(i) !== "{") {
                if (prelude) wezly.push({ surowy: prelude + css.charAt(i) });
                i++;
                continue;
            }
            var koniec = konczyBlok(css, i);
            var wnetrze = css.slice(i + 1, koniec);
            if (/^@(media|supports|layer|container)\b/i.test(prelude)) {
                wezly.push({ at: prelude, dzieci: parsujCss(wnetrze) });
            } else if (prelude.charAt(0) === "@") {
                wezly.push({ surowy: prelude + "{" + wnetrze + "}" });
            } else {
                wezly.push({ selektor: prelude, deklaracje: wnetrze });
            }
            i = koniec + 1;
        }
        return wezly;
    }

    function podzielDeklaracje(tekst) {
        var wynik = [];
        var start = 0;
        var cudzyslow = null;
        var nawias = 0;
        for (var i = 0; i < tekst.length; i++) {
            var c = tekst.charAt(i);
            if (cudzyslow) {
                if (c === "\\") i++;
                else if (c === cudzyslow) cudzyslow = null;
            } else if (c === '"' || c === "'") cudzyslow = c;
            else if (c === "(") nawias++;
            else if (c === ")") nawias--;
            else if (c === ";" && nawias === 0) {
                wynik.push(tekst.slice(start, i));
                start = i + 1;
            }
        }
        wynik.push(tekst.slice(start));
        return wynik.filter(function (d) {
            return d.trim();
        });
    }

    // Zamienia kolory w wartości (z pominięciem url(...)).
    function zamienKolory(wartosc, fn) {
        var kawalki = wartosc.split(/(url\((?:"[^"]*"|'[^']*'|[^)]*)\))/i);
        return kawalki
            .map(function (k) {
                if (/^url\(/i.test(k)) return k;
                return k.replace(RE_KOLOR_W_CSS, function (t) {
                    var kolor = czytajKolor(t);
                    if (!kolor) return t;
                    var nowy = fn(kolor);
                    return nowy ? piszKolor(nowy) : t;
                });
            })
            .join("");
    }

    // Przetwarza jedną regułę. Zwraca nowe deklaracje (tablica) albo null,
    // gdy nic się nie zmieniło.
    function przetworzRegule(selektor, deklaracje, ciemny, tloTresci) {
        var lista = podzielDeklaracje(deklaracje).map(function (d) {
            var dwukropek = d.indexOf(":");
            return {
                prop: d.slice(0, dwukropek).trim().toLowerCase(),
                wartosc: d.slice(dwukropek + 1),
                tekst: d,
            };
        });

        // Kolorowe (ciemne lub nasycone) tło z własnym kolorem tekstu w tej
        // samej regule — przycisk, kafel: zostawiamy oba kolory.
        var wlasneTlo = false;
        var maTekst = false;
        lista.forEach(function (d) {
            var rola = rolaWlasciwosci(d.prop);
            if (rola === "tekst" && d.prop === "color") maTekst = true;
            if (rola === "tlo") {
                zamienKolory(d.wartosc, function (k) {
                    // Ciemne albo nasycone średniej jasności (przycisk). Jasne
                    // podbarwienia (komunikaty) mają w HSL wysokie nasycenie,
                    // ale to zwykłe jasne tło do przeliczenia.
                    var hsl = rgbNaHsl(k.rgb);
                    var nasycone = hsl[1] > 0.5 && hsl[2] > 0.25 && hsl[2] < 0.75;
                    if (k.a > 0.5 && (!jasny(k) || nasycone)) wlasneTlo = true;
                    return null;
                });
            }
        });
        var nieruszaj = ciemny && wlasneTlo && maTekst;

        var przezroczystosc =
            tloTresci !== "pelne" &&
            !tylkoHtmlBody(selektor) &&
            !RE_ZAWSZE_PELNE.test(selektor);

        var zmiana = false;
        var wynik = lista.map(function (d) {
            var rola = rolaWlasciwosci(d.prop);
            if (!rola) return d.tekst;
            var nowa = zamienKolory(d.wartosc, function (k) {
                var wyj = k;
                var zmienione = false;
                if (rola === "tlo" && przezroczystosc && jasny(k) && rgbNaHsl(k.rgb)[1] < 0.3 &&
                    rgbNaHsl(k.rgb)[2] > 0.93) {
                    if (ciemny) wyj = naCiemny(k, rola) || k;
                    if (tloTresci === "przezroczyste") return { rgb: wyj.rgb, a: 0 };
                    return { rgb: wyj.rgb, a: Math.min(wyj.a, 0.75) };
                }
                if (ciemny && !nieruszaj) {
                    var c = naCiemny(k, rola);
                    if (c) {
                        wyj = c;
                        zmienione = true;
                    }
                }
                return zmienione ? wyj : null;
            });
            if (nowa !== d.wartosc) {
                zmiana = true;
                return d.prop + ":" + nowa;
            }
            return null;
        });
        if (!zmiana) return null;
        return { pelne: wynik.map(function (w, i) { return w === null ? lista[i].tekst : w; }),
                 zmienione: wynik.filter(function (w) { return w !== null; }) };
    }

    function przetworzWezly(wezly, ciemny, tloTresci, tylkoZmiany) {
        var wyjscie = [];
        wezly.forEach(function (w) {
            if (w.surowy !== undefined) {
                if (!tylkoZmiany) wyjscie.push(w.surowy);
                return;
            }
            if (w.at !== undefined) {
                // Wydruk zostaje jasny i pełny.
                if (/\bprint\b/i.test(w.at)) {
                    if (!tylkoZmiany) wyjscie.push(w.at + "{" + przetworzWezly(w.dzieci, false, "pelne", false) + "}");
                    return;
                }
                var srodek = przetworzWezly(w.dzieci, ciemny, tloTresci, tylkoZmiany);
                if (srodek || !tylkoZmiany) wyjscie.push(w.at + "{" + srodek + "}");
                return;
            }
            var p = przetworzRegule(w.selektor, w.deklaracje, ciemny, tloTresci);
            if (tylkoZmiany) {
                if (p) wyjscie.push(w.selektor + "{" + p.zmienione.join(";") + "}");
            } else {
                wyjscie.push(w.selektor + "{" + (p ? p.pelne.join(";") : w.deklaracje) + "}");
            }
        });
        return wyjscie.join("");
    }

    // Skompilowany CSS motywu → CSS z trybem kolorów i tłem treści z konfiga.
    // `opcje.trybPodgladu` wymusza jasny/ciemny (podgląd trybu automatycznego).
    function przetworzCss(css, konfig, opcje) {
        opcje = opcje || {};
        var k = normalizuj(konfig);
        var tryb = opcje.trybPodgladu || k.tryb_kolorow;
        css = css.replace(/^\uFEFF/, "");
        if (tryb === "jasny" && k.tlo_tresci === "pelne") return css;
        var wezly = parsujCss(css);
        if (tryb === "automatyczny") {
            var jasnyCss = przetworzWezly(wezly, false, k.tlo_tresci, false);
            var ciemnyCss = przetworzWezly(wezly, true, k.tlo_tresci, true);
            return jasnyCss + "@media (prefers-color-scheme: dark){" + ciemnyCss + "}";
        }
        return przetworzWezly(wezly, tryb === "ciemny", k.tlo_tresci, false);
    }

    return {
        WERSJA: WERSJA,
        SCHEMAT: SCHEMAT,
        DOMYSLNE: DOMYSLNE,
        GOTOWE: GOTOWE,
        CZCIONKI: CZCIONKI,
        WLASNA: WLASNA,
        PROG_KONTRASTU: PROG_KONTRASTU,
        MAKS_DLUGOSC_OBRAZU: MAKS_DLUGOSC_OBRAZU,
        kontrast: kontrast,
        tekstNaTle: tekstNaTle,
        przyciemnijDoKontrastu: przyciemnijDoKontrastu,
        normalizuj: normalizuj,
        waliduj: waliduj,
        wylicz: wylicz,
        doScss: doScss,
        przetworzCss: przetworzCss,
        czytajKolor: czytajKolor,
    };
});
