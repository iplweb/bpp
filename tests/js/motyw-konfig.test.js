// Moduł motywów z konfiguracji: walidacja kontrastu i generowanie SCSS.
// Ostatnie testy kompilują prawdziwy motyw dart-sassem — tak samo, jak
// task Grunta `motywy` i konfigurator w przeglądarce.
import { describe, test, expect } from "vitest";
import { createRequire } from "node:module";
import * as sass from "sass";

const require = createRequire(import.meta.url);
const M = require("../../src/bpp/static/bpp/js/motyw-konfig.js");

const PEŁNY = {
    wersja: 1,
    nazwa: "uczelnia-x",
    opis: "Granatowy",
    kolor_naglowka: "#12203d",
    kolor_glowny: "#284fab",
    kolor_dodatkowy: "#b99a4b",
    tlo_strony: "szare",
    czcionka: "inter",
    rozmiar_tekstu: "wiekszy",
    naglowki: "pogrubione",
    ikony_w_menu: false,
    menu_zaokraglone: false,
    zaokraglenia: "male",
    przyciski_styl: "obrys",
    przyciski_kolory: "jednolite",
    cien_menu: "wyrazny",
    kolor_userway: "#aa0000",
    cien_userway: "delikatny",
};

const PIKSEL =
    "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII=";

function kompiluj(konfig) {
    return sass.compileString(M.doScss(konfig), {
        loadPaths: ["src/bpp/static/scss", "node_modules/foundation-sites/scss"],
        style: "compressed",
        silenceDeprecations: ["global-builtin", "if-function", "import"],
        quietDeps: true,
    }).css;
}

describe("kontrast", () => {
    test("biały na czarnym to 21:1 (z dokładnością do kolorów Foundation)", () => {
        expect(M.kontrast("#ffffff", "#000000")).toBeCloseTo(21, 5);
    });

    test("tekst na tle: biały na ciemnym, czarny na jasnym", () => {
        expect(M.tekstNaTle("#12203d")).toBe("#fefefe");
        expect(M.tekstNaTle("#ffae00")).toBe("#0a0a0a");
    });

    test("przyciemnianie daje kolor czytelny na wszystkich tłach", () => {
        const tla = ["#fefefe", "#f1f5f9"];
        const wynik = M.przyciemnijDoKontrastu("#ffae00", tla);
        for (const t of tla) {
            expect(M.kontrast(wynik, t)).toBeGreaterThanOrEqual(4.5);
        }
    });
});

describe("waliduj", () => {
    test("pełny poprawny konfig nie ma błędów", () => {
        expect(M.waliduj(PEŁNY)).toEqual([]);
    });

    test("domyślne ustawienia są poprawne (poza nazwą)", () => {
        expect(M.waliduj({}, { bezNazwy: true })).toEqual([]);
    });

    test("za jasny kolor główny: błąd z poprawką, która przechodzi", () => {
        const bledy = M.waliduj({ ...PEŁNY, kolor_glowny: "#ffae00" });
        expect(bledy).toHaveLength(1);
        expect(bledy[0].pole).toBe("kolor_glowny");
        expect(
            M.waliduj({ ...PEŁNY, kolor_glowny: bledy[0].poprawka }),
        ).toEqual([]);
    });

    test.each([
        ["kolor_naglowka", "granat"],
        ["czcionka", "comic-sans"],
        ["ikony_w_menu", "tak"],
        ["nazwa", "Uczelnia X"],
        ["nieznane_pole", 1],
        ["wersja", 99],
    ])("odrzuca złą wartość pola %s", (pole, wartosc) => {
        const bledy = M.waliduj({ ...PEŁNY, [pole]: wartosc });
        expect(bledy.map((b) => b.pole)).toContain(pole);
    });
});

