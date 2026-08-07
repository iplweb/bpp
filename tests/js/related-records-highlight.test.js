// Podswietlanie frazy w opisie bibliograficznym (HTML) — wylacznie w
// segmentach TEKSTOWYCH. Po dodaniu <span lang="en"> (WCAG 3.1.2) naiwny
// regex na calym stringu podswietlal fragmenty ATRYBUTOW: fraza "en"
// trafiala w lang="en" i wstawiala <mark> w srodek znacznika, co przy
// .html(text) daje zepsuty markup.
//
// Drugi eksport modulu, bppStripTags(html), rozwiazuje pokrewny problem po
// stronie FILTROWANIA (nie podswietlania): praca_tabela_mono.html filtrowal
// rekordy przez `record.text.indexOf(fraza)` na surowym HTML-u, wiec fraza
// "span"/"lang" dopasowywala KAZDY rekord z <span lang="…"> — falszywie
// pozytywne trafienie, bez zadnego podswietlenia na liscie (regresja I1).

import { describe, it, expect, beforeAll } from "vitest";
import { readFileSync } from "fs";
import { resolve } from "path";

let highlight;
let stripTags;

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
    stripTags = window.bppStripTags;
});

// Powtarza logike filtra z praca_tabela_mono.html (haystack = bppStripTags
// zamiast surowego record.text) — testujemy TĘ SAMĄ logike, nie kopie.
function pasujeDoFiltra(html, fraza) {
    return stripTags(html).toLowerCase().indexOf(fraza.toLowerCase()) !== -1;
}

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

    it("nie podswietla frazy rozdzielonej znacznikiem (dot. PODSWIETLANIA, nie filtrowania)", () => {
        // Zakres: <mark> nie moze rozciagac sie przez granice znacznika —
        // to ograniczenie samego podswietlania (jeden segment tekstowy),
        // niezalezne od bppStripTags. Filtrowanie w praca_tabela_mono.html
        // NIE korzysta juz z tej funkcji do dopasowania rekordu — od naprawy
        // I1 dziala na bppStripTags(html) i TAKA SAMA fraza rekord
        // ZNAJDUJE (patrz "filtr: fraza rozdzielona znacznikiem" nizej).
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

    it("NIE podswietla frazy trafiajacej w podwojnie zescape'owana encje", () => {
        // _escape_bare_angle_brackets (src/bpp/util/text.py) zamienia bare
        // "<" na "&lt;", co po dalszym escapowaniu ampersandu w
        // data-records daje lancuch "&amp;lt;". Fraza "amp" jest pospolita
        // w tytulach medycznych ("ampicylina") — nie moze rozbic encji.
        const html = "Stezenie &amp;lt;30 IU/dL u pacjentow";
        expect(highlight(html, "amp")).toBe(html);
    });

    it("NIE podswietla frazy 'lt' trafiajacej w ten sam lancuch encji", () => {
        const html = "Stezenie &amp;lt;30 IU/dL u pacjentow";
        expect(highlight(html, "lt")).toBe(html);
    });

    it("NIE podswietla frazy 'amp' trafiajacej w prosta encje &amp;", () => {
        const html = "Kowalski &amp; Nowak";
        expect(highlight(html, "amp")).toBe(html);
    });

    it("podswietla fraze w tresci, ale nie wewnatrz encji o tej samej frazie", () => {
        const html = "Kowalski &amp; Nowak, ampicylina";
        expect(highlight(html, "amp")).toBe(
            'Kowalski &amp; Nowak, <mark class="bpp-highlight">amp</mark>icylina'
        );
    });

    it("NIE podswietla frazy trafiajacej w encje numeryczna", () => {
        const html = "Lata 2020&#8211;2023";
        expect(highlight(html, "8211")).toBe(html);
    });

    // CodeQL js/incomplete-multi-character-sanitization, alert 155 (linia
    // 76): "This string may still contain `<script`". Ponizsze testy
    // dokumentuja, ze to falszywy alarm — zob. uzasadnienie w komentarzu
    // nad bppHighlightOutsideTags w related-records-highlight.js.
    describe("zalozenie bezpieczenstwa (CodeQL alert 155, falszywy alarm)", () => {
        it("nie zamienia encji &lt;script&gt; w prawdziwy znacznik <script>", () => {
            // Encje sa PRZEPUSZCZANE, nie dekodowane — "&lt;" zostaje
            // "&lt;", nigdy nie staje sie literalnym "<".
            const html = "Tekst &lt;script&gt;alert(1)&lt;/script&gt; koniec";
            const wynik = highlight(html, "script");
            expect(wynik).not.toContain("<script");
            expect(wynik).toContain("&lt;");
            expect(wynik).toContain("&gt;");
        });

        it("jedyne NOWE znaki '<' w wyniku pochodza z <mark>, nigdy z frazy ani z wejscia", () => {
            const rozneWejscia = [
                "Tekst &lt;script&gt;alert(1)&lt;/script&gt; koniec",
                "<i>Rola</i> <span lang=\"en\">script kiddie</span>",
                "Stezenie &amp;lt;script&amp;gt; u pacjentow",
            ];
            rozneWejscia.forEach((html) => {
                const wynik = highlight(html, "script");
                // Wyciagnij wszystkie znaczniki z wejscia i z wyniku —
                // jedyna dopuszczalna ROZNICA to dodane <mark>/</mark>.
                const znacznikiWejscia = html.match(/<[^>]*>/g) || [];
                const znacznikiWyniku = (wynik.match(/<[^>]*>/g) || []).filter(
                    (t) => !/^<\/?mark\b/i.test(t)
                );
                expect(znacznikiWyniku).toEqual(znacznikiWejscia);
            });
        });

        it("wejscie z ALLOWLISTY (i/b/sub/sup/u/a/span[lang]) nigdy nie moze zawierac <script — nh3 usuwa go po stronie serwera przed dotarciem tutaj", () => {
            // Test dokumentuje zalozenie o gornej warstwie (nh3.clean z
            // clean_content_tags={"script","style"} w
            // safe_opis_bibliograficzny_html, src/bpp/util/text.py) — ta
            // funkcja JS jej nie weryfikuje, tylko na niej polega. Gdyby
            // mimo to <script> trafil do wejscia (regresja gornej warstwy),
            // ponizszy test pokazuje ze i tak zostalby przepuszczony bez
            // zmian (bo funkcja nie usuwa znacznikow) — obrona MUSI byc
            // po stronie serwera, nie tutaj.
            const html = "<script>alert(1)</script>";
            expect(highlight(html, "x")).toBe(html);
        });
    });
});

