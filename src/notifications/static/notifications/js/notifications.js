var bppNotifications = bppNotifications || {};

bppNotifications.init = function (soundAlertPath) {
    this.messageAlertSound = null;
    if (window.Audio && soundAlertPath)
        this.messageAlertSound = new window.Audio(soundAlertPath);

    this.chatSocket = new WebSocket(
        'ws://'
        + window.location.host
        + '/asgi/notifications/'
    );

    this.chatSocket.onmessage = this.onmessage;

    this.chatSocket.onclose = function (e) {
        console.error('Chat socket closed unexpectedly');
    };

    this.chatSocket.onerror = function (e) {
        console.log('error');
    };

};

bppNotifications.goTo = function (url) {
    window.location.href = url;
};

bppNotifications.onmessage = function(event){
    var message =  JSON.parse(event.data);
    bppNotifications.addMessage(message);
}

bppNotifications.addMessage = function (message) {
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
        bppNotifications.goTo(message['url']);
    }

};
