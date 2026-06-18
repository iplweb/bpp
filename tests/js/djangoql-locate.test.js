// @vitest-environment jsdom
//
// djangoql-admin.js to standalone skrypt Media (globalne IIFE) — nie da się
// go importować jako moduł. Ładujemy go dla efektu ubocznego w jsdom: bez
// window.DjangoQL IIFE wystawia czyste helpery na window.bppDjangoQLAdmin
// i wychodzi przed wire()/DOMReady. Testujemy te helpery.
import { describe, test, expect, beforeAll } from "vitest";

let locateValue;
let lineColFromOffset;

beforeAll(async () => {
    await import("../../src/bpp/static/bpp/js/djangoql-admin.js");
    ({ locateValue, lineColFromOffset } = window.bppDjangoQLAdmin);
});

describe("lineColFromOffset (0-based offset → 1-based line/column)", () => {
    test("początek pierwszej linii", () => {
        expect(lineColFromOffset("abc", 0)).toEqual({ line: 1, column: 1 });
    });

    test("offset w pierwszej linii (bez \\n)", () => {
        expect(lineColFromOffset("abc", 2)).toEqual({ line: 1, column: 3 });
    });

    test("offset w drugiej linii liczy kolumnę od \\n", () => {
        // "ab\ncd": offset 4 = 'd' → linia 2, kolumna 2
        expect(lineColFromOffset("ab\ncd", 4)).toEqual({ line: 2, column: 2 });
    });

    test("tuż po \\n → kolumna 1 nowej linii", () => {
        expect(lineColFromOffset("ab\ncd", 3)).toEqual({ line: 2, column: 1 });
    });
});

describe("locateValue (offset tokenu z granicami słownymi)", () => {
    test("znajduje samodzielny token", () => {
        expect(locateValue("rok = 2020", "2020")).toBe(6);
    });

    test("NIE łapie podłańcucha wewnątrz dłuższego słowa", () => {
        // "title" nie powinno trafić w "subtitle"
        expect(locateValue("subtitle = 1 and title = 2", "title")).toBe(17);
    });

    test("token po kropce (ścieżka pola) → fallback do indexOf", () => {
        // regex wyklucza kropkę z lewej, więc 'rok' w 'autor.rok' idzie fallbackiem
        expect(locateValue("autor.rok = 1", "rok")).toBe(6);
    });

    test("brak wartości → -1", () => {
        expect(locateValue("rok = 1", "niema")).toBe(-1);
    });
});
