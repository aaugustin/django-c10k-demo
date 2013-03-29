import base64
import functools
import hashlib

import tulip

from django.http import HttpResponse, HttpResponseServerError

from c10ktools.websockets import WebSocketProtocol


def websocket(handler):
    """Decorator for WebSocket handlers."""

    @functools.wraps(handler)
    def wrapper(request, *args, **kwargs):
        environ = request.META
        try:
            assert environ['wsgi.async']
            stream = environ['tulip.reader']
            transport = environ['tulip.writer']
            assert isinstance(stream, tulip.http.HttpStreamReader)
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
            ws_proto = WebSocketProtocol()
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
        try:
            key = self.check_request(environ)
        except Exception:
            self.status_code = 400
            self.content = "Invalid WebSocket handshake.\n"
        else:
            self.create_headers(key)
            self.close = switch_protocols

    def check_request(self, environ):
        # Host and Origin checking isn't handled at this level.
        # RFC 6455 - 4.2.1. Reading the Client's Opening Handshake
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
        # RFC 6455 - 4.2.2. Sending the Server's Opening Handshake
        guid = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"
        sha1 = hashlib.sha1((key + guid).encode()).digest()
        self['Upgrade'] = 'WebSocket'
        self['Connection'] = 'Upgrade'
        self['Sec-WebSocket-Accept'] = base64.b64encode(sha1)


class DummyTransport(tulip.Transport):
    """Transport that doesn't do anything."""

    def can_write_eof(self):
        return False

    def close(self):
        pass
