var bppNotifications = bppNotifications || {};

bppNotifications.pushstream = new PushStream({
    host: window.location.hostname,
    port: window.location.port,
    modes: "websocket",
    useSSL: true
});

bppNotifications.init = function(){
    this.pushstream.onmessage = messageReceived;
    this.pushstream.addChannel("django_bpp-{{ request.user.username }}");
    this.pushstream.connect();
};

bppNotifications.defaultValue = function(value, defaultValue) {
    if (typeof(value)==='undefined')
        return defaultValue;
    return value;
};


bppNotifications.addMessage = function(message){
    // U¿ywane atrybuty z message:
    //  - cssClass,
    //  - closeURL,
    //  - closeText,
    //  - clickURL,
    //  - hideCloseOption,
    //  - text;

    $("#messagesPlaceholder").append(
        Mustache.render(
        $("#messageTemplate").text(),
        message)
    );
};
