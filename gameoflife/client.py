import random

import asyncio
import websockets

BASE_URL = 'ws://localhost:8000'

@asyncio.coroutine
def reset(size):
    ws = yield from websockets.connect(BASE_URL + '/reset/')
    yield from ws.send(str(size))
    yield from ws.worker


@asyncio.coroutine
def run(row, col, size, wrap, speed, steps=None, state=None):

    if state is None:
        state = random.choice((True, False, False, False))

    neighbors = get_neighbors(row, col, size, wrap)
    neighbors = {n: i for i, n in enumerate(neighbors)}
    n = len(neighbors)

    # Throttle at 100 connections / second on average
    yield from asyncio.sleep(size * size / 100 * random.random())
    ws = yield from websockets.connect(BASE_URL + '/worker/')

    # Wait until all clients are connected.
    msg = yield from ws.recv()
    if msg != 'sub':
        raise Exception("Unexpected message: {}".format(msg))

    # Subscribe to updates sent by neighbors.
    for neighbor in neighbors:
        yield from ws.send('{} {}'.format(*neighbor))
    yield from ws.send('sub')

    # Wait until all clients are subscribed.
    msg = yield from ws.recv()
    if msg != 'run':
        raise Exception("Unexpected message: {}".format(msg))

    yield from ws.send('{} {} {} {}'.format(0, row, col, int(state)))

    # This is the step for which we last sent our state, and for which we're
    # collecting the states of our neighbors.
    step = 0
    # Once we know all our neighbors' states at step N - 1, we compute and
    # send our state at step N. At this point, our neighbors can send their
    # states at steps N and N + 1, but not N + 2, since that requires our
    # state at step N + 1. We only need to keep track of two sets of states.
    states = [[None] * n, [None] * n]

    # Gather state updates from neighbors and send our own state updates.
    while (steps is None or step < steps):
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
            states[target] = [None] * n
            yield from ws.send('{} {} {} {}'.format(step, row, col, int(state)))
            # Throttle, speed is a number of steps per second
            yield from asyncio.sleep(1 / speed)

    yield from ws.close()


def get_neighbors(row, col, size, wrap):
    for i in (-1, 0, 1):
        for j in (-1, 0, 1):
            if i == j == 0:
                continue
            if 0 <= row + i < size and 0 <= col + j < size:
                yield row + i, col + j
            elif wrap:
                yield (row + i) % size, (col + j) % size
