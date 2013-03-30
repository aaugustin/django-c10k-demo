README
======

django-c10k-demo handles 10 000 concurrent real-time connections to Django.

This demo combines several interesting concepts: the `C10k problem`_, the
`WebSocket protocol`_, the `Django web framework`_, and Python's upcoming
`asynchronous IO support`_.

.. _C10k problem: http://en.wikipedia.org/wiki/C10k_problem
.. _WebSocket protocol: http://tools.ietf.org/html/rfc6455
.. _Django web framework: https://www.djangoproject.com/
.. _asynchronous IO support: http://www.python.org/dev/peps/pep-3156/

Running the demo
----------------

* Install `Python 3.3`_, the `Tulip`_ library, and `Django 1.5`_.
* Clone the `websockets`_ repository and add it to your ``PYTHONPATH``.
* Clone `this repository`.
* Configure your OS to allow lots of file descriptors. On OS X: ``sudo sysctl
  -w kern.maxfiles=40960 kern.maxfilesperproc=20480``
* Open two shells and bump their file descriptor limit: ``ulimit -n 10240``
* In the first shell, start the server: ``python manage.py runserver``
* In the second shell, start the clients: ``python manage.py testecho``

If you're lucky, the server won't display anything, and the client will show
the number of connections, peaking at ``10000 clients are connected!``. The
demo takes five minutes if your system is fast enough.

The connections are established over a period of two minutes. Once connected,
each client repeats the following sequence three times: wait one minute, send
a message, and read the reply of the server. Clients also receive a welcome
and a goodbye message from the server.

If you don't reach 10 000 connections, it means that some clients finish their
sequence and disconnect before all the clients are connected, because your
system is too slow. If you see exceptions, it means that your OS isn't tuned
correctly for such benchmarks. Decreasing ``CLIENTS`` or increasing ``DELAY``
in ``testecho`` may help in both cases.

.. _Python 3.3: http://www.python.org/getit/
.. _Tulip: http://code.google.com/p/tulip/
.. _Django 1.5: https://www.djangoproject.com/download/
.. _websockets: https://github.com/aaugustin/websockets
.. _this repository: https://github.com/aaugustin/django-c10k-demo

Under the hood
--------------

Here are the underlying components in no particular order, with some hints on
their quality and reusability.

WebSocket API for Django
........................

Here's an example of a WebSocket handler in Django::

    from c10ktools.http import websocket

    @websocket
    def handler(ws):
        # ws is a WebSocket instance. Let's echo the messages we receive.
        while True:
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
