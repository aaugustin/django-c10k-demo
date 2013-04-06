from optparse import make_option

import tulip

from django.core.management.base import CommandError, NoArgsCommand

from ...client import reset, run


class Command(NoArgsCommand):

    option_list = NoArgsCommand.option_list + (
        make_option('-C', '--no-center', default=True,
                    action='store_false', dest='center',
                    help='Do not center the pattern in the grid.'),
        make_option('-p', '--pattern',
                    help='The initial state of the grid.'),
        make_option('-s', '--size', type='int', default=32,
                    help='The size of the grid.'),
        make_option('-l', '--speed', type='float', default=1.0,
                    help='The maximum number of steps per second.'),
        make_option('-n', '--steps', type='int', default=None,
                    help='The number of steps.'),
        make_option('-W', '--no-wrap', default=True,
                    action='store_false', dest='wrap',
                    help='Do not wrap around the grid.'),
    )
    help = 'Runs one worker for each cell of the Game of Life grid.'

    def handle_noargs(self, **options):
        center = options['center']
        pattern = options['pattern']
        size = options['size']
        speed = options['speed']
        steps = options['steps']
        wrap = options['wrap']

        if pattern is None:
            states = [[None] * size] * size
        else:
            states = self.parse_pattern(pattern, size, center)

        clients = [run(row, col, size, wrap, speed, steps, states[row][col])
                   for row in range(size) for col in range(size)]

        try:
            tulip.get_event_loop().run_until_complete(reset(size))
            tulip.get_event_loop().run_until_complete(tulip.wait(clients))
        except KeyboardInterrupt:
            pass

    def parse_pattern(self, pattern, size, center):
        with open(pattern) as handle:
            rows = [row.rstrip() for row in handle]

        # Check that the pattern fits in the grid
        height = len(rows)
        width = max(len(row) for row in rows)
        if height > size:
            raise CommandError("Too many rows in pattern. Increase size?")
        if width > size:
            raise CommandError("Too many columns in pattern. Increase size?")

        # Center pattern vertically and horizontally
        if center:
            top = (size - height) // 2
            rows = [''] * top + rows
            left = (size - width) // 2
            prefix = ' ' * left
            rows = [prefix + row for row in rows]

        # Add padding to match the grid size
        rows += [''] * (size - len(rows))
        rows = [row.ljust(size) for row in rows]

        # Convert to booleans
        return [[x not in '. ' for x in row] for row in rows]
