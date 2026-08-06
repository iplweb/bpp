// Podswietlanie frazy w opisie bibliograficznym (HTML) — wylacznie w
// segmentach TEKSTOWYCH. Po dodaniu <span lang="en"> (WCAG 3.1.2) naiwny
// regex na calym stringu podswietlal fragmenty ATRYBUTOW: fraza "en"
// trafiala w lang="en" i wstawiala <mark> w srodek znacznika, co przy
// .html(text) daje zepsuty markup.

import { describe, it, expect, beforeAll } from "vitest";
import { readFileSync } from "fs";
import { resolve } from "path";

let highlight;

beforeAll(() => {
    const zrodlo = readFileSync(
        resolve(
            __dirname,
            "../../src/bpp/static/bpp/js/related-records-highlight.js"
        ),
        "utf-8"
    );
    const window = {};
    new Function("window", zrodlo)(window);
    highlight = window.bppHighlightOutsideTags;
});

describe("bppHighlightOutsideTags", () => {
    it("podswietla fraze w tekscie", () => {
        expect(highlight("Effects of X", "effects")).toBe(
            '<mark class="bpp-highlight">Effects</mark> of X'
        );
    });

    it("NIE podswietla frazy wystepujacej tylko w atrybucie", () => {
        const html = '<span lang="en">Wpływ X</span>';
        expect(highlight(html, "en")).toBe(html);
    });

    it("NIE podswietla nazwy atrybutu", () => {
        const html = '<span lang="pl">Tytuł</span>';
        expect(highlight(html, "lang")).toBe(html);
    });

    it("NIE podswietla nazwy znacznika", () => {
        const html = '<span lang="pl">Tytuł</span>';
        expect(highlight(html, "span")).toBe(html);
    });

    it("podswietla w tresci mimo wystapienia w atrybucie", () => {
        const wynik = highlight('<span lang="en">Energy</span>', "en");
        expect(wynik).toBe(
            '<span lang="en"><mark class="bpp-highlight">En</mark>ergy</span>'
        );
    });

    it("nie podswietla frazy rozdzielonej znacznikiem", () => {
        const html = "Rola <i>Candida</i> w X";
        expect(highlight(html, "rola candida")).toBe(html);
    });

    it("traktuje znaki specjalne regexa doslownie", () => {
        expect(highlight("Wpływ (X) na Y", "(x)")).toBe(
            'Wpływ <mark class="bpp-highlight">(X)</mark> na Y'
        );
    });

    it("podswietla wszystkie wystapienia w tresci", () => {
        const wynik = highlight("Ala ma kota, ala ma psa", "ala");
        expect(wynik.match(/<mark/g)).toHaveLength(2);
    });

    it("zachowuje wielkosc liter oryginalu", () => {
        expect(highlight("Effects", "EFFECTS")).toContain(">Effects<");
    });

    it("zwraca wejscie bez zmian dla pustej frazy", () => {
        const html = '<span lang="en">X</span>';
        expect(highlight(html, "")).toBe(html);
    });

    it("nie psuje encji HTML w tresci", () => {
        const html = "Kowalski &amp; Nowak";
        expect(highlight(html, "nowak")).toBe(
            'Kowalski &amp; <mark class="bpp-highlight">Nowak</mark>'
        );
    });
});
