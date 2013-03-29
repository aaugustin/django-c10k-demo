import base64
import collections
import hashlib
import random
import urllib.parse

import tulip
import tulip.http

from c10ktools.websockets import WebSocket


@tulip.coroutine
def connect_websocket(url):
    url = urllib.parse.urlparse(url)
    assert url.scheme == 'ws'
    assert url.params == url.query == url.fragment == ''

    rand = bytes(random.getrandbits(8) for _ in range(16))
    key = base64.b64encode(rand).decode()
    guid = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"
    sha1 = hashlib.sha1((key + guid).encode()).digest()
    accept = base64.b64encode(sha1).decode()

    host = url.netloc
    path = url.path
    headers = collections.OrderedDict((
        ('Host', host),
        ('Upgrade',  'WebSocket'),
        ('Connection', 'Upgrade'),
        ('Sec-WebSocket-Key', key),
        ('Sec-WebSocket-Version', '13'),
        ('Content-Length', '0',)
    ))

    client = WebSocketClientProtocol(host=host, path=path, headers=headers)
    status, headers, stream = yield from client.connect()

    assert status.startswith('101 ')
    assert headers['Upgrade'].lower() == 'websocket'
    assert any(token.strip() == 'upgrade'
            for token in headers['Connection'].lower().split(','))
    assert headers['Sec-WebSocket-Accept'] == accept
    assert 'Sec-WebSocket-Extensions' not in headers
    assert 'Sec-WebSocket-Protocol' not in headers

    return WebSocket(client.stream, client.transport, is_client=True)


class WebSocketClientProtocol(tulip.http.HttpClientProtocol):

    # Prevent Tulip from closing the connection after the request. make_body
    # might be used for this, but it triggers an exception before it's called:
    # AttributeError: 'Request' object has no attribute 'eof'

    def connection_made(self, transport):
        self.transport = transport
        self.stream = tulip.http.HttpStreamReader()

        self.request = tulip.http.Request(
            transport, self.method, self.path, self.version)

        self.request.add_headers(*self.headers.items())
        self.request.send_headers()
