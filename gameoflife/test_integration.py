import asyncio

from django.core.management import call_command
from django.core.urlresolvers import reverse

from c10ktools.test import SeleniumTestCase

from . import client


class IntegrationTests(SeleniumTestCase):

    @classmethod
    def setUpClass(cls):
        super(IntegrationTests, cls).setUpClass()
        client.BASE_URL = cls.live_server_url.replace('http', 'ws')

    def test_gameoflife(self):
        # Reduce size before opening the browser so it gets the right size.
        asyncio.get_event_loop().run_until_complete(client.reset(5))

        # This is just for the eye candy.
        self.selenium.get(self.live_server_url + reverse('gameoflife.views.watch'))

        # Run the game, with and without a pattern.
        call_command('gameoflife', size=5, speed=100, steps=5)

        call_command('gameoflife', size=5, speed=100, steps=5,
                                   pattern='gameoflife/patterns/blinker')
