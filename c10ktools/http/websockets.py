import asyncio
import functools

import websockets
from websockets import handshake

from django.http import HttpResponse, HttpResponseServerError


def websocket(handler):
    """Decorator for WebSocket handlers."""

    @functools.wraps(handler)
    def wrapper(request, *args, **kwargs):
        environ = request.META
        try:
            assert environ['wsgi.async']
            reader = environ['async.reader']
            writer = environ['async.writer']

            # When the following assertions fail, insert an `import pdb;
            # pdb.set_trace()` here and look for internal changes in aiohttp.
            assert isinstance(reader, asyncio.streams.StreamReader)
            assert isinstance(writer, asyncio.streams.StreamWriter)

            # Extract the actual protocol and transport.
            http_protocol = writer._protocol
            transport = http_protocol.transport

            assert http_protocol.reader is reader
            assert http_protocol.writer is writer
            assert reader._transport is transport
            assert writer._transport is transport
            assert transport._protocol is http_protocol

        except (AssertionError, KeyError) as e:             # pragma: no cover
            # When the handshake fails (500), insert a `raise` here.
            return HttpResponseServerError("Unsupported WSGI server: %s." % e)

        @asyncio.coroutine
        def run_ws_handler(ws):
            yield from handler(ws, *args, **kwargs)
            yield from ws.close()

        def switch_protocols():
            # Switch transport from http_protocol to ws_protocol (YOLO).
            ws_protocol = websockets.WebSocketCommonProtocol()
            transport._protocol = ws_protocol
            ws_protocol.connection_made(transport)

            # Ensure aiohttp doesn't interfere.
            http_protocol.transport = None

            # Fire'n'forget the WebSocket handler.
            asyncio.async(run_ws_handler(ws_protocol))

        return WebSocketResponse(environ, switch_protocols)

    return wrapper


class WebSocketResponse(HttpResponse):
    """Upgrade from a WSGI connection with the WebSocket handshake."""

    status_code = 101

    def __init__(self, environ, switch_protocols):
        super().__init__()

        http_1_1 = environ['SERVER_PROTOCOL'] == 'HTTP/1.1'
        get_header = lambda k: environ['HTTP_' + k.upper().replace('-', '_')]
        key = handshake.check_request(get_header)

        if not http_1_1 or key is None:
            self.status_code = 400
            self.content = "Invalid WebSocket handshake.\n"
        else:
            self._headers = {}                  # Reset headers (private API!)
            set_header = self.__setitem__
            handshake.build_response(set_header, key)

            # Here be dragons.
            self.close = switch_protocols
