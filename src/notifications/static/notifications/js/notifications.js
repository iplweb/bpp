var bppNotifications = bppNotifications || {};

bppNotifications.init = function(channel, host, port, useSSL, soundAlertPath){
    this.messageAlertSound = null;
    if (Audio && soundAlertPath)
        this.messageAlertSound = new Audio(soundAlertPath);

    if (host == null)
        host = window.location.hostname;

    if (port == null || port === '')
        port = window.location.port;

    if (useSSL == null) {
        useSSL = false;

        if (window.location.protocol === 'https:')
            useSSL = true;
    }

    this.pushstream = new PushStream({
        host: host,
        port: port,
        modes: "websocket",
        useSSL: useSSL
    });

    this.pushstream.onmessage = this.addMessage;
    this.pushstream.addChannel(channel);
    this.pushstream.connect();

};

bppNotifications.addMessage = function(message){
    // Uzywane atrybuty z message:
    //  - cssClass,
    //  - closeURL,
    //  - closeText,
    //  - clickURL,
    //  - hideCloseOption,
    //  - text;

    $("#messagesPlaceholder").append(
        Mustache.render(
        $("#messageTemplate").html(),
        message)
    );

    if (bppNotifications.messageAlertSound)
        bppNotifications.messageAlertSound.play();
};
