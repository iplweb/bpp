// Fabryka kontekstu (`ctx`): jeden obiekt niosący instancję Cytoscape,
// cache'e, mutowalny stan widoku, szablony URL-i i referencje do DOM.
// Funkcje pozostałych modułów biorą `ctx` zamiast domknięcia.
import { utworzCy } from "./cy.js";

// Buduje `ctx` z kontenera grafu (#cytoscape-container) i jego datasetu.
// Zwraca null, jeśli kontenera nie ma albo Cytoscape się nie załadował —
// wtedy init() po prostu nie startuje.
export function utworzKontekst() {
    const container = document.getElementById("cytoscape-container");
    if (!container) {
        return null;
    }
    if (typeof window.cytoscape === "undefined") {
        console.error("Cytoscape.js nie został załadowany.");
        return null;
    }

    const slider = document.getElementById("graf-topn");
    const sliderGleb = document.getElementById("graf-glebokosc");
    const selMetryka = document.getElementById("graf-metryka");
    const selUklad = document.getElementById("graf-uklad");
    const progWewnSlider = document.getElementById("graf-wewn-prog");

    const topN = parseInt(slider.value, 10);
    const glebokosc = parseInt(sliderGleb.value, 10) || 1;

    const ctx = {
        // --- DOM ---
        container: container,
        emptyEl: document.getElementById("graf-empty"),
        notkaEl: document.getElementById("graf-notka"),
        tooltip: document.getElementById("graf-tooltip"),
        panel: document.getElementById("graf-panel"),
        slider: slider,
        sliderLabel: document.getElementById("graf-topn-label"),
        sliderGleb: sliderGleb,
        sliderGlebLabel: document.getElementById("graf-glebokosc-label"),
        selMetryka: selMetryka,
        selUklad: selUklad,
        rokOdEl: document.getElementById("graf-rok-od"),
        rokDoEl: document.getElementById("graf-rok-do"),
        btnZrodlaToggle: document.getElementById("graf-zrodla-toggle"),
        panelZrodla: document.getElementById("graf-zrodla-panel"),
        filterZrodla: document.getElementById("graf-zrodla-filter"),
        clearZrodla: document.getElementById("graf-zrodla-clear"),
        listaZrodla: document.getElementById("graf-zrodla-lista"),
        inputSzukaj: document.getElementById("graf-szukaj"),
        chkWewn: document.getElementById("graf-wewnetrzne-chk"),
        chkZatrudnieni: document.getElementById("graf-zatrudnieni-chk"),
        progWewnSlider: progWewnSlider,
        progWewnLabel: document.getElementById("graf-wewn-prog-label"),

        // --- szablony URL (z datasetu kontenera) ---
        autorId: String(container.dataset.autorId),
        urlTemplate: container.dataset.daneUrlTemplate,
        siecUrlTemplate: container.dataset.siecUrlTemplate,
        zrodlaUrlTemplate: container.dataset.zrodlaUrlTemplate,
        grafUrlTemplate: container.dataset.grafUrlTemplate,

        // --- stan widoku ---
        topN: topN,
        glebokosc: glebokosc,
        metryka: selMetryka ? selMetryka.value : "works",
        uklad: selUklad ? selUklad.value : "radial",
        lastTree: null,        // { centerId, children, levelOf } z ostatniej sieci
        pokazWewn: false,      // czy rysujemy krawędzie wewnątrz grupy
        tylkoZatrudnieni: false, // tylko współautorzy aktualnie zatrudnieni
        zrodlaZaladowane: false, // czy lista źródeł już pobrana (leniwie)
        progWewn: progWewnSlider
            ? parseInt(progWewnSlider.value, 10) || 1
            : 1,
        extraEdges: [],        // ostatnie krawędzie poprzeczne z serwera
        expanded: {},          // id -> true (węzeł rozwinięty)
        animujDodawanie: true, // fade-in nowych elementów (off przy rebuildzie)

        // --- cache'e ---
        neighborsCache: {},    // id -> [{id,label,url,shared,...}, ...]
        infoCache: {},         // id -> pełny payload autora

        // --- token sekwencji żądań (ignoruj przestarzałe odpowiedzi) ---
        seq: 0,
        seqZrodla: 0,

        // instancja Cytoscape
        cy: null
    };

    ctx.cy = utworzCy(container);

    // Etykiety synchronizujemy z realną wartością suwaka: przeglądarka po
    // odświeżeniu potrafi przywrócić starą pozycję suwaka, a statyczna
    // etykieta z szablonu rozjechałaby się z tym, co faktycznie rysujemy.
    if (ctx.sliderLabel) { ctx.sliderLabel.textContent = topN; }
    if (ctx.sliderGlebLabel) { ctx.sliderGlebLabel.textContent = glebokosc; }

    return ctx;
}

// Zapamiętuje pełny payload autora w cache (po id jako string).
export function zapamietaj(ctx, info) {
    ctx.infoCache[String(info.id)] = info;
}
