import threading

import tulip

from selenium.webdriver import Firefox

from django.contrib.staticfiles.handlers import StaticFilesHandler
from django.core.servers.basehttp import get_internal_wsgi_application
from django.test import TestCase

from .management.commands.runserver import run


# Since it's hard to subclass LiveServerTestCase to run on top of Tulip, and
# since we don't need to share a database connection between the live server
# and the tests, we use a simple ServerTestCase instead of LiveServerTestCase.

class ServerTestCase(TestCase):

    @classmethod
    def setUpClass(cls):
        super(ServerTestCase, cls).setUpClass()
        cls.start_server('localhost', 8999)

    @classmethod
    def tearDownClass(cls):
        cls.stop_server()
        super(ServerTestCase, cls).tearDownClass()

    @classmethod
    def start_server(cls, host, port):
        cls.live_server_url = 'http://{}:{}'.format(host, port)
        cls.server_thread = threading.Thread(target=cls.run_server,
                                             args=(host, port))
        cls.server_thread.start()

    @classmethod
    def run_server(cls, host, port):
        handler = StaticFilesHandler(get_internal_wsgi_application())
        # Save the event loop for the thread in a class variable
        # so we can unblock it when the tests are finished.
        cls.server_thread_loop = tulip.new_event_loop()
        tulip.set_event_loop(cls.server_thread_loop)
        cls.server_stop = tulip.Future()
        run(host, port, handler, cls.server_thread_loop, cls.server_stop)
        cls.server_thread_loop.close()

    @classmethod
    def stop_server(cls):
        cls.server_thread_loop.call_soon_threadsafe(cls.server_stop.set_result, None)
        cls.server_thread.join()


class SeleniumTestCase(ServerTestCase):

    @classmethod
    def setUpClass(cls):
        super(SeleniumTestCase, cls).setUpClass()
        cls.selenium = Firefox()

    @classmethod
    def tearDownClass(cls):
        cls.selenium.quit()
        super(SeleniumTestCase, cls).tearDownClass()
