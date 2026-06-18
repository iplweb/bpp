// Testy budowania URL-i eksploratora powiązań + odczytu filtra.
// Czysty ESM — importujemy wprost, `ctx` to zwykły obiekt, jedyna
// "DOM-owość" (querySelectorAll na liście źródeł) jest trywialnie stubowana.
import { describe, test, expect } from "vitest";
import {
    wybraneZrodla,
    paramyFiltru,
    daneUrl,
    siecUrl,
    zrodlaUrl,
    grafUrl,
} from "../../src/powiazania_autorow/static/powiazania_autorow/js/powiazania/urls.js";

// Stub szuflady źródeł: querySelectorAll(...) ignoruje selektor i zwraca
// checkboxy o podanych `value` (kod i tak filtruje :checked po stronie DOM).
function listaZrodla(values) {
    const cbs = values.map((v) => ({ value: v }));
    return { querySelectorAll: () => cbs };
}

describe("wybraneZrodla", () => {
    test("dekoduje prefiks z/w na osobne listy id", () => {
        const ctx = { listaZrodla: listaZrodla(["z1", "w2", "z3", "w10"]) };
        expect(wybraneZrodla(ctx)).toEqual({ z: ["1", "3"], w: ["2", "10"] });
    });

    test("brak listy w ctx → puste listy", () => {
        expect(wybraneZrodla({})).toEqual({ z: [], w: [] });
    });
});

describe("paramyFiltru", () => {
    test("pusty ctx → pusty string", () => {
        expect(paramyFiltru({})).toBe("");
    });

    test("rok od-do", () => {
        expect(paramyFiltru({ rokOdEl: { value: "2000" }, rokDoEl: { value: "2010" } }))
            .toBe("&rok_od=2000&rok_do=2010");
    });

    test("źródła i wydawcy z listy", () => {
        const ctx = { listaZrodla: listaZrodla(["z5", "w7"]) };
        expect(paramyFiltru(ctx)).toBe("&zrodlo=5&wydawca=7");
    });

    test("flaga tylko zatrudnieni", () => {
        expect(paramyFiltru({ tylkoZatrudnieni: true })).toBe("&tylko_zatrudnieni=1");
    });

    test("wartości są URL-encodowane", () => {
        expect(paramyFiltru({ rokOdEl: { value: "a b&c" } }))
            .toBe("&rok_od=a%20b%26c");
    });
});

describe("daneUrl", () => {
    test("podstawia id w /0/ i bez filtra nie dokleja ?", () => {
        expect(daneUrl({ urlTemplate: "/api/autor/0/dane/" }, 42))
            .toBe("/api/autor/42/dane/");
    });

    test("z filtrem dokleja ? (z obciętym wiodącym &)", () => {
        const ctx = { urlTemplate: "/api/autor/0/dane/", rokOdEl: { value: "2020" } };
        expect(daneUrl(ctx, 42)).toBe("/api/autor/42/dane/?rok_od=2020");
    });
});

describe("siecUrl", () => {
    test("depth/topn + doklejony filtr", () => {
        const ctx = { siecUrlTemplate: "/api/0/siec/", tylkoZatrudnieni: true };
        expect(siecUrl(ctx, 7, 2, 15))
            .toBe("/api/7/siec/?depth=2&topn=15&tylko_zatrudnieni=1");
    });
});

describe("zrodlaUrl", () => {
    test("świadomie POMIJA wybrane źródła/wydawców (sprzężenie zwrotne)", () => {
        const ctx = {
            zrodlaUrlTemplate: "/api/0/zrodla/",
            glebokosc: 3,
            topN: 20,
            rokOdEl: { value: "2018" },
            tylkoZatrudnieni: true,
            // mimo zaznaczonych źródeł NIE powinny trafić do URL-a:
            listaZrodla: listaZrodla(["z1", "w2"]),
        };
        expect(zrodlaUrl(ctx, 9))
            .toBe("/api/9/zrodla/?depth=3&topn=20&rok_od=2018&tylko_zatrudnieni=1");
    });
});

describe("grafUrl", () => {
    test("prosta podmiana id", () => {
        expect(grafUrl({ grafUrlTemplate: "/api/0/graf/" }, 3)).toBe("/api/3/graf/");
    });
});
