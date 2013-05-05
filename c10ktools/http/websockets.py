import functools

import tulip
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
            stream = environ['tulip.reader']
            transport = environ['tulip.writer']
            assert isinstance(stream, tulip.parsers.StreamBuffer)
            assert isinstance(transport, tulip.Transport)
            # All Tulip transports appear to have a _protocol attribute...
            http_proto = transport._protocol
            # ... I still feel guilty about this.
            assert http_proto.stream is stream
            assert http_proto.transport is transport
        except (AssertionError, KeyError) as e:
            return HttpResponseServerError("Unsupported WSGI server: %s." % e)

        @tulip.coroutine
        def run_ws_handler(ws):
            yield from handler(ws, *args, **kwargs)
            yield from ws.close()

        def switch_protocols():
            ws_proto = websockets.WebSocketCommonProtocol()
            # Disconnect transport from http_proto and connect it to ws_proto
            http_proto.transport = DummyTransport()
            transport._protocol = ws_proto
            ws_proto.connection_made(transport)
            # Run the WebSocket handler in a Tulip Task
            tulip.Task(run_ws_handler(ws_proto))

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
            self.close = switch_protocols


class DummyTransport(tulip.Transport):
    """Transport that doesn't do anything, but can be closed silently."""

    def can_write_eof(self):
        return False

    def close(self):
        pass
