/**
 * Centralized event handlers for common inline JavaScript patterns.
 * Replaces inline onclick/onchange handlers with data-attribute based delegation.
 *
 * Supported patterns:
 * - data-confirm: Shows confirmation dialog before action
 * - data-submit-on-change: Submits parent form on change
 * - data-open-url: Opens URL in new window/tab
 */
(function () {
  "use strict";

  /**
   * Handler for data-confirm attribute.
   * Shows browser confirm dialog before allowing the default action.
   *
   * Usage:
   *   <button data-confirm="Czy na pewno chcesz usunąć?">Usuń</button>
   *   <a href="/delete/1" data-confirm="Na pewno?">Usuń</a>
   *   <form data-confirm="Czy zapisać zmiany?">...</form>
   */
  document.addEventListener("click", function (e) {
    var target = e.target.closest("[data-confirm]");
    if (target) {
      var message = target.dataset.confirm;
      if (!confirm(message)) {
        e.preventDefault();
        e.stopPropagation();
      }
    }
  });

  /**
   * Handler for data-submit-on-change attribute.
   * Submits the parent form when the element value changes.
   *
   * Usage:
   *   <select data-submit-on-change>...</select>
   *   <input type="checkbox" data-submit-on-change>
   */
  document.addEventListener("change", function (e) {
    var target = e.target.closest("[data-submit-on-change]");
    if (target) {
      var form = target.closest("form");
      if (form) {
        form.submit();
      }
    }
  });

  /**
   * Handler for data-open-url attribute.
   * Opens URL in a new window/tab.
   *
   * Usage:
   *   <button data-open-url="/some/url" data-target="_blank">Otwórz</button>
   *   <span data-open-url="https://example.com">Link</span>
   *
   * Attributes:
   *   data-open-url: The URL to open (required)
   *   data-target: Window target, defaults to "_blank" (optional)
   */
  document.addEventListener("click", function (e) {
    var target = e.target.closest("[data-open-url]");
    if (target) {
      var url = target.dataset.openUrl;
      var windowTarget = target.dataset.target || "_blank";
      if (url) {
        window.open(url, windowTarget);
        e.preventDefault();
      }
    }
  });
  /**
   * Handler for data-action="open-global-search".
   * Opens the global search modal.
   */
  document.addEventListener("click", function (e) {
    var target = e.target.closest('[data-action="open-global-search"]');
    if (target) {
      e.preventDefault();
      if (typeof openGlobalSearch === "function") {
        openGlobalSearch(e);
      }
    }
  });

  /**
   * Handler for data-action="submit-logout-form".
   * Submits the logout form.
   */
  document.addEventListener("click", function (e) {
    var target = e.target.closest('[data-action="submit-logout-form"]');
    if (target) {
      e.preventDefault();
      var form = document.getElementById("logout-form");
      if (form) {
        form.submit();
      }
    }
  });

  /**
   * Handler for data-action="set-pbn-authorize-next".
   * Sets the href with the current location for PBN authorization redirect.
   */
  document.addEventListener("click", function (e) {
    var target = e.target.closest('[data-action="set-pbn-authorize-next"]');
    if (target) {
      var baseHref = target.href.split("?")[0];
      var nextUrl = encodeURIComponent(
        window.location.pathname + window.location.search + window.location.hash
      );
      target.href = baseHref + "?next=" + nextUrl;
    }
  });

  /**
   * Handler for data-stop-propagation attribute.
   * Stops event propagation when clicking on element.
   */
  document.addEventListener(
    "click",
    function (e) {
      if (e.target.closest("[data-stop-propagation]")) {
        e.stopPropagation();
      }
    },
    true
  );

  /**
   * Handler for data-action="close-global-search".
   * Closes the global search modal.
   */
  document.addEventListener("click", function (e) {
    var target = e.target.closest('[data-action="close-global-search"]');
    if (target) {
      e.preventDefault();
      if (typeof closeGlobalSearch === "function") {
        closeGlobalSearch();
      }
    }
  });

  /**
   * Handler for data-action="close-search-banner".
   * Closes the search shortcut banner.
   */
  document.addEventListener("click", function (e) {
    var target = e.target.closest('[data-action="close-search-banner"]');
    if (target) {
      e.preventDefault();
      if (typeof closeSearchBanner === "function") {
        closeSearchBanner();
      }
    }
  });

  /**
   * Handler for data-navigate-url attribute.
   * Navigates to URL on click/enter/space, but not if event was already prevented.
   */
  document.addEventListener("click", function (e) {
    if (e.defaultPrevented) return;
    var target = e.target.closest("[data-navigate-url]");
    if (target) {
      window.location = target.dataset.navigateUrl;
    }
  });

  document.addEventListener("keydown", function (e) {
    if (e.defaultPrevented) return;
    if (e.key === "Enter" || e.key === " ") {
      var target = e.target.closest("[data-navigate-url]");
      if (target) {
        e.preventDefault();
        window.location = target.dataset.navigateUrl;
      }
    }
  });

  /**
   * Handler for data-action="toggle-error".
   * Toggles error details visibility (e.g. in PBN import dashboard).
   */
  document.addEventListener("click", function (e) {
    var btn = e.target.closest('[data-action="toggle-error"]');
    if (btn) {
      e.preventDefault();
      e.stopPropagation();
      if (typeof toggleError === "function") {
        toggleError(btn);
      } else {
        // Fallback implementation
        var wrapper = btn.closest(".pbn-import__session-item-wrapper");
        if (wrapper) {
          var details = wrapper.querySelector(".pbn-import__error-details");
          if (details) {
            if (details.style.display === "none" || !details.style.display) {
              details.style.display = "block";
              btn.textContent = "Pokaż mniej";
            } else {
              details.style.display = "none";
              btn.textContent = "Pokaż więcej";
            }
          }
        }
      }
    }
  });

  /**
   * Handler for data-action="open-modal".
   * Opens Foundation reveal modal by ID specified in data-modal-id.
   */
  document.addEventListener("click", function (e) {
    var target = e.target.closest('[data-action="open-modal"]');
    if (target) {
      var modalId = target.dataset.modalId;
      if (modalId && typeof $ !== "undefined" && $.fn.foundation) {
        $("#" + modalId).foundation("open");
      }
    }
  });

  /**
   * Handler for data-action="close-window".
   * Closes the current browser window.
   */
  document.addEventListener("click", function (e) {
    var target = e.target.closest('[data-action="close-window"]');
    if (target) {
      e.preventDefault();
      window.close();
    }
  });

  /**
   * Handler for data-action="show-error-alert".
   * Shows an alert with error details from data-error and data-traceback attributes.
   */
  document.addEventListener("click", function (e) {
    var target = e.target.closest('[data-action="show-error-alert"]');
    if (target) {
      e.preventDefault();
      var errorMsg = target.dataset.error || "Nieznany błąd";
      var traceback = target.dataset.traceback;
      var message = errorMsg;
      if (traceback) {
        message += "\n\nTraceback:\n" + traceback;
      }
      alert(message);
    }
  });

  /**
   * Handler for data-action="pokaz-status-generowania".
   * Calls pokazStatusGenerowania function if available.
   */
  document.addEventListener("click", function (e) {
    var target = e.target.closest('[data-action="pokaz-status-generowania"]');
    if (target) {
      e.preventDefault();
      if (typeof pokazStatusGenerowania === "function") {
        pokazStatusGenerowania();
      }
    }
  });
})();
