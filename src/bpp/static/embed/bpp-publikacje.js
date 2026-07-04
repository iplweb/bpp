/*!
 * BPP — widget osadzania listy publikacji autora / jednostki.
 *
 * Użycie (jedna linia na stronie zewnętrznej):
 *   <script src="https://<serwer-bpp>/static/embed/bpp-publikacje.js"
 *           data-autor="Jan-Kowalski" data-limit="25" async></script>
 *
 * Konfiguracja przez atrybuty data-* (patrz dokumentacja). Loader sam:
 *   - wykrywa origin serwera BPP z własnego src,
 *   - wstrzykuje kontener tuż za swoim tagiem (lub w data-target),
 *   - dokłada arkusz stylów (chyba że data-no-css),
 *   - pobiera dane z publicznego API i renderuje listę/tabelę.
 *
 * Czysty vanilla JS, bez zależności — celowo poza bundlem (audytowalny).
 */
(function () {
  "use strict";

  var me = document.currentScript;
  if (!me) {
    // Ścieżka awaryjna (currentScript === null). UWAGA: nie wspiera wielu
    // widgetów na jednej stronie — zwraca pierwszy nieobsłużony tag.
    me = document.querySelector(
      'script[src*="bpp-publikacje.js"]:not([data-bpp-init])'
    );
  }
  if (!me) {
    return;
  }
  me.setAttribute("data-bpp-init", "");

  // --- Sanityzacja (allowlist) ------------------------------------------
  // opis_bibliograficzny pochodzi z pól wprowadzanych ręcznie przez redaktora
  // i jest renderowany jako innerHTML na cudzych domenach → potencjalny
  // stored-XSS. Przepuszczamy tylko tagi formatujące, usuwamy WSZYSTKIE
  // atrybuty (w tym on*, src, href) oraz <script>/<style>.
  var DOZWOLONE_TAGI = {
    B: 1,
    I: 1,
    EM: 1,
    STRONG: 1,
    SUB: 1,
    SUP: 1,
    U: 1,
  };

  function sanitize(html) {
    var tpl = document.createElement("template");
    tpl.innerHTML = html == null ? "" : String(html);

    var walker = document.createTreeWalker(
      tpl.content,
      NodeFilter.SHOW_ELEMENT,
      null
    );
    var elementy = [];
    var node = walker.nextNode();
    while (node) {
      elementy.push(node);
      node = walker.nextNode();
    }

    elementy.forEach(function (el) {
      // Usuń wszystkie atrybuty niezależnie od tagu.
      while (el.attributes.length) {
        el.removeAttribute(el.attributes[0].name);
      }
      if (!DOZWOLONE_TAGI[el.tagName]) {
        if (el.tagName === "SCRIPT" || el.tagName === "STYLE") {
          if (el.parentNode) {
            el.parentNode.removeChild(el);
          }
        } else if (el.parentNode) {
          // "Rozpakuj" niedozwolony tag — zachowaj jego tekst/dzieci.
          while (el.firstChild) {
            el.parentNode.insertBefore(el.firstChild, el);
          }
          el.parentNode.removeChild(el);
        }
      }
    });

    return tpl.innerHTML;
  }

  // Udostępnij sanitizer do testów (idempotentnie).
  if (!window.__bppPublikacjeSanitize) {
    window.__bppPublikacjeSanitize = sanitize;
  }

  // --- Konfiguracja ------------------------------------------------------
  function originZSrc(src) {
    try {
      return new URL(src, window.location.href).origin;
    } catch (e) {
      return "";
    }
  }

  function odczytajKonfiguracje(scriptEl) {
    var d = scriptEl.dataset;
    return {
      autor: d.autor || null,
      jednostka: d.jednostka || null,
      serwer: (d.serwer || originZSrc(scriptEl.src)).replace(/\/+$/, ""),
      limit: d.limit || null,
      rokOd: d.rokOd || null,
      rokDo: d.rokDo || null,
      styl: (d.styl || "lista").toLowerCase(),
      noCss: d.noCss !== undefined,
      target: d.target || null,
    };
  }

  function urlApi(cfg) {
    var sciezka = cfg.jednostka
      ? "recent_unit_publications"
      : "recent_author_publications";
    var id = cfg.jednostka || cfg.autor || "";
    var url =
      cfg.serwer + "/api/v1/" + sciezka + "/" + encodeURIComponent(id) + "/";

    var qs = [];
    if (cfg.limit) {
      qs.push("limit=" + encodeURIComponent(cfg.limit));
    }
    if (cfg.rokOd) {
      qs.push("rok_od=" + encodeURIComponent(cfg.rokOd));
    }
    if (cfg.rokDo) {
      qs.push("rok_do=" + encodeURIComponent(cfg.rokDo));
    }
    if (qs.length) {
      url += "?" + qs.join("&");
    }
    return url;
  }

  // --- DOM ---------------------------------------------------------------
  function dolaczCss(cfg) {
    if (cfg.noCss) {
      return;
    }
    if (document.querySelector("link[data-bpp-publikacje-css]")) {
      return;
    }
    var link = document.createElement("link");
    link.rel = "stylesheet";
    link.href = cfg.serwer + "/static/embed/bpp-publikacje.css";
    link.setAttribute("data-bpp-publikacje-css", "");
    (document.head || document.documentElement).appendChild(link);
  }

  function utworzKontener(scriptEl, cfg) {
    var kontener;
    if (cfg.target) {
      kontener = document.querySelector(cfg.target);
      if (!kontener) {
        return null;
      }
    } else {
      kontener = document.createElement("div");
      scriptEl.parentNode.insertBefore(kontener, scriptEl.nextSibling);
    }
    kontener.className = "bpp-publikacje";
    kontener.innerHTML =
      '<div class="bpp-publikacje__loading">Ładowanie publikacji…</div>';
    return kontener;
  }

  function linkSzczegolow(pub) {
    var a = document.createElement("a");
    a.className = "bpp-publikacje__link";
    a.href = pub.url;
    a.target = "_blank";
    a.rel = "noopener";
    a.textContent = "[szczegóły]";
    return a;
  }

  function elementOpisu(pub) {
    var span = document.createElement("span");
    span.className = "bpp-publikacje__opis";
    span.innerHTML = sanitize(pub.opis_bibliograficzny);
    return span;
  }

  function renderListy(kontener, data) {
    var ol = document.createElement("ol");
    ol.className = "bpp-publikacje__lista";
    data.publications.forEach(function (pub) {
      var li = document.createElement("li");
      li.className = "bpp-publikacje__item";
      li.appendChild(elementOpisu(pub));
      li.appendChild(document.createTextNode(" "));
      li.appendChild(linkSzczegolow(pub));
      ol.appendChild(li);
    });
    kontener.appendChild(ol);
  }

  function renderTabeli(kontener, data) {
    var table = document.createElement("table");
    table.className = "bpp-publikacje__tabela";
    var tbody = document.createElement("tbody");
    data.publications.forEach(function (pub) {
      var tr = document.createElement("tr");
      tr.className = "bpp-publikacje__wiersz";

      var tdOpis = document.createElement("td");
      tdOpis.appendChild(elementOpisu(pub));
      tr.appendChild(tdOpis);

      var tdLink = document.createElement("td");
      tdLink.className = "bpp-publikacje__link-cell";
      tdLink.appendChild(linkSzczegolow(pub));
      tr.appendChild(tdLink);

      tbody.appendChild(tr);
    });
    table.appendChild(tbody);
    kontener.appendChild(table);
  }

  function stopka(data) {
    var p = document.createElement("p");
    p.className = "bpp-publikacje__stopka";
    p.appendChild(
      document.createTextNode("Wyświetlono " + data.count + " publikacji. ")
    );
    if (data.profil_url) {
      var a = document.createElement("a");
      a.href = data.profil_url;
      a.target = "_blank";
      a.rel = "noopener";
      a.textContent = "Zobacz pełny profil w systemie BPP →";
      p.appendChild(a);
    }
    return p;
  }

  function render(kontener, data, cfg) {
    kontener.innerHTML = "";
    if (!data.publications || !data.publications.length) {
      var pusto = document.createElement("p");
      pusto.className = "bpp-publikacje__empty";
      pusto.textContent = "Brak publikacji do wyświetlenia.";
      kontener.appendChild(pusto);
      return;
    }
    if (cfg.styl === "tabela") {
      renderTabeli(kontener, data);
    } else {
      renderListy(kontener, data);
    }
    kontener.appendChild(stopka(data));
  }

  function renderBlad(kontener, cfg) {
    kontener.innerHTML = "";
    var div = document.createElement("div");
    div.className = "bpp-publikacje__error";
    div.textContent = "Nie udało się załadować listy publikacji. ";
    var a = document.createElement("a");
    a.href = cfg.serwer;
    a.target = "_blank";
    a.rel = "noopener";
    a.textContent = "Przejdź do systemu BPP";
    div.appendChild(a);
    kontener.appendChild(div);
  }

  // --- Start -------------------------------------------------------------
  function uruchom() {
    var cfg = odczytajKonfiguracje(me);
    if (!cfg.autor && !cfg.jednostka) {
      return; // brak encji — nic nie renderujemy
    }
    dolaczCss(cfg);
    var kontener = utworzKontener(me, cfg);
    if (!kontener) {
      return;
    }

    fetch(urlApi(cfg))
      .then(function (resp) {
        if (!resp.ok) {
          throw new Error("HTTP " + resp.status);
        }
        return resp.json();
      })
      .then(function (data) {
        render(kontener, data, cfg);
      })
      .catch(function () {
        renderBlad(kontener, cfg);
      });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", uruchom);
  } else {
    uruchom();
  }
})();
