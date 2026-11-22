/*
 * Formularz w module redagowania: link „Przejdź do pierwszego błędu” przy
 * komunikacie „Prosimy naprawić poniższe błędy”. Rozwija zwiniętą sekcję
 * (Grappelli), przewija do pierwszego pola z błędem (z poprawką na
 * przyklejone paski — window.bpp.scrollToVisible), ustawia w nim kursor
 * i na chwilę je podświetla. Działa też dla błędów w inline'ach (autorzy).
 */
(function () {
    "use strict";

    function pierwszyBlad(form) {
        var notatka = form.querySelector(".errornote");
        var kandydaci = form.querySelectorAll(".grp-errors, ul.errorlist");
        for (var i = 0; i < kandydaci.length; i++) {
            var el = kandydaci[i];
            if (notatka && el.parentElement === notatka.parentElement &&
                el.previousElementSibling === notatka) {
                continue; // błędy ogólne formularza — są już pod komunikatem
            }
            if (notatka && (notatka.compareDocumentPosition(el) &
                Node.DOCUMENT_POSITION_PRECEDING)) {
                continue;
            }
            return el;
        }
        return null;
    }

    function rozwinSekcje(el) {
        for (var p = el; p; p = p.parentElement) {
            if (p.classList && p.classList.contains("grp-closed")) {
                p.classList.remove("grp-closed");
                p.classList.add("grp-open");
            }
        }
    }

    function przejdz(form) {
        var blad = pierwszyBlad(form);
        if (!blad) {
            return;
        }
        rozwinSekcje(blad);
        var wiersz = blad.closest(".grp-row, .form-row, .grp-tr, tr") || blad;
        if (window.bpp && window.bpp.scrollToVisible) {
            window.bpp.scrollToVisible(wiersz);
        } else {
            wiersz.scrollIntoView({block: "center"});
        }
        var pole = wiersz.querySelector(
            "input:not([type=hidden]):not([disabled]), select, textarea"
        );
        if (pole) {
            try {
                pole.focus({preventScroll: true});
            } catch (blad_focus) {
                pole.focus(); // stare przeglądarki bez opcji preventScroll
            }
        }
        wiersz.style.transition = "box-shadow .3s";
        wiersz.style.boxShadow = "0 0 0 3px #e0a800";
        window.setTimeout(function () {
            wiersz.style.boxShadow = "";
        }, 2500);
    }

    document.addEventListener("click", function (e) {
        var link = e.target.closest(".bpp-do-pierwszego-bledu");
        if (!link) {
            return;
        }
        e.preventDefault();
        przejdz(link.closest("form") || document);
    });

    function widoczny(el) {
        // Czy wiersz z błędem jest w całości na ekranie (pod przyklejonymi
        // paskami u góry i nad przyklejonym paskiem przycisków na dole).
        var r = el.getBoundingClientRect();
        var gora = 0;
        var dol = window.innerHeight;
        var nav = document.querySelector("nav.sticky-header, #grp-header");
        if (nav) {
            gora = Math.max(gora, nav.getBoundingClientRect().bottom);
        }
        var stopka = document.querySelector(".grp-submit-row.grp-fixed-footer");
        if (stopka) {
            dol = Math.min(dol, stopka.getBoundingClientRect().top);
        }
        return r.height > 0 && r.top >= gora && r.bottom <= dol;
    }

    function ustawLinki() {
        // Link tylko wtedy, gdy jest dokąd przewijać: pole z błędem istnieje
        // i NIE widać go od razu na ekranie razem z komunikatem.
        document.querySelectorAll(".bpp-do-pierwszego-bledu").forEach(function (link) {
            var form = link.closest("form");
            var blad = form && pierwszyBlad(form);
            var wiersz = blad && (blad.closest(".grp-row, .form-row, .grp-tr, tr") || blad);
            var pokaz = wiersz && !widoczny(wiersz);
            link.style.display = pokaz ? "" : "none";
        });
    }

    document.addEventListener("DOMContentLoaded", ustawLinki);
    // Po pełnym załadowaniu (select2, rozwinięte sekcje) układ strony się
    // zmienia — sprawdzamy jeszcze raz.
    window.addEventListener("load", ustawLinki);
})();
