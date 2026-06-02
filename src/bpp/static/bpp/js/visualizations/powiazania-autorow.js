// Eksplorator sieci współautorstwa — Cytoscape.js + fcose.
// Dane z endpointu bpp:browse_autor_powiazania_dane (per autor). Klik w węzeł
// dociąga jego współautorów i animowanie rozrasta sieć. Suwak top-N steruje
// liczbą sąsiadów rysowanych na rozwinięcie (filtr po stronie klienta).
(function () {
    "use strict";

    function init() {
        var container = document.getElementById("cytoscape-container");
        if (!container) {
            return;
        }
        if (typeof cytoscape === "undefined") {
            console.error("Cytoscape.js nie został załadowany.");
            return;
        }

        var autorId = String(container.dataset.autorId);
        var urlTemplate = container.dataset.daneUrlTemplate; // .../autor/0/powiazania/dane.json
        var emptyEl = document.getElementById("graf-empty");
        var tooltip = document.getElementById("graf-tooltip");
        var panel = document.getElementById("graf-panel");
        var slider = document.getElementById("graf-topn");
        var sliderLabel = document.getElementById("graf-topn-label");

        var topN = parseInt(slider.value, 10);
        var expanded = {};        // id -> true (węzeł rozwinięty)
        var neighborsCache = {};  // id -> [{id,label,url,shared}, ...]
        var labelCache = {};      // id -> label
        var urlCache = {};        // id -> url

        var cy = cytoscape({
            container: container,
            minZoom: 0.1,
            maxZoom: 4,
            wheelSensitivity: 0.2,
            style: [
                {
                    selector: "node",
                    style: {
                        "label": "data(label)",
                        "background-color": "#4A90E2",
                        "width": "mapData(degree, 1, 30, 18, 64)",
                        "height": "mapData(degree, 1, 30, 18, 64)",
                        "font-size": 10,
                        "color": "#222",
                        "text-valign": "bottom",
                        "text-halign": "center",
                        "text-margin-y": 3,
                        "min-zoomed-font-size": 7
                    }
                },
                {
                    selector: "node.centrum",
                    style: { "background-color": "#FF6B6B", "font-weight": "bold" }
                },
                {
                    selector: "node.rozwiniety",
                    style: { "border-width": 2, "border-color": "#2c6cb0" }
                },
                {
                    selector: "edge",
                    style: {
                        "width": "mapData(shared, 1, 20, 1, 9)",
                        "line-color": "#bbb",
                        "curve-style": "haystack",
                        "opacity": 0.55
                    }
                }
            ]
        });

        function daneUrl(id) {
            return urlTemplate.replace("/0/", "/" + id + "/");
        }

        // Czyszczenie + budowa DOM bez innerHTML — etykiety pochodzą z nazwisk
        // autorów (dane z bazy), więc nie wstrzykujemy ich jako HTML (XSS).
        function wyczysc(el) {
            while (el.firstChild) {
                el.removeChild(el.firstChild);
            }
        }

        function pokazPanelAutora(label, url) {
            wyczysc(panel);
            var strong = document.createElement("strong");
            strong.textContent = label;
            var link = document.createElement("a");
            link.href = url;
            link.textContent = "Przejdź do strony autora →";
            panel.appendChild(strong);
            panel.appendChild(document.createElement("br"));
            panel.appendChild(link);
            panel.style.display = "block";
        }

        function pokazBlad(msg) {
            panel.textContent = msg;
            panel.style.display = "block";
        }

        function zapamietaj(node) {
            labelCache[node.id] = node.label;
            urlCache[node.id] = node.url;
        }

        function uruchomLayout() {
            cy.layout({
                name: "fcose",
                animate: true,
                animationDuration: 600,
                randomize: false,
                fit: true,
                padding: 40
            }).run();
        }

        function dodajWezel(id, label, url, isCentrum) {
            id = String(id);
            if (cy.getElementById(id).nonempty()) {
                return;
            }
            cy.add({
                group: "nodes",
                data: { id: id, label: label, url: url, degree: 1 },
                classes: isCentrum ? "centrum" : ""
            });
        }

        function dodajKrawedz(zrodloId, n) {
            var lo = Math.min(Number(zrodloId), Number(n.id));
            var hi = Math.max(Number(zrodloId), Number(n.id));
            var eid = "e" + lo + "_" + hi;
            if (cy.getElementById(eid).nonempty()) {
                return;
            }
            cy.add({
                group: "edges",
                data: {
                    id: eid,
                    source: String(zrodloId),
                    target: String(n.id),
                    shared: n.shared
                }
            });
        }

        function odswiezStopnie() {
            cy.batch(function () {
                cy.nodes().forEach(function (node) {
                    node.data("degree", node.degree());
                });
            });
        }

        function pokazSasiadow(id, neighbors) {
            neighbors.slice(0, topN).forEach(function (n) {
                zapamietaj(n);
                dodajWezel(n.id, n.label, n.url, false);
                dodajKrawedz(id, n);
            });
            odswiezStopnie();
        }

        function rozwin(id) {
            id = String(id);
            if (expanded[id]) {
                return;
            }
            expanded[id] = true;
            cy.getElementById(id).addClass("rozwiniety");

            if (neighborsCache[id]) {
                pokazSasiadow(id, neighborsCache[id]);
                uruchomLayout();
                return;
            }
            fetch(daneUrl(id))
                .then(function (r) {
                    if (!r.ok) { throw new Error("HTTP " + r.status); }
                    return r.json();
                })
                .then(function (data) {
                    neighborsCache[id] = data.neighbors;
                    zapamietaj(data.center);
                    pokazSasiadow(id, data.neighbors);
                    uruchomLayout();
                })
                .catch(function (e) {
                    pokazBlad("Błąd pobierania danych: " + e.message);
                });
        }

        function przebuduj() {
            cy.elements().remove();
            dodajWezel(
                autorId,
                labelCache[autorId] || container.dataset.autorLabel,
                urlCache[autorId] || "#",
                true
            );
            cy.getElementById(autorId).addClass("rozwiniety");
            pokazSasiadow(autorId, neighborsCache[autorId] || []);
            Object.keys(expanded).forEach(function (id) {
                if (id !== autorId && neighborsCache[id]) {
                    dodajWezel(id, labelCache[id] || id, urlCache[id] || "#", false);
                    cy.getElementById(id).addClass("rozwiniety");
                    pokazSasiadow(id, neighborsCache[id]);
                }
            });
            uruchomLayout();
        }

        // --- start: centrum + jego sąsiedzi ---
        fetch(daneUrl(autorId))
            .then(function (r) {
                if (!r.ok) { throw new Error("HTTP " + r.status); }
                return r.json();
            })
            .then(function (data) {
                zapamietaj(data.center);
                if (!data.neighbors.length) {
                    container.style.display = "none";
                    if (emptyEl) { emptyEl.style.display = "block"; }
                    return;
                }
                neighborsCache[autorId] = data.neighbors;
                expanded[autorId] = true;
                dodajWezel(data.center.id, data.center.label, data.center.url, true);
                cy.getElementById(autorId).addClass("rozwiniety");
                pokazSasiadow(autorId, data.neighbors);
                uruchomLayout();
            })
            .catch(function (e) {
                if (emptyEl) {
                    emptyEl.textContent = "Błąd: " + e.message;
                    emptyEl.style.display = "block";
                }
            });

        // --- hover -> tooltip ---
        cy.on("mouseover", "node", function (evt) {
            wyczysc(tooltip);
            var strong = document.createElement("strong");
            strong.textContent = evt.target.data("label");
            tooltip.appendChild(strong);
            tooltip.style.display = "block";
        });
        cy.on("mousemove", function (evt) {
            var pos = evt.renderedPosition || { x: 0, y: 0 };
            tooltip.style.left = (pos.x + 14) + "px";
            tooltip.style.top = (pos.y + 14) + "px";
        });
        cy.on("mouseout", "node", function () {
            tooltip.style.display = "none";
        });

        // --- klik -> rozwiń + panel z linkiem ---
        cy.on("tap", "node", function (evt) {
            var n = evt.target;
            rozwin(n.id());
            pokazPanelAutora(n.data("label"), n.data("url"));
        });

        // --- suwak top-N -> przebuduj z cache ---
        slider.addEventListener("input", function () {
            topN = parseInt(slider.value, 10);
            if (sliderLabel) { sliderLabel.textContent = topN; }
            przebuduj();
        });
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", init);
    } else {
        init();
    }
})();
