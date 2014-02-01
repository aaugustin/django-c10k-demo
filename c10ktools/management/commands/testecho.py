import random

import asyncio
import websockets

from django.core.management.base import NoArgsCommand


class Command(NoArgsCommand):

    CLIENTS = 10000
    DELAY = 60
    ECHO_URL = 'ws://localhost:8000/test/ws/'

    def handle_noargs(self, **options):
        self.count = 0
        connections = [self.test_echo() for _ in range(self.CLIENTS)]
        asyncio.get_event_loop().run_until_complete(asyncio.wait(connections))
        assert self.count == 0

    @asyncio.coroutine
    def test_echo(self):

        # Distribute the connections a bit
        yield from asyncio.sleep(2 * self.DELAY * random.random())
        ws = yield from websockets.connect(self.ECHO_URL)

        self.count += 1
        if self.count % (self.CLIENTS * 3 // self.DELAY) == 0:
            self.stdout.write("> {:5} connections\n".format(self.count))
        if self.count == self.CLIENTS:
            self.stdout.write("\n{} clients are connected!\n\n".format(self.count))

        messages = []
        messages.append((yield from ws.recv()))
        yield from asyncio.sleep(self.DELAY)
        ws.send('Spam?')
        messages.append((yield from ws.recv()))
        yield from asyncio.sleep(self.DELAY)
        ws.send('Eggs!')
        messages.append((yield from ws.recv()))
        yield from asyncio.sleep(self.DELAY)
        ws.send('Python.')
        messages.append((yield from ws.recv()))
        messages.append((yield from ws.recv()))
        assert messages == [
            "Hello!",
            "1. Spam?",
            "2. Eggs!",
            "3. Python.",
            "Goodbye!",
        ]

        yield from ws.close()

        self.count -= 1
        if self.count % (self.CLIENTS * 3 // self.DELAY) == 0:
            self.stdout.write("< {:5} connections\n".format(self.count))
