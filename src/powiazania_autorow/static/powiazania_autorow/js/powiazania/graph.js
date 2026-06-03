// Budowa grafu: dodawanie węzłów/krawędzi, render całej pod-sieci (BFS)
// z endpointu siec.json oraz lokalne rozwijanie "pączka" po kliknięciu.
import { zapamietaj } from "./state.js";
import { daneUrl } from "./urls.js";
import { przeliczRozmiary } from "./sizing.js";
import { pokazBlad } from "./panel.js";
import { szukaj } from "./search.js";
import {
    dodajKrawedzieWewn,
    konfigurujProgWewn
} from "./group-edges.js";
import { rozmiescWokol, ulozGraf } from "./layout.js";

export function dodajWezel(ctx, id, info, isCentrum, seedPos) {
    const cy = ctx.cy;
    id = String(id);
    const node = cy.getElementById(id);
    if (node.nonempty()) {
        return node;
    }
    const ele = cy.add({
        group: "nodes",
        data: {
            id: id,
            label: info.label,
            url: info.url,
            works: info.total_works || 0,
            if_sum: info.if_sum || 0,
            pk_sum: info.pk_sum || 0,
            rozmiar: 20
        },
        position: { x: seedPos.x, y: seedPos.y },
        classes: isCentrum ? "centrum" : ""
    });
    if (ctx.animujDodawanie) { ele.addClass("nowy"); }
    return ele;
}

export function dodajKrawedz(ctx, zrodloId, n) {
    const cy = ctx.cy;
    const lo = Math.min(Number(zrodloId), Number(n.id));
    const hi = Math.max(Number(zrodloId), Number(n.id));
    const eid = "e" + lo + "_" + hi;
    if (cy.getElementById(eid).nonempty()) {
        return;
    }
    const ele = cy.add({
        group: "edges",
        data: {
            id: eid,
            source: String(zrodloId),
            target: String(n.id),
            shared: n.shared
        }
    });
    if (ctx.animujDodawanie) { ele.addClass("nowy"); }
}

// Krawędź z gotowych id (bez obiektu sąsiada) — dla renderu siatki BFS.
export function dodajKrawedzProsta(ctx, source, target, shared) {
    const cy = ctx.cy;
    const lo = Math.min(Number(source), Number(target));
    const hi = Math.max(Number(source), Number(target));
    const eid = "e" + lo + "_" + hi;
    if (cy.getElementById(eid).nonempty()) {
        return;
    }
    cy.add({
        group: "edges",
        data: {
            id: eid,
            source: String(source),
            target: String(target),
            shared: shared
        }
    });
}

export function pokazSasiadow(ctx, id, neighbors, animujPoz) {
    const cy = ctx.cy;
    const parent = cy.getElementById(String(id));
    const seed = parent.nonempty() ? parent.position() : { x: 0, y: 0 };
    const nowe = [];
    // neighbors są już posortowani malejąco po wspólnych publikacjach,
    // więc slice(0, topN) bierze najczęstszych współautorów.
    neighbors.slice(0, ctx.topN).forEach(function (n) {
        zapamietaj(ctx, n);
        const byl = cy.getElementById(String(n.id)).nonempty();
        const node = dodajWezel(ctx, n.id, n, false, seed);
        if (!byl) { nowe.push(node); }
        dodajKrawedz(ctx, id, n);
    });
    rozmiescWokol(ctx, id, nowe, animujPoz);
    // Zdjęcie klasy ".nowy" w następnej klatce uruchamia fade-in:
    // elementy zdążyły wyrenderować się z opacity 0, więc zmiana na
    // wartość docelową przechodzi przez transition zamiast skoku.
    if (ctx.animujDodawanie) {
        requestAnimationFrame(function () {
            cy.elements(".nowy").removeClass("nowy");
        });
    }
    przeliczRozmiary(ctx);
    // dowinięte węzły mogą domykać powiązania w grupie / pasować do
    // wyszukiwania — odśwież oba, jeśli aktywne.
    if (ctx.pokazWewn) { dodajKrawedzieWewn(ctx); }
    if (ctx.inputSzukaj && ctx.inputSzukaj.value) {
        szukaj(ctx, ctx.inputSzukaj.value);
    }
}

