import tulip

from django.core.management.base import NoArgsCommand

from ...client import run
from ...models import SIZE


class Command(NoArgsCommand):

    def handle_noargs(self, **options):
        clients = [run(row, col, SIZE)
                   for row in range(SIZE)
                   for col in range(SIZE)]
        try:
            tulip.get_event_loop().run_until_complete(tulip.wait(clients))
        except KeyboardInterrupt:
            pass