describe("czcionki", () => {
    test("czcionka z internetu: domyślnie z Bunny Fonts, @import na początku", () => {
        const scss = M.doScss({ ...PEŁNY, czcionka: "web:Lora" });
        const pierwszaRegula = scss.split("\n").find((l) => l && !l.startsWith("//"));
        expect(pierwszaRegula).toBe(
            '@import url("https://fonts.bunny.net/css?family=lora:400,600,700&display=swap");',
        );
    });

    test("Google Fonts i dwie różne czcionki w jednym adresie", () => {
        const w = M.wylicz({
            ...PEŁNY,
            czcionka: "web:Montserrat",
            czcionka_naglowkow: "web:Roboto Slab",
            zrodlo_czcionek: "google",
        });
        expect(w.czcionkiWebUrl).toBe(
            "https://fonts.googleapis.com/css?family=Montserrat:400,600,700|Roboto+Slab:400,600,700&display=swap",
        );
        expect(w.czcionkaNaglowkow.rodzina).toMatch(/^'Roboto Slab', Georgia/);
    });

    test("lokalna czcionka nie odpytuje internetu", () => {
        expect(M.wylicz(PEŁNY).czcionkiWebUrl).toBeNull();
    });

    test("własna czcionka z Google Fonts wymaga poprawnej nazwy", () => {
        const k = { ...PEŁNY, czcionka: M.WLASNA, czcionka_wlasna: "" };
        expect(M.waliduj(k).map((b) => b.pole)).toContain("czcionka_wlasna");
        const ok = { ...k, czcionka_wlasna: "Red Hat Display" };
        expect(M.waliduj(ok)).toEqual([]);
        expect(M.wylicz(ok).czcionkiWebUrl).toContain("red-hat-display");
    });
});

describe("UserWay i obrazek tła", () => {
    test("kolor UserWay pusty = kolor główny", () => {
        expect(M.wylicz({ ...PEŁNY, kolor_userway: "" }).kolorUserway).toBe("#284fab");
    });

    test("za jasny kolor UserWay: błąd z poprawką 3:1", () => {
        const bledy = M.waliduj({ ...PEŁNY, kolor_userway: "#ffee88" });
        expect(bledy.map((b) => b.pole)).toEqual(["kolor_userway"]);
        expect(M.kontrast("#fefefe", bledy[0].poprawka)).toBeGreaterThanOrEqual(3);
    });

    test.each([
        "http://example.com/a.png",
        "data:text/html;base64,PGI+",
        "data:image/png;base64,\"); background: red",
    ])("odrzuca niebezpieczny obrazek %s", (obraz) => {
        expect(M.waliduj({ ...PEŁNY, tlo_obraz: obraz }).map((b) => b.pole)).toContain(
            "tlo_obraz",
        );
    });

    test("za duży obrazek", () => {
        const duzy = "data:image/png;base64," + "A".repeat(M.MAKS_DLUGOSC_OBRAZU);
        expect(M.waliduj({ ...PEŁNY, tlo_obraz: duzy }).map((b) => b.pole)).toContain(
            "tlo_obraz",
        );
    });
});

