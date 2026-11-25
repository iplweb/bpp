/**
 * Menu górne strony publicznej (top_bar.html): mysz i dotyk.
 *
 * Podmenu są dwojakie:
 *  - zwykłe listy (`li > ul.menu.vertical`) — obsługuje je Foundation
 *    DropdownMenu (klasa `is-active`), także na dotyku;
 *  - bloki wielokolumnowe (`li.has-submenu > .menu-columns-wrapper`) —
 *    Foundation ich NIE widzi (podmenu to <div>, nie <ul>), więc otwierał
 *    je wyłącznie `:hover` i skrypt na `mouseenter`.
 *
 * FD#626: na telefonie nie ma najechania kursorem — jest tylko to, co
 * przeglądarka „dorobi” po stuknięciu, a to bywa różne (iOS potrafi nie
 * wysłać kliknięcia albo nie zdjąć `:hover`). Dlatego dotyk ma tu własną,
 * jawną ścieżkę: stuknięcie pozycji przełącza klasę `is-active`, stuknięcie
 * poza menu ją zdejmuje, a zdarzenia myszy „dorobione” po dotyku są
 * ignorowane. Ścieżka myszy (pokazanie od razu, chowanie z opóźnieniem)
 * działa jak dotąd.
 *
 * Pilnuje tego test src/integration_tests/test_top_bar_menu_dotyk.py.
 */
