/*
 * Konfigurator wyglądu (strona /konfigurator-wygladu/).
 *
 * Formularz powstaje z BppMotywKonfig.SCHEMAT. Po każdej zmianie worker
 * (motyw-kompilator-worker.js) kompiluje motyw tym samym SCSS-em, co build,
 * a wynik trafia do <style id="bpp-motyw-podglad"> w ramkach z prawdziwymi
 * stronami BPP (otwieranymi z ?podglad_motywu=1). Na końcu klient pobiera
 * konfig jako JSON — z niego powstaje motyw (scss/motywy/<nazwa>.json).
 */
(function () {
    "use strict";

    var M = window.BppMotywKonfig;
    var adresy = JSON.parse(document.getElementById("konfigurator-adresy").textContent);
    var podglady = JSON.parse(document.getElementById("konfigurator-podglady").textContent);
    var serwer = JSON.parse(document.getElementById("konfigurator-serwer").textContent);

    var KLUCZ_PAMIECI = "bpp-konfigurator-wygladu";
    var ROZMIAR = {
        komputer: { szerokosc: 1280, wysokosc: 800 },
        telefon: { szerokosc: 390, wysokosc: 780 },
    };
    var UKRYJ_W_PODGLADZIE = "#CookielawBanner, .cookie-pasek { display: none !important; }";

    var stan = wczytajZPamieci();
    var css = null;
    var ostatnieZlecenie = 0;
    var odliczanie = null;
    var startKompilacji = 0;

    var elPola = document.getElementById("pola");
    var elStatus = document.getElementById("status");
    var elNazwa = document.getElementById("pole-nazwa");
    var elOpis = document.getElementById("pole-opis");

    // --- Stan ------------------------------------------------------------------

    // Kolejność: szkic z tej przeglądarki, potem motyw zapisany (niezastosowany),
    // potem zastosowany na stronie, potem domyślne.
    function wczytajZPamieci() {
        var zapisany = window.localStorage.getItem(KLUCZ_PAMIECI);
        if (!zapisany) {
            var zSerwera = (serwer.roboczy && serwer.roboczy.konfig) || serwer.zapisany_konfig;
            return M.normalizuj(zSerwera || {});
        }
        try {
            return M.normalizuj(JSON.parse(zapisany));
        } catch (e) {
            if (e instanceof SyntaxError) return M.normalizuj({}); // uszkodzony wpis
            throw e;
        }
    }

    function zapiszWPamieci() {
        window.localStorage.setItem(KLUCZ_PAMIECI, JSON.stringify(stan));
    }

    function ustaw(klucz, wartosc) {
        stan[klucz] = wartosc;
        zapiszWPamieci();
        if (klucz === "tryb_kolorow") pokazPrzelacznikTrybu();
        odswiezWidocznosc();
        pokazBledy();
        zaplanujKompilacje();
    }

    // --- Formularz -------------------------------------------------------------

    function el(tag, atrybuty, dzieci) {
        var e = document.createElement(tag);
        Object.keys(atrybuty || {}).forEach(function (k) {
            if (k === "tekst") e.textContent = atrybuty[k];
            else e.setAttribute(k, atrybuty[k]);
        });
        (dzieci || []).forEach(function (d) {
            e.appendChild(d);
        });
        return e;
    }

    function poleKolor(p) {
        var probnik = el("input", { type: "color", id: "pole-" + p.klucz });
        var hex = el("input", {
            type: "text",
            maxlength: "7",
            spellcheck: "false",
            "aria-label": p.etykieta + " (kod koloru)",
        });
        var wartosc = stan[p.klucz] || stan.kolor_glowny;
        probnik.value = wartosc;
        hex.value = wartosc;
        probnik.addEventListener("input", function () {
            hex.value = probnik.value;
            ustaw(p.klucz, probnik.value);
        });
        hex.addEventListener("input", function () {
            var v = hex.value.trim();
            if (/^#[0-9a-fA-F]{6}$/.test(v)) probnik.value = v.toLowerCase();
            ustaw(p.klucz, v.toLowerCase());
        });
        return el("div", { class: "kolor" }, [probnik, hex]);
    }

    // Kolor albo „automatycznie” (pusta wartość) — np. UserWay jak kolor główny.
    function poleKolorAuto(p) {
        var kolor = poleKolor(p);
        var auto = el("input", { type: "checkbox" });
        auto.checked = !stan[p.klucz];
        function przelacz() {
            kolor.querySelectorAll("input").forEach(function (i) {
                i.disabled = auto.checked;
            });
        }
        auto.addEventListener("change", function () {
            ustaw(p.klucz, auto.checked ? "" : kolor.querySelector("input[type=color]").value);
            przelacz();
        });
        przelacz();
        return el("div", {}, [
            el("label", { class: "tak-nie tak-nie-maly" }, [auto, el("span", { tekst: p.auto })]),
            kolor,
        ]);
    }

    function poleWybor(p) {
        var grupa = el("div", { class: "wybor", role: "radiogroup", "aria-labelledby": "etykieta-" + p.klucz });
        p.opcje.forEach(function (o) {
            var radio = el("input", { type: "radio", name: p.klucz, value: o[0] });
            radio.checked = stan[p.klucz] === o[0];
            radio.addEventListener("change", function () {
                if (radio.checked) ustaw(p.klucz, o[0]);
            });
            grupa.appendChild(el("label", {}, [radio, el("span", { tekst: o[1] })]));
        });
        return grupa;
    }

    function poleLista(p) {
        var lista = el("select", { id: "pole-" + p.klucz, class: "lista" });
        p.opcje.forEach(function (o) {
            var opcja = el("option", { value: o[0], tekst: o[1] });
            opcja.selected = stan[p.klucz] === o[0];
            lista.appendChild(opcja);
        });
        lista.addEventListener("change", function () {
            ustaw(p.klucz, lista.value);
        });
        return lista;
    }

    function poleTekst(p) {
        var pole = el("input", { type: "text", class: "tekst", id: "pole-" + p.klucz, spellcheck: "false" });
        pole.value = stan[p.klucz];
        pole.addEventListener("input", function () {
            ustaw(p.klucz, pole.value.trim());
        });
        return pole;
    }

    function poleTakNie(p) {
        var box = el("input", { type: "checkbox", id: "pole-" + p.klucz });
        box.checked = !!stan[p.klucz];
        box.addEventListener("change", function () {
            ustaw(p.klucz, box.checked);
        });
        return el("label", { class: "tak-nie" }, [box, el("span", { tekst: p.etykieta })]);
    }

    // Obrazek: zmniejszany w przeglądarce (canvas → WebP) do limitu
    // M.MAKS_DLUGOSC_OBRAZU, zapisywany w konfigu jako data URL. SVG bez zmian.
    function poleObraz(p) {
        // Natywne „Choose File / No file chosen” (angielskie, systemowa
        // czcionka) ukryte — własny opis po lewej, przycisk „Wybierz” po prawej.
        var plik = el("input", { type: "file", id: "pole-" + p.klucz, accept: "image/png,image/jpeg,image/webp,image/gif,image/svg+xml" });
        plik.hidden = true;
        var opis = el("span", { class: "obraz-opis" });
        var wybierz = el("button", { type: "button", class: "obraz-wybierz", tekst: "Wybierz plik…" });
        wybierz.addEventListener("click", function () {
            plik.click();
        });
        var miniatura = el("img", { class: "miniatura", alt: "" });
        var usun = el("button", { type: "button", tekst: "Usuń obrazek" });
        function pokaz() {
            miniatura.hidden = !stan[p.klucz];
            usun.hidden = !stan[p.klucz];
            opis.textContent = stan[p.klucz] ? "Obrazek wybrany" : "Nie wybrano pliku";
            if (stan[p.klucz]) miniatura.src = bezpiecznyObraz(stan[p.klucz]);
        }
        plik.addEventListener("change", function () {
            var f = plik.files[0];
            plik.value = "";
            if (!f) return;
            ustawStatus("Przygotowuję obrazek…");
            przygotujObraz(f, p).then(
                function (wynik) {
                    if (p.szerokoscKlucz) stan[p.szerokoscKlucz] = wynik.szerokosc;
                    ustaw(p.klucz, wynik.dataUrl);
                    pokaz();
                    odswiezWidocznosc();
                },
                function (blad) {
                    ustawStatus(blad.message, true);
                },
            );
        });
        usun.addEventListener("click", function () {
            if (p.szerokoscKlucz) stan[p.szerokoscKlucz] = 0;
            ustaw(p.klucz, "");
            pokaz();
            odswiezWidocznosc();
        });
        pokaz();
        return el("div", { class: "obraz" }, [
            el("div", { class: "obraz-wybor" }, [opis, wybierz, plik]),
            miniatura,
            usun,
        ]);
    }

    function szerokoscPrzy28(szer, wys) {
        if (!szer || !wys) return 28;
        return Math.max(8, Math.min(400, Math.round((28 * szer) / wys)));
    }

    function wymiary(url) {
        return new Promise(function (ok) {
            var img = new Image();
            img.onload = function () {
                ok({ width: img.naturalWidth || img.width, height: img.naturalHeight || img.height });
            };
            // SVG bez wymiarów — szerokość domyślna (kwadrat), nie błąd.
            img.onerror = function () {
                ok({ width: 0, height: 0 });
            };
            img.src = url;
        });
    }

    // Do <img src> tylko obrazki jako data URL albo adresy z tej domeny
    // (np. /media/… faviconu) — nic, co przeglądarka mogłaby zinterpretować
    // inaczej niż obrazek.
    var RE_OBRAZ_DATA = /^data:image\/(png|jpeg|webp|gif|svg\+xml|x-icon);base64,[A-Za-z0-9+/=]+$/;

    function bezpiecznyObraz(adres) {
        if (typeof adres !== "string") return "";
        if (RE_OBRAZ_DATA.test(adres)) return adres;
        var u = new URL(adres, window.location.href);
        return u.origin === window.location.origin ? u.href : "";
    }

    function czytajJakoDataUrl(f) {
        return new Promise(function (ok, blad) {
            var r = new FileReader();
            r.onload = function () {
                ok(r.result);
            };
            r.onerror = function () {
                blad(new Error("Nie udało się odczytać pliku."));
            };
            r.readAsDataURL(f);
        });
    }

    var TYPY_OBRAZOW = ["image/png", "image/jpeg", "image/webp", "image/gif", "image/svg+xml"];
    var MAKS_PLIK_MB = 10;
    var MAKS_BOK_PX = 10000;

    // Wstępna kontrola przed wczytaniem: typ, wielkość pliku, wymiary
    // (ochrona przed „bombami” dekompresji). Serwer i kompilator sprawdzają
    // wynik jeszcze raz.
    // Wynik: {dataUrl, szerokosc} — szerokość w px przy wysokości 28 px
    // (dla logo na pasku, p.szerokoscKlucz).
    function przygotujObraz(f, p) {
        var limit = p.maksDlugosc || M.MAKS_DLUGOSC_OBRAZU;
        if (TYPY_OBRAZOW.indexOf(f.type) === -1) {
            return Promise.reject(new Error("Dozwolone są obrazki PNG, JPG, WebP, GIF i SVG."));
        }
        if (f.size > MAKS_PLIK_MB * 1024 * 1024) {
            return Promise.reject(
                new Error(
                    "Plik ma " + (f.size / 1024 / 1024).toFixed(1) + " MB — maksymalnie " +
                        MAKS_PLIK_MB + " MB.",
                ),
            );
        }
        if (f.type === "image/svg+xml") {
            return czytajJakoDataUrl(f).then(function (url) {
                if (url.length > limit) {
                    throw new Error(
                        "Plik SVG jest za duży (limit ok. " + Math.round((limit * 0.75) / 1024) + " KB).",
                    );
                }
                return wymiary(url).then(function (w) {
                    return { dataUrl: url, szerokosc: szerokoscPrzy28(w.width, w.height) };
                });
            });
        }
        return czytajJakoDataUrl(f).then(function (url) {
            return new Promise(function (ok, blad) {
                var img = new Image();
                img.onload = function () {
                    if (img.width > MAKS_BOK_PX || img.height > MAKS_BOK_PX) {
                        blad(new Error("Obrazek jest za duży (maksymalnie " + MAKS_BOK_PX + " px na bok)."));
                        return;
                    }
                    // Logo: do wysokości p.wysokoscPx (2× na ekrany Retina);
                    // tło: dłuższy bok do 1200 px.
                    var bok = p.wysokoscPx
                        ? Math.min(img.height, p.wysokoscPx) * Math.max(1, img.width / img.height)
                        : Math.min(1200, Math.max(img.width, img.height));
                    for (var proba = 0; proba < 8; proba++) {
                        var skala = bok / Math.max(img.width, img.height);
                        var c = document.createElement("canvas");
                        c.width = Math.max(1, Math.round(img.width * skala));
                        c.height = Math.max(1, Math.round(img.height * skala));
                        c.getContext("2d").drawImage(img, 0, 0, c.width, c.height);
                        // WebP zachowuje przezroczystość; przeglądarki bez
                        // kodera WebP zwracają PNG.
                        var wynik = c.toDataURL("image/webp", 0.85);
                        if (wynik.length <= limit) {
                            return ok({
                                dataUrl: wynik,
                                szerokosc: szerokoscPrzy28(img.width, img.height),
                            });
                        }
                        bok = Math.round(bok * 0.75);
                    }
                    blad(new Error("Nie udało się zmniejszyć obrazka do dopuszczalnego rozmiaru."));
                };
                img.onerror = function () {
                    blad(new Error("To nie jest obsługiwany obrazek."));
                };
                img.src = url;
            });
        });
    }

    var BUDOWNICZOWIE = {
        kolor: poleKolor,
        kolor_auto: poleKolorAuto,
        wybor: poleWybor,
        lista: poleLista,
        tekst: poleTekst,
        tak_nie: poleTakNie,
        obraz: poleObraz,
    };

    function zbudujFormularz() {
        elPola.textContent = "";
        var grupy = {};
        M.SCHEMAT.forEach(function (p) {
            if (p.ukryte) return; // wyliczane (np. szerokość logo), bez pola
            if (!grupy[p.grupa]) {
                var sekcja = el("details", { class: "sekcja", "data-sekcja": p.grupa }, [
                    el("summary", { tekst: p.grupa }),
                ]);
                grupy[p.grupa] = el("div", { class: "sekcja-tresc" });
                sekcja.appendChild(grupy[p.grupa]);
                elPola.appendChild(sekcja);
            }
            var pole = el("div", { class: "pole", "data-klucz": p.klucz });
            if (p.typ !== "tak_nie") {
                var tag = ["kolor", "lista", "tekst", "obraz"].indexOf(p.typ) !== -1 ? "label" : "div";
                var etykieta = el(tag, { class: "etykieta", id: "etykieta-" + p.klucz, tekst: p.etykieta });
                if (tag === "label") etykieta.setAttribute("for", "pole-" + p.klucz);
                pole.appendChild(etykieta);
            }
            if (p.opis) pole.appendChild(el("div", { class: "opis", tekst: p.opis }));
            pole.appendChild(BUDOWNICZOWIE[p.typ](p));
            pole.appendChild(el("div", { class: "blad", id: "blad-" + p.klucz, hidden: "" }));
            grupy[p.grupa].appendChild(pole);
        });
        elNazwa.value = stan.nazwa;
        elOpis.value = stan.opis;
        // Sekcje według ważności (kolejność w SCHEMAT wynika z budowy pól).
        KOLEJNOSC_SEKCJI.slice().reverse().forEach(function (nazwa) {
            var sekcja = elPola.querySelector('.sekcja[data-sekcja="' + nazwa + '"]');
            if (sekcja) elPola.insertBefore(sekcja, elPola.firstChild);
        });
        przywrocSekcje();
        odswiezWidocznosc();
        pokazBledy();
    }

    var KOLEJNOSC_SEKCJI = [
        "Kolory",
        "Tekst",
        "Menu",
        "Przyciski",
        "Kształt",
        "Strona główna i wykresy",
        "Okruszki i stopka",
        "Komunikaty",
        "Grafika w tle",
        "Przycisk dostępności (UserWay)",
    ];

    // Które sekcje są rozwinięte — pamiętane w przeglądarce; na start
    // pierwsza („Kolory”).
    var KLUCZ_SEKCJI = "bpp-konfigurator-wygladu-sekcje";

    function przywrocSekcje() {
        var otwarte;
        try {
            otwarte = JSON.parse(window.localStorage.getItem(KLUCZ_SEKCJI) || "null");
        } catch (e) {
            if (!(e instanceof SyntaxError)) throw e;
            otwarte = null; // uszkodzony wpis — jak przy pierwszej wizycie
        }
        document.querySelectorAll(".sekcja").forEach(function (sekcja, i) {
            var nazwa = sekcja.dataset.sekcja;
            sekcja.open = otwarte ? otwarte.indexOf(nazwa) !== -1 : i === 0;
            if (!sekcja.bppPodpieta) {
                sekcja.bppPodpieta = true;
                sekcja.addEventListener("toggle", zapamietajSekcje);
            }
        });
    }

    function zapamietajSekcje() {
        var otwarte = [];
        document.querySelectorAll(".sekcja[open]").forEach(function (sekcja) {
            otwarte.push(sekcja.dataset.sekcja);
        });
        window.localStorage.setItem(KLUCZ_SEKCJI, JSON.stringify(otwarte));
    }

    function ustawWszystkieSekcje(otwarte) {
        document.querySelectorAll(".panel .sekcja").forEach(function (sekcja) {
            sekcja.open = otwarte;
        });
        zapamietajSekcje();
    }

    document.getElementById("rozwin-wszystkie").addEventListener("click", function () {
        ustawWszystkieSekcje(true);
    });
    document.getElementById("zwin-wszystkie").addEventListener("click", function () {
        ustawWszystkieSekcje(false);
    });

    // Błąd w zwiniętej sekcji — rozwiń ją, żeby był widoczny.
    function rozwinSekcjeZBledami(bledy) {
        bledy.forEach(function (b) {
            var pole = document.getElementById("blad-" + b.pole);
            var sekcja = pole && pole.closest(".sekcja");
            if (sekcja) sekcja.open = true;
        });
    }

    // Pola zależne od innych (np. położenie grafiki tylko, gdy jest obrazek).
    function odswiezWidocznosc() {
        M.SCHEMAT.forEach(function (p) {
            if (!p.pokaz) return;
            var pole = elPola.querySelector('.pole[data-klucz="' + p.klucz + '"]');
            if (pole) pole.hidden = !p.pokaz(stan);
        });
    }

    elNazwa.addEventListener("input", function () {
        ustaw("nazwa", elNazwa.value.trim());
    });
    elOpis.addEventListener("input", function () {
        ustaw("opis", elOpis.value.trim());
    });

    // Błędy przy polach. Nazwa jest wymagana dopiero przy pobieraniu.
    function pokazBledy(zNazwa) {
        document.querySelectorAll(".pole .blad").forEach(function (b) {
            b.hidden = true;
            b.textContent = "";
        });
        var bledy = M.waliduj(stan, { bezNazwy: !zNazwa });
        bledy.forEach(function (b) {
            var miejsce = document.getElementById("blad-" + b.pole);
            if (!miejsce) return;
            miejsce.hidden = false;
            miejsce.appendChild(el("div", { tekst: b.komunikat }));
            if (b.poprawka) {
                var przycisk = el("button", { type: "button", tekst: "Użyj czytelnego odcienia " + b.poprawka });
                przycisk.addEventListener("click", function () {
                    stan[b.pole] = b.poprawka;
                    zapiszWPamieci();
                    zbudujFormularz();
                    zaplanujKompilacje();
                });
                miejsce.appendChild(przycisk);
            }
        });
        return bledy;
    }

    // --- Kompilacja --------------------------------------------------------------

    var worker = new Worker(
        adresy.worker +
            "?sass=" + encodeURIComponent(adresy.sass) +
            "&konfig=" + encodeURIComponent(adresy.konfig) +
            "&kompilator=" + encodeURIComponent(adresy.kompilator) +
            "&zrodla=" + encodeURIComponent(adresy.zrodla),
    );

    // Naraz najwyżej JEDNA kompilacja. Zmiany w trakcie nie tworzą kolejki
    // zleceń — zapamiętujemy tylko, że trzeba skompilować jeszcze raz
    // (z aktualnego stanu), więc po serii szybkich kliknięć wykonuje się
    // jedna kompilacja, a nie kilkanaście.
    var kompilacjaTrwa = false;
    var czekaKolejna = false;

    function kompilacjaZakonczona() {
        kompilacjaTrwa = false;
        if (czekaKolejna) {
            czekaKolejna = false;
            kompiluj();
        }
    }

    worker.onmessage = function (e) {
        if (e.data.id !== ostatnieZlecenie) return; // nieaktualny wynik
        if (e.data.blad) {
            ustawStatus("Nie udało się zbudować podglądu: " + e.data.blad, true);
            kompilacjaZakonczona();
            return;
        }
        css = e.data.css;
        // Strony w ramkach czytają to synchronicznie przy starcie (bare.html).
        window.BppKonfiguratorCss = css;
        uruchomRamki();
        var sekundy = ((Date.now() - startKompilacji) / 1000).toFixed(1);
        ustawStatus("Podgląd aktualny (" + sekundy + " s).");
        wszystkieRamki().forEach(zastosuj);
        kompilacjaZakonczona();
    };

    worker.onerror = function (e) {
        ustawStatus("Błąd kompilatora podglądu: " + e.message, true);
        kompilacjaZakonczona();
    };

    function zaplanujKompilacje() {
        window.clearTimeout(odliczanie);
        odliczanie = window.setTimeout(kompiluj, 300);
    }

    function kompiluj() {
        // Błąd formatu (np. kolor albo nazwa czcionki w trakcie pisania) —
        // nie kompilujemy. Błędy kontrastu (z poprawką) nie blokują podglądu,
        // żeby było widać, czemu kolor nie przechodzi.
        var zlyFormat = M.waliduj(stan, { bezNazwy: true }).some(function (b) {
            return !b.poprawka;
        });
        if (zlyFormat) return;
        if (kompilacjaTrwa) {
            czekaKolejna = true;
            return;
        }
        kompilacjaTrwa = true;
        ostatnieZlecenie += 1;
        startKompilacji = Date.now();
        ustawStatus("Buduję podgląd…");
        worker.postMessage({
            id: ostatnieZlecenie,
            konfig: stan,
            czcionkiUrl: adresy.czcionki.replace(/\/$/, ""),
            trybPodgladu: stan.tryb_kolorow === "automatyczny" ? trybPodgladu : null,
        });
    }

    // Podgląd trybu automatycznego: który wariant pokazać.
    var trybPodgladu = "jasny";
    var elTrybPodgladu = document.getElementById("tryb-podgladu");

    function pokazPrzelacznikTrybu() {
        elTrybPodgladu.hidden = stan.tryb_kolorow !== "automatyczny";
        elTrybPodgladu.querySelectorAll("button").forEach(function (b) {
            b.setAttribute("aria-pressed", String(b.dataset.tryb === trybPodgladu));
        });
    }

    elTrybPodgladu.querySelectorAll("button").forEach(function (b) {
        b.addEventListener("click", function () {
            trybPodgladu = b.dataset.tryb;
            pokazPrzelacznikTrybu();
            kompiluj();
        });
    });

    function ustawStatus(tekst, blad) {
        elStatus.textContent = tekst;
        elStatus.classList.toggle("blad", !!blad);
    }

    // --- Podglądy ------------------------------------------------------------------

    function adresPodgladu(adres) {
        var url = new URL(adres, window.location.href);
        url.searchParams.set("podglad_motywu", "1");
        return url.href;
    }

    function wszystkieRamki() {
        return Array.prototype.slice.call(document.querySelectorAll("iframe[data-podglad]"));
    }

    // Wstawia motyw do strony w ramce. Strona bez miejsca na motyw (np. po
    // kliknięciu linku — adres stracił ?podglad_motywu) jest przeładowywana
    // z parametrem.
    function zastosuj(ramka) {
        var doc = ramka.contentDocument;
        if (!doc || !doc.head) return; // inna domena albo jeszcze się ładuje
        var miejsce = doc.getElementById("bpp-motyw-podglad");
        if (!miejsce) {
            var url = new URL(ramka.contentWindow.location.href);
            if (url.origin === window.location.origin && !url.searchParams.has("podglad_motywu")) {
                ramka.contentWindow.location.replace(adresPodgladu(url.href));
            }
            return;
        }
        if (!doc.getElementById("bpp-motyw-podglad-dodatki")) {
            var dodatki = doc.createElement("style");
            dodatki.id = "bpp-motyw-podglad-dodatki";
            dodatki.textContent = UKRYJ_W_PODGLADZIE;
            doc.head.appendChild(dodatki);
        }
        if (css === null) return;
        miejsce.textContent = css;
        pilnujLudzika(doc);
        // Ramki w ramce (np. wyniki multiseek) — ten sam motyw.
        doc.querySelectorAll("iframe").forEach(function (wewnetrzna) {
            if (!wewnetrzna.bppPodpieta) {
                wewnetrzna.bppPodpieta = true;
                wewnetrzna.addEventListener("load", function () {
                    zastosuj(wewnetrzna);
                });
            }
            zastosuj(wewnetrzna);
        });
        var zaslona = ramka.parentNode && ramka.parentNode.querySelector(".zaslona");
        if (zaslona) zaslona.classList.add("ukryta");
    }

    // Widget UserWay wpisuje kolor przycisku w style inline z !important
    // (z data-color odczytanego raz, przy starcie strony) — żaden CSS go nie
    // przebije. W podglądzie ustawiamy go więc wprost i pilnujemy, bo widget
    // doładowuje się później i potrafi nadpisać styl.
    var ID_LUDZIKA = ["userwayAccessibilityIcon", "userwayLstIcon"];

    function ustawLudzika(doc) {
        var kolor = M.wylicz(stan).kolorUserway;
        ID_LUDZIKA.forEach(function (id) {
            var e = doc.getElementById(id);
            if (!e || e.dataset.bppStyl === e.getAttribute("style")) return;
            e.style.setProperty("background", kolor, "important");
            e.dataset.bppStyl = e.getAttribute("style");
        });
    }

    function pilnujLudzika(doc) {
        ID_LUDZIKA.forEach(function (id) {
            var e = doc.getElementById(id);
            if (e) delete e.dataset.bppStyl; // zmienił się konfig — ustaw na nowo
        });
        ustawLudzika(doc);
        if (doc.bppObserwatorLudzika || !doc.body) return;
        doc.bppObserwatorLudzika = new MutationObserver(function () {
            ustawLudzika(doc);
        });
        doc.bppObserwatorLudzika.observe(doc.body, {
            childList: true,
            subtree: true,
            attributes: true,
            attributeFilter: ["style"],
        });
    }

    function oknoPodgladu(p) {
        // Adres ustawiamy dopiero, gdy jest pierwszy CSS (uruchomRamki):
        // strona bez motywu przy starcie źle rozpoznałaby rozmiar ekranu.
        var ramka = el("iframe", {
            "data-src": adresPodgladu(p.adres),
            title: "Podgląd: " + p.tytul,
            "data-podglad": p.urzadzenie,
            tabindex: "-1",
        });
        ramka.addEventListener("load", function () {
            zastosuj(ramka);
            ramkaZaladowana(ramka);
        });
        return el("div", { class: "okno" }, [
            ramka,
            el("div", { class: "zaslona", tekst: "Buduję podgląd…" }),
        ]);
    }

    function przyciskPowieksz(p) {
        var powieksz = el("button", { type: "button", tekst: "Powiększ" });
        powieksz.addEventListener("click", function () {
            otworzPowiekszenie(p);
        });
        return powieksz;
    }

    // Komputer: karta na stronę. Telefony: jedna karta z ekranami obok
    // siebie — pojedynczy wąski ekran w szerokiej karcie zostawiał puste pasy.
    function zbudujPodglady() {
        var siatka = document.getElementById("siatka");
        var telefony = el("div", { class: "telefony" });
        podglady.forEach(function (p) {
            if (p.urzadzenie === "telefon") {
                telefony.appendChild(
                    el("div", { class: "telefon" }, [
                        el("div", { class: "telefon-naglowek" }, [
                            el("span", { tekst: p.tytul.replace(/^Telefon: /, "") }),
                            przyciskPowieksz(p),
                        ]),
                        oknoPodgladu(p),
                    ]),
                );
                return;
            }
            siatka.appendChild(
                el("section", { class: "karta komputer" }, [
                    el("header", {}, [el("span", { tekst: p.tytul }), przyciskPowieksz(p)]),
                    oknoPodgladu(p),
                ]),
            );
        });
        if (telefony.children.length) {
            siatka.appendChild(
                el("section", { class: "karta karta-telefony" }, [
                    el("header", {}, [el("span", { tekst: "Telefon" })]),
                    telefony,
                ]),
            );
        }
        przeskaluj();
        new ResizeObserver(przeskaluj).observe(siatka);
    }

    // Ramki ładujemy PO KOLEI (następna po załadowaniu poprzedniej), żeby nie
    // uderzać w serwer kilkunastoma stronami naraz.
    var kolejkaRamek = [];
    var ladowanaRamka = null;
    var bezpiecznik = null;

    function nastepnaRamka() {
        window.clearTimeout(bezpiecznik);
        ladowanaRamka = null;
        if (!kolejkaRamek.length) return;
        ladowanaRamka = kolejkaRamek.shift();
        ladowanaRamka.src = ladowanaRamka.dataset.src;
        // Gdyby strona nie zgłosiła „load” (zerwane połączenie), nie
        // blokujemy reszty podglądów.
        bezpiecznik = window.setTimeout(nastepnaRamka, 30000);
    }

    function ramkaZaladowana(ramka) {
        if (ramka === ladowanaRamka && ramka.getAttribute("src") !== "about:blank") {
            nastepnaRamka();
        }
    }

    function wstrzymajRamki() {
        kolejkaRamek = [];
        window.clearTimeout(bezpiecznik);
        ladowanaRamka = null;
        wszystkieRamki().forEach(function (ramka) {
            if (ramka.dataset.src) ramka.src = "about:blank";
        });
    }

    function uruchomRamki() {
        wszystkieRamki().forEach(function (ramka) {
            var src = ramka.getAttribute("src");
            var czeka = kolejkaRamek.indexOf(ramka) !== -1 || ramka === ladowanaRamka;
            if (ramka.dataset.src && (!src || src === "about:blank") && !czeka) {
                kolejkaRamek.push(ramka);
            }
        });
        if (!ladowanaRamka) nastepnaRamka();
    }

    function ustawSkale(okno, rodzaj, szerokosc) {
        var r = ROZMIAR[rodzaj];
        var skala = Math.min(1, szerokosc / r.szerokosc);
        var ramka = okno.querySelector("iframe");
        ramka.style.width = r.szerokosc + "px";
        ramka.style.height = r.wysokosc + "px";
        ramka.style.transform = "scale(" + skala + ")";
        okno.style.width = r.szerokosc * skala + "px";
        okno.style.height = r.wysokosc * skala + "px";
    }

    // Ramki mają rozmiar prawdziwego ekranu i są pomniejszane transformacją.
    function przeskaluj() {
        document.querySelectorAll(".karta.komputer").forEach(function (karta) {
            ustawSkale(karta.querySelector(".okno"), "komputer", karta.clientWidth);
        });
        document.querySelectorAll(".karta-telefony").forEach(function (karta) {
            var telefony = karta.querySelectorAll(".telefon");
            var odstep = 12;
            var szer = (karta.clientWidth - 2 * odstep - odstep * (telefony.length - 1)) / telefony.length;
            telefony.forEach(function (t) {
                ustawSkale(t.querySelector(".okno"), "telefon", szer);
            });
        });
    }

    var elPowiekszenie = document.getElementById("powiekszenie");
    var elPowiekszenieRamka = document.getElementById("powiekszenie-ramka");
    elPowiekszenieRamka.setAttribute("data-podglad", "powiekszenie");
    elPowiekszenieRamka.addEventListener("load", function () {
        if (elPowiekszenieRamka.getAttribute("src") !== "about:blank") {
            document.getElementById("powiekszenie-ladowanie").hidden = true;
        }
        zastosuj(elPowiekszenieRamka);
    });

    // Na czas powiększenia ramki siatki są odpinane: każda wczytana strona
    // trzyma stałe połączenia (np. SSE autoprzeładowania w trybie dev),
    // a przy HTTP/1.1 przeglądarka ma tylko 6 połączeń na host — strona
    // w powiększeniu czekałaby w kolejce bez końca.
    function otworzPowiekszenie(p) {
        wstrzymajRamki();
        document.getElementById("powiekszenie-ladowanie").hidden = false;
        document.getElementById("powiekszenie-tytul").textContent = p.tytul;
        elPowiekszenie.querySelector(".ramka").classList.toggle("telefon", p.urzadzenie === "telefon");
        elPowiekszenieRamka.src = adresPodgladu(p.adres);
        elPowiekszenie.classList.add("otwarte");
        document.getElementById("zamknij-powiekszenie").focus();
    }

    function zamknijPowiekszenie() {
        elPowiekszenie.classList.remove("otwarte");
        elPowiekszenieRamka.src = "about:blank";
        uruchomRamki();
    }

    document.getElementById("zamknij-powiekszenie").addEventListener("click", zamknijPowiekszenie);
    elPowiekszenie.addEventListener("click", function (e) {
        if (e.target === elPowiekszenie) zamknijPowiekszenie();
    });
    document.addEventListener("keydown", function (e) {
        if (e.key === "Escape" && elPowiekszenie.classList.contains("otwarte")) zamknijPowiekszenie();
    });

    // --- Pobieranie i wczytywanie konfiga ------------------------------------------

    function konfigDoPobrania() {
        var wynik = { wersja: M.WERSJA, nazwa: stan.nazwa, opis: stan.opis };
        M.SCHEMAT.forEach(function (p) {
            wynik[p.klucz] = stan[p.klucz];
        });
        return JSON.stringify(wynik, null, 2) + "\n";
    }

    // Nazwa pliku jest opcjonalna (wymagana tylko dla motywów w repo) —
    // sprawdzamy ją, tylko gdy ktoś ją wpisał.
    function nazwaPliku() {
        return stan.nazwa || "motyw-bpp";
    }

    function gotowyDoPobrania() {
        var bledy = pokazBledy(!!stan.nazwa);
        if (bledy.length) {
            ustawStatus("Popraw zaznaczone pola: " + bledy.map(function (b) {
                return b.komunikat;
            }).join(" "), true);
            return false;
        }
        return true;
    }

    document.getElementById("pobierz").addEventListener("click", function () {
        if (!gotowyDoPobrania()) return;
        var plik = new Blob([konfigDoPobrania()], { type: "application/json" });
        var a = el("a", { href: URL.createObjectURL(plik), download: nazwaPliku() + ".json" });
        document.body.appendChild(a);
        a.click();
        a.remove();
        URL.revokeObjectURL(a.href);
        ustawStatus("Zapisano plik " + nazwaPliku() + ".json (w katalogu pobranych plików przeglądarki).");
    });

    document.getElementById("kopiuj").addEventListener("click", function () {
        if (!gotowyDoPobrania()) return;
        navigator.clipboard.writeText(konfigDoPobrania()).then(
            function () {
                ustawStatus("Ustawienia skopiowane do schowka.");
            },
            function (e) {
                ustawStatus("Nie udało się skopiować: " + e.message, true);
            },
        );
    });

    document.getElementById("wczytaj").addEventListener("change", function (e) {
        var plik = e.target.files[0];
        if (!plik) return;
        plik.text().then(function (tekst) {
            var konfig;
            try {
                konfig = JSON.parse(tekst);
            } catch (blad) {
                if (!(blad instanceof SyntaxError)) throw blad;
                ustawStatus("To nie jest plik z ustawieniami (niepoprawny JSON).", true);
                return;
            }
            stan = M.normalizuj(konfig);
            zapiszWPamieci();
            zbudujFormularz();
            zaplanujKompilacje();
            ustawStatus("Wczytano " + plik.name + ".");
        });
        e.target.value = "";
    });

    var elGotowy = document.getElementById("gotowy-motyw");
    M.GOTOWE.forEach(function (g) {
        elGotowy.appendChild(el("option", { value: g.klucz, tekst: g.etykieta }));
    });

    document.getElementById("wczytaj-gotowy").addEventListener("click", function () {
        var gotowy = M.GOTOWE.filter(function (g) {
            return g.klucz === elGotowy.value;
        })[0];
        var konfig = JSON.parse(JSON.stringify(gotowy.konfig));
        konfig.nazwa = stan.nazwa;
        konfig.opis = stan.opis;
        stan = M.normalizuj(konfig);
        zapiszWPamieci();
        zbudujFormularz();
        zaplanujKompilacje();
        var bledy = M.waliduj(stan, { bezNazwy: true });
        rozwinSekcjeZBledami(bledy);
        ustawStatus(
            "Wczytano: " + gotowy.etykieta + "." +
                (bledy.length ? " Sprawdź zaznaczone pola — ten motyw nie spełnia wymogów czytelności." : ""),
            bledy.length > 0,
        );
    });

    // --- Historia i cofanie -------------------------------------------------------------

    function pobierzJson(adres, opcje) {
        return fetch(adres, opcje).then(function (r) {
            return r.json().then(function (dane) {
                if (!r.ok) throw new Error(dane.blad || "HTTP " + r.status);
                return dane;
            });
        });
    }

    function pokazHistorie() {
        var lista = document.getElementById("historia-lista");
        lista.textContent = "";
        (serwer.historia || []).forEach(function (w, i) {
            var wczytaj = el("button", { type: "button", tekst: "Wczytaj" });
            wczytaj.addEventListener("click", function () {
                wczytajWersje(w);
            });
            var pozycja = el("li", {}, [el("span", { tekst: w.kiedy + (w.kto ? " · " + w.kto : "") })]);
            if (w.id) pozycja.appendChild(wczytaj); // świeży wpis: id po przeładowaniu
            if (i === 0 && serwer.motyw_aktywny === "app-wlasny") {
                pozycja.appendChild(el("span", { class: "aktualny", tekst: "(na stronie teraz)" }));
            }
            lista.appendChild(pozycja);
        });
        document.getElementById("historia-pusta").hidden = (serwer.historia || []).length > 0;

        var sprzed = serwer.motyw_sprzed;
        var blok = document.getElementById("motyw-sprzed");
        blok.hidden = !(sprzed && serwer.mozna_zastosowac && serwer.motyw_aktywny !== sprzed.wartosc);
        if (sprzed) {
            document.getElementById("przywroc-sprzed").textContent =
                "Wróć do motywu sprzed konfiguratora: " + sprzed.etykieta;
        }
    }

    function wczytajWersje(w) {
        pobierzJson(serwer.adres_historia.replace("{id}", w.id), { credentials: "same-origin" })
            .then(function (dane) {
                stan = M.normalizuj(dane.konfig);
                zapiszWPamieci();
                zbudujFormularz();
                zaplanujKompilacje();
                ustawStatus("Wczytano motyw z " + w.kiedy + ". Kliknij „Zastosuj”, żeby przywrócić go na stronie.");
            })
            .catch(function (blad) {
                ustawStatus("Nie udało się wczytać wersji: " + blad.message, true);
            });
    }

    document.getElementById("przywroc-sprzed").addEventListener("click", function () {
        var sprzed = serwer.motyw_sprzed;
        if (!window.confirm("Przywrócić na stronie motyw „" + sprzed.etykieta + "”? Ustawienia z konfiguratora zostaną w historii.")) return;
        pobierzJson(serwer.adres_przywroc, {
            method: "POST",
            credentials: "same-origin",
            headers: { "Content-Type": "application/json", "X-CSRFToken": csrf() },
            body: JSON.stringify({ motyw: sprzed.wartosc }),
        })
            .then(function () {
                serwer.motyw_aktywny = sprzed.wartosc;
                pokazHistorie();
                ustawStatus("Przywrócono motyw „" + sprzed.etykieta + "”.");
            })
            .catch(function (blad) {
                ustawStatus("Nie udało się przywrócić motywu: " + blad.message, true);
            });
    });

    // --- Favicon ---------------------------------------------------------------------

    var MAKS_FAVICON = 1024 * 1024; // jak MAKS_ROZMIAR_FAVICON w pliki_uczelni.py
    var nowyFavicon = null; // data URL czekający na „Zastosuj”
    var elFaviconBlad = document.getElementById("favicon-blad");
    var elFaviconCofnij = document.getElementById("favicon-cofnij");

    function pokazFavicon() {
        var url = bezpiecznyObraz(nowyFavicon || serwer.favicon_url || "/favicon.ico");
        ["favicon-podglad", "favicon-32", "favicon-64"].forEach(function (id) {
            document.getElementById(id).src = url;
        });
        elFaviconCofnij.hidden = !nowyFavicon;
    }

    function bladFaviconu(tekst) {
        elFaviconBlad.hidden = !tekst;
        elFaviconBlad.textContent = tekst || "";
    }

    document.getElementById("favicon-plik").addEventListener("change", function (e) {
        var f = e.target.files[0];
        e.target.value = "";
        if (!f) return;
        var ico = /\.ico$/i.test(f.name) || /icon/.test(f.type);
        if (!ico && f.type !== "image/png") {
            bladFaviconu("Ikona musi być plikiem PNG albo ICO.");
            return;
        }
        if (f.size > MAKS_FAVICON) {
            bladFaviconu("Ikona ma " + (f.size / 1024).toFixed(0) + " KB — maksymalnie 1 MB.");
            return;
        }
        czytajJakoDataUrl(f).then(function (url) {
            // Przeglądarki różnie podpisują ICO (albo wcale) — ujednolicamy.
            if (ico) url = url.replace(/^data:[^;]*;/, "data:image/x-icon;");
            return wymiary(url).then(function (w) {
                if (!w.width) {
                    bladFaviconu("Nie udało się odczytać obrazka — sprawdź plik.");
                    return;
                }
                if (w.width < 16 || w.height < 16) {
                    bladFaviconu("Ikona jest za mała (co najmniej 16×16 px).");
                    return;
                }
                bladFaviconu(
                    w.width !== w.height
                        ? "Uwaga: ikona nie jest kwadratowa (" + w.width + "×" + w.height +
                              " px) — przeglądarka ją zniekształci."
                        : "",
                );
                nowyFavicon = url;
                pokazFavicon();
                ustawStatus("Nowa ikona zapisze się po kliknięciu „Zastosuj”.");
            });
        });
    });

    elFaviconCofnij.addEventListener("click", function () {
        nowyFavicon = null;
        bladFaviconu("");
        pokazFavicon();
    });

    // --- Zastosowanie na stronie ---------------------------------------------------

    var elZastosuj = document.getElementById("zastosuj");
    var elWroc = document.getElementById("wroc-do-zapisanego");

    function csrf() {
        return document.querySelector("input[name=csrfmiddlewaretoken]").value;
    }

    var elZapisz = document.getElementById("zapisz");

    // Bez kompilatora (albo bez prawa „Zastosuj”) proponujemy zapisanie
    // motywu — strona się nie zmienia, motyw czeka na zastosowanie.
    function ustawPrzyciski() {
        var moznaZastosowac = serwer.mozna_zastosowac && serwer.kompilator_dostepny;
        elZastosuj.hidden = !moznaZastosowac;
        // „Zapisz w bazie” zawsze dostępne; główny przycisk, gdy nie da się
        // zastosować (kompilator niedostępny albo brak uprawnień).
        elZapisz.hidden = false;
        elZapisz.classList.toggle("glowny", !moznaZastosowac);
        document.getElementById("przymierz").hidden = !serwer.kompilator_dostepny;
        document.getElementById("tylko-superuzytkownik").hidden = serwer.mozna_zastosowac;
        var uwaga = document.getElementById("uwaga-kompilator");
        uwaga.hidden = serwer.kompilator_dostepny;
        uwaga.textContent =
            "Kompilator motywów jest teraz niedostępny, więc motywu nie da się " +
            "zastosować. Możesz go zapisać — zastosujesz go, gdy kompilator zacznie działać.";
    }

    function pokazRoboczy() {
        var uwaga = document.getElementById("uwaga-roboczy");
        uwaga.hidden = !serwer.roboczy;
        if (serwer.roboczy) {
            uwaga.textContent =
                "Jest zapisany, jeszcze niezastosowany motyw" +
                (serwer.roboczy.kto ? " (" + serwer.roboczy.kto + ", " + serwer.roboczy.kiedy + ")" : "") +
                ". „Zastosuj” włączy go na stronie.";
        }
    }

    // Przymiarka: serwer kompiluje motyw dla tej sesji, potem przechodzimy
    // na stronę główną — motyw widać wszędzie, ale tylko u mnie.
    var elPrzymierz = document.getElementById("przymierz");
    elPrzymierz.addEventListener("click", function () {
        var bledy = pokazBledy(false);
        if (bledy.length) {
            rozwinSekcjeZBledami(bledy);
            ustawStatus("Popraw zaznaczone pola przed przymiarką.", true);
            return;
        }
        elPrzymierz.disabled = true;
        // Karta otwierana od razu (w geście kliknięcia) — po zapytaniu
        // przeglądarka zablokowałaby ją jako wyskakujące okno.
        var karta = window.open("about:blank", "_blank");
        ustawStatus("Buduję motyw do przymiarki…");
        wstrzymajRamki(); // jak przy „Zastosuj” — wolne połączenie dla zapytania
        pobierzJson(serwer.adres_przymierz, {
            method: "POST",
            credentials: "same-origin",
            headers: { "Content-Type": "application/json", "X-CSRFToken": csrf() },
            body: JSON.stringify({ konfig: stan }),
        })
            .then(function (dane) {
                if (karta) karta.location = dane.adres;
                else window.location = dane.adres;
                ustawStatus("Przymiarka włączona — otworzyłem stronę w nowej karcie. Widzisz ją tylko Ty.");
            })
            .catch(function (blad) {
                if (karta) karta.close();
                ustawStatus("Nie udało się włączyć przymiarki: " + blad.message, true);
            })
            .then(function () {
                elPrzymierz.disabled = false;
                uruchomRamki();
            });
    });

    elZapisz.addEventListener("click", function () {
        var bledy = pokazBledy(false);
        if (bledy.length) {
            rozwinSekcjeZBledami(bledy);
            ustawStatus("Popraw zaznaczone pola przed zapisaniem.", true);
            return;
        }
        elZapisz.disabled = true;
        var konfig = JSON.parse(JSON.stringify(stan));
        fetch(serwer.adres_zapisz, {
            method: "POST",
            credentials: "same-origin",
            headers: { "Content-Type": "application/json", "X-CSRFToken": csrf() },
            body: JSON.stringify({ konfig: konfig }),
        })
            .then(function (r) {
                return r.json().then(function (dane) {
                    if (!r.ok) throw new Error(dane.blad || "HTTP " + r.status);
                    return dane;
                });
            })
            .then(function () {
                serwer.roboczy = { konfig: konfig, kto: "", kiedy: "przed chwilą" };
                pokazRoboczy();
                ustawStatus("Zapisano motyw. Strona się nie zmieniła — zastosujesz go później.");
            })
            .catch(function (blad) {
                ustawStatus("Nie udało się zapisać: " + blad.message, true);
            })
            .then(function () {
                elZapisz.disabled = false;
            });
    });

    elZastosuj.addEventListener("click", function () {
        var bledy = pokazBledy(false);
        if (bledy.length) {
            rozwinSekcjeZBledami(bledy);
            ustawStatus("Popraw zaznaczone pola przed zastosowaniem.", true);
            return;
        }
        if (!window.confirm("Zmienić wygląd strony dla wszystkich użytkowników?")) return;
        elZastosuj.disabled = true;
        ustawStatus("Zapisuję i buduję motyw na serwerze…");
        // Ramki odpinamy na czas zapisu: każda strona trzyma długie połączenia
        // (np. SSE autoprzeładowania w trybie dev), a przy HTTP/1.1
        // przeglądarka ma tylko 6 połączeń na host — POST by na nie czekał
        // albo został zerwany. Po zapisie ramki ładują się na nowo.
        wstrzymajRamki();
        // CSS buduje serwer tym samym kodem co podgląd (V8); wysyłamy tylko
        // ustawienia.
        var konfig = JSON.parse(JSON.stringify(stan));
        fetch(serwer.adres_zastosuj, {
            method: "POST",
            credentials: "same-origin",
            headers: { "Content-Type": "application/json", "X-CSRFToken": csrf() },
            body: JSON.stringify({ konfig: konfig, favicon: nowyFavicon }),
        })
            .then(function (r) {
                return r.json().then(function (dane) {
                    if (dane.niedostepny) {
                        serwer.kompilator_dostepny = false;
                        ustawPrzyciski();
                    }
                    if (!r.ok) throw new Error(dane.blad || "HTTP " + r.status);
                    return dane;
                });
            })
            .then(function () {
                serwer.roboczy = null;
                pokazRoboczy();
                serwer.zapisany_konfig = konfig;
                serwer.motyw_aktywny = "app-wlasny";
                (serwer.historia = serwer.historia || []).unshift({
                    id: null,
                    kiedy: "przed chwilą",
                    kto: "",
                });
                // Pełna lista (z identyfikatorami) po przeładowaniu strony.
                pokazHistorie();
                if (nowyFavicon) {
                    serwer.favicon_url = nowyFavicon;
                    nowyFavicon = null;
                    pokazFavicon();
                }
                serwer.zapisany_w_wersji = serwer.wersja_bpp;
                serwer.zapisany_aktywny = true;
                pokazUwageOWersji();
                elWroc.hidden = false;
                ustawStatus("Zastosowano. Nowy wygląd widzą już wszyscy odwiedzający.");
            })
            .catch(function (blad) {
                ustawStatus("Nie udało się zastosować: " + blad.message, true);
            })
            .then(function () {
                elZastosuj.disabled = false;
                uruchomRamki();
            });
    });

    if (serwer.zapisany_konfig) elWroc.hidden = false;
    elWroc.addEventListener("click", function () {
        stan = M.normalizuj(serwer.zapisany_konfig);
        zapiszWPamieci();
        zbudujFormularz();
        zaplanujKompilacje();
    });

    // Motyw zapisany w starszej wersji BPP nie zawiera stylów nowych
    // elementów stron — przypominamy o ponownym „Zastosuj”.
    function pokazUwageOWersji() {
        var uwaga = document.getElementById("uwaga-wersja");
        var nieaktualny =
            serwer.zapisany_aktywny &&
            serwer.zapisany_w_wersji &&
            serwer.zapisany_w_wersji !== serwer.wersja_bpp;
        uwaga.hidden = !nieaktualny;
        if (nieaktualny) {
            uwaga.textContent =
                "Motyw zbudowano w wersji BPP " + serwer.zapisany_w_wersji +
                ", a strona działa już na wersji " + serwer.wersja_bpp +
                ". Zwykle przebudowuje się sam przy aktualizacji; jeśli ten " +
                "komunikat nie znika, kliknij „Zastosuj”.";
        }
    }

    // --- Układ podglądów (1/2/3 kolumny albo automatycznie) ----------------------

    var KLUCZ_UKLADU = "bpp-konfigurator-wygladu-uklad";

    function ustawUklad(kolumny) {
        var siatka = document.getElementById("siatka");
        siatka.classList.remove("kolumny-1", "kolumny-2", "kolumny-3");
        if (kolumny !== "auto") siatka.classList.add("kolumny-" + kolumny);
        document.querySelectorAll(".uklad-podgladow button").forEach(function (b) {
            b.setAttribute("aria-pressed", String(b.dataset.kolumny === kolumny));
        });
        window.localStorage.setItem(KLUCZ_UKLADU, kolumny);
        przeskaluj();
    }

    document.querySelectorAll(".uklad-podgladow button").forEach(function (b) {
        b.addEventListener("click", function () {
            ustawUklad(b.dataset.kolumny);
        });
    });

    pokazUwageOWersji();
    pokazHistorie();
    ustawPrzyciski();
    pokazRoboczy();
    pokazFavicon();
    pokazPrzelacznikTrybu();
    zbudujFormularz();
    zbudujPodglady();
    ustawUklad(window.localStorage.getItem(KLUCZ_UKLADU) || "auto");
    kompiluj();
})();
