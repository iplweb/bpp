/*
 * Pigułka trybu kolorów ☀ | ☾ na pasku menu (tryb_kolorow_pigulka.html).
 *
 * Każdy motyw ma tryb domyślny — <html data-tryb-domyslny="jasny|ciemny|auto">
 * (zwykłe motywy: jasny, `*-ciemny`: ciemny, `*-auto` i konfigurator
 * w trybie automatycznym: wg ustawień systemu) — i drugą wersję, którą
 * odwiedzający włącza pigułką. Podświetlona połówka = tryb, który faktycznie
 * widać. Klik w połówkę trybu domyślnego albo w połówkę wybraną ręcznie
 * wraca do domyślnego; klik w drugą — wymusza ją.
 *
 * Wybór trzymamy w localStorage („bpp-tryb-kolorow”), bez serwera — działa
 * dla niezalogowanych, a strona główna jest dla nich w cache. Atrybut
 * <html data-tryb-kolorow="jasny|ciemny"> ustawia przy wczytaniu krótki
 * skrypt w <head> (bare.html, przed CSS). Wygląd pigułki (która połówka
 * podświetlona, znacznik wyboru ręcznego) liczy CSS z tych atrybutów i media
 * query systemu — od pierwszej klatki, bez czekania na ten skrypt. Tu tylko
 * kliknięcia, klawiatura oraz aria-checked / tabindex / opisy.
 *
 * Semantyka: role="radiogroup" z dwoma role="radio". Zaznaczone radio to
 * widoczny tryb; strzałki przenoszą wybór (jak w każdej grupie radio),
 * Spacja/Enter na zaznaczonym przy wyborze ręcznym wraca do domyślnego.
 */
(function () {
    "use strict";

    var KLUCZ = "bpp-tryb-kolorow";
    var NAZWA = { jasny: "Tryb jasny", ciemny: "Tryb ciemny" };
    var systemCiemny = window.matchMedia
        ? window.matchMedia("(prefers-color-scheme: dark)")
        : null;

    // Wybór ręczny: "jasny" | "ciemny" albo "auto" (brak atrybutu).
    function biezacy() {
        var t = document.documentElement.getAttribute("data-tryb-kolorow");
        return t === "jasny" || t === "ciemny" ? t : "auto";
    }

    // Tryb motywu bez wyboru odwiedzającego: "jasny" | "ciemny" | "auto".
    function domyslny() {
        var t = document.documentElement.getAttribute("data-tryb-domyslny");
        return t === "ciemny" || t === "auto" ? t : "jasny";
    }

    // Co widać bez wyboru odwiedzającego.
    function domyslnyWidoczny() {
        var t = domyslny();
        if (t !== "auto") return t;
        return systemCiemny && systemCiemny.matches ? "ciemny" : "jasny";
    }

    // Tryb, który faktycznie widać.
    function widoczny() {
        var t = biezacy();
        return t !== "auto" ? t : domyslnyWidoczny();
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

    function opis(tryb, zaznaczony, reczny) {
        var powrot =
            domyslny() === "auto" ? "ustawień systemu" : "domyślnego wyglądu strony";
        if (zaznaczony && reczny) {
            return (
                NAZWA[tryb] +
                " (wybrany ręcznie) — kliknij, aby wrócić do " +
                powrot
            );
        }
        if (zaznaczony) {
            return (
                NAZWA[tryb] +
                (domyslny() === "auto"
                    ? " (zgodnie z ustawieniami systemu)"
                    : " (domyślny wygląd strony)")
            );
        }
        if (reczny && tryb === domyslnyWidoczny()) {
            return NAZWA[tryb] + " — kliknij, aby wrócić do " + powrot;
        }
        return NAZWA[tryb] + " — kliknij, aby wybrać";
    }

    function odswiezPigulki() {
        var tryb = widoczny();
        var reczny = biezacy() !== "auto";
        document.querySelectorAll(".bpp-pigulka").forEach(function (grupa) {
            grupa
                .querySelectorAll("[data-ustaw-tryb-kolorow]")
                .forEach(function (radio) {
                    var t = radio.getAttribute("data-ustaw-tryb-kolorow");
                    var zaznaczony = t === tryb;
                    var tekst = opis(t, zaznaczony, reczny);
                    radio.setAttribute("aria-checked", zaznaczony ? "true" : "false");
                    radio.setAttribute("tabindex", zaznaczony ? "0" : "-1");
                    radio.setAttribute("aria-label", tekst);
                    radio.setAttribute("title", tekst);
                });
        });
    }

    function ustaw(tryb) {
        if (tryb !== "auto" && !NAZWA[tryb]) return;
        if (tryb === "auto") document.documentElement.removeAttribute("data-tryb-kolorow");
        else document.documentElement.setAttribute("data-tryb-kolorow", tryb);
        zapamietaj(tryb);
        odswiezPigulki();
    }

    // Klik w połówkę: tryb domyślny albo już wybrany ręcznie → wróć do
    // domyślnego (bez wpisu w localStorage); drugi tryb → wymuś go.
    function wybierz(tryb) {
        if (tryb === domyslnyWidoczny() || tryb === biezacy()) ustaw("auto");
        else ustaw(tryb);
    }

    function radioZe(zdarzenie) {
        var cel = zdarzenie.target;
        return cel && cel.closest
            ? cel.closest(".bpp-pigulka [data-ustaw-tryb-kolorow]")
            : null;
    }

    document.addEventListener("click", function (e) {
        var radio = radioZe(e);
        if (!radio) return;
        e.preventDefault();
        wybierz(radio.getAttribute("data-ustaw-tryb-kolorow"));
    });

    var STRZALKI = ["ArrowLeft", "ArrowRight", "ArrowUp", "ArrowDown"];

    document.addEventListener("keydown", function (e) {
        var radio = radioZe(e);
        if (!radio) return;
        if (e.key === " " || e.key === "Enter") {
            e.preventDefault();
            wybierz(radio.getAttribute("data-ustaw-tryb-kolorow"));
            return;
        }
        if (STRZALKI.indexOf(e.key) === -1) return;
        // Dwa radio — każda strzałka przechodzi na drugie i je zaznacza.
        e.preventDefault();
        var drugi = Array.prototype.filter.call(
            radio.closest(".bpp-pigulka").querySelectorAll("[data-ustaw-tryb-kolorow]"),
            function (r) {
                return r !== radio;
            }
        )[0];
        if (!drugi) return;
        wybierz(drugi.getAttribute("data-ustaw-tryb-kolorow"));
        drugi.focus();
    });

    // Zmiana trybu w systemie (tryb automatyczny) — zaznaczona inna połówka.
    if (systemCiemny && systemCiemny.addEventListener) {
        systemCiemny.addEventListener("change", odswiezPigulki);
    }

    // Wybór w innej karcie tej samej witryny.
    window.addEventListener("storage", function (e) {
        if (e.key !== KLUCZ) return;
        var t = e.newValue;
        if (t === "jasny" || t === "ciemny") {
            document.documentElement.setAttribute("data-tryb-kolorow", t);
        } else {
            document.documentElement.removeAttribute("data-tryb-kolorow");
        }
        odswiezPigulki();
    });

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", odswiezPigulki);
    } else {
        odswiezPigulki();
    }

    window.bppTrybKolorow = {
        ustaw: ustaw,
        biezacy: biezacy,
        domyslny: domyslny,
        widoczny: widoczny,
    };
})();
