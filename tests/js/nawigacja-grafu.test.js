// Nawigacja po grafie powiazan bez przeciagania (WCAG 2.5.7) i z klawiatury
// (2.1.1). Modul operuje na instancji Cytoscape przez jej publiczne API,
// wiec testujemy go na atrapie — bez uruchamiania biblioteki.

import { describe, it, expect, beforeEach } from "vitest";
import {
    przesun,
    zoomuj,
    dopasuj
} from "../../src/powiazania_autorow/static/powiazania_autorow/js/powiazania/nawigacja.js";

function atrapaCy(opcje) {
    opcje = opcje || {};
    const stan = {
        panBy: null,
        zoomArg: null,
        fitWolane: false,
        poziomZoom: opcje.zoom === undefined ? 1 : opcje.zoom
    };
    return {
        _stan: stan,
        width: () => (opcje.width === undefined ? 1000 : opcje.width),
        height: () => (opcje.height === undefined ? 500 : opcje.height),
        minZoom: () => 0.1,
        maxZoom: () => 4,
        zoom: function (arg) {
            if (arg === undefined) {
                return stan.poziomZoom;
            }
            stan.zoomArg = arg;
            stan.poziomZoom = arg.level;
            return undefined;
        },
        panBy: function (arg) {
            stan.panBy = arg;
        },
        fit: function () {
            stan.fitWolane = true;
        }
    };
}

describe("przesun", () => {
    let cy;
    beforeEach(() => {
        cy = atrapaCy();
    });

    it("w prawo przesuwa widok w lewo (ujemny x)", () => {
        przesun(cy, "prawo");
        expect(cy._stan.panBy.x).toBeLessThan(0);
        expect(cy._stan.panBy.y).toBe(0);
    });

    it("w lewo przesuwa widok w prawo (dodatni x)", () => {
        przesun(cy, "lewo");
        expect(cy._stan.panBy.x).toBeGreaterThan(0);
        expect(cy._stan.panBy.y).toBe(0);
    });

    it("w dol przesuwa widok w gore (ujemny y)", () => {
        przesun(cy, "dol");
        expect(cy._stan.panBy.y).toBeLessThan(0);
        expect(cy._stan.panBy.x).toBe(0);
    });

    it("w gore przesuwa widok w dol (dodatni y)", () => {
        przesun(cy, "gora");
        expect(cy._stan.panBy.y).toBeGreaterThan(0);
        expect(cy._stan.panBy.x).toBe(0);
    });

    it("krok skaluje sie z szerokoscia widoku", () => {
        const waski = atrapaCy({ width: 500 });
        const szeroki = atrapaCy({ width: 2000 });
        przesun(waski, "prawo");
        przesun(szeroki, "prawo");
        expect(Math.abs(szeroki._stan.panBy.x)).toBeGreaterThan(
            Math.abs(waski._stan.panBy.x)
        );
    });

    it("krok skaluje sie z wysokoscia widoku", () => {
        // Osobny test dla osi Y, bo `przesun` liczy dy z `cy.height()`, a nie
        // z `cy.width()`: pomylka w tej jednej literze przeszlaby test wyzej
        // (tam wysokosc jest stala), a pionowy krok skalowalby sie szerokoscia.
        const niski = atrapaCy({ height: 250 });
        const wysoki = atrapaCy({ height: 1000 });
        przesun(niski, "gora");
        przesun(wysoki, "gora");
        expect(Math.abs(wysoki._stan.panBy.y)).toBeGreaterThan(
            Math.abs(niski._stan.panBy.y)
        );
    });

    it("nieznany kierunek nic nie robi", () => {
        przesun(cy, "wszedzie");
        expect(cy._stan.panBy).toBeNull();
    });
});

describe("zoomuj", () => {
    it("przyblizanie zwieksza poziom", () => {
        const cy = atrapaCy({ zoom: 1 });
        zoomuj(cy, 1.2);
        expect(cy._stan.zoomArg.level).toBeCloseTo(1.2);
    });

    it("oddalanie zmniejsza poziom", () => {
        const cy = atrapaCy({ zoom: 1 });
        zoomuj(cy, 1 / 1.2);
        expect(cy._stan.zoomArg.level).toBeLessThan(1);
    });

    it("nie przekracza maxZoom", () => {
        const cy = atrapaCy({ zoom: 3.9 });
        zoomuj(cy, 1.2);
        expect(cy._stan.zoomArg.level).toBe(4);
    });

    it("nie schodzi ponizej minZoom", () => {
        const cy = atrapaCy({ zoom: 0.11 });
        zoomuj(cy, 1 / 1.2);
        expect(cy._stan.zoomArg.level).toBe(0.1);
    });

    it("zoomuje wokol srodka widoku", () => {
        const cy = atrapaCy({ width: 1000, height: 500 });
        zoomuj(cy, 1.2);
        expect(cy._stan.zoomArg.renderedPosition).toEqual({ x: 500, y: 250 });
    });
});

describe("dopasuj", () => {
    it("wola cy.fit()", () => {
        const cy = atrapaCy();
        dopasuj(cy);
        expect(cy._stan.fitWolane).toBe(true);
    });
});