describe("bppStripTags", () => {
    it("usuwa znaczniki, zostawia tresc", () => {
        expect(stripTags('<span lang="en">Effects</span>')).toBe("Effects");
    });

    it("fraza 'span' NIE wystepuje w wyniku strip dla opisu ze znacznikiem", () => {
        const opis =
            'Kowalski Jan. <span lang="en">Effects of X on Y</span>. ' +
            "Postępy Higieny 2024, t. 78, s. 112-119.";
        expect(stripTags(opis).toLowerCase()).not.toContain("span");
    });

    it("fraza 'lang' NIE wystepuje w wyniku strip dla opisu ze znacznikiem", () => {
        const opis =
            'Kowalski Jan. <span lang="en">Effects of X on Y</span>. ' +
            "Postępy Higieny 2024, t. 78, s. 112-119.";
        expect(stripTags(opis).toLowerCase()).not.toContain("lang");
    });

    it("dekoduje encje: &amp; -> &", () => {
        expect(stripTags("Kowalski &amp; Nowak")).toBe("Kowalski & Nowak");
    });

    it("dekoduje encje: &lt; &gt; &quot; &#39;", () => {
        expect(stripTags("&lt;a&gt; &quot;x&quot; &#39;y&#39;")).toBe(
            '<a> "x" \'y\''
        );
    });

    it("laczy tresc z wielu segmentow tekstowych rozdzielonych znacznikiem", () => {
        expect(stripTags("Rola <i>Candida</i> w X")).toBe("Rola Candida w X");
    });

    // CodeQL js/incomplete-multi-character-sanitization, alert 156 (linia
    // 145): "This string may still contain `<script`". CodeQL ma racje co
    // do faktu (test ponizej to POTWIERDZA — dekodowanie podwojnie
    // zescape'owanych encji MOZE odtworzyc tekst "<script>"), ale to
    // falszywy alarm co do WPLYWU: bppStripTags() ma jedno miejsce uzycia w
    // calym repo (praca_tabela_mono.html:1185) i jego wynik trafia
    // WYLACZNIE do .indexOf() przy filtrowaniu — nigdy do DOM. Zob.
    // uzasadnienie w komentarzu nad bppStripTags w
    // related-records-highlight.js.
    describe("zalozenie bezpieczenstwa (CodeQL alert 156, falszywy alarm)", () => {
        it("MOZE odtworzyc tekst '<script>' z podwojnie zescape'owanej encji — to znany, zamierzony efekt uboczny funkcji 'strip'", () => {
            // "&amp;lt;script&amp;gt;" to dokladnie to, co powstaje gdy
            // safe_opis_bibliograficzny_html (nh3) zserializuje literalny
            // tekst "&lt;script&gt;" wpisany przez autora jako proza, a
            // nastepnie szablon dolozy |escapejs->JSON.parse (patrz
            // praca_tabela_mono.html). Wynik zawiera SUBSTRING "<script>"
            // jako zwykly tekst — nie jako znacznik HTML.
            const wynik = stripTags("Tekst &amp;lt;script&amp;gt; koniec");
            expect(wynik).toContain("<script>");
        });

        it("wynik zawierajacy '<script>' NIGDZIE w repo nie jest wstawiany jako HTML (jedyny consumer: indexOf w filtrze)", () => {
            // Ten test nie moze zweryfikowac calego repo statycznie, ale
            // dokumentuje kontrakt: konsument (praca_tabela_mono.html)
            // wolno mu uzywac wyniku WYLACZNIE tekstowo.
            const html = "Tekst &amp;lt;script&amp;gt; koniec";
            const haystack = stripTags(html).toLowerCase();
            // Jedyne dozwolone uzycie w produkcyjnym kodzie:
            expect(haystack.indexOf("script")).toBeGreaterThanOrEqual(0);
            // (nie: $(...).html(haystack) ani podobne — patrz komentarz
            // nad definicja bppStripTags)
        });
    });
});

