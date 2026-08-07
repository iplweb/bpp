// Obsluga grafu powiazan klawiatura (WCAG 2.1.1) — mapowanie klawisza na
// akcje (obsluzKlawisz) siedzi w nawigacja.js, wiec testujemy je na atrapie
// cy (jak w nawigacja-grafu.test.js), bez importowania controls.js (ktory
// ciagnie pol aplikacji).

import { describe, it, expect, beforeEach } from "vitest";
import { obsluzKlawisz } from "../../src/powiazania_autorow/static/powiazania_autorow/js/powiazania/nawigacja.js";

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

// Zdarzenie klawiatury jako zwykly obiekt — obsluzKlawisz nie wywoluje na
// nim nic poza odczytem pol, wiec nie potrzeba prawdziwego KeyboardEvent.
function zdarzenie(key, modyfikatory) {
    modyfikatory = modyfikatory || {};
    return {
        key: key,
        ctrlKey: modyfikatory.ctrlKey || false,
        metaKey: modyfikatory.metaKey || false,
        altKey: modyfikatory.altKey || false,
        shiftKey: modyfikatory.shiftKey || false
    };
}

describe("obsluzKlawisz — strzalki", () => {
    let cy;
    beforeEach(() => {
        cy = atrapaCy();
    });

    it("ArrowUp przesuwa w gore i zwraca true", () => {
        const wynik = obsluzKlawisz(cy, zdarzenie("ArrowUp"));
        expect(wynik).toBe(true);
        expect(cy._stan.panBy.y).toBeGreaterThan(0);
        expect(cy._stan.panBy.x).toBe(0);
    });

    it("ArrowDown przesuwa w dol i zwraca true", () => {
        const wynik = obsluzKlawisz(cy, zdarzenie("ArrowDown"));
        expect(wynik).toBe(true);
        expect(cy._stan.panBy.y).toBeLessThan(0);
        expect(cy._stan.panBy.x).toBe(0);
    });

    it("ArrowLeft przesuwa w lewo i zwraca true", () => {
        const wynik = obsluzKlawisz(cy, zdarzenie("ArrowLeft"));
        expect(wynik).toBe(true);
        expect(cy._stan.panBy.x).toBeGreaterThan(0);
        expect(cy._stan.panBy.y).toBe(0);
    });

    it("ArrowRight przesuwa w prawo i zwraca true", () => {
        const wynik = obsluzKlawisz(cy, zdarzenie("ArrowRight"));
        expect(wynik).toBe(true);
        expect(cy._stan.panBy.x).toBeLessThan(0);
        expect(cy._stan.panBy.y).toBe(0);
    });
});

describe("obsluzKlawisz — zoom", () => {
    let cy;
    beforeEach(() => {
        cy = atrapaCy({ zoom: 1 });
    });

    it("'+' przyblizA (wspolczynnik > 1) i zwraca true", () => {
        const wynik = obsluzKlawisz(cy, zdarzenie("+"));
        expect(wynik).toBe(true);
        expect(cy._stan.zoomArg.level).toBeGreaterThan(1);
    });

    it("'=' przyblizA i zwraca true (bez Shift na wiekszosci ukladow)", () => {
        const wynik = obsluzKlawisz(cy, zdarzenie("="));
        expect(wynik).toBe(true);
        expect(cy._stan.zoomArg.level).toBeGreaterThan(1);
    });

    it("'-' oddala (wspolczynnik < 1) i zwraca true", () => {
        const wynik = obsluzKlawisz(cy, zdarzenie("-"));
        expect(wynik).toBe(true);
        expect(cy._stan.zoomArg.level).toBeLessThan(1);
    });

    it("'_' oddala i zwraca true", () => {
        const wynik = obsluzKlawisz(cy, zdarzenie("_"));
        expect(wynik).toBe(true);
        expect(cy._stan.zoomArg.level).toBeLessThan(1);
    });
});

describe("obsluzKlawisz — Home", () => {
    it("Home dopasowuje graf (cy.fit()) i zwraca true", () => {
        const cy = atrapaCy();
        const wynik = obsluzKlawisz(cy, zdarzenie("Home"));
        expect(wynik).toBe(true);
        expect(cy._stan.fitWolane).toBe(true);
    });
});

describe("obsluzKlawisz — klawisze nieobslugiwane (bez pulapki, 2.1.2)", () => {
    let cy;
    beforeEach(() => {
        cy = atrapaCy();
    });

    it.each(["Tab", "Escape", "Enter", "a"])(
        "%s zwraca false i nic nie wola",
        (klawisz) => {
            const wynik = obsluzKlawisz(cy, zdarzenie(klawisz));
            expect(wynik).toBe(false);
            expect(cy._stan.panBy).toBeNull();
            expect(cy._stan.zoomArg).toBeNull();
            expect(cy._stan.fitWolane).toBe(false);
        }
    );
});

describe("obsluzKlawisz — skroty przegladarki nie sa przechwytywane (1.4.4)", () => {
    let cy;
    beforeEach(() => {
        cy = atrapaCy();
    });

    it("Ctrl+ArrowUp zwraca false i nic nie wola (skrot przegladarki)", () => {
        const wynik = obsluzKlawisz(cy, zdarzenie("ArrowUp", { ctrlKey: true }));
        expect(wynik).toBe(false);
        expect(cy._stan.panBy).toBeNull();
    });

    it("Cmd(meta)+'+' zwraca false (Cmd+Plus to zoom przegladarki)", () => {
        const wynik = obsluzKlawisz(cy, zdarzenie("+", { metaKey: true }));
        expect(wynik).toBe(false);
        expect(cy._stan.zoomArg).toBeNull();
    });

    it("Ctrl+Home zwraca false (przewijanie strony na gore)", () => {
        const wynik = obsluzKlawisz(cy, zdarzenie("Home", { ctrlKey: true }));
        expect(wynik).toBe(false);
        expect(cy._stan.fitWolane).toBe(false);
    });

    it("Alt+ArrowLeft zwraca false (nawigacja wstecz przegladarki)", () => {
        const wynik = obsluzKlawisz(cy, zdarzenie("ArrowLeft", { altKey: true }));
        expect(wynik).toBe(false);
        expect(cy._stan.panBy).toBeNull();
    });

    it("'+' z Shift zwraca true i przyblizA (Shift potrzebny do wpisania +)", () => {
        const wynik = obsluzKlawisz(cy, zdarzenie("+", { shiftKey: true }));
        expect(wynik).toBe(true);
        expect(cy._stan.zoomArg.level).toBeGreaterThan(1);
    });
});
