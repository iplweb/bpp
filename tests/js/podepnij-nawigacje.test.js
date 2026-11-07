// @vitest-environment jsdom
//
// Spoiwo miedzy DOM-em a nawigacja po grafie: ktory przycisk wywoluje ktora
// akcje i GDZIE wisi handler klawiatury.
//
// Ten plik powstal po przegladzie mutacyjnym, ktory pokazal, ze sama logika
// (`przesun`, `zoomuj`, `obsluzKlawisz`) byla przetestowana porzadnie, ale
// spoiwo nie bylo testowane WCALE. Cztery mutacje przechodzily wtedy cala
// suite na zielono:
//   * zamiana "gora" z "dol" w mapie kierunkow,
//   * wszystkie cztery strzalki robiace to samo,
//   * odpiety handler zoom-out albo "dopasuj",
//   * podpiecie keydown do `document` zamiast do kontenera grafu,
//   * usuniety `preventDefault`.
// Ostatnia jest najgrozniejsza: `+` i `-` to znaki drukowalne, wiec podlegaja
// 2.1.4, a spelniamy je trzecim wariantem kryterium ("aktywne wylacznie przy
// focusie komponentu"). Handler na `document` zamienia je w globalne skroty
// jednoznakowe — czyli lamie dokladnie to, co ta galaz naprawia.

import { beforeEach, describe, expect, it, vi } from "vitest";

import {
    KIERUNKI_PRZYCISKOW,
    podepnijNawigacje
} from "../../src/powiazania_autorow/static/powiazania_autorow/js/powiazania/nawigacja.js";

const PRZYCISKI = [
    "graf-nav-gora",
    "graf-nav-dol",
    "graf-nav-lewo",
    "graf-nav-prawo",
    "graf-nav-zoom-in",
    "graf-nav-zoom-out",
    "graf-nav-dopasuj"
];

function atrapaCy() {
    const stan = { panBy: [], zoom: [], fit: 0 };
    return {
        _stan: stan,
        width: () => 1000,
        height: () => 500,
        zoom: (arg) => {
            if (arg === undefined) {
                return 1;
            }
            stan.zoom.push(arg);
            return undefined;
        },
        minZoom: () => 0.1,
        maxZoom: () => 4,
        panBy: (arg) => stan.panBy.push(arg),
        fit: () => (stan.fit += 1)
    };
}

function zbudujDom() {
    document.body.innerHTML =
        '<div id="cytoscape-container"></div>' +
        PRZYCISKI.map((id) => `<button id="${id}"></button>`).join("");
    return document;
}

