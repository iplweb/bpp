// @vitest-environment jsdom
//
// Filtr `checkIgnore` dla frontendowego Rollbara: odsiewa zgłoszenia, na
// których nie da się nic zrobić — błędy z obcych skryptów (widget dostępności
// UserWay na CDN) oraz zdarzenia bez użytecznego stack trace'u.
//
// rollbar-filters.js jest ZWYKŁYM skryptem (nie modułem), bo rollbar.html
// ładuje go wcześnie w <head> — `type="module"` odroczyłoby wykonanie i część
// błędów z czasu ładowania strony uciekłaby przed inicjalizacją. Dlatego
// ładujemy go tu dla efektu ubocznego i czytamy z `window`, tak samo jak
// robi to djangoql-locate.test.js.
import { describe, test, expect, beforeAll } from "vitest";

let czyPominac;

beforeAll(async () => {
    await import("../../src/bpp/static/bpp/js/rollbar-filters.js");
    ({ czyPominac } = window.bppRollbarFilters);
});

const ORIGIN = "https://bpp.piwet.pulawy.pl";

function payloadZRamkami(filenames, exception) {
    return {
        body: {
            trace: {
                exception: exception || { class: "TypeError", message: "x" },
                frames: filenames.map((f) => ({ filename: f })),
            },
        },
    };
}

describe("błędy z naszego kodu — raportujemy", () => {
    test("ramka z naszego origin", () => {
        const p = payloadZRamkami([`${ORIGIN}/static/bpp/js/core.js`]);
        expect(czyPominac(p, ORIGIN)).toBe(false);
    });

    test("ścieżka względna też jest nasza", () => {
        expect(czyPominac(payloadZRamkami(["/static/bpp/js/core.js"]), ORIGIN)).toBe(
            false,
        );
    });

    test("mieszanka: nasza ramka w stosie obok obcej", () => {
        const p = payloadZRamkami([
            "https://cdn.userway.org/widgetapp/widget.js",
            `${ORIGIN}/static/bpp/js/core.js`,
        ]);
        expect(czyPominac(p, ORIGIN)).toBe(false);
    });
});

describe("obce skrypty — pomijamy", () => {
    test("widget UserWay (Rollbar #1477: lookbehind w starym Safari)", () => {
        const p = payloadZRamkami(
            ["https://cdn.userway.org/widgetapp/2026-07-07/widget_app_base.js"],
            {
                class: "SyntaxError",
                message: "invalid group specifier name",
            },
        );
        expect(czyPominac(p, ORIGIN)).toBe(true);
    });

    test("dowolny inny obcy host", () => {
        const p = payloadZRamkami(["https://example.com/tracker.js"]);
        expect(czyPominac(p, ORIGIN)).toBe(true);
    });
});

describe("zgłoszenia bez lokalizacji I bez treści — pomijamy", () => {
    test("Rollbar #444: błąd ładowania <link>, class '(unknown)', message '{}'", () => {
        const p = {
            body: { trace: { exception: { class: "(unknown)", message: "{}" }, frames: [] } },
        };
        expect(czyPominac(p, ORIGIN)).toBe(true);
    });

    test("filename '(unknown)' przy pustym opisie też pomijamy", () => {
        const p = payloadZRamkami(["(unknown)"], { class: "(unknown)", message: "" });
        expect(czyPominac(p, ORIGIN)).toBe(true);
    });

    test("ALE filename '(unknown)' z konkretnym wyjątkiem → raportuj", () => {
        // Brak lokalizacji nie znaczy brak informacji: klasa i komunikat
        // wystarczą, żeby zacząć szukać. Za szeroka reguła zjadałaby nasze
        // błędy — patrz sekcja niżej.
        const p = payloadZRamkami(["(unknown)"], {
            class: "TypeError",
            message: "x is not a function",
        });
        expect(czyPominac(p, ORIGIN)).toBe(false);
    });
});

describe("bezpieczeństwo filtra — w razie wątpliwości raportuj", () => {
    test("payload bez body nie wywala filtra i NIE wycisza", () => {
        expect(czyPominac({}, ORIGIN)).toBe(false);
        expect(czyPominac(null, ORIGIN)).toBe(false);
        expect(czyPominac(undefined, ORIGIN)).toBe(false);
    });

    test("trace_chain (wyjątki łańcuchowe) jest obsługiwany", () => {
        const p = {
            body: {
                trace_chain: [
                    { frames: [{ filename: `${ORIGIN}/static/a.js` }] },
                    { frames: [{ filename: "https://cdn.userway.org/w.js" }] },
                ],
            },
        };
        expect(czyPominac(p, ORIGIN)).toBe(false);
    });

    test("trace_chain wyłącznie z obcych skryptów jest pomijany", () => {
        const p = {
            body: {
                trace_chain: [{ frames: [{ filename: "https://cdn.userway.org/w.js" }] }],
            },
        };
        expect(czyPominac(p, ORIGIN)).toBe(true);
    });
});

// Kształty payloadów zmierzone na rollbar.js 3.1.0 (nie wymyślone):
// ręczny log daje `body.message` BEZ `trace`/`frames`, a odrzucona obietnica
// z reason innym niż Error daje ramkę z filename "(unknown)".
describe("nasze błędy, które wcześniej filtr zjadał", () => {
    test("ręczny Rollbar.error('...') — body.message, zero ramek", () => {
        const p = { body: { message: { body: "coś poszło nie tak" }, telemetry: [] } };
        expect(czyPominac(p, ORIGIN)).toBe(false);
    });

    test("ostrzeżenie samego Rollbara o rate-limicie (też body.message)", () => {
        const p = {
            body: { message: { body: "maxItems has been hit. Ignoring errors..." } },
        };
        expect(czyPominac(p, ORIGIN)).toBe(false);
    });

    test("odrzucona obietnica z reason innym niż Error", () => {
        const p = {
            body: {
                trace: {
                    exception: { class: "UnhandledRejection", message: "{...}" },
                    frames: [{ filename: "(unknown)" }],
                },
            },
        };
        expect(czyPominac(p, ORIGIN)).toBe(false);
    });

    test("SyntaxError bez ścieżki NIE jest wyciszany — to może być nasz bundle", () => {
        // Rollbar #502. Przeglądarka ujawnia treść błędu parsowania tylko dla
        // skryptów same-origin (obce bez CORS dają "Script error."), więc
        // konkretny komunikat sugeruje, że któryś NASZ statyk się nie parsuje.
        const p = payloadZRamkami(["SyntaxError: Unexpected token ="], {
            class: "SyntaxError",
            message: "Unexpected token =",
        });
        expect(czyPominac(p, ORIGIN)).toBe(false);
    });

    test("ale SyntaxError z obcego skryptu nadal wyciszamy (#1477)", () => {
        const p = payloadZRamkami(["https://cdn.userway.org/widgetapp/w.js"], {
            class: "SyntaxError",
            message: "invalid group specifier name",
        });
        expect(czyPominac(p, ORIGIN)).toBe(true);
    });
});

describe("odporność filtra", () => {
    test("brak origin (stara przeglądarka bez location.origin) → raportuj", () => {
        expect(czyPominac(payloadZRamkami(["https://cdn.userway.org/w.js"]), undefined)).toBe(
            false,
        );
    });

    test("host podszywający się pod nasz nie uchodzi za nasz", () => {
        const p = payloadZRamkami([`${ORIGIN}.evil.example/x.js`]);
        expect(czyPominac(p, ORIGIN)).toBe(true);
    });
});
