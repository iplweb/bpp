// Panel akcji (klik w węzeł), komunikat błędu oraz tooltipy hover
// (autor / krawędź). Cała treść budowana przez textContent (XSS-safe).
import { wyczysc, linkAkcja } from "./dom.js";
import { grafUrl } from "./urls.js";

// Panel akcji po kliknięciu w węzeł: nagłówek (nazwisko + tytuł), ORCID,
// oraz linki kontekstowe — PBN/ORCID tylko gdy autor ma identyfikator.
export function pokazPanelAutora(ctx, info) {
    const panel = ctx.panel;
    wyczysc(panel);

    const strong = document.createElement("strong");
    strong.textContent =
        info.label + (info.tytul ? ", " + info.tytul : "");
    panel.appendChild(strong);

    if (info.orcid) {
        const orcidLinia = document.createElement("div");
        orcidLinia.textContent = "ORCID: " + info.orcid;
        orcidLinia.style.fontSize = "11px";
        orcidLinia.style.color = "#666";
        orcidLinia.style.marginTop = "2px";
        panel.appendChild(orcidLinia);
    }

    panel.appendChild(linkAkcja(info.url || "#", "Pokaż prace", false));
    if (info.id) {
        panel.appendChild(
            linkAkcja(grafUrl(ctx, info.id), "Pokaż sieć powiązań", false)
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

export function pokazBlad(ctx, msg) {
    ctx.panel.textContent = msg;
    ctx.panel.style.display = "block";
}

export function pokazTooltipAutor(ctx, info) {
    const tooltip = ctx.tooltip;
    wyczysc(tooltip);
    const strong = document.createElement("strong");
    strong.textContent =
        info.label + (info.tytul ? ", " + info.tytul : "");
    tooltip.appendChild(strong);
    if (info.orcid) {
        const l = document.createElement("div");
        l.textContent = "ORCID: " + info.orcid;
        l.style.fontSize = "11px";
        l.style.color = "#666";
        tooltip.appendChild(l);
    }
    tooltip.style.display = "block";
}

export function pokazTooltipKrawedz(ctx, labelA, labelB, shared) {
    const tooltip = ctx.tooltip;
    wyczysc(tooltip);
    const para = document.createElement("div");
    para.textContent = (labelA || "?") + " ↔ " + (labelB || "?");
    const ile = document.createElement("strong");
    const n = shared || 0;
    ile.textContent =
        n + (n === 1 ? " wspólna publikacja" : " wspólnych publikacji");
    tooltip.appendChild(para);
    tooltip.appendChild(ile);
    tooltip.style.display = "block";
}
