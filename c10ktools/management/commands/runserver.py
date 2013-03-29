import tulip
import tulip.http


def run(addr, port, wsgi_handler, **options):
    """
    Alternate version of django.core.servers.basehttp.run running on Tulip.
    """
    loop = tulip.get_event_loop()
    if loop is None:
        # The auto-reloader runs in the main thread and starts the server
        # in another thread. Create an event loop for that thread.
        loop = tulip.new_event_loop()
        tulip.set_event_loop(loop)
    # The code that reads environ['wsgi.input'] is deep inside Django and hard
    # to make asynchronous. Pre-loading the payload is the simplest option.
    protocol_factory = lambda: tulip.http.WSGIServerHttpProtocol(
            wsgi_handler, readpayload=True)
    loop.start_serving(protocol_factory, addr, port)
    loop.run_forever()


# Monkey-patch runserver to run on top of Tulip.
from django.core.management.commands import runserver
runserver.run = run
del runserver


# Emulate runserver.
from django.core.management.commands.runserver import Command
