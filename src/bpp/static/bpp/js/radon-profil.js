// Sekcja „Osiągnięcia (RAD-on)" na podstronie autora — warstwa integracji.
//
// Pobiera dane po stronie klienta z RAD-on OpenData (pakiet @iplweb/radon-opendata),
// dopasowując rekordy po ORCID autora, i renderuje je do kontenera
// [data-radon-osiagniecia]. Cała treść trafia przez textContent (bez innerHTML)
// — żadne pole z API nie może wstrzyknąć HTML-a. Przy braku danych/błędzie
// kontener zostaje ukryty (degradacja bez wyjątku).
import {
    createRadonClient,
    fetchAchievementsByOrcid,
} from "@iplweb/radon-opendata";

function el(tag, text, className) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text != null && text !== "") node.textContent = String(text);
    return node;
}

function formatPln(n) {
    if (n == null) return null;
    const grouped = String(n).replace(/\B(?=(\d{3})+(?!\d))/g, " ");
    return grouped + " zł";
}

function lata(od, doo) {
    const a = (od || "").slice(0, 4);
    const b = (doo || "").slice(0, 4);
    if (a && b) return `${a}–${b}`;
    return a || b || "";
}

function blok(tytul, pozycje) {
    if (!pozycje.length) return null;
    const wrap = el("div", null, "radon-osiagniecia__blok");
    wrap.appendChild(el("h4", tytul, "radon-osiagniecia__blok-tytul"));
    const ul = el("ul", null, "radon-osiagniecia__lista");
    for (const linia of pozycje) ul.appendChild(el("li", linia));
    wrap.appendChild(ul);
    return wrap;
}

/**
 * Wyrenderuj wynik RAD-on do kontenera i pokaż go. Pusty wynik → kontener
 * zostaje bez zmian (ukryty). Wszystko przez textContent (anty-XSS).
 */
export function renderRadonAchievements(container, result) {
    const wynik = container.querySelector(".radon-osiagniecia__wynik");
    if (!wynik || !result) return;
    wynik.textContent = "";

    const bloki = [];

    if (result.cv) {
        const cv = result.cv;
        const linie = [];
        for (const d of cv.degrees || []) {
            const czesci = [d.name, d.year, d.institution].filter(Boolean);
            if (czesci.length) linie.push(czesci.join(", "));
        }
        for (const t of cv.titles || []) {
            const czesci = [t.name, t.year].filter(Boolean);
            if (czesci.length) linie.push(czesci.join(", "));
        }
        bloki.push(blok("Stopnie i tytuły", linie));
    }

    bloki.push(
        blok(
            "Projekty naukowe",
            (result.projects || []).map((p) => {
                const meta = [p.competition, formatPln(p.funds), lata(p.startDate, p.endDate)]
                    .filter(Boolean)
                    .join(" · ");
                return meta ? `${p.title} (${meta})` : p.title;
            }),
        ),
    );

    bloki.push(
        blok(
            "Patenty i prawa ochronne",
            (result.patents || []).map((p) =>
                [p.title, p.type].filter(Boolean).join(" — "),
            ),
        ),
    );

    bloki.push(
        blok(
            "Osiągnięcia artystyczne",
            (result.artisticAchievements || []).map((a) => {
                const nagrody = (a.awards || [])
                    .map((w) => [w.competition, w.year].filter(Boolean).join(" "))
                    .filter(Boolean)
                    .join(", ");
                const baza = [a.title, a.year].filter(Boolean).join(", ");
                return nagrody ? `${baza} — nagrody: ${nagrody}` : baza;
            }),
        ),
    );

    for (const b of bloki) if (b) wynik.appendChild(b);
    container.hidden = false;
}

/**
 * Znajdź kontenery sekcji RAD-on w ``root``, dociągnij dane po ORCID i
 * wyrenderuj. Zwraca Promise (allSettled-owe) — degraduje bez wyjątku.
 * ``opts.fetchAchievements`` pozwala wstrzyknąć klienta (testy).
 */
export function wireRadonSections(root = document, opts = {}) {
    const fetcher =
        opts.fetchAchievements ||
        ((q) => fetchAchievementsByOrcid(createRadonClient(), q));

    const kontenery = Array.from(
        root.querySelectorAll("[data-radon-osiagniecia]"),
    );

    return Promise.all(
        kontenery.map(async (container) => {
            try {
                const orcid = container.dataset.orcid || "";
                if (!orcid) return null;
                const firstName = (container.dataset.imie || "").trim().split(/\s+/)[0] || "";
                const lastName = container.dataset.nazwisko || "";
                const result = await fetcher({ firstName, lastName, orcid });
                if (result && result.hasAny) {
                    renderRadonAchievements(container, result);
                }
                return result;
            } catch (e) {
                if (typeof console !== "undefined") {
                    console.debug("[radon] wireRadonSections", e);
                }
                return null;
            }
        }),
    );
}

// Auto-wire przy załadowaniu strony (efekt uboczny dla bundla).
if (typeof document !== "undefined") {
    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", () => wireRadonSections());
    } else {
        wireRadonSections();
    }
}
