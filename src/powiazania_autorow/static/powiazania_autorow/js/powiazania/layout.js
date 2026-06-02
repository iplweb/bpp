// Rozmieszczanie węzłów: "pączek" wokół rodzica przy lokalnym rozwijaniu
// oraz deterministyczne układy całej sieci (radialny / koncentryczny) i
// siłowy fcose. Pozycje radialne/koncentryczne liczone z drzewa ostatniej
// sieci (ctx.lastTree).

// "Pączek": rozmieszcza NOWE węzły na okręgu wokół rodzica. Dla centrum
// pełny okrąg; dla węzła na obrzeżu — łuk skierowany na zewnątrz (od
// środka grafu), żeby pączek rozkwitał w wolną przestrzeń, a nie do
// środka. Istniejących węzłów nie ruszamy.
export function rozmiescWokol(ctx, parentId, nowe, animujPoz) {
    if (!nowe.length) {
        return;
    }
    const cy = ctx.cy;
    const pp = cy.getElementById(String(parentId)).position();
    const center = cy.getElementById(ctx.autorId);
    const cc = center.nonempty() ? center.position() : { x: 0, y: 0 };
    const n = nowe.length;
    const jestCentrum = String(parentId) === ctx.autorId;
    // promień rośnie z liczbą węzłów, by etykiety się nie zlewały
    const R = Math.max(80, 38 + n * 11);
    const outward = Math.atan2(pp.y - cc.y, pp.x - cc.x);
    const spread = Math.PI * 1.5; // ~270° łuku na zewnątrz

    nowe.forEach(function (node, i) {
        let angle;
        if (jestCentrum) {
            angle = (2 * Math.PI * i) / n - Math.PI / 2;
        } else {
            const frac = n === 1 ? 0 : i / (n - 1) - 0.5;
            angle = outward + frac * spread;
        }
        const target = {
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

// Układ drzewa radialnego: każdemu poddrzewu przydzielamy wycinek kąta
// proporcjonalny do liczby jego liści, a promień rośnie z poziomem.
// Dzięki temu gałęzie nie nachodzą na siebie nawet przy dużej
// głębokości (każda dostaje własny klin i własny pierścień).
export function pozycjeRadialne(centerId, children) {
    const ringStep = 190;
    const liscie = {};
    function liczLisci(id) {
        const kids = children[id];
        if (!kids || !kids.length) {
            liscie[id] = 1;
            return 1;
        }
        let s = 0;
        kids.forEach(function (k) { s += liczLisci(k); });
        liscie[id] = s;
        return s;
    }
    liczLisci(centerId);

    const pozycje = {};
    function umiesc(id, a0, a1, level) {
        const ang = (a0 + a1) / 2;
        const r = level * ringStep;
        pozycje[id] = { x: r * Math.cos(ang), y: r * Math.sin(ang) };
        const kids = children[id];
        if (!kids || !kids.length) {
            return;
        }
        const suma = liscie[id];
        let a = a0;
        kids.forEach(function (k) {
            const span = (a1 - a0) * (liscie[k] / suma);
            umiesc(k, a, a + span, level + 1);
            a += span;
        });
    }
    umiesc(centerId, 0, 2 * Math.PI, 0);
    return pozycje;
}

// Koncentryczny równomierny: każdy poziom rozłożony EQUIDISTANT na okręgu
// (bez grupowania w kliny jak radialny) — czyste pierścienie.
export function pozycjeKoncentryczne(centerId, children, levelOf) {
    const ringStep = 165;
    const wgPoziomu = {};
    Object.keys(levelOf).forEach(function (id) {
        const l = levelOf[id];
        (wgPoziomu[l] = wgPoziomu[l] || []).push(id);
    });
    const pozycje = {};
    Object.keys(wgPoziomu).forEach(function (l) {
        const ids = wgPoziomu[l];
        const level = Number(l);
        if (level === 0) {
            pozycje[ids[0]] = { x: 0, y: 0 };
            return;
        }
        const r = level * ringStep;
        ids.forEach(function (id, i) {
            const ang = (2 * Math.PI * i) / ids.length - Math.PI / 2;
            pozycje[id] = { x: r * Math.cos(ang), y: r * Math.sin(ang) };
        });
    });
    return pozycje;
}

export function pozycjeUkladu(ctx, centerId, children, levelOf) {
    if (ctx.uklad === "koncentryczny") {
        return pozycjeKoncentryczne(centerId, children, levelOf);
    }
    return pozycjeRadialne(centerId, children);
}

// Ułożenie grafu wg bieżącego układu. "sila" = layout siłowy fcose
// (organiczne skupiska); pozostałe = deterministyczne pozycje liczone
// z drzewa ostatniej sieci. `animuj` steruje animacją przejścia.
export function ulozGraf(ctx, animuj) {
    const cy = ctx.cy;
    if (ctx.uklad === "sila") {
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
    if (!ctx.lastTree) {
        return;
    }
    const pozycje = pozycjeUkladu(
        ctx, ctx.lastTree.centerId, ctx.lastTree.children, ctx.lastTree.levelOf
    );
    if (animuj) {
        cy.nodes().forEach(function (n) {
            const p = pozycje[n.id()];
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
                const p = pozycje[n.id()];
                if (p) { n.position(p); }
            });
        });
        cy.fit(cy.elements(), 50);
    }
}