describe("przyciski, komunikaty, kafle, logo", () => {
    test("różne kolory przycisków: każdy rodzaj z konfiguracji", () => {
        const w = M.wylicz({
            ...PEŁNY,
            przyciski_kolory: "kolorowe",
            kolor_przycisku_sukces: "#00aa00",
            kolor_przycisku_alert: "#990000",
        });
        expect(w.przyciski.success).toBe("#00aa00");
        expect(w.przyciski.alert).toBe("#990000");
        expect(w.przyciski.secondary).toBe(PEŁNY.kolor_dodatkowy);
    });

    test("tekst komunikatu czytelny na jego tle, także dla jasnego koloru", () => {
        const w = M.wylicz({ ...PEŁNY, kolor_komunikatu_ostrzezenie: "#ffee00" });
        for (const typ of Object.keys(w.komunikaty)) {
            const k = w.komunikaty[typ];
            expect(M.kontrast(k.tekst, k.tlo)).toBeGreaterThanOrEqual(4.5);
        }
    });

    test("kafle wypełnione i logo w kolorze napisów się kompilują", () => {
        const css = kompiluj({ ...PEŁNY, kafle_styl: "wypelnione", logo_bpp: "jak_napisy" });
        expect(css).toMatch(/\.uczelnia__tile\{background:#284fab/);
        expect(css).toContain("brightness(0) invert(1) !important");
    }, 30000);
});

describe("przetworzCss — tryb ciemny i tło treści", () => {
    const CSS =
        '@import"x";a{color:#1779ba}body{background:#fefefe;color:#0a0a0a}' +
        ".card{background-color:white;border:1px solid #e6e6e6}" +
        ".button.warning{background-color:#ffae00;color:#0a0a0a}" +
        '.x{background:url("data:image/png;base64,white") white}' +
        ".top-bar .menu{background:#fff}" +
        "@media print{a{color:#000}}";

    test("tryb jasny i pełne tło: bez zmian (poza BOM)", () => {
        expect(M.przetworzCss("\uFEFF" + CSS, { tryb_kolorow: "jasny" })).toBe(CSS);
    });

    test("ciemny: jasne tła ciemne, ciemny tekst jasny, przycisk i wydruk bez zmian", () => {
        const css = M.przetworzCss(CSS, { tryb_kolorow: "ciemny" });
        expect(css).toContain("body{background:#1a1a1a;color:#ececec}");
        expect(css).toContain(".button.warning{background-color:#ffae00;color:#0a0a0a}");
        expect(css).toContain("@media print{a{color:#000}}");
        expect(css).toContain('url("data:image/png;base64,white")');
        expect(css.startsWith('@import"x";')).toBe(true);
    });

    test("tekst w kolorze głównym zostaje w odcieniu, ale jaśnieje", () => {
        const css = M.przetworzCss(CSS, { tryb_kolorow: "ciemny" });
        const kolor = /a\{color:(#[0-9a-f]{6})\}/.exec(css)[1];
        expect(M.kontrast(kolor, "#1a1a1a")).toBeGreaterThanOrEqual(4.5);
    });

    test("automatyczny: jasny CSS + wariant w prefers-color-scheme", () => {
        const css = M.przetworzCss(CSS, { tryb_kolorow: "automatyczny" });
        expect(css.startsWith(CSS)).toBe(true);
        expect(css).toContain("@media (prefers-color-scheme: dark){");
        expect(css).toContain("body{background:#1a1a1a;color:#ececec}");
    });

    test("zmienne --bpp-* (style spoza CSS motywu) tylko w wariancie ciemnym", () => {
        expect(M.przetworzCss(CSS, { tryb_kolorow: "jasny", tlo_tresci: "przezroczyste" }))
            .not.toContain("--bpp-tlo-pow");
        const ciemny = M.przetworzCss(CSS, { tryb_kolorow: "ciemny" });
        const tlo = /--bpp-tlo-pow:(#[0-9a-f]{6})/.exec(ciemny)[1];
        const tekst = /--bpp-tekst:(#[0-9a-f]{6})/.exec(ciemny)[1];
        expect(M.kontrast(tekst, tlo)).toBeGreaterThanOrEqual(4.5);
        expect(ciemny).toMatch(/--bpp-akcent:#[0-9a-f]{6}/);
        // Automatyczny: definicje wewnątrz prefers-color-scheme, nie w jasnym CSS.
        const auto = M.przetworzCss(CSS, { tryb_kolorow: "automatyczny" });
        const media = auto.indexOf("@media (prefers-color-scheme: dark){");
        expect(auto.indexOf("--bpp-tlo-pow")).toBeGreaterThan(media);
    });

    test("przezroczyste tło treści: karty tak, menu i body nie", () => {
        const css = M.przetworzCss(CSS, { tryb_kolorow: "jasny", tlo_tresci: "przezroczyste" });
        expect(css).toContain(".card{background-color:rgba(255,255,255,0)");
        expect(css).toContain(".top-bar .menu{background:#fff}");
        expect(css).toContain("body{background:#fefefe");
    });

    test("prawdziwy motyw w trybie automatycznym się kompiluje", () => {
        const k = { ...PEŁNY, tryb_kolorow: "automatyczny", tlo_tresci: "polprzezroczyste" };
        const css = M.przetworzCss(kompiluj(k), k);
        expect(css).toContain("@media (prefers-color-scheme: dark){");
    }, 30000);
});

describe("pasek menu: napis i logo uczelni", () => {
    test("własny skrót zamiast „BPP”", () => {
        const css = kompiluj({ ...PEŁNY, napis_w_pasku: "wlasny", napis_wlasny: "Kaer Morhen" });
        expect(css).toContain(".top-bar .bpp-strona-glowna .bpp-napis{display:none}");
        expect(css).toContain('.top-bar .bpp-strona-glowna::after{content:"Kaer Morhen"');
    }, 30000);

    test.each(['a"b', "a\\b", "", "x".repeat(21), "<b>"])(
        "odrzuca niebezpieczny albo pusty skrót %j",
        (napis) => {
            const bledy = M.waliduj({ ...PEŁNY, napis_w_pasku: "wlasny", napis_wlasny: napis });
            expect(bledy.map((b) => b.pole)).toContain("napis_wlasny");
        },
    );

    test("logo uczelni o wyliczonej szerokości", () => {
        const css = kompiluj({
            ...PEŁNY,
            logo_uczelni: PIKSEL,
            logo_uczelni_szerokosc: 70,
            logo_bpp: "ukryte",
        });
        expect(css).toMatch(/\.top-bar \.bpp-strona-glowna::before\{[^}]*width:70px/);
        expect(css).toContain(".top-bar .bpp-logo{display:none !important}");
    }, 30000);

    test("za duże logo uczelni", () => {
        const duze = "data:image/png;base64," + "A".repeat(200 * 1024);
        expect(M.waliduj({ ...PEŁNY, logo_uczelni: duze }).map((b) => b.pole)).toContain(
            "logo_uczelni",
        );
    });
});

describe("gotowe motywy i wykresy", () => {
    test("każdy gotowy motyw ma tylko znane pola", () => {
        for (const g of M.GOTOWE) {
            const nieznane = M.waliduj(g.konfig, { bezNazwy: true }).filter((b) =>
                b.komunikat.startsWith("Nieznane"),
            );
            expect(nieznane).toEqual([]);
        }
    });

    // Dotychczasowe motywy app-* odwzorowują stare kolory i część z nich
    // celowo nie spełnia wymogu kontrastu — tych nie sprawdzamy.
    const NOWE = M.GOTOWE.filter((g) => !g.klucz.startsWith("app-"));

    test("klucze gotowych motywów są unikalne", () => {
        const klucze = M.GOTOWE.map((g) => g.klucz);
        expect(new Set(klucze).size).toBe(klucze.length);
    });

    test.each(NOWE.map((g) => [g.klucz, g]))(
        "gotowy motyw %s przechodzi walidację (z kontrastem)",
        (klucz, g) => {
            expect(M.waliduj(g.konfig, { bezNazwy: true })).toEqual([]);
        },
    );

    test.each(NOWE.filter((g) => g.klucz !== "domyslny").map((g) => [g.klucz, g]))(
        "gotowy motyw %s nie dostaje stylu dotychczasowego i się kompiluje",
        (klucz, g) => {
            expect(g.konfig.kolor_naglowka).not.toBe("#e6e6e6");
            const css = M.przetworzCss(kompiluj(g.konfig), M.normalizuj(g.konfig));
            expect(css).toContain(".top-bar");
        },
        30000,
    );

    test("motywy dotychczasowe: jasne i kanciaste", () => {
        const zielony = M.GOTOWE.find((g) => g.klucz === "app-green");
        expect(zielony.konfig.tryb_kolorow).toBe("jasny");
        expect(zielony.konfig.zaokraglenia).toBe("brak");
    });

    test("za jasny kolor wykresów: błąd z poprawką 3:1", () => {
        const bledy = M.waliduj({ ...PEŁNY, kolor_wykresow: "#ffee99" });
        expect(bledy.map((b) => b.pole)).toEqual(["kolor_wykresow"]);
        expect(M.kontrast(bledy[0].poprawka, "#fefefe")).toBeGreaterThanOrEqual(3);
    });

    test("wykresy w kolorze z konfiguracji", () => {
        const css = kompiluj({ ...PEŁNY, kolor_wykresow: "#8a1538" });
        expect(css).toMatch(/\.autor-page__wykres-linia\{stroke:#8a1538\}/);
        expect(css).toContain("button:not(.close-button):not(.bpp-support-button):not(.autor-page__slupek)");
    }, 30000);
});

describe("doScss", () => {
    test("jednolite przyciski: wszystko w kolorze głównym poza alertem", () => {
        const w = M.wylicz(PEŁNY);
        expect(w.przyciski.secondary).toBe("#284fab");
        expect(w.przyciski.alert).not.toBe("#284fab");
    });

    test("napisy przycisków z obrysem są czytelne na tle strony", () => {
        const w = M.wylicz({ ...PEŁNY, przyciski_kolory: "kolorowe" });
        for (const kolor of Object.values(w.tekstyPrzyciskow)) {
            expect(M.kontrast(kolor, w.tlo)).toBeGreaterThanOrEqual(4.5);
        }
    });
});

describe("kompilacja SCSS", () => {
    test("domyślny konfig", () => {
        const css = kompiluj({});
        expect(css).toContain(".top-bar");
        expect(css).not.toContain("@font-face");
    }, 30000);

    test("pełny konfig: czcionka, brak ikon w menu, przyciski z obrysem", () => {
        const css = kompiluj(PEŁNY);
        expect(css).toContain("inter-600-latin-ext.woff2");
        expect(css).toMatch(/\.top-bar \[class\^=fi-\][^}]*display:none ?!important/);
        expect(css).toContain("background-color:rgba(0,0,0,0)");
    }, 30000);

    test("rogi, cień menu, UserWay i obrazek tła", () => {
        const css = kompiluj({
            ...PEŁNY,
            zaokraglenia: "pigulka",
            tlo_obraz: PIKSEL,
            tlo_pozycja: "lewy-gorny",
        });
        expect(css).toContain("border-radius:999px !important");
        expect(css).toMatch(/nav\.sticky-header\{[^}]*box-shadow:0 3px 10px rgba\(0, ?0, ?0, ?0?\.2\)/);
        expect(css).toMatch(/#userwayAccessibilityIcon\.uai[^{]*\{background-color:#a00 ?!important/);
        expect(css).toMatch(/html::after\{[^}]*background-position:left top/);
        expect(css).toContain("--bpp-userway-kolor: #aa0000");
    }, 30000);

    test.each([
        ["brak", "0"],
        ["male", ".375rem"],
        ["duze", ".75rem"],
        ["pigulka", ".75rem"],
    ])("rogi %s: zakładka „Pomoc” ma zawsze proste dolne rogi", (z, gora) => {
        const css = kompiluj({ ...PEŁNY, zaokraglenia: z });
        expect(css).toContain(
            ".bpp-support-button{border-radius:" + gora + " " + gora + " 0 0 !important}",
        );
        // Wybrane zaokrąglenie działa mimo `$global-radius: 6px` w _callouts.scss.
        expect(css).toContain("[class*=__card]{border-radius:" + gora + " !important}");
    }, 30000);

    test.each(["pelne", "cien"])("styl przycisków %s się kompiluje", (styl) => {
        expect(kompiluj({ ...PEŁNY, przyciski_styl: styl })).toContain(".button");
    }, 30000);
});

describe("własny kolor tła strony", () => {
    test("trafia do $body-background", () => {
        const k = M.normalizuj({ tlo_strony: "wlasne", kolor_tla_strony: "#f5f1e8" });
        expect(M.doScss(k, {})).toContain("$body-background: #f5f1e8;");
    });

    test("za ciemne tło to błąd z jaśniejszą poprawką", () => {
        const k = M.normalizuj({ tlo_strony: "wlasne", kolor_tla_strony: "#333333" });
        const blad = M.waliduj(k, { bezNazwy: true }).find((b) => b.pole === "kolor_tla_strony");
        expect(blad).toBeTruthy();
        const poprawione = M.normalizuj({ ...k, kolor_tla_strony: blad.poprawka });
        expect(
            M.waliduj(poprawione, { bezNazwy: true }).some((b) => b.pole === "kolor_tla_strony"),
        ).toBe(false);
    });
});
