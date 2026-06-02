// Wiązanie wszystkich zdarzeń UI: zdarzenia Cytoscape (hover/tap),
// suwaki (top-N, głębokość, próg powiązań w grupie), filtr roku, szuflada
// źródeł/wydawców, opcje zaawansowane, metryka, układ, wyszukiwarka,
// odśwież oraz eksport PNG/SVG. Debounce dla żądań sterowanych suwakami.
import { pobierzPlik } from "./dom.js";
import {
    pokazPanelAutora,
    pokazTooltipAutor,
    pokazTooltipKrawedz
} from "./panel.js";
import { przeliczRozmiary } from "./sizing.js";
import { szukaj } from "./search.js";
import { odswiezKrawedzieWewn } from "./group-edges.js";
import { ulozGraf } from "./layout.js";
import { rozwin } from "./graph.js";
import {
    zaladujSiec,
    zaladujZrodla,
    aktualizujLabelZrodla,
    filtrujListeZrodel
} from "./loaders.js";

export function podepnijZdarzenia(ctx) {
    const cy = ctx.cy;

    // Suwaki sterują żądaniem do serwera (BFS), więc dławimy częstotliwość
    // przeładowań przy przeciąganiu, żeby nie zasypać backendu.
    let debTimer = null;
    function zaladujSiecZwloka() {
        if (debTimer) { clearTimeout(debTimer); }
        debTimer = setTimeout(function () { zaladujSiec(ctx); }, 250);
    }

    // Zmiana roku wpływa i na sieć, i na listę źródeł — przeładuj oba.
    let debFiltr = null;
    function poZmianieRoku() {
        if (debFiltr) { clearTimeout(debFiltr); }
        debFiltr = setTimeout(function () {
            zaladujZrodla(ctx);
            zaladujSiec(ctx);
        }, 350);
    }

    // --- hover na węźle -> tooltip z nazwiskiem, tytułem i ORCID ---
    cy.on("mouseover", "node", function (evt) {
        const info = ctx.infoCache[evt.target.id()] || {
            label: evt.target.data("label")
        };
        pokazTooltipAutor(ctx, info);
    });
    cy.on("mouseout", "node", function () {
        ctx.tooltip.style.display = "none";
    });

    // --- hover na krawędzi -> tooltip z liczbą wspólnych publikacji ---
    cy.on("mouseover", "edge", function (evt) {
        const e = evt.target;
        e.addClass("podswietlona");
        const a = ctx.infoCache[e.data("source")] || {};
        const b = ctx.infoCache[e.data("target")] || {};
        pokazTooltipKrawedz(ctx, a.label, b.label, e.data("shared"));
    });
    cy.on("mouseout", "edge", function (evt) {
        evt.target.removeClass("podswietlona");
        ctx.tooltip.style.display = "none";
    });

    cy.on("mousemove", function (evt) {
        const pos = evt.renderedPosition || { x: 0, y: 0 };
        ctx.tooltip.style.left = (pos.x + 14) + "px";
        ctx.tooltip.style.top = (pos.y + 14) + "px";
    });

    // --- klik -> rozwiń (pączek) + panel akcji ---
    cy.on("tap", "node", function (evt) {
        const n = evt.target;
        rozwin(ctx, n.id());
        const info = ctx.infoCache[n.id()] || {
            label: n.data("label"), url: n.data("url")
        };
        pokazPanelAutora(ctx, info);
    });

    // --- przeciąganie zabiera ze sobą CAŁY poddrzew węzła ---
    // Chwytając węzeł przesuwamy jego potomków (z drzewa rozwijania) tym samym
    // wektorem; przodek i inne gałęzie zostają nieruchome. Dzięki temu da się
    // rozsunąć/uporządkować gałąź jednym ruchem zamiast węzeł po węźle.
    function potomkowiePoddrzewa(id) {
        const kids = ctx.lastTree ? ctx.lastTree.children : null;
        let coll = cy.collection();
        if (!kids) { return coll; }
        const stos = [String(id)];
        while (stos.length) {
            const cur = stos.pop();
            (kids[cur] || []).forEach(function (c) {
                const el = cy.getElementById(c);
                if (el.nonempty()) { coll = coll.union(el); }
                stos.push(c);
            });
        }
        return coll;
    }

    cy.on("grab", "node", function (evt) {
        const n = evt.target;
        n.scratch("_poddrzew", potomkowiePoddrzewa(n.id()));
        n.scratch("_ostPoz", { x: n.position("x"), y: n.position("y") });
    });
    cy.on("drag", "node", function (evt) {
        const n = evt.target;
        const prev = n.scratch("_ostPoz");
        const pot = n.scratch("_poddrzew");
        if (!prev || !pot) { return; }
        const dx = n.position("x") - prev.x;
        const dy = n.position("y") - prev.y;
        if (dx || dy) {
            pot.positions(function (ele) {
                return { x: ele.position("x") + dx, y: ele.position("y") + dy };
            });
        }
        n.scratch("_ostPoz", { x: n.position("x"), y: n.position("y") });
    });
    cy.on("free", "node", function (evt) {
        const n = evt.target;
        n.removeScratch("_poddrzew");
        n.removeScratch("_ostPoz");
    });

    // --- suwak top-N -> przeładuj sieć (top-N per węzeł) ---
    ctx.slider.addEventListener("input", function () {
        ctx.topN = parseInt(ctx.slider.value, 10);
        if (ctx.sliderLabel) { ctx.sliderLabel.textContent = ctx.topN; }
        zaladujSiecZwloka();
    });

    // --- suwak głębokości -> przeładuj sieć (BFS na N poziomów) ---
    ctx.sliderGleb.addEventListener("input", function () {
        ctx.glebokosc = parseInt(ctx.sliderGleb.value, 10);
        if (ctx.sliderGlebLabel) {
            ctx.sliderGlebLabel.textContent = ctx.glebokosc;
        }
        zaladujSiecZwloka();
    });

    // --- filtr roku (od-do) -> przeładuj listę źródeł + sieć ---
    if (ctx.rokOdEl) { ctx.rokOdEl.addEventListener("input", poZmianieRoku); }
    if (ctx.rokDoEl) { ctx.rokDoEl.addEventListener("input", poZmianieRoku); }

    // --- szuflada źródeł/wydawców (multi-select) ---
    if (ctx.btnZrodlaToggle && ctx.panelZrodla) {
        ctx.btnZrodlaToggle.addEventListener("click", function () {
            ctx.panelZrodla.style.display =
                ctx.panelZrodla.style.display === "block" ? "none" : "block";
        });
        // zamknięcie po kliknięciu poza szufladą
        document.addEventListener("click", function (e) {
            if (ctx.panelZrodla.style.display === "block"
                && !ctx.panelZrodla.contains(e.target)
                && e.target !== ctx.btnZrodlaToggle) {
                ctx.panelZrodla.style.display = "none";
            }
        });
    }
    if (ctx.listaZrodla) {
        ctx.listaZrodla.addEventListener("change", function (e) {
            if (e.target && e.target.type === "checkbox") {
                aktualizujLabelZrodla(ctx);
                zaladujSiecZwloka();
            }
        });
    }
    if (ctx.clearZrodla) {
        ctx.clearZrodla.addEventListener("click", function (e) {
            e.preventDefault();
            const cbs = ctx.listaZrodla.querySelectorAll(
                "input[type=checkbox]:checked"
            );
            Array.prototype.forEach.call(cbs, function (cb) {
                cb.checked = false;
            });
            aktualizujLabelZrodla(ctx);
            zaladujSiec(ctx);
        });
    }
    if (ctx.filterZrodla) {
        ctx.filterZrodla.addEventListener("input", function () {
            filtrujListeZrodel(ctx);
        });
    }

    // --- rozwijane "Opcje zaawansowane" (chowamy filtry/eksport, żeby nie
    // przytłoczyć początkującego użytkownika) ---
    const btnZaawansowane = document.getElementById("graf-zaawansowane-toggle");
    const panelZaawansowane = document.getElementById("graf-zaawansowane");
    if (btnZaawansowane && panelZaawansowane) {
        btnZaawansowane.addEventListener("click", function () {
            const widoczne = panelZaawansowane.style.display !== "none";
            panelZaawansowane.style.display = widoczne ? "none" : "flex";
            const t = btnZaawansowane.lastChild;
            if (t && t.nodeType === 3) {
                t.textContent =
                    widoczne
                        ? " Opcje zaawansowane ▾"
                        : " Opcje zaawansowane ▴";
            }
        });
    }

    // --- odśwież układ: wróć do czystego drzewa radialnego ---
    // (kasuje ręczne przesunięcia węzłów i lokalne dowinięcia klikiem,
    // odtwarzając ładny "pączek" dla bieżącej głębokości i top-N).
    const btnOdswiez = document.getElementById("graf-odswiez");
    if (btnOdswiez) {
        btnOdswiez.addEventListener("click", function () {
            zaladujSiec(ctx);
        });
    }

    // --- metryka wielkości kółka: prace / IF / PK (bez przeładowania) ---
    if (ctx.selMetryka) {
        ctx.selMetryka.addEventListener("change", function () {
            ctx.metryka = ctx.selMetryka.value;
            przeliczRozmiary(ctx);
        });
    }

    // --- układ: radialny / drzewo / koncentryczny (bez przeładowania) ---
    if (ctx.selUklad) {
        ctx.selUklad.addEventListener("change", function () {
            ctx.uklad = ctx.selUklad.value;
            ulozGraf(ctx, true);
        });
    }

    // --- powiązania wewnątrz grupy: checkbox + próg "od ilu wspólnych prac" ---
    if (ctx.chkWewn) {
        ctx.chkWewn.addEventListener("change", function () {
            ctx.pokazWewn = ctx.chkWewn.checked;
            odswiezKrawedzieWewn(ctx);
        });
    }
    if (ctx.progWewnSlider) {
        ctx.progWewnSlider.addEventListener("input", function () {
            ctx.progWewn = parseInt(ctx.progWewnSlider.value, 10) || 1;
            if (ctx.progWewnLabel) {
                ctx.progWewnLabel.textContent = ctx.progWewn;
            }
            odswiezKrawedzieWewn(ctx);
        });
    }

    // --- wyszukiwanie po nazwisku ---
    if (ctx.inputSzukaj) {
        ctx.inputSzukaj.addEventListener("input", function () {
            szukaj(ctx, ctx.inputSzukaj.value);
        });
    }

    // --- pobierz graf jako PNG (cały graf, 2x, białe tło) ---
    const btnPobierz = document.getElementById("graf-pobierz");
    if (btnPobierz) {
        btnPobierz.addEventListener("click", function () {
            pobierzPlik(
                cy.png({ full: true, scale: 2, bg: "#ffffff" }),
                "siec-powiazan.png"
            );
        });
    }

    // --- pobierz graf jako SVG (wektorowy) ---
    const btnSvg = document.getElementById("graf-pobierz-svg");
    if (btnSvg && typeof cy.svg === "function") {
        btnSvg.addEventListener("click", function () {
            const svgStr = cy.svg({ full: true, bg: "#ffffff" });
            const blob = new Blob([svgStr], {
                type: "image/svg+xml;charset=utf-8"
            });
            const url = URL.createObjectURL(blob);
            pobierzPlik(url, "siec-powiazan.svg");
            URL.revokeObjectURL(url);
        });
    } else if (btnSvg) {
        btnSvg.style.display = "none"; // rozszerzenie SVG nie załadowane
    }
}
