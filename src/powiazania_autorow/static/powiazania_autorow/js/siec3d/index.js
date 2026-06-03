// Widok 3D sieci współautorstwa (3d-force-graph → Three.js → WebGL).
//
// Czyta DOKŁADNIE ten sam endpoint co widok 2D (siec.json) — żadnych zmian po
// stronie backendu. Mapowanie:
//   * węzeł  -> kula; rozmiar = wybrana metryka (prace / IF / PK),
//              kolor = poziom BFS (centrum -> liście),
//   * krawędź -> linia; grubość = liczba wspólnych publikacji.
// Interakcja (gratis z 3d-force-graph): obrót orbitalny i zoom myszą,
// klik = dolot kamery + panel akcji jak w 2D, przeciąganie węzła = sprężysta
// reakcja układu siłowego (efekt "gumy" w 3D).
//
// Opcje: rok od-do i "tylko aktualnie zatrudnieni" idą do siec.json
// (przeładowanie z serwera); "powiązania w grupie" (extra_edges, domyślnie
// WYŁĄCZONE) z progiem dorysowujemy po stronie klienta w innym kolorze, bez
// przerysowywania układu; "pokaż etykiety" rysuje nazwiska top-N węzłów;
// "odśwież układ" rozgrzewa symulację i dopasowuje kamerę.

import SpriteText from "three-spritetext";

// Kolory wg poziomu: centrum złote, dalej chłodna paleta (dobre na ciemnym tle).
const PALETA = [
    "#ffd54a", "#4ea1ff", "#36c9c0", "#7ed957",
    "#c792ea", "#ff8a65", "#9aa7b2"
];

// Ile najważniejszych (wg bieżącej metryki) węzłów dostaje stałą etykietę.
const TOP_ETYKIETY = 25;

function kolorPoziomu(level) {
    return PALETA[Math.min(level || 0, PALETA.length - 1)];
}

// Escape do HTML — etykiety to nazwiska autorów z bazy; nodeLabel renderuje
// się jako HTML tooltipa.
function esc(s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) {
        return {
            "&": "&amp;", "<": "&lt;", ">": "&gt;",
            '"': "&quot;", "'": "&#39;"
        }[c];
    });
}

// nodeVal steruje OBJĘTOŚCIĄ kuli; metryki bywają duże (sumy IF/PK), a
// 3d-force-graph i tak skaluje promień ~cbrt(val). Pilnujemy minimum.
function wartoscMetryki(n, metryka) {
    if (metryka === "if") { return Math.max(0.2, n.if_sum || 0); }
    if (metryka === "pk") { return Math.max(0.2, n.pk_sum || 0); }
    return Math.max(1, n.total_works || 1);
}

// Link akcji jak w panelu 2D (panel.js/dom.js) — odtworzony lokalnie, bo
// widok 3D to osobny bundle i nie importuje modułów widoku 2D.
function linkAkcja(href, text, zewnetrzny) {
    const a = document.createElement("a");
    a.href = href;
    a.textContent = text;
    a.style.display = "block";
    a.style.marginTop = "4px";
    if (zewnetrzny) {
        a.target = "_blank";
        a.rel = "noopener";
    }
    return a;
}