export function rozwin(ctx, id) {
    const cy = ctx.cy;
    id = String(id);
    if (ctx.expanded[id]) {
        return;
    }
    ctx.expanded[id] = true;
    cy.getElementById(id).addClass("rozwiniety");

    if (ctx.neighborsCache[id]) {
        pokazSasiadow(ctx, id, ctx.neighborsCache[id], true);
        return;
    }
    fetch(daneUrl(ctx, id))
        .then(function (r) {
            if (!r.ok) { throw new Error("HTTP " + r.status); }
            return r.json();
        })
        .then(function (data) {
            ctx.neighborsCache[id] = data.neighbors;
            zapamietaj(ctx, data.center);
            pokazSasiadow(ctx, id, data.neighbors, true);
        })
        .catch(function (e) {
            pokazBlad(ctx, "Błąd pobierania danych: " + e.message);
        });
}

// Granice pól roku z danych centrum (placeholdery pokazują zakres;
// wartości zostają puste = bez ograniczenia, dopóki user nie wpisze).
export function ustawZakresLat(ctx, rokMin, rokMax) {
    if (rokMin == null || rokMax == null) { return; }
    [ctx.rokOdEl, ctx.rokDoEl].forEach(function (el) {
        if (!el) { return; }
        el.min = rokMin;
        el.max = rokMax;
    });
    if (ctx.rokOdEl) { ctx.rokOdEl.placeholder = "od " + rokMin; }
    if (ctx.rokDoEl) { ctx.rokDoEl.placeholder = "do " + rokMax; }
}

// Render całej pod-sieci (BFS) z endpointu siec.json jako drzewo
// radialne: centrum w środku, kolejne poziomy w coraz szerszych
// pierścieniach, poddrzewa w rozłącznych klinach.
export function renderujSiec(ctx, data) {
    const cy = ctx.cy;
    ctx.animujDodawanie = false;
    cy.elements().remove();
    ctx.expanded = {};
    // Pełne przeładowanie sieci unieważnia per-węzłowy cache sąsiadów: top-N
    // lub filtr (rok/źródło/zatrudnieni) mogły się zmienić, więc dotychczasowe
    // listy są nieaktualne. infoCache (metadane autora) może zostać.
    ctx.neighborsCache = {};

    const centerId = String(data.center_id);
    data.nodes.forEach(function (n) { zapamietaj(ctx, n); });

    if (!data.nodes || data.nodes.length <= 1) {
        ctx.container.style.display = "none";
        if (ctx.emptyEl) { ctx.emptyEl.style.display = "block"; }
        if (ctx.notkaEl) { ctx.notkaEl.style.display = "none"; }
        ctx.animujDodawanie = true;
        return;
    }
    ctx.container.style.display = "";
    if (ctx.emptyEl) { ctx.emptyEl.style.display = "none"; }

    const children = {};
    const levelOf = {};
    data.nodes.forEach(function (n) {
        levelOf[String(n.id)] = n.level || 0;
        if (n.parent !== null && n.parent !== undefined) {
            const p = String(n.parent);
            (children[p] = children[p] || []).push(String(n.id));
        }
    });

    ctx.lastTree = {
        centerId: centerId, children: children, levelOf: levelOf
    };

    data.nodes.forEach(function (n) {
        const id = String(n.id);
        const jestCentrum = id === centerId;
        dodajWezel(ctx, n.id, n, jestCentrum, { x: 0, y: 0 });
        if (jestCentrum || children[id]) {
            cy.getElementById(id).addClass("rozwiniety");
            ctx.expanded[id] = true; // ma dzieci -> klik nie dowija ponownie
        }
    });

    data.edges.forEach(function (e) {
        dodajKrawedzProsta(ctx, e.source, e.target, e.shared);
    });

    ctx.extraEdges = data.extra_edges || [];
    konfigurujProgWewn(ctx);
    if (ctx.pokazWewn) { dodajKrawedzieWewn(ctx); }

    przeliczRozmiary(ctx);
    ulozGraf(ctx, false);
    ctx.animujDodawanie = true;
    ustawZakresLat(ctx, data.rok_min, data.rok_max);
    if (ctx.notkaEl) {
        ctx.notkaEl.style.display = data.truncated ? "block" : "none";
    }
    // po przeładowaniu utrzymaj aktywne wyszukiwanie
    if (ctx.inputSzukaj && ctx.inputSzukaj.value) {
        szukaj(ctx, ctx.inputSzukaj.value);
    }
}
