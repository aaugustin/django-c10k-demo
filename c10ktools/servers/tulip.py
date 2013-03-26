import http.client
import inspect
import io

import tulip
import tulip.http

from django.core.servers import basehttp


class TulipHandler(basehttp.ServerHandler):
    """
    WSGI handler compatible with Tulip.

    Some methods are copied and transformed into coroutines.

    The write methods are adjusted to the tulip.http.Response API.
    """

    @tulip.coroutine
    def run(self, application):
        # Identical to parent, except for the 'yield from'.
        try:
            self.setup_environ()
            self.result = application(self.environ, self.start_response)
            yield from self.finish_response()
        except:
            try:
                self.handle_error()
            except:
                self.close()
                raise

    @tulip.coroutine
    def finish_response(self):
        # Identical to parent, except for the 'yield from'.
        if not self.result_is_file() or not self.sendfile():
            for data in self.result:
                self.write(data)
            self.finish_content()
        yield from self.close()

    @tulip.coroutine
    def close(self):
        # Identical to parent, except for the 'yield from'.
        try:
            if hasattr(self.result, 'close'):
                close = self.result.close()
                if (inspect.isgenerator(close)
                        or isinstance(close, tulip.Future)):
                    yield from close
        finally:
            self.result = self.headers = self.status = self.environ = None
            self.bytes_sent = 0
            self.headers_sent = False

        # Also drop the parent connection.
        self.request_handler.response.write_eof()

    def start_response(self, status, headers, exc_info=None):
        """'start_response()' callable as specified by PEP 3333"""

        if exc_info:
            try:
                if self.headers_sent:
                    # Re-raise original exception if headers sent
                    raise exc_info[0](exc_info[1]).with_traceback(exc_info[2])
            finally:
                exc_info = None        # avoid dangling circular ref
        elif self.headers is not None:
            raise AssertionError("Headers already set!")

        self.status = status
        self.headers = self.headers_class(headers)

        # Override values set by tulip.http.Response.__init__
        r = self.request_handler.response
        r.status = int(status[:3])
        r.status_line = r.status_line[:9] + status + '\r\n'

        return self.write

    def send_headers(self):
        self.cleanup_headers()
        self.headers_sent = True
        r = self.request_handler.response
        r.add_headers(*self.headers.items())
        r.send_headers()

    def _write(self, data):
        self.request_handler.response.write(data)

    def _flush(self):
        pass


class WSGIRequestHandler(
        tulip.http.ServerHttpProtocol, basehttp.WSGIRequestHandler):
    """
    Tulip protocol and WSGI request handler.

    These classes have similar roles and they have many overlapping features.
    Luckily, there isn't any method name conflict.

    This class is primarily a ServerHttpProtocol, but it defines enough
    attributes to masquerade as a WSGIRequestHandler for the WSGI handler.
    """

    def __init__(self, server, *args, **kwargs):
        # There isn't a concept of request and the client address isn't known.
        basehttp.WSGIRequestHandler.__init__(self, self, None, server)
        tulip.http.ServerHttpProtocol.__init__(self, *args, **kwargs)

    # Disable socket-related methods called by WSGIRequestHandler.__init__().

    def setup(self):
        pass

    def handle(self):
        pass

    def finish(self):
        pass

    # This is the documented extension point for ServerHttpProtocol.

    @tulip.coroutine
    def handle_request(self, info, message):
        # Mix of ServerHttpProtocol.handle() and WSGIRequestHandler.handle().

        # Add the client address that wasn't known in __init__.
        self.client_address = self.transport.get_extra_info('addr')

        # Create the same attributes as WSGIRequestHandler.parse_request().
        self.command = info.method
        self.path = info.uri
        self.request_version = 'HTTP/{0}.{1}'.format(*info.version)
        self.requestline = '{0} {1} HTTP/{2[0]}.{2[1]}'.format(*info)
        self.headers = http.client.HTTPMessage()
        for header in message.headers:
            self.headers.set_raw(*header)

        self.response = tulip.http.Response(self.transport, 200,
                http_version=info.version, close=message.should_close)

        # Read the entire request body. This is gross, but it makes it easier
        # to upgrade to WebSocket later on. See the hack below.
        try:
            content_length = int(self.headers['CONTENT_LENGTH'])
        except (KeyError, TypeError, ValueError):
            payload = yield from message.payload.read()
        else:
            payload = yield from message.payload.readexactly(content_length)

        # Delegate to the Tulip-compatible WSGI handler.
        stdin = io.BytesIO(payload)
        stdout = self.response
        stderr = self.get_stderr()
        environ = self.get_environ()
        # Hack to implement the WebSocket protocol within WSGI.
        # Redirect the data received on the socket to a new stream.
        environ['tulip.reader'] = self.stream = tulip.StreamReader()
        environ['tulip.writer'] = self.response.transport
        handler = TulipHandler(stdin, stdout, stderr, environ)
        handler.request_handler = self
        yield from handler.run(self.server.get_app())

        self.close()


class WSGIServer:
    """
    Tulip protocol factory and WSGI server.

    Connections are handled by the Tulip event loop. Unlike the servers in the
    standard library, no connection management is necessary.

    This class defines a few attributes to quack like a WSGIServer.
    """

    def __init__(self, host, port, handler_class):
        self.server_name = host             # Avoid socket.getfqdn, it's slow.
        self.server_port = port
        self.handler_class = handler_class  # Nicer than RequestHandlerClass.
        self.setup_environ()

    # Tulip calls the protocol factory with no arguments.

    def __call__(self):
        return self.handler_class(self)

    # The following methods are taken from wsgiref.simple_server.WSGIServer.

    def setup_environ(self):
        # Set up base environment
        env = self.base_environ = {}
        env['SERVER_NAME'] = self.server_name
        env['GATEWAY_INTERFACE'] = 'CGI/1.1'
        env['SERVER_PORT'] = str(self.server_port)
        env['REMOTE_HOST'] = ''
        env['CONTENT_LENGTH'] = ''
        env['SCRIPT_NAME'] = ''

    def get_app(self):
        return self.application

    def set_app(self, application):
        self.application = application


def run(addr, port, wsgi_handler, ipv6=False, threading=False):
    """
    Alternate version of django.core.servers.basehttp.run running on Tulip.
    """
    assert not ipv6, "IPv6 isn't supported"
    assert threading, "threading is irrelevant"
    httpd = WSGIServer(addr, port, WSGIRequestHandler)
    httpd.set_app(wsgi_handler)
    # The auto-reloader runs in the main thread and starts the server in
    # another thread. Since the event loop in thread-local we must create one.
    loop = tulip.get_event_loop()
    if loop is None:
        loop = tulip.new_event_loop()
        tulip.set_event_loop(loop)
    loop.start_serving(httpd, addr, port)
    loop.run_forever()
