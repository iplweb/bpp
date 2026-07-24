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

describe("zgłoszenia bez użytecznego stack trace'u — pomijamy", () => {
    test("brak ramek w ogóle (Rollbar #444: błąd ładowania <link>, '{}')", () => {
        const p = {
            body: { trace: { exception: { class: "(unknown)", message: "{}" }, frames: [] } },
        };
        expect(czyPominac(p, ORIGIN)).toBe(true);
    });

    test("filename '(unknown)' nie jest ścieżką", () => {
        expect(czyPominac(payloadZRamkami(["(unknown)"]), ORIGIN)).toBe(true);
    });

    test("filename będący komunikatem błędu (Rollbar #502: Chrome 64)", () => {
        const p = payloadZRamkami(["SyntaxError: Unexpected token ="], {
            class: "SyntaxError",
            message: "Unexpected token =",
        });
        expect(czyPominac(p, ORIGIN)).toBe(true);
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
