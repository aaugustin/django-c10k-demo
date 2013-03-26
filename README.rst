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
* Clone this repository.
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

Behind the hood
---------------

Here are the underlying components in no particular order, with some hints on
their quality and reusability.

WebSocket implementation
........................

django-c10k-demo provides a server-side implementation of the WebSocket
protocol compatible with Tulip.

The ``WebSocket`` class provides three methods:

- ``read_message()`` is a coroutine that returns the content of the next
  message asynchronously;
- ``write_message(data, opcode=None)`` writes the next message — Tulip ensures
  this doesn't block;
- ``close()`` closes the connection.

The code is in ``c10ktools.websockets``.

WSGI server running on top of Tulip
...................................

django-c10k-demo adapts Django's built-in developement server to run on top of
Tulip. This involves some inelegant plumbing to resolve the impedance mismatch
between WSGI and ``tulip.http``.

The code is merely functional. There's little point in optimizing it: either
the standard library will eventually provide an asynchronous WSGI server, or
the future of asynchronous apps won't involve WSGI.

This component can be used independently by adding the ``'c10ktools'``
application to ``INSTALLED_APPS``. This overrides the ``django-admin.py
runserver`` command to run on Tulip. Auto-reload works.

The implementation is in ``c10ktools.servers.tulip``. A test page is available
at http://localhost:8000/test/wsgi/.

Hook for the upgrade to WebSocket
.................................

The design of WSGI predates real-time on the web and PEP 3156 doesn't propose
to update it. Hopefully his point will be addressed by a future version of the
standard (PEP 3356 anyone?). In the meantime our only choice is to bastardize
it, steering away from WSGI compliance — `sorry Graham`_.

The WebSocket handler needs to grab the read and write streams for further
communications. A straightforward solution is to add them in ``environ``,
`like httpclient does`_.

More importantly, it needs to hook on the WSGI request processing. Since it's
a coroutine, it can only be called from another coroutine. I chose to call it
in ``close()`` to allow completing the handshake cleanly within WSGI. (Still,
the handshake isn't compliant because the reply contains a hop-by-hop header.)

These features are also implemented in ``c10ktools.servers.tulip``.

Once again, there's little point in optimizing them until the future of WSGI
and asynchronous servers is clarified.

.. _sorry Graham: https://twitter.com/GrahamDumpleton/status/316315348049752064
.. _like httpclient does: https://github.com/fafhrd91/httpclient/blob/master/httpclient/server.py

WebSocket API for Django
........................

Here's an example of a WebSocket handler in Django::

    from c10ktools.http import websocket

    @websocket
    def handler(ws):
        # ws is a WebSocket instance. Let's echo the messages we receive.
        while True:
            ws.write_message((yield from ws.read_message()))

WebSocket handlers are hooked in the URLconf like regular HTTP views.
Arguments can be captured in the URLconf and passed to the handlers.

This doesn't allow sharing an URL between a regular HTTP view and a WebSocket
handler, but I'm happy with this limitation as it's probably a good practice
to keep them separate anyway.

Inside a WebSocket handler, you can use ``yield from ws.read_message()`` and
``ws.write_message()`` freely. You can also call ``ws.write_message()`` from
outside the handler.

The ``@websocket`` decorator takes care of marking the handler as a
``@tulip.coroutine``. ``ws.close()`` is called automatically when the handler
returns.

The implementation is in ``c10ktools.http.websockets``. A test page is
available at http://localhost:8000/test/.

Testing script
..............

There isn't much to say about this code. It's located in
``c10ktools.clients.tulip`` and ``c10ktools.management.commands.testecho``.
