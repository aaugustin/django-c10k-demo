from django.shortcuts import render

from c10ktools.http import websocket


def basic(request):
    return render(request, 'c10ktools/basic.html', {'request': request})


def echo(request):
    return render(request, 'c10ktools/echo.html')


@websocket
def echo_ws(ws):
    ws.send('Hello!')
    for i in range(3):
        message = yield from ws.recv()
        ws.send('{}. {}'.format(i + 1, message))
    ws.send('Goodbye!')
