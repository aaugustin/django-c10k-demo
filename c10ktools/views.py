from django.shortcuts import render

from c10ktools.http import websocket


def basic(request):
    return render(request, 'c10ktools/basic.html', {'request': request})


def echo(request):
    return render(request, 'c10ktools/echo.html')


@websocket
def echo_ws(ws):
    ws.write_message('Hello!')
    for i in range(3):
        message = yield from ws.read_message()
        ws.write_message('{}. {}'.format(i + 1, message))
    ws.write_message('Goodbye!')