describe("podepnijNawigacje — mapowanie przyciskow", () => {
    let cy;

    beforeEach(() => {
        cy = atrapaCy();
        podepnijNawigacje(cy, zbudujDom());
    });

    // Znaki `panBy` sa odwrocone wzgledem intuicji: przesuwaja PLOTNO, a
    // przycisk opisuje ruch WIDOKU. "w gore" => plotno w dol => dodatni y.
    it.each([
        ["graf-nav-gora", "y", 1],
        ["graf-nav-dol", "y", -1],
        ["graf-nav-lewo", "x", 1],
        ["graf-nav-prawo", "x", -1]
    ])("%s przesuwa wlasciwa os we wlasciwa strone", (id, os, znak) => {
        document.getElementById(id).click();

        expect(cy._stan.panBy).toHaveLength(1);
        const ruch = cy._stan.panBy[0];
        expect(Math.sign(ruch[os])).toBe(znak);
        // druga os musi zostac nietknieta — inaczej "w gore" moglby
        // jednoczesnie jechac w bok
        expect(ruch[os === "x" ? "y" : "x"]).toBe(0);
    });

    it("kazdy kierunek daje INNY ruch niz pozostale", () => {
        // Lapie mutacje "wszystkie strzalki robia to samo", ktorej testy
        // per-przycisk osobno by nie zlapaly, gdyby akurat trafily w ten
        // sam kierunek.
        Object.keys(KIERUNKI_PRZYCISKOW).forEach((id) =>
            document.getElementById(id).click()
        );

        const podpisy = cy._stan.panBy.map((r) => `${r.x}|${r.y}`);
        expect(new Set(podpisy).size).toBe(4);
    });

    it("przyblizanie zwieksza, oddalanie zmniejsza", () => {
        document.getElementById("graf-nav-zoom-in").click();
        document.getElementById("graf-nav-zoom-out").click();

        expect(cy._stan.zoom).toHaveLength(2);
        expect(cy._stan.zoom[0].level).toBeGreaterThan(1);
        expect(cy._stan.zoom[1].level).toBeLessThan(1);
    });

    it("dopasuj wola cy.fit()", () => {
        // Jedyna akcja RATUNKOWA: uzytkownik klawiatury, ktory wyjechal
        // widokiem poza graf, bez niej nie ma powrotu.
        document.getElementById("graf-nav-dopasuj").click();

        expect(cy._stan.fit).toBe(1);
    });

    it("kazdy z siedmiu przyciskow cos robi", () => {
        // Strazniik przed odpieciem dowolnego handlera. Test szablonowy
        // potwierdza tylko, ze przycisk ISTNIEJE w HTML-u, a martwy przycisk
        // jest gorszy niz jego brak: audyt widzi kontrolke, uzytkownik nie
        // dostaje funkcji (2.5.7 formalnie niespelnione).
        PRZYCISKI.forEach((id) => {
            const przed = cy._stan.panBy.length + cy._stan.zoom.length + cy._stan.fit;
            document.getElementById(id).click();
            const po = cy._stan.panBy.length + cy._stan.zoom.length + cy._stan.fit;

            expect(po, `przycisk ${id} nie robi nic`).toBeGreaterThan(przed);
        });
    });
});

describe("podepnijNawigacje — gdzie wisi klawiatura (2.1.4)", () => {
    let cy;
    let kontener;

    beforeEach(() => {
        cy = atrapaCy();
        kontener = podepnijNawigacje(cy, zbudujDom());
    });

    it("handler wisi na kontenerze grafu, nie na document", () => {
        expect(kontener).toBe(document.getElementById("cytoscape-container"));
    });

    it("strzalka w kontenerze przesuwa widok", () => {
        kontener.dispatchEvent(
            new window.KeyboardEvent("keydown", { key: "ArrowUp", bubbles: true })
        );

        expect(cy._stan.panBy).toHaveLength(1);
    });

    it("`+` POZA grafem nie zoomuje", () => {
        // Sedno zgodnosci z 2.1.4 dla `+`/`-`. Gdyby handler wisial na
        // `document`, to zdarzenie by go uruchomilo i skrot jednoznakowy
        // dzialalby globalnie.
        const obcy = document.createElement("input");
        document.body.appendChild(obcy);

        obcy.dispatchEvent(
            new window.KeyboardEvent("keydown", { key: "+", bubbles: true })
        );

        expect(cy._stan.zoom).toHaveLength(0);
    });

    it("obsluzony klawisz dostaje preventDefault, nieobsluzony nie", () => {
        // Bez preventDefault strzalka jednoczesnie przesuwa graf i przewija
        // strone. Z preventDefault na WSZYSTKIM — Tab przestaje wyprowadzac
        // focus i robi sie pulapka klawiaturowa (2.1.2).
        const strzalka = new window.KeyboardEvent("keydown", {
            key: "ArrowUp",
            bubbles: true,
            cancelable: true
        });
        const tab = new window.KeyboardEvent("keydown", {
            key: "Tab",
            bubbles: true,
            cancelable: true
        });

        kontener.dispatchEvent(strzalka);
        kontener.dispatchEvent(tab);

        expect(strzalka.defaultPrevented).toBe(true);
        expect(tab.defaultPrevented).toBe(false);
    });

    it("brak przyciskow w DOM nie wywala podpinania", () => {
        document.body.innerHTML = "";
        const cy2 = atrapaCy();

        expect(() => podepnijNawigacje(cy2, document)).not.toThrow();
    });
});
