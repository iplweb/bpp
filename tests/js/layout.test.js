// Testy czystej geometrii układów grafu. Funkcje zwracają mapę id→{x,y}
// licząc tylko z drzewa (centerId/children/levelOf), bez Cytoscape ani DOM.
import { describe, test, expect } from "vitest";
import {
    pozycjeRadialne,
    pozycjeKoncentryczne,
} from "../../src/powiazania_autorow/static/powiazania_autorow/js/powiazania/layout.js";

const odl = (p) => Math.hypot(p.x, p.y);

describe("pozycjeRadialne", () => {
    test("centrum w (0,0), dzieci na pierwszym pierścieniu (r=190)", () => {
        const poz = pozycjeRadialne("A", { A: ["B", "C"], B: [], C: [] });
        expect(poz.A.x).toBeCloseTo(0);
        expect(poz.A.y).toBeCloseTo(0);
        expect(odl(poz.B)).toBeCloseTo(190);
        expect(odl(poz.C)).toBeCloseTo(190);
    });

    test("dwoje dzieci dostaje przeciwległe półokręgi (B↑, C↓)", () => {
        const poz = pozycjeRadialne("A", { A: ["B", "C"], B: [], C: [] });
        // B: kąt środka klina [0,π] = π/2 → (0, +190); C: [π,2π] = 3π/2 → (0, -190)
        expect(poz.B.y).toBeCloseTo(190);
        expect(poz.C.y).toBeCloseTo(-190);
    });

    test("promień rośnie z poziomem (wnuk na r=380)", () => {
        const poz = pozycjeRadialne("A", { A: ["B"], B: ["C"], C: [] });
        expect(odl(poz.B)).toBeCloseTo(190);
        expect(odl(poz.C)).toBeCloseTo(380);
    });

    test("szerszy klin dla poddrzewa z większą liczbą liści", () => {
        // B ma 2 liście, C ma 1 — B powinno dostać 2/3 pełnego kąta.
        const poz = pozycjeRadialne("A", {
            A: ["B", "C"], B: ["B1", "B2"], C: [], B1: [], B2: [],
        });
        // Sanity: wszystkie węzły mają pozycję.
        ["A", "B", "C", "B1", "B2"].forEach((id) => expect(poz[id]).toBeDefined());
    });
});

describe("pozycjeKoncentryczne", () => {
    test("centrum w (0,0), poziom 1 równomiernie na r=165", () => {
        const poz = pozycjeKoncentryczne(
            "A", {}, { A: 0, B: 1, C: 1 }
        );
        expect(odl(poz.A)).toBeCloseTo(0);
        expect(odl(poz.B)).toBeCloseTo(165);
        expect(odl(poz.C)).toBeCloseTo(165);
    });

    test("dwa węzły poziomu 1 są przeciwległe (góra/dół)", () => {
        const poz = pozycjeKoncentryczne("A", {}, { A: 0, B: 1, C: 1 });
        expect(poz.B.y).toBeCloseTo(-165); // i=0 → kąt -π/2
        expect(poz.C.y).toBeCloseTo(165); //  i=1 → kąt +π/2
    });

    test("drugi pierścień na r=330", () => {
        const poz = pozycjeKoncentryczne("A", {}, { A: 0, B: 1, C: 2 });
        expect(odl(poz.C)).toBeCloseTo(330);
    });
});
