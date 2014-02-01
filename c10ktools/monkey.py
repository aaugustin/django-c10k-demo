import asyncio

from aiohttp.wsgi import WSGIServerHttpProtocol


def run(addr, port, wsgi_handler, loop=None, stop=None, **options):
    """
    Alternate version of django.core.servers.basehttp.run running on asyncio.
    """
    if loop is None:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    # The code that reads environ['wsgi.input'] is deep inside Django and hard
    # to make asynchronous. Pre-loading the payload is the simplest option.
    protocol_factory = lambda: WSGIServerHttpProtocol(
            wsgi_handler, readpayload=True)
    server = loop.run_until_complete(
            loop.create_server(protocol_factory, addr, port))
    try:
        if stop is None:
            loop.run_forever()
        else:
            loop.run_until_complete(stop)
    finally:
        server.close()
        loop.run_until_complete(server.wait_closed())


def patch():
    from django.core.management.commands import runserver
    runserver.run = run