describe("filtr rekordow powiazanych (bppStripTags jako haystack)", () => {
    it("fraza 'lang' NIE pasuje do opisu ze znacznikiem — brak falszywego trafienia", () => {
        const html = '<span lang="en">Effects of X on Y</span>';
        expect(pasujeDoFiltra(html, "lang")).toBe(false);
    });

    it("fraza 'span' NIE pasuje do opisu ze znacznikiem — brak falszywego trafienia", () => {
        const html = '<span lang="en">Effects of X on Y</span>';
        expect(pasujeDoFiltra(html, "span")).toBe(false);
    });

    it("fraza z realnej tresci PASUJE", () => {
        const html = '<span lang="en">Effects of X on Y</span>';
        expect(pasujeDoFiltra(html, "effects")).toBe(true);
    });

    it("filtr: fraza rozdzielona znacznikiem TERAZ pasuje (zmiana zamierzona, patrz I1)", () => {
        // Kontrast z testem highlight() wyzej: podswietlanie nadal nie
        // rozciaga <mark> przez granice znacznika, ale FILTROWANIE od tej
        // naprawy dziala na tekscie bez znacznikow — usuwa to zarowno
        // falszywe trafienia ("span"/"lang"), jak i ten zastany przypadek.
        const html = "Rola <i>Candida</i> w X";
        expect(pasujeDoFiltra(html, "rola candida")).toBe(true);
    });
});
