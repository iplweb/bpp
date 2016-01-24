if (window.bpp == undefined) window.bpp = {};

var queryDict = {};

location.search.substr(1).split("&").forEach(
    function (item) {
        queryDict[item.split("=")[0]] = item.split("=")[1]
    });
