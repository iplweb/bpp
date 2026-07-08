// @vitest-environment jsdom
//
// Testy warstwy integracji RAD-on (radon-profil.js): renderowanie wyniku do
// kontenera sekcji + spinanie [data-radon-osiagniecia] z klientem RAD-on.
// Klient jest wstrzykiwany (opts.fetchAchievements) — nie ruszamy sieci.
import { describe, test, expect, beforeAll, beforeEach } from "vitest";

let renderRadonAchievements;
let wireRadonSections;

beforeAll(async () => {
    ({ renderRadonAchievements, wireRadonSections } = await import(
        "../../src/bpp/static/bpp/js/radon-profil.js"
    ));
});

beforeEach(() => {
    document.body.innerHTML = "";
});

function makeContainer(dataset = {}) {
    const el = document.createElement("div");
    el.setAttribute("data-radon-osiagniecia", "");
    el.dataset.orcid = dataset.orcid ?? "0000-0002-0153-4624";
    el.dataset.imie = dataset.imie ?? "Przemysław Jan";
    el.dataset.nazwisko = dataset.nazwisko ?? "Kowalczewski";
    el.hidden = true;
    const wynik = document.createElement("div");
    wynik.className = "radon-osiagniecia__wynik";
    el.appendChild(wynik);
    document.body.appendChild(el);
    return el;
}

const SAMPLE = {
    hasAny: true,
    cv: {
        level: "dr hab. inż.",
        degrees: [
            { name: "Doktor", year: "2016", institution: "UP Poznań", discipline: null },
        ],
        titles: [],
        education: [],
        employment: [],
        sources: "POLON",
    },
    projects: [
        { title: "Badanie soku", competition: "MINIATURA", funds: 47861, startDate: "2019", endDate: "2020" },
    ],
    patents: [{ title: "Sposób kapsułkowania", type: "Wynalazek" }],
    artisticAchievements: [],
};

describe("renderRadonAchievements", () => {
    test("wypełnia kontener i pokazuje go", () => {
        const el = makeContainer();
        renderRadonAchievements(el, SAMPLE);
        const txt = el.querySelector(".radon-osiagniecia__wynik").textContent;
        expect(txt).toContain("Doktor");
        expect(txt).toContain("Badanie soku");
        expect(txt).toContain("zł");
        expect(txt).toContain("Sposób kapsułkowania");
        expect(el.hidden).toBe(false);
    });

    test("renderuje bez innerHTML (żadne surowe pole nie tworzy elementów)", () => {
        const el = makeContainer();
        renderRadonAchievements(el, {
            ...SAMPLE,
            projects: [{ title: "<img src=x onerror=alert(1)>", funds: null }],
        });
        const wynik = el.querySelector(".radon-osiagniecia__wynik");
        // Treść trafia jako tekst, więc żaden <img> nie powstaje.
        expect(wynik.querySelector("img")).toBeNull();
        expect(wynik.textContent).toContain("<img src=x onerror=alert(1)>");
    });
});

describe("wireRadonSections", () => {
    test("parsuje imię/nazwisko/orcid i renderuje przy hasAny", async () => {
        const el = makeContainer();
        let seen;
        await wireRadonSections(document, {
            fetchAchievements: async (q) => {
                seen = q;
                return SAMPLE;
            },
        });
        expect(seen).toEqual({
            firstName: "Przemysław",
            lastName: "Kowalczewski",
            orcid: "0000-0002-0153-4624",
        });
        expect(el.hidden).toBe(false);
    });

    test("zostaje ukryty gdy brak danych (hasAny=false)", async () => {
        const el = makeContainer();
        await wireRadonSections(document, {
            fetchAchievements: async () => ({ hasAny: false, projects: [], patents: [], artisticAchievements: [], cv: null }),
        });
        expect(el.hidden).toBe(true);
    });

    test("degraduje bez wyjątku gdy fetch rzuci", async () => {
        const el = makeContainer();
        await expect(
            wireRadonSections(document, {
                fetchAchievements: async () => {
                    throw new Error("network down");
                },
            }),
        ).resolves.toBeDefined();
        expect(el.hidden).toBe(true);
    });
});
