if (window.bpp == undefined) window.bpp = {};

var queryDict = {};

location.search.substr(1).split("&").forEach(
    function (item) {
        queryDict[item.split("=")[0]] = item.split("=")[1]
    });


function qs(key) {
    key = key.replace(/[*+?^$.\[\]{}()|\\\/]/g, "\\$&"); // escape RegEx meta chars
    var match = location.search.match(new RegExp("[?&]"+key+"=([^&]+)(&|$)"));
    return match && decodeURIComponent(match[1].replace(/\+/g, " "));
}