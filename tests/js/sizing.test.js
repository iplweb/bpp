// Testy normalizacji metryki na średnicę węzła + wyboru metryki.
import { describe, test, expect } from "vitest";
import {
    ROZMIAR_NEUTRALNY,
    srednica,
    wartoscMetryki,
} from "../../src/powiazania_autorow/static/powiazania_autorow/js/powiazania/sizing.js";

describe("srednica", () => {
    test("wartość 0 → minimalna średnica 12", () => {
        expect(srednica(0, 100)).toBe(12);
    });

    test("wartość = max → 46 (12 + 34)", () => {
        expect(srednica(100, 100)).toBeCloseTo(46);
    });

    test("clamp górny: powyżej max nie przekracza 46", () => {
        expect(srednica(400, 100)).toBe(46);
    });

    test("skala pierwiastkowa: 1/4 max → 12 + 34*0.5 = 29", () => {
        expect(srednica(25, 100)).toBeCloseTo(29);
    });

    test("monotoniczność: większa wartość → nie mniejsza średnica", () => {
        expect(srednica(10, 100)).toBeLessThan(srednica(40, 100));
    });
});

describe("wartoscMetryki", () => {
    const node = {
        data: (k) => ({ if_sum: 5, pk_sum: 7, works: 9 }[k]),
    };

    test("metryka 'if' → if_sum", () => {
        expect(wartoscMetryki({ metryka: "if" }, node)).toBe(5);
    });

    test("metryka 'pk' → pk_sum", () => {
        expect(wartoscMetryki({ metryka: "pk" }, node)).toBe(7);
    });

    test("domyślnie → works", () => {
        expect(wartoscMetryki({ metryka: "prace" }, node)).toBe(9);
    });

    test("brak danych → 0", () => {
        const pusty = { data: () => undefined };
        expect(wartoscMetryki({ metryka: "if" }, pusty)).toBe(0);
    });
});

describe("autor spoza uczelni (FD#640)", () => {
    const obcy = {
        data: (k) => ({
            spoza_uczelni: true, works: 0, if_sum: 0, pk_sum: 0,
        }[k]),
    };

    test("brak metryki niezależnie od wybranej (null)", () => {
        for (const metryka of ["works", "if", "pk"]) {
            expect(wartoscMetryki({ metryka }, obcy)).toBeNull();
        }
    });

    test("null → stały, neutralny rozmiar (nie najmniejsze kółko)", () => {
        expect(srednica(null, 100)).toBe(ROZMIAR_NEUTRALNY);
        expect(srednica(null, 100)).toBeGreaterThan(srednica(0, 100));
    });
});
