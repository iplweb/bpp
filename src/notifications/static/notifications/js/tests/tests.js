QUnit.module( "notifications.js", {
  beforeEach: function() {
      $("#messagesPlaceholder").children().remove();
  },
  afterEach: function() {
    // clean up after each test
  }
});

QUnit.test( "addMessage", function( assert ) {

  assert.ok(
      document.getElementById("messagesPlaceholder") !== null,
      "DIV istnieje i ma children");

  bppNotifications.addMessage({
      'text':'aapud'
  });

  assert.equal(
      $("#messagesPlaceholder").children().length,
      1,
      "Komunikat zostal dolozony do DIVu");

});

QUnit.test( "addMessage + klasa css", function( assert ) {

  bppNotifications.addMessage({
      'text':'aapud',
      'cssClass': 'infoi'
  });

  assert.equal(
      $("#messagesPlaceholder").children().first().hasClass("infoi"),
      true,
      "Komunikat zostal dolozony do DIVu z odpowiednia klasa");

});

QUnit.test( "addMessage + clickURL", function( assert ) {

  bppNotifications.addMessage({
      'text':'aapud',
      'clickURL': 'onet.pl'
  });

  assert.equal(
      $("#messagesPlaceholder").find("a").first().attr("href"),
      "onet.pl",
      "Komunikat zostal dolozony do DIVu z odpowiednim linkiem");

});

QUnit.test( "addMessage + closeURL", function( assert ) {

  bppNotifications.addMessage({
      'text':'aapud',
      'closeURL': 'onet.pl'
  });

  assert.equal(
      $("#messagesPlaceholder").find("a").first().attr("href"),
      "onet.pl",
      "Komunikat zostal dolozony do DIVu z odpowiednim linkiem zamkni�cia");

});


QUnit.test( "addMessage + hideCloseOption=True", function( assert ) {

  bppNotifications.addMessage({
      'text':'aapud',
      'hideCloseOption': true,
  });

  assert.deepEqual(
      $("#messagesPlaceholder").find("a").length,
      0,
      "Nie by�o iksa do zamykania");

});

QUnit.test( "addMessage + hideCloseOption default (not specified)", function( assert ) {

  bppNotifications.addMessage({
      'text':'aapud',
  });

  assert.deepEqual(
      $("#messagesPlaceholder").find("a").length,
      1,
      "Byl iks do zamykania");

});

QUnit.test( "addMessage closeURL", function( assert ) {

  bppNotifications.addMessage({
      'text':'aapud',
      'closeURL': 'onet.pl',
  });

  assert.deepEqual(
      $("#messagesPlaceholder").find("a").last().attr("href"),
      'onet.pl',
      "Atrybut do zamykania jest OK");

});

QUnit.test( "bppNotifications.init", function( assert ) {
    bppNotifications.init("foo", "bar", "baz");
    assert.ok(bppNotifications.chatSocket);
});

QUnit.test( "bppNotifications.goTo", function( assert ) {
    var goTo = sinon.stub(bppNotifications, "goTo");
    bppNotifications.messageCookieId = "123"
    bppNotifications.addMessage({'url': 'www.onet.pl', 'cookieId': "123"});
    assert.ok(goTo.calledOnce);
    goTo.restore();

});