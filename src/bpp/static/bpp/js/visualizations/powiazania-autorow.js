// Eksplorator sieci współautorstwa — Cytoscape.js.
// Dane z endpointu bpp:browse_autor_powiazania_dane (per autor).
//
// Układ jest radialny i PRZYROSTOWY: autor centralny w środku, jego
// współautorzy w pierścieniu wokół niego, a każde rozwinięcie kolejnego węzła
// "zakwita" własnym pączkiem współautorów wokół KLIKNIĘTEGO węzła. Istniejące
// węzły nigdy nie są przesuwane — dzięki temu rozwijanie obrzeży nie nadpisuje
// głównego wykresu ani nie tworzy plątaniny (to był problem globalnego layoutu).
//
// Dwa suwaki sterują widokiem (oba przeładowują sieć z serwera):
//   * "Maks. współautorów na węzeł" (top-N) — ilu najsilniejszych (najwięcej
//     wspólnych publikacji) sąsiadów rozwijamy na każdym węźle,
//   * "Głębokość sieci" — na ile poziomów BFS auto-rozwinąć wianuszek bez
//     klikania (endpoint siec.json liczy to po stronie serwera).
// Klik w węzeł nadal lokalnie dowija jego współautorów (pączek) ponad to.
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
        var siecUrlTemplate = container.dataset.siecUrlTemplate; // .../autor/0/powiazania/siec.json
        var grafUrlTemplate = container.dataset.grafUrlTemplate; // .../autor/0/powiazania/
        var emptyEl = document.getElementById("graf-empty");
        var notkaEl = document.getElementById("graf-notka");
        var tooltip = document.getElementById("graf-tooltip");
        var panel = document.getElementById("graf-panel");
        var slider = document.getElementById("graf-topn");
        var sliderLabel = document.getElementById("graf-topn-label");
        var sliderGleb = document.getElementById("graf-glebokosc");
        var sliderGlebLabel = document.getElementById("graf-glebokosc-label");
        var selMetryka = document.getElementById("graf-metryka");
        var selUklad = document.getElementById("graf-uklad");
        var inputSzukaj = document.getElementById("graf-szukaj");
        var chkWewn = document.getElementById("graf-wewnetrzne-chk");
        var progWewnSlider = document.getElementById("graf-wewn-prog");
        var progWewnLabel = document.getElementById("graf-wewn-prog-label");

        var topN = parseInt(slider.value, 10);
        var glebokosc = parseInt(sliderGleb.value, 10) || 1;
        // Etykiety synchronizujemy z realną wartością suwaka: przeglądarka po
        // odświeżeniu potrafi przywrócić starą pozycję suwaka, a statyczna
        // etykieta z szablonu rozjechałaby się z tym, co faktycznie rysujemy.
        if (sliderLabel) { sliderLabel.textContent = topN; }
        if (sliderGlebLabel) { sliderGlebLabel.textContent = glebokosc; }

        var metryka = selMetryka ? selMetryka.value : "works";
        var uklad = selUklad ? selUklad.value : "radial"; // radial | drzewo | koncentryczny
        var lastTree = null;      // { centerId, children, levelOf } z ostatniej sieci
        var pokazWewn = false;    // czy rysujemy krawędzie wewnątrz grupy
        var progWewn = progWewnSlider ? parseInt(progWewnSlider.value, 10) || 1 : 1;
        var extraEdges = [];      // ostatnie krawędzie poprzeczne z serwera
        var expanded = {};        // id -> true (węzeł rozwinięty)
        var neighborsCache = {};  // id -> [{id,label,url,shared,...}, ...]
        var infoCache = {};       // id -> pełny payload autora (label,url,tytul,...)
        var animujDodawanie = true; // fade-in nowych elementów (off przy rebuildzie)

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
                        "width": "data(rozmiar)",
                        "height": "data(rozmiar)",
                        "font-size": 10,
                        "color": "#222",
                        "text-valign": "bottom",
                        "text-halign": "center",
                        "text-margin-y": 3,
                        "min-zoomed-font-size": 7,
                        "transition-property": "opacity",
                        "transition-duration": "0.4s"
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
                        "opacity": 0.55,
                        "transition-property": "opacity",
                        "transition-duration": "0.4s"
                    }
                },
                {
                    selector: "edge.podswietlona",
                    style: { "line-color": "#2c6cb0", "opacity": 0.9 }
                },
                {
                    // Świeżo dodane elementy startują niewidoczne; zdjęcie klasy
                    // w następnej klatce uruchamia płynny fade-in (transition).
                    selector: ".nowy",
                    style: { "opacity": 0 }
                },
                {
                    // Krawędzie "poprzeczne" (powiązania wewnątrz grupy) — żeby
                    // odróżnić je od drzewa rozwijania: przerywane, pomarańczowe.
                    selector: "edge.wewnetrzna",
                    style: {
                        "line-color": "#e08a3c",
                        "line-style": "dashed",
                        "opacity": 0.5,
                        "width": "mapData(shared, 1, 20, 1, 5)"
                    }
                },
                {
                    // Wyszukiwanie: trafiony węzeł na wierzch, jaskrawy.
                    selector: "node.znaleziony",
                    style: {
                        "background-color": "#FFD400",
                        "border-width": 3,
                        "border-color": "#c79100",
                        "font-weight": "bold",
                        "color": "#000",
                        "z-index": 9999
                    }
                },
                {
                    selector: "edge.powiazana-szukana",
                    style: {
                        "line-color": "#d7263d",
                        "opacity": 0.95,
                        "width": "mapData(shared, 1, 20, 2, 9)",
                        "z-index": 9998
                    }
                },
                {
                    // Reszta grafu przygaszona, gdy coś wyszukano.
                    selector: ".przygaszony",
                    style: { "opacity": 0.12 }
                }
            ]
        });

        function daneUrl(id) {
            return urlTemplate.replace("/0/", "/" + id + "/");
        }

        function siecUrl(id, depth, topn) {
            return siecUrlTemplate.replace("/0/", "/" + id + "/")
                + "?depth=" + depth + "&topn=" + topn;
        }

        function grafUrl(id) {
            return grafUrlTemplate.replace("/0/", "/" + id + "/");
        }

        // Wybrana metryka węzła (suma prac / IF / PK) — surowe wartości siedzą
        // w danych węzła, więc zmiana metryki nie wymaga ponownego pobrania.
        function wartoscMetryki(node) {
            if (metryka === "if") { return node.data("if_sum") || 0; }
            if (metryka === "pk") { return node.data("pk_sum") || 0; }
            return node.data("works") || 0;
        }

        // Wielkość kółka = wybrana metryka, znormalizowana do maksimum w grafie
        // (skala pierwiastkowa + niski clamp), żeby różne metryki o różnych
        // zakresach dawały porównywalnie czytelny rozrzut wielkości.
        function przeliczRozmiary() {
            var maxV = 1;
            cy.nodes().forEach(function (n) {
                var v = wartoscMetryki(n);
                if (v > maxV) { maxV = v; }
            });
            cy.batch(function () {
                cy.nodes().forEach(function (n) {
                    var d = 12 + 34 * Math.sqrt(wartoscMetryki(n) / maxV);
                    n.data("rozmiar", Math.max(12, Math.min(46, d)));
                });
            });
        }

        // Czyszczenie + budowa DOM bez innerHTML — etykiety pochodzą z nazwisk
        // autorów (dane z bazy), więc nie wstrzykujemy ich jako HTML (XSS).
        function wyczysc(el) {
            while (el.firstChild) {
                el.removeChild(el.firstChild);
            }
        }

        function linkAkcja(href, text, zewnetrzny) {
            var a = document.createElement("a");
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

        // Panel akcji po kliknięciu w węzeł: nagłówek (nazwisko + tytuł), ORCID,
        // oraz linki kontekstowe — PBN/ORCID tylko gdy autor ma identyfikator.
        function pokazPanelAutora(info) {
            wyczysc(panel);

            var strong = document.createElement("strong");
            strong.textContent =
                info.label + (info.tytul ? ", " + info.tytul : "");
            panel.appendChild(strong);

            if (info.orcid) {
                var orcidLinia = document.createElement("div");
                orcidLinia.textContent = "ORCID: " + info.orcid;
                orcidLinia.style.fontSize = "11px";
                orcidLinia.style.color = "#666";
                orcidLinia.style.marginTop = "2px";
                panel.appendChild(orcidLinia);
            }

            panel.appendChild(linkAkcja(info.url || "#", "Pokaż prace", false));
            if (info.id) {
                panel.appendChild(
                    linkAkcja(grafUrl(info.id), "Pokaż sieć powiązań", false)
                );
            }
            if (info.pbn_url) {
                panel.appendChild(linkAkcja(info.pbn_url, "Zobacz w PBN", true));
            }
            if (info.orcid) {
                panel.appendChild(
                    linkAkcja(
                        "https://orcid.org/" + info.orcid, "Zobacz w ORCID", true
                    )
                );
            }
            panel.style.display = "block";
        }

        function pokazBlad(msg) {
            panel.textContent = msg;
            panel.style.display = "block";
        }

        function pokazTooltipAutor(info) {
            wyczysc(tooltip);
            var strong = document.createElement("strong");
            strong.textContent =
                info.label + (info.tytul ? ", " + info.tytul : "");
            tooltip.appendChild(strong);
            if (info.orcid) {
                var l = document.createElement("div");
                l.textContent = "ORCID: " + info.orcid;
                l.style.fontSize = "11px";
                l.style.color = "#666";
                tooltip.appendChild(l);
            }
            tooltip.style.display = "block";
        }

        function pokazTooltipKrawedz(labelA, labelB, shared) {
            wyczysc(tooltip);
            var para = document.createElement("div");
            para.textContent = (labelA || "?") + " ↔ " + (labelB || "?");
            var ile = document.createElement("strong");
            var n = shared || 0;
            ile.textContent =
                n + (n === 1 ? " wspólna publikacja" : " wspólnych publikacji");
            tooltip.appendChild(para);
            tooltip.appendChild(ile);
            tooltip.style.display = "block";
        }

        function zapamietaj(info) {
            infoCache[String(info.id)] = info;
        }

        function dodajWezel(id, info, isCentrum, seedPos) {
            id = String(id);
            var node = cy.getElementById(id);
            if (node.nonempty()) {
                return node;
            }
            var ele = cy.add({
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
            if (animujDodawanie) { ele.addClass("nowy"); }
            return ele;
        }

        function dodajKrawedz(zrodloId, n) {
            var lo = Math.min(Number(zrodloId), Number(n.id));
            var hi = Math.max(Number(zrodloId), Number(n.id));
            var eid = "e" + lo + "_" + hi;
            if (cy.getElementById(eid).nonempty()) {
                return;
            }
            var ele = cy.add({
                group: "edges",
                data: {
                    id: eid,
                    source: String(zrodloId),
                    target: String(n.id),
                    shared: n.shared
                }
            });
            if (animujDodawanie) { ele.addClass("nowy"); }
        }

        // Krawędź z gotowych id (bez obiektu sąsiada) — dla renderu siatki BFS.
        function dodajKrawedzProsta(source, target, shared) {
            var lo = Math.min(Number(source), Number(target));
            var hi = Math.max(Number(source), Number(target));
            var eid = "e" + lo + "_" + hi;
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

        // Krawędzie "poprzeczne": powiązania między widocznymi autorami spoza
        // drzewa rozwijania. Osobny prefiks id ("w") i klasa, żeby nie kolidować
        // z krawędziami drzewa i dało się je hurtem usunąć.
        function dodajKrawedzieWewn() {
            extraEdges.forEach(function (e) {
                if (e.shared < progWewn) {
                    return; // poniżej progu "od ilu wspólnych prac"
                }
                var s = String(e.source);
                var t = String(e.target);
                if (cy.getElementById(s).empty() || cy.getElementById(t).empty()) {
                    return;
                }
                var lo = Math.min(Number(s), Number(t));
                var hi = Math.max(Number(s), Number(t));
                var eid = "w" + lo + "_" + hi;
                if (cy.getElementById(eid).nonempty()) {
                    return;
                }
                cy.add({
                    group: "edges",
                    data: { id: eid, source: s, target: t, shared: e.shared },
                    classes: "wewnetrzna"
                });
            });
        }

        function usunKrawedzieWewn() {
            cy.edges(".wewnetrzna").remove();
        }

        // Zakres progu "od ilu wspólnych prac" dopasowany do danych: maksimum =
        // najwięcej wspólnych publikacji wśród krawędzi poprzecznych.
        function konfigurujProgWewn() {
            if (!progWewnSlider) {
                return;
            }
            var maxShared = 1;
            extraEdges.forEach(function (e) {
                if (e.shared > maxShared) { maxShared = e.shared; }
            });
            progWewnSlider.max = maxShared;
            if (progWewn > maxShared) {
                progWewn = maxShared;
                progWewnSlider.value = maxShared;
                if (progWewnLabel) { progWewnLabel.textContent = maxShared; }
            }
        }

        function odswiezKrawedzieWewn() {
            usunKrawedzieWewn();
            if (pokazWewn) { dodajKrawedzieWewn(); }
        }

        // Wyszukiwanie po nazwisku: trafione węzły jaskrawe i na wierzch, ich
        // krawędzie czerwone, reszta przygaszona. Pusty tekst -> reset.
        function szukaj(q) {
            q = (q || "").trim().toLowerCase();
            cy.batch(function () {
                cy.elements().removeClass(
                    "znaleziony przygaszony powiazana-szukana"
                );
                if (!q) {
                    return;
                }
                var trafione = cy.nodes().filter(function (n) {
                    return (n.data("label") || "").toLowerCase().indexOf(q) !== -1;
                });
                if (trafione.empty()) {
                    return;
                }
                cy.elements().addClass("przygaszony");
                trafione.removeClass("przygaszony").addClass("znaleziony");
                var kraw = trafione.connectedEdges();
                kraw.removeClass("przygaszony").addClass("powiazana-szukana");
                kraw.connectedNodes().removeClass("przygaszony");
            });
        }

        // "Pączek": rozmieszcza NOWE węzły na okręgu wokół rodzica. Dla centrum
        // pełny okrąg; dla węzła na obrzeżu — łuk skierowany na zewnątrz (od
        // środka grafu), żeby pączek rozkwitał w wolną przestrzeń, a nie do
        // środka. Istniejących węzłów nie ruszamy.
        function rozmiescWokol(parentId, nowe, animujPoz) {
            if (!nowe.length) {
                return;
            }
            var pp = cy.getElementById(String(parentId)).position();
            var center = cy.getElementById(autorId);
            var cc = center.nonempty() ? center.position() : { x: 0, y: 0 };
            var n = nowe.length;
            var jestCentrum = String(parentId) === autorId;
            // promień rośnie z liczbą węzłów, by etykiety się nie zlewały
            var R = Math.max(80, 38 + n * 11);
            var outward = Math.atan2(pp.y - cc.y, pp.x - cc.x);
            var spread = Math.PI * 1.5; // ~270° łuku na zewnątrz

            nowe.forEach(function (node, i) {
                var angle;
                if (jestCentrum) {
                    angle = (2 * Math.PI * i) / n - Math.PI / 2;
                } else {
                    var frac = n === 1 ? 0 : i / (n - 1) - 0.5;
                    angle = outward + frac * spread;
                }
                var target = {
                    x: pp.x + R * Math.cos(angle),
                    y: pp.y + R * Math.sin(angle)
                };
                if (animujPoz) {
                    node.animate(
                        { position: target },
                        { duration: 450, easing: "ease-out" }
                    );
                } else {
                    node.position(target);
                }
            });
        }

        function pokazSasiadow(id, neighbors, animujPoz) {
            var parent = cy.getElementById(String(id));
            var seed = parent.nonempty() ? parent.position() : { x: 0, y: 0 };
            var nowe = [];
            // neighbors są już posortowani malejąco po wspólnych publikacjach,
            // więc slice(0, topN) bierze najczęstszych współautorów.
            neighbors.slice(0, topN).forEach(function (n) {
                zapamietaj(n);
                var byl = cy.getElementById(String(n.id)).nonempty();
                var node = dodajWezel(n.id, n, false, seed);
                if (!byl) { nowe.push(node); }
                dodajKrawedz(id, n);
            });
            rozmiescWokol(id, nowe, animujPoz);
            // Zdjęcie klasy ".nowy" w następnej klatce uruchamia fade-in:
            // elementy zdążyły wyrenderować się z opacity 0, więc zmiana na
            // wartość docelową przechodzi przez transition zamiast skoku.
            if (animujDodawanie) {
                requestAnimationFrame(function () {
                    cy.elements(".nowy").removeClass("nowy");
                });
            }
            przeliczRozmiary();
            // dowinięte węzły mogą domykać powiązania w grupie / pasować do
            // wyszukiwania — odśwież oba, jeśli aktywne.
            if (pokazWewn) { dodajKrawedzieWewn(); }
            if (inputSzukaj && inputSzukaj.value) { szukaj(inputSzukaj.value); }
        }

        function rozwin(id) {
            id = String(id);
            if (expanded[id]) {
                return;
            }
            expanded[id] = true;
            cy.getElementById(id).addClass("rozwiniety");

            if (neighborsCache[id]) {
                pokazSasiadow(id, neighborsCache[id], true);
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
                    pokazSasiadow(id, data.neighbors, true);
                })
                .catch(function (e) {
                    pokazBlad("Błąd pobierania danych: " + e.message);
                });
        }

        // Układ drzewa radialnego: każdemu poddrzewu przydzielamy wycinek kąta
        // proporcjonalny do liczby jego liści, a promień rośnie z poziomem.
        // Dzięki temu gałęzie nie nachodzą na siebie nawet przy dużej
        // głębokości (każda dostaje własny klin i własny pierścień).
        function pozycjeRadialne(centerId, children) {
            var ringStep = 190;
            var liscie = {};
            function liczLisci(id) {
                var kids = children[id];
                if (!kids || !kids.length) {
                    liscie[id] = 1;
                    return 1;
                }
                var s = 0;
                kids.forEach(function (k) { s += liczLisci(k); });
                liscie[id] = s;
                return s;
            }
            liczLisci(centerId);

            var pozycje = {};
            function umiesc(id, a0, a1, level) {
                var ang = (a0 + a1) / 2;
                var r = level * ringStep;
                pozycje[id] = { x: r * Math.cos(ang), y: r * Math.sin(ang) };
                var kids = children[id];
                if (!kids || !kids.length) {
                    return;
                }
                var suma = liscie[id];
                var a = a0;
                kids.forEach(function (k) {
                    var span = (a1 - a0) * (liscie[k] / suma);
                    umiesc(k, a, a + span, level + 1);
                    a += span;
                });
            }
            umiesc(centerId, 0, 2 * Math.PI, 0);
            return pozycje;
        }

        // Koncentryczny równomierny: każdy poziom rozłożony EQUIDISTANT na okręgu
        // (bez grupowania w kliny jak radialny) — czyste pierścienie.
        function pozycjeKoncentryczne(centerId, children, levelOf) {
            var ringStep = 165;
            var wgPoziomu = {};
            Object.keys(levelOf).forEach(function (id) {
                var l = levelOf[id];
                (wgPoziomu[l] = wgPoziomu[l] || []).push(id);
            });
            var pozycje = {};
            Object.keys(wgPoziomu).forEach(function (l) {
                var ids = wgPoziomu[l];
                var level = Number(l);
                if (level === 0) {
                    pozycje[ids[0]] = { x: 0, y: 0 };
                    return;
                }
                var r = level * ringStep;
                ids.forEach(function (id, i) {
                    var ang = (2 * Math.PI * i) / ids.length - Math.PI / 2;
                    pozycje[id] = { x: r * Math.cos(ang), y: r * Math.sin(ang) };
                });
            });
            return pozycje;
        }

        function pozycjeUkladu(centerId, children, levelOf) {
            if (uklad === "koncentryczny") {
                return pozycjeKoncentryczne(centerId, children, levelOf);
            }
            return pozycjeRadialne(centerId, children);
        }

        // Ułożenie grafu wg bieżącego układu. "sila" = layout siłowy fcose
        // (organiczne skupiska); pozostałe = deterministyczne pozycje liczone
        // z drzewa ostatniej sieci. `animuj` steruje animacją przejścia.
        function ulozGraf(animuj) {
            if (uklad === "sila") {
                cy.layout({
                    name: "fcose",
                    quality: "default",
                    randomize: true,
                    animate: animuj,
                    animationDuration: 500,
                    fit: true,
                    padding: 50,
                    nodeRepulsion: 9000,
                    idealEdgeLength: 95
                }).run();
                return;
            }
            if (!lastTree) {
                return;
            }
            var pozycje = pozycjeUkladu(
                lastTree.centerId, lastTree.children, lastTree.levelOf
            );
            if (animuj) {
                cy.nodes().forEach(function (n) {
                    var p = pozycje[n.id()];
                    if (p) {
                        n.animate(
                            { position: p }, { duration: 450, easing: "ease-out" }
                        );
                    }
                });
                cy.animate({ fit: { eles: cy.elements(), padding: 50 }, duration: 450 });
            } else {
                cy.batch(function () {
                    cy.nodes().forEach(function (n) {
                        var p = pozycje[n.id()];
                        if (p) { n.position(p); }
                    });
                });
                cy.fit(cy.elements(), 50);
            }
        }

        // Render całej pod-sieci (BFS) z endpointu siec.json jako drzewo
        // radialne: centrum w środku, kolejne poziomy w coraz szerszych
        // pierścieniach, poddrzewa w rozłącznych klinach.
        function renderujSiec(data) {
            animujDodawanie = false;
            cy.elements().remove();
            expanded = {};

            var centerId = String(data.center_id);
            data.nodes.forEach(zapamietaj);

            if (!data.nodes || data.nodes.length <= 1) {
                container.style.display = "none";
                if (emptyEl) { emptyEl.style.display = "block"; }
                if (notkaEl) { notkaEl.style.display = "none"; }
                animujDodawanie = true;
                return;
            }
            container.style.display = "";
            if (emptyEl) { emptyEl.style.display = "none"; }

            var children = {};
            var levelOf = {};
            data.nodes.forEach(function (n) {
                levelOf[String(n.id)] = n.level || 0;
                if (n.parent !== null && n.parent !== undefined) {
                    var p = String(n.parent);
                    (children[p] = children[p] || []).push(String(n.id));
                }
            });

            lastTree = { centerId: centerId, children: children, levelOf: levelOf };

            data.nodes.forEach(function (n) {
                var id = String(n.id);
                var jestCentrum = id === centerId;
                dodajWezel(n.id, n, jestCentrum, { x: 0, y: 0 });
                if (jestCentrum || children[id]) {
                    cy.getElementById(id).addClass("rozwiniety");
                    expanded[id] = true; // ma dzieci -> klik nie dowija ponownie
                }
            });

            data.edges.forEach(function (e) {
                dodajKrawedzProsta(e.source, e.target, e.shared);
            });

            extraEdges = data.extra_edges || [];
            konfigurujProgWewn();
            if (pokazWewn) { dodajKrawedzieWewn(); }

            przeliczRozmiary();
            ulozGraf(false);
            animujDodawanie = true;
            if (notkaEl) {
                notkaEl.style.display = data.truncated ? "block" : "none";
            }
            // po przeładowaniu utrzymaj aktywne wyszukiwanie
            if (inputSzukaj && inputSzukaj.value) { szukaj(inputSzukaj.value); }
        }

        function zaladujSiec() {
            fetch(siecUrl(autorId, glebokosc, topN))
                .then(function (r) {
                    if (!r.ok) { throw new Error("HTTP " + r.status); }
                    return r.json();
                })
                .then(renderujSiec)
                .catch(function (e) {
                    if (emptyEl) {
                        emptyEl.textContent = "Błąd: " + e.message;
                        emptyEl.style.display = "block";
                    }
                });
        }

        // Suwaki sterują żądaniem do serwera (BFS), więc dławimy częstotliwość
        // przeładowań przy przeciąganiu, żeby nie zasypać backendu.
        var debTimer = null;
        function zaladujSiecZwloka() {
            if (debTimer) { clearTimeout(debTimer); }
            debTimer = setTimeout(zaladujSiec, 250);
        }

        // --- start: cała sieć do bieżącej głębokości ---
        zaladujSiec();

        // --- hover na węźle -> tooltip z nazwiskiem, tytułem i ORCID ---
        cy.on("mouseover", "node", function (evt) {
            var info = infoCache[evt.target.id()] || {
                label: evt.target.data("label")
            };
            pokazTooltipAutor(info);
        });
        cy.on("mouseout", "node", function () {
            tooltip.style.display = "none";
        });

        // --- hover na krawędzi -> tooltip z liczbą wspólnych publikacji ---
        cy.on("mouseover", "edge", function (evt) {
            var e = evt.target;
            e.addClass("podswietlona");
            var a = infoCache[e.data("source")] || {};
            var b = infoCache[e.data("target")] || {};
            pokazTooltipKrawedz(a.label, b.label, e.data("shared"));
        });
        cy.on("mouseout", "edge", function (evt) {
            evt.target.removeClass("podswietlona");
            tooltip.style.display = "none";
        });

        cy.on("mousemove", function (evt) {
            var pos = evt.renderedPosition || { x: 0, y: 0 };
            tooltip.style.left = (pos.x + 14) + "px";
            tooltip.style.top = (pos.y + 14) + "px";
        });

        // --- klik -> rozwiń (pączek) + panel akcji ---
        cy.on("tap", "node", function (evt) {
            var n = evt.target;
            rozwin(n.id());
            var info = infoCache[n.id()] || {
                label: n.data("label"), url: n.data("url")
            };
            pokazPanelAutora(info);
        });

        // --- suwak top-N -> przeładuj sieć (top-N per węzeł) ---
        slider.addEventListener("input", function () {
            topN = parseInt(slider.value, 10);
            if (sliderLabel) { sliderLabel.textContent = topN; }
            zaladujSiecZwloka();
        });

        // --- suwak głębokości -> przeładuj sieć (BFS na N poziomów) ---
        sliderGleb.addEventListener("input", function () {
            glebokosc = parseInt(sliderGleb.value, 10);
            if (sliderGlebLabel) { sliderGlebLabel.textContent = glebokosc; }
            zaladujSiecZwloka();
        });

        // --- odśwież układ: wróć do czystego drzewa radialnego ---
        // (kasuje ręczne przesunięcia węzłów i lokalne dowinięcia klikiem,
        // odtwarzając ładny "pączek" dla bieżącej głębokości i top-N).
        var btnOdswiez = document.getElementById("graf-odswiez");
        if (btnOdswiez) {
            btnOdswiez.addEventListener("click", function () {
                zaladujSiec();
            });
        }

        // --- metryka wielkości kółka: prace / IF / PK (bez przeładowania) ---
        if (selMetryka) {
            selMetryka.addEventListener("change", function () {
                metryka = selMetryka.value;
                przeliczRozmiary();
            });
        }

        // --- układ: radialny / drzewo / koncentryczny (bez przeładowania) ---
        if (selUklad) {
            selUklad.addEventListener("change", function () {
                uklad = selUklad.value;
                ulozGraf(true);
            });
        }

        // --- powiązania wewnątrz grupy: checkbox + próg "od ilu wspólnych prac" ---
        if (chkWewn) {
            chkWewn.addEventListener("change", function () {
                pokazWewn = chkWewn.checked;
                odswiezKrawedzieWewn();
            });
        }
        if (progWewnSlider) {
            progWewnSlider.addEventListener("input", function () {
                progWewn = parseInt(progWewnSlider.value, 10) || 1;
                if (progWewnLabel) { progWewnLabel.textContent = progWewn; }
                odswiezKrawedzieWewn();
            });
        }

        // --- wyszukiwanie po nazwisku ---
        if (inputSzukaj) {
            inputSzukaj.addEventListener("input", function () {
                szukaj(inputSzukaj.value);
            });
        }

        function pobierzPlik(href, nazwa) {
            var a = document.createElement("a");
            a.href = href;
            a.download = nazwa;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
        }

        // --- pobierz graf jako PNG (cały graf, 2x, białe tło) ---
        var btnPobierz = document.getElementById("graf-pobierz");
        if (btnPobierz) {
            btnPobierz.addEventListener("click", function () {
                pobierzPlik(
                    cy.png({ full: true, scale: 2, bg: "#ffffff" }),
                    "siec-powiazan.png"
                );
            });
        }

        // --- pobierz graf jako SVG (wektorowy) ---
        var btnSvg = document.getElementById("graf-pobierz-svg");
        if (btnSvg && typeof cy.svg === "function") {
            btnSvg.addEventListener("click", function () {
                var svgStr = cy.svg({ full: true, bg: "#ffffff" });
                var blob = new Blob([svgStr], {
                    type: "image/svg+xml;charset=utf-8"
                });
                var url = URL.createObjectURL(blob);
                pobierzPlik(url, "siec-powiazan.svg");
                URL.revokeObjectURL(url);
            });
        } else if (btnSvg) {
            btnSvg.style.display = "none"; // rozszerzenie SVG nie załadowane
        }
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", init);
    } else {
        init();
    }
})();
