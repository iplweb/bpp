/**
 * live-operations.js — channels_broadcast plugin for live_operations.
 *
 * On DOMContentLoaded: scans the page for elements that carry both
 * data-liveop-channel and data-liveop-token, then calls
 * channelsBroadcast.init() with the subscription token so the
 * channels_broadcast client connects to the right operation channel.
 *
 * Overrides channelsBroadcast.addMessage to handle:
 *
 *   msg.liveop_html   — parse the HTML fragment and apply hx-swap-oob
 *                       by element id (outerHTML replace for oob="true",
 *                       append for oob="beforeend:#id"). Then calls
 *                       htmx.process(node) if htmx is present so that
 *                       hx-* attributes in the new content activate.
 *
 *   msg.liveop_chain  — the current operation chained to a new one;
 *                       re-initialise the socket for the next channel via
 *                       channelsBroadcast.init() (idempotent — closes old
 *                       socket cleanly, §17.10).
 *
 *   anything else     — delegate to the original addMessage handler.
 */
(function () {
    "use strict";

    // ------------------------------------------------------------------ //
    // OOB-swap helper                                                     //
    // ------------------------------------------------------------------ //

    function applyOobSwap(fragment) {
        var parser = new DOMParser();
        var doc = parser.parseFromString(fragment, "text/html");
        var nodes = Array.prototype.slice.call(doc.body.children);

        for (var i = 0; i < nodes.length; i++) {
            var node = nodes[i];
            var oob = node.getAttribute("hx-swap-oob");
            if (!oob) continue;

            var inserted = null;

            if (oob === "true") {
                // outerHTML replace by id
                var targetId = node.id;
                if (!targetId) continue;
                var target = document.getElementById(targetId);
                var clone = node.cloneNode(true);
                if (target) {
                    target.replaceWith(clone);
                    inserted = clone;
                } else {
                    document.body.appendChild(clone);
                    inserted = clone;
                }
            } else if (oob.indexOf("outerHTML:") === 0) {
                // outerHTML replace by explicit CSS selector
                // e.g. hx-swap-oob="outerHTML:#op-abc123" replaces the
                // selected element with this node (oob attr stripped).
                var outerSelector = oob.slice("outerHTML:".length).trim();
                var outerTarget = document.querySelector(outerSelector);
                var outerClone = node.cloneNode(true);
                outerClone.removeAttribute("hx-swap-oob");
                if (outerTarget) {
                    outerTarget.replaceWith(outerClone);
                } else {
                    document.body.appendChild(outerClone);
                }
                inserted = outerClone;
            } else if (oob.indexOf("beforeend:") === 0) {
                // beforeend:#some-id — append children
                var selector = oob.slice("beforeend:".length).trim();
                var appendTarget = document.querySelector(selector);
                if (!appendTarget) continue;
                var cloneNode = node.cloneNode(true);
                while (cloneNode.firstChild) {
                    appendTarget.appendChild(cloneNode.firstChild);
                }
                inserted = appendTarget;
            }

            // Let htmx wire up hx-* attributes in the new content.
            if (inserted && window.htmx) {
                try {
                    window.htmx.process(inserted);
                } catch (e) {
                    console.debug("live-operations: htmx.process threw", e);
                }
            }
        }
    }

    // ------------------------------------------------------------------ //
    // Initialisation                                                      //
    // ------------------------------------------------------------------ //

    function init() {
        var cn = window.channelsBroadcast;
        if (!cn) {
            console.warn(
                "live-operations: channelsBroadcast not loaded — " +
                "include channels_broadcast/js/notifications.js first"
            );
            return;
        }

        var container = document.querySelector(
            "[data-liveop-channel][data-liveop-token]"
        );
        if (!container) return;

        var token = container.getAttribute("data-liveop-token");

        // Save the original addMessage so unknown payload types fall through.
        var _origAddMessage = cn.addMessage.bind(cn);

        cn.addMessage = function (message) {
            if (message.liveop_html) {
                applyOobSwap(message.liveop_html);
                return;
            }
            if (message.liveop_chain) {
                // Chain to next operation: re-init socket with new token.
                var next = message.liveop_chain;
                cn.init(null, { subscriptionToken: next.token });
                return;
            }
            // Unknown message type — delegate to default handler.
            _origAddMessage(message);
        };

        // null extraChannels — the token carries the channel name.
        cn.init(null, { subscriptionToken: token });
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", init);
    } else {
        // DOM already ready (script loaded deferred or at end of body).
        init();
    }
})();
