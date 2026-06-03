// Krawędzie "poprzeczne" (powiązania wewnątrz grupy): powiązania między
// widocznymi autorami spoza drzewa rozwijania. Osobny prefiks id ("w")
// i klasa "wewnetrzna", żeby nie kolidowały z krawędziami drzewa i dało
// się je hurtem usunąć. Próg "od ilu wspólnych prac" steruje gęstością.

export function dodajKrawedzieWewn(ctx) {
    const cy = ctx.cy;
    ctx.extraEdges.forEach(function (e) {
        if (e.shared < ctx.progWewn) {
            return; // poniżej progu "od ilu wspólnych prac"
        }
        const s = String(e.source);
        const t = String(e.target);
        if (cy.getElementById(s).empty() || cy.getElementById(t).empty()) {
            return;
        }
        const lo = Math.min(Number(s), Number(t));
        const hi = Math.max(Number(s), Number(t));
        const eid = "w" + lo + "_" + hi;
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

export function usunKrawedzieWewn(ctx) {
    ctx.cy.edges(".wewnetrzna").remove();
}

// Zakres progu "od ilu wspólnych prac" dopasowany do danych: maksimum =
// najwięcej wspólnych publikacji wśród krawędzi poprzecznych.
export function konfigurujProgWewn(ctx) {
    if (!ctx.progWewnSlider) {
        return;
    }
    let maxShared = 1;
    ctx.extraEdges.forEach(function (e) {
        if (e.shared > maxShared) { maxShared = e.shared; }
    });
    ctx.progWewnSlider.max = maxShared;
    if (ctx.progWewn > maxShared) {
        ctx.progWewn = maxShared;
        ctx.progWewnSlider.value = maxShared;
        if (ctx.progWewnLabel) { ctx.progWewnLabel.textContent = maxShared; }
    }
}

export function odswiezKrawedzieWewn(ctx) {
    usunKrawedzieWewn(ctx);
    if (ctx.pokazWewn) { dodajKrawedzieWewn(ctx); }
}
