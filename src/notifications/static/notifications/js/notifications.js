var bppNotifications = bppNotifications || {};

bppNotifications.init = function (soundAlertPath, extraChannels) {
   this.messageAlertSound = null;
    if (window.Audio && soundAlertPath)
        this.messageAlertSound = new window.Audio(soundAlertPath);

    var url = (window.location.protocol == "https:" ? "wss:" : "ws:");

    url += "//" + window.location.host  + '/asgi/notifications/';
    if (extraChannels)
        url += '?extraChannels=' + encodeURIComponent(extraChannels);

    this.chatSocket = new WebSocket(url);

    this.chatSocket.onmessage = this.onmessage;

    this.chatSocket.onopen = function(e){
      console.info('Chat available');
    };

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
    console.log(event);
    var message =  JSON.parse(event.data);

    if (message['id']) {
        bppNotifications.chatSocket.send(
            JSON.stringify({
                "id": message["id"],
                "type": "ack_message",
                "channel_name": event['channel_name']
            }));
    };


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
    } else if (message['progress']) {
        $("#notifications-progress").css("width", message['percent']);
    }

};
