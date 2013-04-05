import random

import tulip
import websockets


@tulip.coroutine
def run(row, col, size, state=None):

    if state is None:
        state = random.choice((True, False, False, False))

    neighbors = {n: i for i, n in enumerate(get_neighbors(row, col, size))}

    # Throttle at 100 connections / second on average
    yield from tulip.sleep(size * size / 100 * random.random())
    ws = yield from websockets.connect('ws://localhost:8000/worker/')

    # Wait until all clients are connected.
    msg = yield from ws.recv()
    if msg != 'sub':
        raise Exception("Unexpected message: {}".format(msg))

    # Subscribe to updates sent by neighbors.
    for neighbor in neighbors:
        ws.send('sub {} {}'.format(*neighbor))

    # Wait until all clients are subscribed.
    msg = yield from ws.recv()
    if msg != 'run':
        raise Exception("Unexpected message: {}".format(msg))

    ws.send('{} {} {} {}'.format(0, row, col, int(state)))

    # This is the step for which we last sent our state, and for which we're
    # collecting the states of our neighbors.
    step = 0
    # Once we know all our neighbors' states at step N - 1, we compute and
    # send our state at step N. At this point, our neighbors can send their
    # states at steps N and N + 1, but not N + 2, since that requires our
    # state at step N + 1. We only need to keep track of two sets of states.
    states = [[None] * 8, [None] * 8]

    # Gather state updates from neighbors and send our own state updates.
    while True:
        msg = yield from ws.recv()
        if msg is None:
            break
        _step, _row, _col, _state = (int(x) for x in msg.split())
        target = _step % 2
        states[target][neighbors[(_row, _col)]] = bool(_state)
        # Compute next state
        if None not in states[target]:
            assert _step == step
            step += 1
            alive = states[target].count(True)
            state = alive == 3 or (state and alive == 2)
            states[target] = [None] * 8
            ws.send('{} {} {} {}'.format(step, row, col, int(state)))
            # Throttle at one step per second
            yield from tulip.sleep(1)


def get_neighbors(row, col, size):
    for i in (-1, 0, 1):
        for j in (-1, 0, 1):
            if i == j == 0:
                continue
            yield (row + i) % size, (col + j) % size
