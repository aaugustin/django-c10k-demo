import base64
import functools
import hashlib

import tulip

from django.http import HttpResponse, HttpResponseServerError

from c10ktools.websockets import WebSocket


def websocket(hdlr):
    """Decorator for websocket handlers."""
    hdlr = tulip.coroutine(hdlr)        # Mark the handler as a coroutine.

    @functools.wraps(hdlr)
    def wrapper(request, *args, **kwargs):
        environ = request.META
        try:
            reader = environ['tulip.reader']
            writer = environ['tulip.writer']
        except KeyError:
            return HttpResponseServerError("Unsupported WSGI server.")
        return WebSocketResponse(environ, reader, writer, hdlr, args, kwargs)

    return wrapper


class WebSocketResponse(HttpResponse):
    """Upgrade from a WSGI connection with the WebSocket handshake."""

    status_code = 101

    def __init__(self, environ, reader, writer, hdlr, hdlr_args, hdlr_kwargs):
        super().__init__()
        try:
            key = self.check_request(environ)
        except Exception:
            self.status_code = 400
            self.content = "Invalid WebSocket handshake."
        else:
            self.create_headers(key)

        self.ws = WebSocket(reader, writer)
        self.ws_handler = hdlr(self.ws, *hdlr_args, **hdlr_kwargs)

    def check_request(self, environ):
        # Host and Origin checking isn't handled at this level.
        # RFC6455 - 4.2.1. Reading the Client's Opening Handshake
        assert environ['SERVER_PROTOCOL'] == 'HTTP/1.1'
        assert environ['HTTP_HOST']     # the server's authority isn't known
        assert environ['HTTP_UPGRADE'].lower() == 'websocket'
        assert any(token.strip() == 'upgrade'
                for token in environ['HTTP_CONNECTION'].lower().split(','))
        assert len(base64.b64decode(environ['HTTP_SEC_WEBSOCKET_KEY'])) == 16
        assert environ['HTTP_SEC_WEBSOCKET_VERSION'] == '13'
        return environ['HTTP_SEC_WEBSOCKET_KEY']

    def create_headers(self, key):
        # Reset headers (private API!)
        self._headers = {}
        # RFC6455 - 4.2.2. Sending the Server's Opening Handshake
        guid = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"
        sha1 = hashlib.sha1((key + guid).encode()).digest()
        self['Upgrade'] = 'WebSocket'
        self['Connection'] = 'Upgrade'
        self['Sec-WebSocket-Accept'] = base64.b64encode(sha1)

    @tulip.coroutine
    def close(self):
        # This is where the magic happens.
        yield from self.ws_handler
        self.ws.close()
        super().close()