export function init(ForceGraph3D) {
    const el = document.getElementById("siec3d-container");
    if (!el || typeof ForceGraph3D !== "function") {
        return; // brak kontenera lub biblioteki — nic nie robimy
    }

    const autorId = String(el.dataset.autorId);
    const siecTpl = el.dataset.siecUrlTemplate;
    const graf3dTpl = el.dataset.graf3dUrlTemplate;

    // --- kontrolki podstawowe ---
    const sliderGleb = document.getElementById("siec3d-glebokosc");
    const sliderTopn = document.getElementById("siec3d-topn");
    const selMetryka = document.getElementById("siec3d-metryka");
    const glebLabel = document.getElementById("siec3d-glebokosc-label");
    const topnLabel = document.getElementById("siec3d-topn-label");
    const info = document.getElementById("siec3d-info");
    const ukladEl = document.getElementById("siec3d-uklad");
    const chkEtykiety = document.getElementById("siec3d-etykiety-chk");

    // --- opcje zaawansowane ---
    const rokOdEl = document.getElementById("siec3d-rok-od");
    const rokDoEl = document.getElementById("siec3d-rok-do");
    const chkZatr = document.getElementById("siec3d-zatrudnieni-chk");
    const chkWewn = document.getElementById("siec3d-wewnetrzne-chk");
    const progWewn = document.getElementById("siec3d-wewn-prog");
    const progWewnLabel = document.getElementById("siec3d-wewn-prog-label");

    let metryka = selMetryka ? selMetryka.value : "works";
    let etykietyOn = chkEtykiety ? chkEtykiety.checked : false;
    // ostatnio pobrana sieć (raw siec.json) — do klienckiego przebudowania
    // linków przy zmianie opcji "powiązania w grupie" bez ponownego fetcha.
    let rawData = { nodes: [], edges: [], extra_edges: [] };

    const Graph = ForceGraph3D()(el)
        .backgroundColor("#0b1020")
        .nodeRelSize(4)
        .nodeVal(function (n) { return wartoscMetryki(n, metryka); })
        .nodeColor(function (n) { return kolorPoziomu(n.level); })
        .nodeOpacity(0.95)
        .nodeLabel(function (n) {
            return "<b>" + esc(n.label) + "</b><br>prace: " + (n.total_works | 0);
        })
        // etykieta jako sprite obok kuli (extend = nie zastępuje kuli);
        // tylko dla top-N i gdy włączone "pokaż etykiety"
        .nodeThreeObjectExtend(true)
        .linkColor(function (l) {
            // powiązania w grupie wyróżnione kolorem (bursztyn), drzewo białe
            return l.grupa ? "rgba(255,179,71,0.55)" : "rgba(255,255,255,0.16)";
        })
        .linkWidth(function (l) { return Math.max(0.4, Math.log2(l.shared + 1)); })
        .linkOpacity(0.5)
        .onNodeClick(function (n) {
            // Dolot kamery do węzła (klasyczny recipe 3d-force-graph).
            const dist = 140;
            const r = 1 + dist / Math.max(1, Math.hypot(n.x, n.y, n.z));
            Graph.cameraPosition(
                { x: n.x * r, y: n.y * r, z: n.z * r }, n, 1000
            );
            pokazPanel(n);
        });

    // Etykieta węzła (SpriteText) — tylko dla top-N i gdy włączone.
    function budujEtykiete(n) {
        if (!etykietyOn || !n._top) { return null; }
        const s = new SpriteText(n.label || "");
        s.color = "#fff";
        s.textHeight = 5;
        s.backgroundColor = "rgba(11,16,32,0.65)";
        s.padding = 1.5;
        s.position.set(0, 9, 0); // unieś nad kulę
        return s;
    }
    // Re-assign przez świeży wrapper => 3d-force-graph regeneruje obiekty
    // węzłów (np. po przełączeniu etykiet albo zmianie listy top-N).
    function odswiezEtykiety() {
        Graph.nodeThreeObject(function (n) { return budujEtykiete(n); });
    }
    odswiezEtykiety();

    // Panel akcji jak w 2D: nagłówek (nazwisko + tytuł), ORCID i linki
    // kontekstowe. Budowany przez DOM (textContent/createElement) — zero XSS.
    function pokazPanel(n) {
        if (!info) { return; }
        info.textContent = "";
        const strong = document.createElement("strong");
        strong.textContent = (n.label || "") + (n.tytul ? ", " + n.tytul : "");
        info.appendChild(strong);

        if (n.orcid) {
            const o = document.createElement("div");
            o.textContent = "ORCID: " + n.orcid;
            o.style.fontSize = "11px";
            o.style.color = "#666";
            o.style.marginTop = "2px";
            info.appendChild(o);
        }
        if (n.url) {
            info.appendChild(linkAkcja(n.url, "Pokaż prace", false));
        }
        if (graf3dTpl) {
            info.appendChild(linkAkcja(
                graf3dTpl.replace("/0/", "/" + n.id + "/"),
                "Pokaż sieć powiązań (3D)", false
            ));
        }
        if (n.pbn_url) {
            info.appendChild(linkAkcja(n.pbn_url, "Zobacz w PBN", true));
        }
        if (n.orcid) {
            info.appendChild(linkAkcja(
                "https://orcid.org/" + n.orcid, "Zobacz w ORCID", true
            ));
        }
        info.style.display = "block";
    }

    function mapLink(e, grupa) {
        return {
            source: String(e.source),
            target: String(e.target),
            shared: e.shared || 1,
            grupa: !!grupa
        };
    }

    // Ustaw flagę _top na top-N węzłach wg bieżącej metryki (do etykiet).
    function oznaczTop(nodes) {
        nodes.forEach(function (n) { n._top = false; });
        nodes.slice()
            .sort(function (a, b) {
                return wartoscMetryki(b, metryka) - wartoscMetryki(a, metryka);
            })
            .slice(0, TOP_ETYKIETY)
            .forEach(function (n) { n._top = true; });
    }

    // Linki dla bieżącego układu: krawędzie drzewa zawsze; powiązania w grupie
    // (extra_edges) tylko gdy włączone i poza układem "drzewo" (cykle psują DAG).
    function zbudujLinki(uklad) {
        const links = (rawData.edges || []).map(function (e) {
            return mapLink(e, false);
        });
        if (uklad !== "drzewo" && chkWewn && chkWewn.checked) {
            const prog = progWewn ? (parseInt(progWewn.value, 10) || 1) : 1;
            (rawData.extra_edges || []).forEach(function (e) {
                if ((e.shared || 1) >= prog) { links.push(mapLink(e, true)); }
            });
        }
        return links;
    }

    // "Sferyczne powłoki": każdy poziom BFS na własnej sferze (promień ∝ poziom),
    // węzły rozłożone równomiernie metodą Fibonacciego. Centrum w środku.
    function ustawSfery(nodes, R) {
        const wgPoziomu = {};
        nodes.forEach(function (n) {
            const l = n.level || 0;
            (wgPoziomu[l] = wgPoziomu[l] || []).push(n);
        });
        const GA = Math.PI * (3 - Math.sqrt(5)); // złoty kąt
        Object.keys(wgPoziomu).forEach(function (lk) {
            const grupa = wgPoziomu[lk];
            const promien = Number(lk) * R;
            const k = grupa.length;
            grupa.forEach(function (n, i) {
                if (promien === 0) { n.fx = 0; n.fy = 0; n.fz = 0; return; }
                const y = k === 1 ? 0 : 1 - (i / (k - 1)) * 2;
                const r = Math.sqrt(Math.max(0, 1 - y * y));
                const theta = i * GA;
                n.fx = promien * Math.cos(theta) * r;
                n.fy = promien * y;
                n.fz = promien * Math.sin(theta) * r;
            });
        });
    }

    // Przełączanie formy układu. Drzewo = dagMode radialny (krawędzie drzewa są
    // acykliczne). Warstwy = poziom→oś Z, X/Y swobodne. Sfery = pozycje
    // zamrożone. Siłowy = brak ograniczeń (domyślna chmura).
    function zastosujUklad(uklad) {
        const nodes = Graph.graphData().nodes;
        if (uklad === "drzewo") {
            nodes.forEach(function (n) { n.fx = n.fy = n.fz = undefined; });
            Graph.dagMode("radialout").dagLevelDistance(70)
                .onDagError(function () {});
        } else if (uklad === "warstwy") {
            Graph.dagMode(null);
            nodes.forEach(function (n) {
                n.fx = undefined; n.fy = undefined; n.fz = (n.level || 0) * 80;
            });
        } else if (uklad === "sfery") {
            Graph.dagMode(null);
            ustawSfery(nodes, 95);
        } else { // siłowy
            Graph.dagMode(null);
            nodes.forEach(function (n) { n.fx = n.fy = n.fz = undefined; });
        }
        Graph.d3ReheatSimulation();
    }

    // Pełna przebudowa (świeże węzły) — przy pobraniu danych i zmianie układu.
    function render() {
        const uklad = ukladEl ? ukladEl.value : "sila";
        const nodes = (rawData.nodes || []).map(function (n) {
            return {
                id: String(n.id),
                label: n.label,
                url: n.url,
                tytul: n.tytul,
                orcid: n.orcid,
                pbn_url: n.pbn_url,
                level: n.level || 0,
                total_works: n.total_works || 0,
                if_sum: n.if_sum || 0,
                pk_sum: n.pk_sum || 0
            };
        });
        oznaczTop(nodes);
        Graph.graphData({ nodes: nodes, links: zbudujLinki(uklad) });
        zastosujUklad(uklad);
    }

    // Przebudowa SAMYCH krawędzi z zachowaniem węzłów (i ich pozycji) — dla
    // przełącznika/progu "powiązań w grupie", żeby nie przerzucać układu.
    function przebudujKrawedzie() {
        const uklad = ukladEl ? ukladEl.value : "sila";
        const nodes = Graph.graphData().nodes;
        Graph.graphData({ nodes: nodes, links: zbudujLinki(uklad) });
    }

    function dopasujRozmiar() {
        Graph.width(el.clientWidth).height(el.clientHeight);
    }
    dopasujRozmiar();
    window.addEventListener("resize", dopasujRozmiar);

    // Token sekwencji — szybkie ruchy suwaków/filtrów odpalają kilka fetchy;
    // render aplikujemy tylko dla wciąż bieżącej odpowiedzi.
    let seq = 0;
    function zaladuj() {
        const depth = sliderGleb ? parseInt(sliderGleb.value, 10) : 2;
        const topn = sliderTopn ? parseInt(sliderTopn.value, 10) : 10;
        let p = "depth=" + depth + "&topn=" + topn;
        if (rokOdEl && rokOdEl.value) {
            p += "&rok_od=" + encodeURIComponent(rokOdEl.value);
        }
        if (rokDoEl && rokDoEl.value) {
            p += "&rok_do=" + encodeURIComponent(rokDoEl.value);
        }
        if (chkZatr && chkZatr.checked) {
            p += "&tylko_zatrudnieni=1";
        }
        const url = siecTpl.replace("/0/", "/" + autorId + "/") + "?" + p;
        const moj = ++seq;
        fetch(url)
            .then(function (r) {
                if (!r.ok) { throw new Error("HTTP " + r.status); }
                return r.json();
            })
            .then(function (data) {
                if (moj !== seq) { return; }
                rawData = data;
                render();
            })
            .catch(function (e) {
                if (info) {
                    info.textContent = "Błąd: " + e.message;
                    info.style.display = "block";
                }
            });
    }

    let deb = null;
    function zaladujZwloka() {
        if (deb) { clearTimeout(deb); }
        deb = setTimeout(zaladuj, 300);
    }

    // --- podstawowe ---
    if (sliderGleb) {
        sliderGleb.addEventListener("input", function () {
            if (glebLabel) { glebLabel.textContent = sliderGleb.value; }
            zaladujZwloka();
        });
    }
    if (sliderTopn) {
        sliderTopn.addEventListener("input", function () {
            if (topnLabel) { topnLabel.textContent = sliderTopn.value; }
            zaladujZwloka();
        });
    }
    if (selMetryka) {
        selMetryka.addEventListener("change", function () {
            metryka = selMetryka.value;
            Graph.nodeVal(function (n) { return wartoscMetryki(n, metryka); });
            // top-N (a więc i etykiety) zależy od metryki
            oznaczTop(Graph.graphData().nodes);
            odswiezEtykiety();
        });
    }
    if (ukladEl) {
        // przez render(), bo "drzewo" wymaga przefiltrowania krawędzi do
        // samego drzewa (potem zastosujUklad nada formę)
        ukladEl.addEventListener("change", render);
    }
    if (chkEtykiety) {
        chkEtykiety.addEventListener("change", function () {
            etykietyOn = chkEtykiety.checked;
            odswiezEtykiety();
        });
    }

    // --- zaawansowane: rok / zatrudnieni -> przeładuj sieć ---
    if (rokOdEl) { rokOdEl.addEventListener("input", zaladujZwloka); }
    if (rokDoEl) { rokDoEl.addEventListener("input", zaladujZwloka); }
    if (chkZatr) { chkZatr.addEventListener("change", zaladuj); }

    // --- zaawansowane: powiązania w grupie -> przebuduj SAME linki ---
    if (chkWewn) { chkWewn.addEventListener("change", przebudujKrawedzie); }
    if (progWewn) {
        progWewn.addEventListener("input", function () {
            if (progWewnLabel) { progWewnLabel.textContent = progWewn.value; }
            przebudujKrawedzie();
        });
    }

    // --- odśwież układ: rozgrzej symulację i dopasuj kamerę ---
    const btnOdswiez = document.getElementById("siec3d-odswiez");
    if (btnOdswiez) {
        btnOdswiez.addEventListener("click", function () {
            Graph.d3ReheatSimulation();
            Graph.zoomToFit(700, 40);
        });
    }

    // --- rozwijane "Opcje zaawansowane" (jak w 2D) ---
    const btnZaaw = document.getElementById("siec3d-zaawansowane-toggle");
    const panelZaaw = document.getElementById("siec3d-zaawansowane");
    if (btnZaaw && panelZaaw) {
        btnZaaw.addEventListener("click", function () {
            const widoczne = panelZaaw.style.display !== "none";
            panelZaaw.style.display = widoczne ? "none" : "flex";
            const t = btnZaaw.lastChild;
            if (t && t.nodeType === 3) {
                t.textContent = widoczne
                    ? " Opcje zaawansowane ▾"
                    : " Opcje zaawansowane ▴";
            }
        });
    }

    zaladuj();
}