(function () {
  "use strict";

  // Mysz: podmenu chowa się dopiero po chwili od zjechania kursorem.
  var CZAS_ZAMYKANIA_MS = 500;
  // Tyle po dotyku zdarzenia myszy uznajemy za „dorobione” przez
  // przeglądarkę (mouseenter/mouseleave/click po stuknięciu), a nie za
  // prawdziwy ruch kursora.
  var OKNO_DOTYKU_MS = 1000;
  // Odstęp otwartego podmenu od dolnej krawędzi ekranu (dotyk).
  var MARGINES_DOLNY_PX = 12;
  var MIN_WYSOKOSC_PODMENU_PX = 160;

  var STYLE_MYSZY = [
    "visibility",
    "opacity",
    "max-height",
    "transform",
    "pointer-events",
  ];

  var ostatniDotyk = 0;
  var zegary = new WeakMap();

  function dotykPrzedChwila() {
    return Date.now() - ostatniDotyk < OKNO_DOTYKU_MS;
  }

  function podmenu(li) {
    return li.querySelector(
      ":scope > .menu.vertical, :scope > .menu-columns-wrapper",
    );
  }

  function anulujZamykanie(li) {
    var zegar = zegary.get(li);
    if (zegar) {
      clearTimeout(zegar);
      zegary.delete(li);
    }
  }

  function pokazMysza(sub) {
    sub.style.visibility = "visible";
    sub.style.opacity = "1";
    sub.style.maxHeight = "800px";
    sub.style.transform = "translateY(0) scaleY(1)";
    // Jawnie, nie przez :hover z arkusza: ten działa tylko przy
    // `(hover: hover)`, a mysz bywa też podpięta do tabletu.
    sub.style.pointerEvents = "auto";
  }

  function schowajMysza(sub) {
    sub.style.visibility = "hidden";
    sub.style.opacity = "0";
    sub.style.maxHeight = "0";
    sub.style.transform = "translateY(-20px) scaleY(0.8)";
    sub.style.removeProperty("pointer-events");
  }

  /**
   * Zdejmuje style wpisane przez ścieżkę myszy. Inaczej `visibility:
   * hidden` w atrybucie style wygrywa z klasą `is-active` i podmenu
   * otwarte dotykiem pozostaje niewidoczne.
   */
  function wyczyscStyleMyszy(sub) {
    STYLE_MYSZY.forEach(function (nazwa) {
      sub.style.removeProperty(nazwa);
    });
  }

  // Odstęp bloku wielokolumnowego od krawędzi okna, gdy trzeba go przesunąć.
  var MARGINES_BOCZNY_PX = 8;

  /**
   * Blok wielokolumnowy otwiera się w prawo od swojej pozycji, a gdy się
   * tam nie mieści — w lewo; gdy nie mieści się w żadną stronę, jest
   * przesuwany tak, żeby cały leżał w oknie. Na telefonie zajmuje całą szerokość (top_bar.scss), więc
   * tam te ustawienia nie mają znaczenia.
   */
  function ustawStrone(li, sub) {
    li.classList.remove("opens-left");
    sub.style.left = "";
    sub.style.right = "";

    // Szerokość okna mierzymy ZANIM blok trafi do układu i nie z samego
    // window.innerWidth: na telefonie i tablecie blok wystający poza ekran
    // poszerza obszar układu strony, więc innerWidth rośnie razem z nim
    // i blok „mieścił się” zawsze — stąd ucięta „ewaluacja” w telefonie
    // poziomo i na tablecie pionowo.
    var szerokoscOkna = Math.min(
      window.innerWidth,
      document.documentElement.clientWidth,
    );

    // Na czas pomiaru: w układzie, ale niewidoczne.
    var widocznosc = sub.style.visibility;
    var wyswietlanie = sub.style.display;
    sub.style.visibility = "hidden";
    sub.style.display = "flex";

    var szerokosc = sub.getBoundingClientRect().width;
    var liRect = li.getBoundingClientRect();
    var wystajeWPrawo = Math.max(
      0,
      liRect.left + szerokosc - szerokoscOkna,
    );
    var wystajeWLewo = Math.max(0, -(liRect.right - szerokosc));

    sub.style.visibility = widocznosc;
    sub.style.display = wyswietlanie;

    if (wystajeWPrawo === 0) {
      sub.style.left = "0";
      sub.style.right = "";
    } else if (wystajeWLewo === 0) {
      li.classList.add("opens-left");
      sub.style.left = "auto";
      sub.style.right = "0";
    } else {
      // Nie mieści się ani w prawo, ani w lewo od swojej pozycji (telefon
      // poziomo, tablet pionowo: pozycja w środku paska, blok szeroki) —
      // przesuń go tak, żeby cały leżał w oknie.
      var lewaKrawedz = Math.max(
        MARGINES_BOCZNY_PX,
        szerokoscOkna - szerokosc - MARGINES_BOCZNY_PX,
      );
      sub.style.left = lewaKrawedz - liRect.left + "px";
      sub.style.right = "auto";
    }
  }

  /**
   * Dotyk: na szerokim ekranie pasek menu jest przyklejony do góry, więc
   * podmenu wyższe niż ekran nie dałoby się przewinąć razem ze stroną.
   * Ograniczamy jego wysokość do miejsca pod pozycją — reszta przewija się
   * w środku (top_bar.scss, `--bpp-podmenu-max`).
   */
  function ograniczWysokosc(li, sub) {
    var miejsce =
      window.innerHeight - li.getBoundingClientRect().bottom - MARGINES_DOLNY_PX;
    sub.style.setProperty(
      "--bpp-podmenu-max",
      Math.max(MIN_WYSOKOSC_PODMENU_PX, Math.round(miejsce)) + "px",
    );
  }

  function init() {
    var pozycje = Array.prototype.filter.call(
      document.querySelectorAll(".top-bar .dropdown.menu > li"),
      function (li) {
        return !!podmenu(li);
      },
    );
    if (!pozycje.length) {
      return;
    }
    var wielokolumnowe = pozycje.filter(function (li) {
      return li.classList.contains("has-submenu");
    });

    function ustawOtwarte(li, otwarte) {
      li.classList.toggle("is-active", otwarte);
      var link = li.querySelector(":scope > a");
      if (link) {
        link.setAttribute("aria-expanded", String(otwarte));
      }
    }

    function zamknijWielokolumnowe(procz) {
      wielokolumnowe.forEach(function (li) {
        if (li !== procz && li.classList.contains("is-active")) {
          ustawOtwarte(li, false);
        }
      });
    }

    /**
     * Zamyka zwykłe podmenu otwarte przez Foundation — tak, jak robi to
     * jego własne `_hide()` (klasy + znacznik „otwarte kliknięciem”,
     * bez którego kolejne stuknięcie by je zamykało zamiast otwierać).
     */
    function zamknijZwykle() {
      pozycje.forEach(function (li) {
        if (li.classList.contains("has-submenu")) {
          return;
        }
        li.classList.remove("is-active");
        if (li.hasAttribute("data-is-click")) {
          li.setAttribute("data-is-click", "false");
        }
        podmenu(li).classList.remove("js-dropdown-active");
      });
    }

    function przelaczWielokolumnowe(li) {
      var otworz = !li.classList.contains("is-active");
      zamknijWielokolumnowe(li);
      if (otworz) {
        zamknijZwykle();
        var sub = podmenu(li);
        ustawStrone(li, sub);
        ograniczWysokosc(li, sub);
      }
      ustawOtwarte(li, otworz);
    }

    // --- Dotyk -----------------------------------------------------------

    function poDotyku(e) {
      ostatniDotyk = Date.now();
      if (e.type !== "touchstart") {
        return;
      }
      // Stan po myszy (urządzenia z myszą i ekranem dotykowym) nie może
      // przesłaniać klas ustawianych dotykiem.
      pozycje.forEach(function (li) {
        anulujZamykanie(li);
        wyczyscStyleMyszy(podmenu(li));
      });
      // Stuknięcie poza otwartym blokiem wielokolumnowym zamyka go. Zwykłe
      // podmenu zamyka w tej sytuacji samo Foundation.
      var wSrodku = e.target.closest
        ? e.target.closest(".top-bar .dropdown.menu > li.has-submenu.is-active")
        : null;
      zamknijWielokolumnowe(wSrodku);
    }

    document.addEventListener("touchstart", poDotyku, {
      capture: true,
      passive: true,
    });
    document.addEventListener("touchend", poDotyku, {
      capture: true,
      passive: true,
    });

    // Urządzenia z myszą i ekranem dotykowym: blok otwarty dotykiem
    // zamyka też kliknięcie myszą obok.
    document.addEventListener("mousedown", function (e) {
      if (dotykPrzedChwila()) {
        return;
      }
      zamknijWielokolumnowe(
        e.target.closest(".top-bar .dropdown.menu > li.has-submenu.is-active"),
      );
    });

    wielokolumnowe.forEach(function (li) {
      var link = li.querySelector(":scope > a");
      if (!link) {
        return;
      }
      link.setAttribute("aria-expanded", "false");

      // Tak samo jak Foundation dla zwykłych podmenu: reagujemy już na
      // touchstart i blokujemy „dorobione” zdarzenia myszy oraz kliknięcie.
      // Dzięki temu stuknięcie daje dokładnie jedno przełączenie,
      // niezależnie od tego, co przeglądarka robi po dotyku.
      link.addEventListener(
        "touchstart",
        function (e) {
          e.preventDefault();
          przelaczWielokolumnowe(li);
        },
        { passive: false },
      );

      link.addEventListener("click", function (e) {
        // Dalej nie puszczamy: Foundation uważa tę pozycję za zwykły link
        // i po kliknięciu zamyka wszystkie menu — także to, które właśnie
        // otwieramy.
        e.stopPropagation();
        // Klawiatura (Enter na pozycji): detail === 0.
        if (e.detail === 0) {
          przelaczWielokolumnowe(li);
        }
      });

      // Z tego samego powodu: kliknięcie w puste miejsce otwartego bloku
      // (odstęp, linia) nie może go zamykać. Kliknięcia linków idą dalej —
      // korzystają z nich handlery na dokumencie (data-action).
      podmenu(li).addEventListener("click", function (e) {
        if (!e.target.closest("a")) {
          e.stopPropagation();
        }
      });
    });

    // Pozycje z podmenu mają href="#": kliknięcie przewijało stronę na samą
    // górę i dopisywało „#” do adresu.
    pozycje.forEach(function (li) {
      var link = li.querySelector(":scope > a");
      if (link && link.getAttribute("href") === "#") {
        link.addEventListener("click", function (e) {
          e.preventDefault();
        });
      }
    });

    if (window.jQuery) {
      // Foundation otworzyło zwykłe podmenu (mysz, dotyk albo klawiatura).
      window
        .jQuery(".top-bar .dropdown.menu")
        .on("show.zf.dropdownMenu", function (e, $sub) {
          zamknijWielokolumnowe(null);
          var sub = $sub && $sub[0];
          if (sub && dotykPrzedChwila()) {
            ograniczWysokosc(sub.parentElement, sub);
          }
        });
    }

    // --- Mysz ------------------------------------------------------------
    // Widocznością steruje tu skrypt (style w atrybucie), nie samo :hover:
    // pokazanie od razu, schowanie pozostałych od razu, a własnego —
    // dopiero po CZAS_ZAMYKANIA_MS od zjechania kursorem.

    pozycje.forEach(function (li) {
      var sub = podmenu(li);

      li.addEventListener("mouseenter", function () {
        if (dotykPrzedChwila()) {
          return;
        }
        if (li.classList.contains("has-submenu")) {
          ustawStrone(li, sub);
        }
        anulujZamykanie(li);
        pokazMysza(sub);

        pozycje.forEach(function (inne) {
          if (inne !== li) {
            anulujZamykanie(inne);
            schowajMysza(podmenu(inne));
          }
        });
        zamknijWielokolumnowe(li);
      });

      li.addEventListener("mouseleave", function (e) {
        if (dotykPrzedChwila()) {
          return;
        }
        var naInnaPozycje =
          e.relatedTarget &&
          e.relatedTarget.closest &&
          e.relatedTarget.closest(".dropdown.menu > li");
        if (naInnaPozycje) {
          return;
        }
        anulujZamykanie(li);
        zegary.set(
          li,
          setTimeout(function () {
            zegary.delete(li);
            schowajMysza(sub);
            if (li.classList.contains("has-submenu")) {
              ustawOtwarte(li, false);
            }
          }, CZAS_ZAMYKANIA_MS),
        );
      });
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
