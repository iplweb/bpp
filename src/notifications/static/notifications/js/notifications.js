var bppNotifications = bppNotifications || {};

bppNotifications.init = function(channel, host, port, useSSL, messageCookieId, soundAlertPath){
    this.messageCookieId = messageCookieId;

    this.messageAlertSound = null;
    if (window.Audio && soundAlertPath)
        this.messageAlertSound = new window.Audio(soundAlertPath);

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

bppNotifications.goTo = function(url){
    window.location.href = url;
};

bppNotifications.addMessage = function(message){
    // Uzywane atrybuty z message:
    //  - cssClass,
    //  - closeURL,
    //  - closeText,
    //  - clickURL,
    //  - hideCloseOption,
    //  - text;

    if (message['text']) {
        $("#messagesPlaceholder").append(
            Mustache.render(
                $("#messageTemplate").html(),
                message)
        );

        if (bppNotifications.messageAlertSound)
            if (message['sound'] != false)
                bppNotifications.messageAlertSound.play();

    } else if (message['url']) {
        if (message['cookieId'] == bppNotifications.messageCookieId)
            bppNotifications.goTo(message['url']);
    }

};
