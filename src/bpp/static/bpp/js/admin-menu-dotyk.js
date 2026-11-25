/**
 * Menu modułu redagowania (#navigation-menu) na ekranie dotykowym.
 *
 * Podmenu otwiera tu `:hover` (admin-menu.css). Na dotyku „najechanie”
 * dorabia przeglądarka po stuknięciu i trzyma je do następnego stuknięcia
 * w coś klikalnego — na iOS stuknięcie w puste miejsce strony menu NIE
 * zamykało. FD#626: stuknięcie pozycji przełącza klasę `over` (admin-menu.css
 * i motywy traktują ją tak samo jak `:hover`), a stuknięcie poza menu ją
 * zdejmuje. Zdarzenia myszy „dorobione” po dotyku są blokowane
 * (preventDefault na touchstart), więc `:hover` się nie przykleja. Pozycje
 * z podmenu mają href="#", więc nie odbiera to żadnego linku.
 *
 * Mysz działa bez zmian — ten skrypt przełącza podmenu wyłącznie dotykiem.
 * Pilnuje tego test src/integration_tests/test_admin_menu_dotyk.py.
 */
(function () {
  "use strict";

  function init() {
    var menu = document.getElementById("navigation-menu");
    if (!menu) {
      return;
    }
    var pozycje = Array.prototype.filter.call(menu.children, function (li) {
      return !!li.querySelector(":scope > ul");
    });

    function zamknij(procz) {
      pozycje.forEach(function (li) {
        if (li !== procz) {
          li.classList.remove("over");
        }
      });
    }

    pozycje.forEach(function (li) {
      var link = li.querySelector(":scope > a");
      if (!link) {
        return;
      }
      link.addEventListener(
        "touchstart",
        function (e) {
          e.preventDefault();
          zamknij(li);
          li.classList.toggle("over");
        },
        { passive: false },
      );
    });

    document.addEventListener(
      "touchstart",
      function (e) {
        if (!menu.contains(e.target)) {
          zamknij(null);
        }
      },
      { capture: true, passive: true },
    );

    // Urządzenia z myszą i ekranem dotykowym: podmenu otwarte dotykiem
    // zamyka też kliknięcie myszą obok.
    document.addEventListener("mousedown", function (e) {
      if (!menu.contains(e.target)) {
        zamknij(null);
      }
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
