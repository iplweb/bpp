// Explicitly use window to ensure global scope even in IIFE bundles
window.bppNotifications = window.bppNotifications || {};

bppNotifications.init = function (extraChannels) {
    // Initialize Tone.js synth for notifications
    this.synth = null;
    this.toneInitialized = false;

    // Setup one-time click listener to initialize Tone.js on user interaction
    var initToneOnClick = function() {
        if (!bppNotifications.toneInitialized) {
            Tone.start().then(function() {
                bppNotifications.synth = new Tone.PolySynth(Tone.Synth, {
                    oscillator: { type: "sine" },
                    envelope: { attack: 0.01, decay: 0.3, sustain: 0.1, release: 0.8 }
                }).toDestination();
                bppNotifications.synth.volume.value = -14; // 50% quieter volume
                bppNotifications.toneInitialized = true;
                console.info('Audio context initialized');
            }).catch(function(err) {
                console.warn('Could not initialize audio context:', err);
            });
        }
        // Remove the listener after first click
        document.removeEventListener('click', initToneOnClick);
        document.removeEventListener('keydown', initToneOnClick);
    };

    // Add listeners for user interaction
    document.addEventListener('click', initToneOnClick);
    document.addEventListener('keydown', initToneOnClick);

    var url = (window.location.protocol == "https:" ? "wss:" : "ws:");

    url += "//" + window.location.host + '/asgi/notifications/';
    if (extraChannels)
        url += '?extraChannels=' + encodeURIComponent(extraChannels);

    this.chatSocket = new WebSocket(url);

    this.chatSocket.onmessage = this.onmessage;

    this.chatSocket.onopen = function (e) {
        console.info('Chat available');
    };

    this.chatSocket.onclose = function (e) {
        console.info('Chat socket closed');
    };

    this.chatSocket.onerror = function (e) {
        console.log('error');
    };

    window.addEventListener("unload", function () {
        if (bppNotifications.chatSocket.readyState == WebSocket.OPEN)
            bppNotifications.chatSocket.close();
    });
};

bppNotifications.goTo = function (url) {
    window.location.href = url;
};

bppNotifications.onmessage = function (event) {
    // console.log(event);
    var message = JSON.parse(event.data);

    if (message['id']) {
        bppNotifications.chatSocket.send(
            JSON.stringify({
                "id": message["id"],
                "type": "ack_message",
                "channel_name": event['channel_name']
            }));
    }
    ;


    bppNotifications.addMessage(message);
}

bppNotifications.playChime = function() {
    // Only play if Tone.js is initialized
    if (!this.toneInitialized) {
        // Try to initialize on notification if user hasn't clicked yet
        if (typeof Tone !== 'undefined') {
            Tone.start().then(function() {
                bppNotifications.synth = new Tone.PolySynth(Tone.Synth, {
                    oscillator: { type: "sine" },
                    envelope: { attack: 0.01, decay: 0.3, sustain: 0.1, release: 0.8 }
                }).toDestination();
                bppNotifications.synth.volume.value = -14; // 50% quieter volume
                bppNotifications.toneInitialized = true;

                // Play the chime after initialization
                var now = Tone.now();
                bppNotifications.synth.triggerAttackRelease("C5", 0.1, now);
                bppNotifications.synth.triggerAttackRelease("E5", 0.1, now + 0.05);
                bppNotifications.synth.triggerAttackRelease("G5", 0.1, now + 0.1);
                bppNotifications.synth.triggerAttackRelease("C6", 0.15, now + 0.15);
            }).catch(function(err) {
                // Silently fail if audio context can't be started
                console.debug('Audio context not available:', err);
            });
        }
        return;
    }

    // Play the chime sequence
    try {
        var now = Tone.now();
        this.synth.triggerAttackRelease("C5", 0.1, now);
        this.synth.triggerAttackRelease("E5", 0.1, now + 0.05);
        this.synth.triggerAttackRelease("G5", 0.1, now + 0.1);
        this.synth.triggerAttackRelease("C6", 0.15, now + 0.15);
    } catch(err) {
        console.debug('Could not play notification sound:', err);
    }
};

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

        if (message['sound'] != false)
            bppNotifications.playChime();

    } else if (message['url']) {
        bppNotifications.goTo(message['url']);
    } else if (message['progress']) {
        $("#notifications-progress").css("width", message['percent']);
    }

};
