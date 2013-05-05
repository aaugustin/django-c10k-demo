import itertools

import tulip

from django.shortcuts import render

from c10ktools.http import websocket

# Server-wide state used by the watchers
global_subscribers = set()
size = 32

def watch(request):
    context = {
        'size': size,
        'sizelist': list(range(size)),
    }
    return render(request, 'gameoflife/watch.html', context)


@websocket
def watcher(ws):
    print("Watcher connected")
    global_subscribers.add(ws)
    # Block until the client goes away
    yield from ws.recv()
    global_subscribers.remove(ws)
    print("Watcher disconnected")


@websocket
# Server-wide state
def reset(ws):
    global size, expected, connected, subscribed, sub_latch, run_latch, subscribers
    size = int((yield from ws.recv()))
    expected = size * size
    connected = 0
    subscribed = 0
    sub_latch = tulip.Future()
    run_latch = tulip.Future()
    subscribers = [[set() for col in range(size)] for row in range(size)]


@websocket
def worker(ws):
    global connected, subscribed

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
    subscriptions = set()
    while True:
        msg = yield from ws.recv()
        if msg == 'sub':
            break
        row, col = msg.split()
        row, col = int(row), int(col)
        subscriptions.add((row, col))
        subscribers[row][col].add(ws)

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

    # Unsubscribe from updates.
    for row, col in subscriptions:
        subscribers[row][col].remove(ws)
