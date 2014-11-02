README
======

django-c10k-demo is an experimental playground for high concurrency in Django
with WebSockets.

It was originally written to handle 10 000 concurrent real-time connections to
Django, hence the name.

It combines several interesting concepts: the `C10k problem`_, the `WebSocket
protocol`_, the `Django web framework`_, and Python's built-in `asynchronous
IO support`_.

.. _C10k problem: http://en.wikipedia.org/wiki/C10k_problem
.. _WebSocket protocol: http://tools.ietf.org/html/rfc6455
.. _Django web framework: https://www.djangoproject.com/
.. _asynchronous IO support: http://www.python.org/dev/peps/pep-3156/

Running the code
----------------

Prerequisites
.............

* Install `Python`_ 3.4 or 3.3.
* Install aiohttp_, Django_, and websockets_, most likely with
  ``virtualenv`` and ``pip``. If you're using Python 3.3, install asyncio_.
* Clone `this repository`_.
* Configure your OS to allow lots of file descriptors.
  On OS X: ``sudo sysctl -w kern.maxfiles=40960 kern.maxfilesperproc=20480``
* Open two shells and bump their file descriptor limit: ``ulimit -n 10240``

.. _Python: http://www.python.org/getit/
.. _aiohttp: https://pypi.python.org/pypi/aiohttp
.. _Django: https://www.djangoproject.com/download/
.. _websockets: https://pypi.python.org/pypi/websockets
.. _asyncio: https://pypi.python.org/pypi/asyncio
.. _this repository: https://github.com/aaugustin/django-c10k-demo

Game of Life demo
.................

This demo is a distributed `Game of Life`_. One client manages the life of one
cell. Clients connect to a server through a WebSocket and register to receive
updates from their neighbors. The server coordinates the startup sequence and
relays messages between clients, but it doesn't know anything about the rules
of the game; all the logic is handled by the clients!

* In the first shell, start the server: ``python manage.py runserver``
* In the second shell, start the workers: ``python manage.py gameoflife``
* In a browser, go to http://localhost:8000/

``gameoflife`` shouldn't display anything. ``runserver`` should display an
increasing number of workers connected and then an increasing number of
workers subscribed.

The page in the browser registers to receive updates from all clients, and
updates in real time as soon as the workers start running. Alive cells are
dark, dead cells are light. Their hue shifts slightly at each step to show how
the grid updates.

.. image:: https://raw.github.com/aaugustin/django-c10k-demo/master/gameoflife/screenshot.png
   :width: 917
   :height: 938

``gameoflife`` accepts a number of options to configure the game:

* The size of the grid is 32. You can change it with ``-s``.
* The initial state is random with one cell alive out of four on average.
  You can load a pattern from a file with ``-p``. See ``gameoflife/patterns/``
  for some common examples.
* When a pattern is provided, it's centered on the grid. You can disable this
  behavior with ``-C``.
* The grid is cyclic: the left side is connected to the right side and the top
  to the bottom. You can disable this behavior with ``-W``, for example to
  test guns.
* The workers run forever, unless you specify a number of steps with ``-n``.
* The workers make at most one step per second — this only matters on small
  grids since the game won't run that fast on larger grids. You can adjust the
  speed limit with ``-l``.

.. _Game of Life: http://en.wikipedia.org/wiki/Conway%27s_Game_of_Life

C10k demo
.........

This is the original demo in this project. It handles 10 000 concurrent real-
time connections to Django.

* In the first shell, start the server: ``python manage.py runserver``
* In the second shell, start the clients: ``python manage.py testecho``

``runserver`` shouldn't display anything and ``testecho`` should show the
number of connections, peaking at ``10000 clients are connected!``.

The connections are established over a period of two minutes. Once connected,
each client repeats the following sequence three times: wait one minute, send
a message, and read the reply of the server. Clients also receive a welcome
and a goodbye message from the server. The entire demo takes five minutes if
your system is fast enough.

If you don't reach 10 000 connections, it means that some clients finish their
sequence and disconnect before all the clients are connected, because your
system is too slow. If you see exceptions, it means that your OS isn't tuned
correctly for such benchmarks. Decreasing ``CLIENTS`` or increasing ``DELAY``
in ``testecho`` may help in both cases.

Under the hood
--------------

Here are the underlying components in no particular order, with some hints on
their quality and reusability.

WebSocket API for Django
........................

Here's an example of a WebSocket echo server in Django::

    from c10ktools.http import websocket

    @websocket
    def handler(ws):
        yield from ws.send((yield from ws.recv()))

WebSocket handlers are hooked in the URLconf like regular HTTP views.
Arguments can be captured in the URLconf and passed to the handlers.

This doesn't allow sharing an URL between a regular HTTP view and a WebSocket
handler, but I'm happy with this limitation as it's probably a good practice
to keep them separate anyway.

Inside a WebSocket handler, you can use ``yield from ws.recv()`` and ``yield
from ws.send()`` freely. You can also call ``yield from ws.send()`` outside
the handler.

The ``@websocket`` decorator should only be applied to coroutines. It takes
care of closing the WebSocket connection when the handler terminates.

Hook for the upgrade to WebSocket
.................................

The API described above requires the upgrade from HTTP to WebSocket to happen
after Django's URL dispatcher has routed the request to a view. As a
consequence, the upgrade must be performed within the framework of WSGI.

PEP 3333 predates real-time on the web and PEP 3156 doesn't propose to update
it. This point might be addressed by a future version of the standard (PEP
3356 anyone?) In the meantime our only choice is to bastardize WSGI, steering
away from compliance — `sorry`_ `Graham`_.

The WebSocket opening handshake is completed by sending a HTTP response. This
is achieved with WSGI, but it isn't compliant because the response includes
hop-by-hop headers, ``Upgrade`` and ``Connection``.

The switch to the WebSocket protocol is performed in ``close()``. In asyncio
terms, the transport is disconnected for the HTTP protocol and reconnected to
the WebSocket protocol. Then a task is started to run the WebSocket handler
and close the connection when it terminates. This design is very debatable:

- This isn't an intended use case for the ``close()`` method.
- The protocol transplant relies on non-standard variables in ``environ``.
- It abuses private APIs of asyncio and of aiohttp which aren't quite stable.

.. _sorry: https://twitter.com/GrahamDumpleton/status/316315348049752064
.. _Graham: https://twitter.com/GrahamDumpleton/status/316726248837611521

Asynchronous development server
...............................

django-c10k-demo takes advantage of aiohttp's WSGI support to adapt Django's
built-in developement server to run on top of asyncio.

This component can be used independently by adding the ``'c10ktools'``
application to ``INSTALLED_APPS``. It monkey-patches the ``django-admin.py
runserver`` command to run on top of the asyncio event loop.

Asynchronous production server
..............................

django-c10k-demo works with aiohttp's gunicorn worker class::

  $ gunicorn -k aiohttp.worker.AsyncGunicornWorker c10kdemo.wsgi

Of course, this stack is experimental. It's unlikely to ever become
"production-ready". Use it at your own risk!
