from io import StringIO

from django.core.management import call_command
from django.core.urlresolvers import reverse

from .management.commands.testecho import Command as TestEchoCommand
from .test import ServerTestCase


class CommandsTests(ServerTestCase):

    def test_testecho(self):
        # Tweak a few parameters to make the test run faster.
        TestEchoCommand.CLIENTS = 12
        TestEchoCommand.DELAY = 0.1
        TestEchoCommand.ECHO_URL = (self.live_server_url.replace('http', 'ws')
                                    + reverse('c10ktools.views.echo_ws'))

        call_command('testecho', stdout=StringIO())
