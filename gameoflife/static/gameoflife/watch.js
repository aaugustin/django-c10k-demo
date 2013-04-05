window.onload = function () {
    var ws = new WebSocket("ws://" + window.location.host + window.location.pathname + "watcher/");
    ws.onmessage = function(e) {
        var bits = e.data.split(' '),
            step = parseInt(bits[0], 10),
            square = document.getElementById(bits[1] + '-' + bits[2]),
            state = parseInt(bits[3], 2),
            hue = step * 20 % 256,
            lum = state ? 25 : 95,
            color = 'hsl(' + hue + ', 100%, ' + lum + '%)';
        square.style.backgroundColor = color;
    };
};
