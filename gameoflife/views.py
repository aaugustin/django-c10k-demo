import itertools

import tulip

from django.shortcuts import render

from c10ktools.http import websocket

from .models import SIZE


# Non-resettable server-wide state
expected = SIZE * SIZE
global_subscribers = set()

# Resettable server-wide state
def reset():
    global connected, subscribed, sub_latch, run_latch, subscribers
    connected = 0
    subscribed = 0
    sub_latch = tulip.Future()
    run_latch = tulip.Future()
    subscribers = [[set() for col in range(SIZE)] for row in range(SIZE)]

reset()


def watch(request):
    context = {
        'size': SIZE,
        'sizelist': list(range(SIZE)),
    }
    return render(request, 'gameoflife/watch.html', context)


@websocket
def watcher_ws(ws):
    global_subscribers.add(ws)
    # Block until the client goes away
    yield from ws.recv()
    global_subscribers.remove(ws)


@websocket
def worker_ws(ws):
    global connected, subscribed

    if subscribed > 0:
        reset()

    # Wait until all clients are connected.
    connected += 1
    if connected == expected:
        print("{:5} workers connected".format(connected))
        print("Telling workers to subscribe")
        sub_latch.set_result(None)
    elif connected % 100 == 0:
        print("{:5} workers connected".format(connected))
    yield from sub_latch
    ws.send('sub')

    # Subscribe to updates sent by neighbors.
    for _ in range(8):
        msg = yield from ws.recv()
        action, row, col = msg.split()
        if action != 'sub':
            raise Exception("Unexpected action: {}".format(action))
        subscribers[int(row)][int(col)].add(ws)

    # Wait until all clients are subscribed.
    subscribed += 1
    if subscribed == expected:
        print("{:5} workers subscribed".format(subscribed))
        print("Telling workers to run")
        run_latch.set_result(None)
    elif subscribed % 100 == 0:
        print("{:5} workers subscribed".format(subscribed))
    yield from run_latch
    ws.send('run')

    # Relay state updates to subscribers.
    while True:
        msg = yield from ws.recv()
        if msg is None:
            break
        step, row, col, state = msg.split()
        for subscriber in itertools.chain(
                subscribers[int(row)][int(col)], global_subscribers):
            subscriber.send(msg)
