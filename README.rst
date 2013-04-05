README
======

django-c10k-demo is an experimental playground for high concurrency in Django
with WebSockets.

It was originally written to handle 10 000 concurrent real-time connections to
Django, hence the name.

It combines several interesting concepts: the `C10k problem`_, the `WebSocket
protocol`_, the `Django web framework`_, and Python's upcoming `asynchronous
IO support`_.

.. _C10k problem: http://en.wikipedia.org/wiki/C10k_problem
.. _WebSocket protocol: http://tools.ietf.org/html/rfc6455
.. _Django web framework: https://www.djangoproject.com/
.. _asynchronous IO support: http://www.python.org/dev/peps/pep-3156/

Running the code
----------------

Prerequisites
.............

* Install `Python 3.3`_.
* Clone the repositories for `Tulip`_, `Django`_  `websockets`_ and add them
  to your ``PYTHONPATH``.
* Clone `this repository`_.
* Configure your OS to allow lots of file descriptors.
  On OS X: ``sudo sysctl -w kern.maxfiles=40960 kern.maxfilesperproc=20480``
* Open two shells and bump their file descriptor limit: ``ulimit -n 10240``

.. _Python 3.3: http://www.python.org/getit/
.. _Tulip: http://code.google.com/p/tulip/
.. _Django: https://github.com/django/django
.. _websockets: https://github.com/aaugustin/websockets
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
increasing number of workers connected, and then and increasing number of
workers subscribed.

The page in the browser registers to receive updates from all clients, and
updates in real time as soon as the workers start running. Alive cells are
dark, dead cells are light. Their hue shifts slightly at each step to show how
the grid updates.

The grid is cyclic: the left side is connected to the right side, and the top
to the bottom. The initial state is random with one cell alive out of four on
average.

If you encounter errors, you can change ``SIZE`` in ``gameoflife.models`` to
run this demo on a smaller grid.

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
        ws.send((yield from ws.recv()))

WebSocket handlers are hooked in the URLconf like regular HTTP views.
Arguments can be captured in the URLconf and passed to the handlers.

This doesn't allow sharing an URL between a regular HTTP view and a WebSocket
handler, but I'm happy with this limitation as it's probably a good practice
to keep them separate anyway.

Inside a WebSocket handler, you can use ``yield from ws.recv()`` and
``ws.send()`` freely. You can also call ``ws.send()`` from outside the
handler.

The ``@websocket`` decorator should only be applied to coroutines. It takes
care of closing the WebSocket when the handler terminates.

Hook for the upgrade to WebSocket
.................................

The API described above requires the upgrade from HTTP to WebSocket to happen
after Django's URL dispatcher has routed the request to a view. As a
consequence, the upgrade must be performed within the framework of WSGI.

PEP 3333 predates real-time on the web and PEP 3156 doesn't propose to update
it. Hopefully his point will be addressed by a future version of the standard
(PEP 3356 anyone?). In the meantime our only choice is to bastardize WSGI,
steering away from compliance — `sorry`_ `Graham`_.

The WebSocket opening handshake is completed by sending a HTTP response. This
is achieved with WSGI, but it isn't compliant because the response includes
hop-by-hop headers, ``Upgrade`` and ``Connection``.

The switch to the WebSocket protocol is performed in ``close()``. In Tulip
terms, the transport is disconnected for the HTTP protocol and reconnected to
the WebSocket protocol. Then a task is started to run the WebSocket handler
and close the connection when it terminates. This design is very debatable:

- This isn't an intended use case for the ``close()`` method.
- The protocol transplant relies on non-standard variables in ``environ``.
- It also abuses private APIs of Tulip.

.. _sorry: https://twitter.com/GrahamDumpleton/status/316315348049752064
.. _Graham: https://twitter.com/GrahamDumpleton/status/316726248837611521

Asynchronous development server
...............................

django-c10k-demo adapts Django's built-in developement server to run on top of
Tulip, taking advantage of Tulip's built-in WSGI support.

This component can be used independently by adding the ``'c10ktools'``
application to ``INSTALLED_APPS``. This overrides the ``django-admin.py
runserver`` command to run on Tulip. Auto-reload works.
