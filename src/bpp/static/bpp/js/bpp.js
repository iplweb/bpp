// BPP namespace and utilities
// Using window.* for IIFE bundle compatibility
if (window.bpp == undefined) window.bpp = {};

window.queryDict = {};

location.search.substr(1).split("&").forEach(
    function (item) {
        window.queryDict[item.split("=")[0]] = item.split("=")[1]
    });

// Local reference for convenience within this module
var queryDict = window.queryDict;

window.qs = function(key) {
    key = key.replace(/[*+?^$.\[\]{}()|\\\/]/g, "\\$&"); // escape RegEx meta chars
    var match = location.search.match(new RegExp("[?&]"+key+"=([^&]+)(&|$)"));
    return match && decodeURIComponent(match[1].replace(/\+/g, " "));
};

// Local reference for convenience
var qs = window.qs;
