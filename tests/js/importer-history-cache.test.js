// @vitest-environment jsdom
//
// `history_cache.js` kasuje z cache'u historii HTMX-a (localStorage) wpisy
// należące do importera publikacji. Powód jest opisany w samym pliku: HTMX
// czyta ten cache przy Back/Forward NIEZALEŻNIE od `hx-history="false"`
// (flaga blokuje tylko zapis), więc snapshot zapisany przed zmianą layoutu
// przywracał układ, którego nie ma już w kodzie.
//
// Plik jest ZWYKŁYM skryptem (nie modułem) — szablon ładuje go tagiem
// `<script src>` przed htmx.min.js. Importujemy go tu dla efektu ubocznego
// i czytamy z `window`, tak samo jak robi to rollbar-filters.test.js.
// Auto-start w pliku odpala się tylko gdy istnieje `document.currentScript`
// z atrybutem `data-prefiks` — przy imporcie ESM `currentScript` jest null,
// więc testy dostają czyste funkcje bez efektów ubocznych na `localStorage`.
import { describe, test, expect, beforeAll } from "vitest";

let usunWpisy, KLUCZ;

beforeAll(async () => {
    await import(
        "../../src/importer_publikacji/static/importer_publikacji/js/history_cache.js"
    );
    ({ usunWpisy, KLUCZ } = window.bppImporterHistoryCache);
});

const PREFIKS = "/importer_publikacji/";

// Minimalny dubler Storage — bez dzielenia stanu z prawdziwym localStorage
// jsdom-a (testy nie mogą na siebie wpływać kolejnością).
function pamiec(poczatkowe) {
    const dane = poczatkowe === undefined ? {} : { ...poczatkowe };
    return {
        dane,
        getItem: (k) => (k in dane ? dane[k] : null),
        setItem: (k, v) => {
            dane[k] = String(v);
        },
        removeItem: (k) => {
            delete dane[k];
        },
    };
}

function cache(storage) {
    const surowe = storage.getItem(KLUCZ);
    return surowe === null ? null : JSON.parse(surowe);
}

describe("usunWpisy", () => {
    test("kasuje wpisy importera, zostawia obce strony", () => {
        const s = pamiec({
            [KLUCZ]: JSON.stringify([
                { url: "/liveops/", content: "obce" },
                { url: "/importer_publikacji/", content: "stary layout" },
                { url: "/importer_publikacji/?provider=crossref", content: "x" },
                { url: "/bpp/autorzy/", content: "obce 2" },
            ]),
        });

        expect(usunWpisy(s, PREFIKS)).toBe(2);
        expect(cache(s).map((w) => w.url)).toEqual([
            "/liveops/",
            "/bpp/autorzy/",
        ]);
    });

    test("dopasowuje po PREFIKSIE, nie po fragmencie w środku URL-a", () => {
        const s = pamiec({
            [KLUCZ]: JSON.stringify([
                { url: "/admin/redirect/?next=/importer_publikacji/", content: "x" },
            ]),
        });

        expect(usunWpisy(s, PREFIKS)).toBe(0);
        expect(cache(s)).toHaveLength(1);
    });

    test("brak cache'u = nic do roboty, klucz nie powstaje", () => {
        const s = pamiec();

        expect(usunWpisy(s, PREFIKS)).toBe(0);
        expect(cache(s)).toBeNull();
    });

    test("nic nie pasuje = cache zostaje nietknięty", () => {
        const wejscie = JSON.stringify([{ url: "/liveops/", content: "obce" }]);
        const s = pamiec({ [KLUCZ]: wejscie });

        expect(usunWpisy(s, PREFIKS)).toBe(0);
        expect(s.getItem(KLUCZ)).toBe(wejscie);
    });

    test("uszkodzony JSON jest kasowany w całości", () => {
        const s = pamiec({ [KLUCZ]: "{to nie jest JSON" });

        expect(usunWpisy(s, PREFIKS)).toBe(0);
        expect(cache(s)).toBeNull();
    });

    test("cache nie będący tablicą jest kasowany w całości", () => {
        const s = pamiec({ [KLUCZ]: JSON.stringify({ url: "/importer_publikacji/" }) });

        expect(usunWpisy(s, PREFIKS)).toBe(0);
        expect(cache(s)).toBeNull();
    });

    test("znosi wpisy bez URL-a (obcy kod pisał pod ten klucz)", () => {
        const s = pamiec({
            [KLUCZ]: JSON.stringify([
                null,
                { content: "bez url" },
                { url: "/importer_publikacji/", content: "stary layout" },
            ]),
        });

        expect(usunWpisy(s, PREFIKS)).toBe(1);
        expect(cache(s)).toHaveLength(2);
    });
});
