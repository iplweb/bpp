/*
 * Picker kolekcji DSpace dla admina Mapowanie_DSpace (Feature B).
 *
 * Progressive enhancement: pole `collection_uuid` to zwykły <input> tekstowy
 * z UUID. Ten skrypt dorabia obok niego <select> zasilany NA ŻYWO z DSpace
 * (endpoint admina `collections/?uczelnia=<id>`), zależny od wybranej uczelni.
 * Gdy DSpace jest nieosiągalny / zwróci błąd / pustą listę — select się nie
 * pojawia i zostaje pole tekstowe (ręczne wpisanie UUID). Zawsze można też
 * przełączyć się na ręczne wpisanie linkiem.
 */
(function () {
    "use strict";

    function ready(fn) {
        if (document.readyState !== "loading") {
            fn();
        } else {
            document.addEventListener("DOMContentLoaded", fn);
        }
    }

    function setupPicker(input) {
        var url = input.getAttribute("data-collections-url");
        var uczelniaFieldId = input.getAttribute("data-uczelnia-field");
        if (!url || !uczelniaFieldId) {
            return;
        }
        var uczelniaField = document.getElementById(uczelniaFieldId);

        // Kontener UI obok pola tekstowego.
        var wrap = document.createElement("span");
        wrap.className = "dspace-collection-picker-wrap";

        var select = document.createElement("select");
        select.className = "dspace-collection-picker-select";
        select.style.display = "none";

        var status = document.createElement("span");
        status.className = "dspace-collection-picker-status help";
        status.style.display = "none";
        status.style.marginLeft = "0.5em";

        var toggle = document.createElement("a");
        toggle.href = "#";
        toggle.className = "dspace-collection-picker-toggle";
        toggle.style.marginLeft = "0.5em";
        toggle.style.display = "none";

        input.parentNode.insertBefore(wrap, input);
        wrap.appendChild(select);
        wrap.appendChild(input);
        wrap.appendChild(toggle);
        wrap.appendChild(status);

        var manual = true; // true = widoczne pole tekstowe

        function showManual(message) {
            manual = true;
            select.style.display = "none";
            input.style.display = "";
            toggle.textContent = "Wybierz kolekcję z listy";
            // Pokaż link do listy tylko, gdy jest co wybierać.
            toggle.style.display = select.options.length ? "" : "none";
            status.textContent = message || "";
            status.style.display = message ? "" : "none";
        }

        function showSelect() {
            manual = false;
            input.style.display = "none";
            select.style.display = "";
            toggle.textContent = "Wpisz UUID ręcznie";
            toggle.style.display = "";
            status.textContent = "";
            status.style.display = "none";
            // Zsynchronizuj pole tekstowe z aktualnym wyborem.
            if (select.value) {
                input.value = select.value;
            }
        }

        toggle.addEventListener("click", function (ev) {
            ev.preventDefault();
            if (manual && select.options.length) {
                showSelect();
            } else {
                showManual("");
            }
        });

        select.addEventListener("change", function () {
            input.value = select.value;
        });

        function populate(collections) {
            var current = (input.value || "").trim();
            select.options.length = 0;
            var seen = false;
            collections.forEach(function (c) {
                var opt = document.createElement("option");
                opt.value = c.uuid;
                opt.textContent = c.name + " (" + c.uuid + ")";
                if (c.uuid === current) {
                    opt.selected = true;
                    seen = true;
                }
                select.appendChild(opt);
            });
            // Zachowaj zapisaną wartość, nawet gdy nie ma jej już w DSpace.
            if (current && !seen) {
                var opt = document.createElement("option");
                opt.value = current;
                opt.textContent = current + " (spoza listy DSpace)";
                opt.selected = true;
                select.insertBefore(opt, select.firstChild);
            }
        }

        function load() {
            if (!uczelniaField || !uczelniaField.value) {
                select.options.length = 0;
                showManual("");
                return;
            }
            status.textContent = "Pobieranie kolekcji z DSpace…";
            status.style.display = "";
            var reqUrl =
                url +
                (url.indexOf("?") === -1 ? "?" : "&") +
                "uczelnia=" +
                encodeURIComponent(uczelniaField.value);
            fetch(reqUrl, { credentials: "same-origin" })
                .then(function (resp) {
                    return resp.json();
                })
                .then(function (data) {
                    var collections = (data && data.collections) || [];
                    if (data && data.error) {
                        showManual(data.error);
                        return;
                    }
                    if (!collections.length) {
                        showManual(
                            "DSpace nie zwrócił żadnych kolekcji — wpisz UUID ręcznie."
                        );
                        return;
                    }
                    populate(collections);
                    showSelect();
                })
                .catch(function () {
                    showManual(
                        "Błąd połączenia z DSpace — wpisz UUID kolekcji ręcznie."
                    );
                });
        }

        if (uczelniaField) {
            uczelniaField.addEventListener("change", load);
        }
        load();
    }

    ready(function () {
        var inputs = document.querySelectorAll("input.dspace-collection-picker");
        Array.prototype.forEach.call(inputs, setupPicker);
    });
})();
