README
======

django-c10k-demo handles 10 000 concurrent real-time connections to Django.

This demo combines several interesting concepts: the `C10k problem`_, the
`WebSocket protocol`_, the `Django web framework`_, and Python's upcoming
`asynchronous IO support`_.

It requires Django 1.5, Python 3.3, and the `Tulip`_ library. Here's a short
description of the moving pieces, in no particular order.

.. _C10k problem: http://en.wikipedia.org/wiki/C10k_problem
.. _WebSocket protocol: http://tools.ietf.org/html/rfc6455
.. _Django web framework: https://www.djangoproject.com/
.. _asynchronous IO support: http://www.python.org/dev/peps/pep-3156/
.. _Tulip: http://code.google.com/p/tulip/

WebSocket implementation
------------------------

django-c10k-demo provides a server-side implementation of the WebSocket
protocol compatible with Tulip.

The ``WebSocket`` class is instantiated with a ``tulip.StreamReader`` and a
``tulip.WriteTransport``. It provides three methods:

- ``read_message()`` is a coroutine that returns the content of the next
  message asynchronously;
- ``write_message(data, opcode=None)`` writes the next message — Tulip ensures
  this doesn't block;
- ``close()`` closes the connection.

The code is in ``c10ktools.websockets``.

WSGI server running on top of Tulip
-----------------------------------

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
---------------------------------

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
------------------------

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
