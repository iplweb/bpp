// Przycisk „Cofnij” na liście przemapowań źródeł w adminie: pyta
// o potwierdzenie i wysyła POST (widok cofania nie przyjmuje GET).
// Tekst pytania przychodzi w atrybucie data-potwierdzenie — dane
// (nazwa źródła) nigdy nie są wklejane do kodu JS.
(function () {
    "use strict";

    function tokenCsrf() {
        var pole = document.querySelector("[name=csrfmiddlewaretoken]");
        if (pole && pole.value) {
            return pole.value;
        }
        var m = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/);
        return m ? decodeURIComponent(m[1]) : "";
    }

    function cofnij(link) {
        if (link.getAttribute("data-wyslano")) {
            return;
        }
        if (!window.confirm(link.getAttribute("data-potwierdzenie") || "")) {
            return;
        }
        link.setAttribute("data-wyslano", "1");
        var form = document.createElement("form");
        form.method = "POST";
        form.action = link.getAttribute("href");
        var csrf = document.createElement("input");
        csrf.type = "hidden";
        csrf.name = "csrfmiddlewaretoken";
        csrf.value = tokenCsrf();
        form.appendChild(csrf);
        document.body.appendChild(form);
        form.submit();
    }

    document.addEventListener("click", function (ev) {
        var link =
            ev.target && ev.target.closest
                ? ev.target.closest("a.przemapowanie-cofnij")
                : null;
        if (!link) {
            return;
        }
        ev.preventDefault();
        cofnij(link);
    });
})();
