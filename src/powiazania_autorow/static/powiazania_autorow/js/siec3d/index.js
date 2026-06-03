// Widok 3D sieci współautorstwa (3d-force-graph → Three.js → WebGL).
//
// Czyta DOKŁADNIE ten sam endpoint co widok 2D (siec.json) — żadnych zmian po
// stronie backendu. Mapowanie:
//   * węzeł  -> kula; rozmiar = wybrana metryka (prace / IF / PK),
//              kolor = poziom BFS (centrum -> liście),
//   * krawędź -> linia; grubość = liczba wspólnych publikacji.
// Interakcja (gratis z 3d-force-graph): obrót orbitalny i zoom myszą,
// klik = dolot kamery + panel z linkiem do autora, przeciąganie węzła =
// sprężysta reakcja układu siłowego (efekt "gumy" w 3D).

// Kolory wg poziomu: centrum złote, dalej chłodna paleta.
const PALETA = [
    "#ffd54a", "#4ea1ff", "#36c9c0", "#7ed957",
    "#c792ea", "#ff8a65", "#9aa7b2"
];

function kolorPoziomu(level) {
    return PALETA[Math.min(level || 0, PALETA.length - 1)];
}

// Escape do HTML — etykiety to nazwiska autorów z bazy (mogą teoretycznie
// zawierać znaki specjalne), a nodeLabel renderuje się jako HTML tooltipa.
function esc(s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) {
        return {
            "&": "&amp;", "<": "&lt;", ">": "&gt;",
            '"': "&quot;", "'": "&#39;"
        }[c];
    });
}

// nodeVal steruje OBJĘTOŚCIĄ kuli; metryki bywają duże (sumy IF/PK), więc
// 3d-force-graph i tak skaluje promień ~cbrt(val). Pilnujemy minimum, by
// węzły bez prac nie znikały.
function wartoscMetryki(n, metryka) {
    if (metryka === "if") { return Math.max(0.2, n.if_sum || 0); }
    if (metryka === "pk") { return Math.max(0.2, n.pk_sum || 0); }
    return Math.max(1, n.total_works || 1);
}

// siec.json -> {nodes, links}. Krawędzie drzewa (edges) i poprzeczne
// (extra_edges) łączymy w jeden zbiór linków.
function budujDane(data) {
    const nodes = (data.nodes || []).map(function (n) {
        return {
            id: String(n.id),
            label: n.label,
            url: n.url,
            level: n.level || 0,
            total_works: n.total_works || 0,
            if_sum: n.if_sum || 0,
            pk_sum: n.pk_sum || 0
        };
    });
    const krawedzie = [].concat(data.edges || [], data.extra_edges || []);
    const links = krawedzie.map(function (e) {
        return {
            source: String(e.source),
            target: String(e.target),
            shared: e.shared || 1
        };
    });
    return { nodes: nodes, links: links };
}

export function init(ForceGraph3D) {
    const el = document.getElementById("siec3d-container");
    if (!el || typeof ForceGraph3D !== "function") {
        return; // brak kontenera lub biblioteki — nic nie robimy
    }

    const autorId = String(el.dataset.autorId);
    const siecTpl = el.dataset.siecUrlTemplate;

    const sliderGleb = document.getElementById("siec3d-glebokosc");
    const sliderTopn = document.getElementById("siec3d-topn");
    const selMetryka = document.getElementById("siec3d-metryka");
    const glebLabel = document.getElementById("siec3d-glebokosc-label");
    const topnLabel = document.getElementById("siec3d-topn-label");
    const info = document.getElementById("siec3d-info");

    let metryka = selMetryka ? selMetryka.value : "works";

    const Graph = ForceGraph3D()(el)
        .backgroundColor("#0b1020")
        .nodeRelSize(4)
        .nodeVal(function (n) { return wartoscMetryki(n, metryka); })
        .nodeColor(function (n) { return kolorPoziomu(n.level); })
        .nodeOpacity(0.95)
        .nodeLabel(function (n) {
            return "<b>" + esc(n.label) + "</b><br>prace: " + (n.total_works | 0);
        })
        .linkColor(function () { return "rgba(255,255,255,0.16)"; })
        .linkWidth(function (l) { return Math.max(0.4, Math.log2(l.shared + 1)); })
        .linkOpacity(0.45)
        .onNodeClick(function (n) {
            // Dolot kamery do węzła (klasyczny recipe 3d-force-graph): kamera
            // ustawia się na osi środek–węzeł w stałej odległości i patrzy nań.
            const dist = 140;
            const r = 1 + dist / Math.max(1, Math.hypot(n.x, n.y, n.z));
            Graph.cameraPosition(
                { x: n.x * r, y: n.y * r, z: n.z * r }, n, 1000
            );
            if (info) {
                // Budujemy panel przez DOM (textContent + createElement),
                // bez innerHTML z danymi autora — zero ryzyka XSS.
                info.textContent = "";
                const b = document.createElement("b");
                b.textContent = n.label || "";
                info.appendChild(b);
                info.appendChild(document.createElement("br"));
                info.appendChild(
                    document.createTextNode("prace: " + (n.total_works | 0))
                );
                if (n.url) {
                    info.appendChild(document.createTextNode(" · "));
                    const a = document.createElement("a");
                    a.href = n.url; // ścieżka z reverse(); a.href nie wykonuje JS
                    a.textContent = "strona autora →";
                    info.appendChild(a);
                }
                info.style.display = "block";
            }
        });

    function dopasujRozmiar() {
        Graph.width(el.clientWidth).height(el.clientHeight);
    }
    dopasujRozmiar();
    window.addEventListener("resize", dopasujRozmiar);

    // Token sekwencji — szybkie ruchy suwaków odpalają kilka fetchy; render
    // aplikujemy tylko, gdy odpowiedź jest wciąż bieżąca.
    let seq = 0;
    function zaladuj() {
        const depth = sliderGleb ? parseInt(sliderGleb.value, 10) : 2;
        const topn = sliderTopn ? parseInt(sliderTopn.value, 10) : 10;
        const url = siecTpl.replace("/0/", "/" + autorId + "/")
            + "?depth=" + depth + "&topn=" + topn;
        const moj = ++seq;
        fetch(url)
            .then(function (r) {
                if (!r.ok) { throw new Error("HTTP " + r.status); }
                return r.json();
            })
            .then(function (data) {
                if (moj !== seq) { return; }
                Graph.graphData(budujDane(data));
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
        deb = setTimeout(zaladuj, 250);
    }

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
            // przestawienie akcesora wymusza ponowne policzenie rozmiarów kul
            Graph.nodeVal(function (n) { return wartoscMetryki(n, metryka); });
        });
    }

    zaladuj();
}
