/*
 * Przełącznik trybu kolorów na pasku menu (top_bar.html): automatyczny
 * (jak w systemie) / jasny / ciemny.
 *
 * Wybór trzymamy w localStorage („bpp-tryb-kolorow”), bez serwera — działa
 * dla niezalogowanych, a strona główna jest dla nich w cache. Atrybut
 * <html data-tryb-kolorow="jasny|ciemny"> ustawia przy wczytaniu krótki
 * skrypt w <head> (bare.html, przed CSS); tu tylko obsługa kliknięć.
 * CSS motywu (_tryb-ciemny.scss / przetworzCss konfiguratora) ma ciemne
 * reguły pod `html:not([data-tryb-kolorow="jasny"])` (w media query systemu)
 * i `html[data-tryb-kolorow="ciemny"]`.
 */
(function () {
    "use strict";

    var KLUCZ = "bpp-tryb-kolorow";
    var OPIS = {
        auto: { ikona: "fi-monitor", etykieta: "automatyczny (jak w systemie)" },
        jasny: { ikona: "fi-lightbulb", etykieta: "jasny" },
        ciemny: { ikona: "fi-contrast", etykieta: "ciemny" },
    };

    function biezacy() {
        var t = document.documentElement.getAttribute("data-tryb-kolorow");
        return t === "jasny" || t === "ciemny" ? t : "auto";
    }

    function zapamietaj(tryb) {
        try {
            if (tryb === "auto") window.localStorage.removeItem(KLUCZ);
            else window.localStorage.setItem(KLUCZ, tryb);
        } catch (e) {
            // localStorage zablokowany — wybór działa tylko do przeładowania.
            if (e.name !== "SecurityError") throw e;
        }
    }

    function odswiezPrzelacznik() {
        var tryb = biezacy();
        document.querySelectorAll(".bpp-tryb-kolorow").forEach(function (li) {
            var przycisk = li.querySelector(".bpp-tryb-kolorow__przycisk");
            var ikona = li.querySelector(".bpp-tryb-kolorow__ikona");
            if (przycisk) przycisk.setAttribute("aria-label", "Tryb kolorów: " + OPIS[tryb].etykieta);
            if (ikona) ikona.className = "bpp-tryb-kolorow__ikona " + OPIS[tryb].ikona;
            li.querySelectorAll("[data-ustaw-tryb-kolorow]").forEach(function (a) {
                var wybrany = a.getAttribute("data-ustaw-tryb-kolorow") === tryb;
                a.setAttribute("aria-checked", wybrany ? "true" : "false");
            });
        });
    }

    function ustaw(tryb) {
        if (!OPIS[tryb]) return;
        if (tryb === "auto") document.documentElement.removeAttribute("data-tryb-kolorow");
        else document.documentElement.setAttribute("data-tryb-kolorow", tryb);
        zapamietaj(tryb);
        odswiezPrzelacznik();
    }

    document.addEventListener("click", function (e) {
        var a = e.target.closest ? e.target.closest("[data-ustaw-tryb-kolorow]") : null;
        if (a) {
            e.preventDefault();
            ustaw(a.getAttribute("data-ustaw-tryb-kolorow"));
            return;
        }
        // Sam przycisk na pasku nie jest linkiem — nie przewijaj do góry.
        if (e.target.closest && e.target.closest(".bpp-tryb-kolorow__przycisk")) {
            e.preventDefault();
        }
    });

    // Spacja na pozycji menu (role=menuitemradio) — jak kliknięcie.
    document.addEventListener("keydown", function (e) {
        if (e.key !== " ") return;
        var a = e.target.closest ? e.target.closest("[data-ustaw-tryb-kolorow]") : null;
        if (a) {
            e.preventDefault();
            ustaw(a.getAttribute("data-ustaw-tryb-kolorow"));
        }
    });

    // Wybór w innej karcie tej samej witryny.
    window.addEventListener("storage", function (e) {
        if (e.key !== KLUCZ) return;
        var t = e.newValue;
        if (t === "jasny" || t === "ciemny") {
            document.documentElement.setAttribute("data-tryb-kolorow", t);
        } else {
            document.documentElement.removeAttribute("data-tryb-kolorow");
        }
        odswiezPrzelacznik();
    });

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", odswiezPrzelacznik);
    } else {
        odswiezPrzelacznik();
    }

    window.bppTrybKolorow = { ustaw: ustaw, biezacy: biezacy };
})();
