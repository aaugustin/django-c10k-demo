window.onload = function () {

    function show_message(message) {
        var messages = document.getElementById("messages");
        var item = document.createElement("li");
        var content = document.createTextNode(message);
        item.appendChild(content);
        messages.appendChild(item);
    }

    var ws = new WebSocket("ws://" + window.location.host + window.location.pathname + "ws/");
    ws.onopen = function(e) {
        show_message("Connection open.");
    };
    ws.onmessage = function(e) {
        show_message(e.data);
    };
    ws.onclose = function(e) {
        show_message("Connection closed.");
    };

    var text = document.getElementById("text");
    document.getElementById("form").addEventListener(
        'submit', function (evt) {
            ws.send(text.value);
            text.value = "";
            evt.preventDefault();
        }, false);
    text.focus();
};
