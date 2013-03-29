import collections
import io
import random
import struct
import warnings

import tulip


Frame = collections.namedtuple('Frame', ('fin', 'opcode', 'data'))


class WebSocket:
    """
    Basic WebSocket implementation.

    This class assumes that the opening handshake and the upgrade from HTTP
    have been completed. It deals with with sending and receiving data, and
    with the close handshake.

    """

    def __init__(self, reader, writer, is_client=False):
        """
        Create a WebSocket handler.

        The `reader` must provide a `readexactly(n)` coroutine.
        The `writer` must provide a non-blocking `write()`.

        This class implements the server side behavior by default. To obtain
        the client side behavior, instantiate it with `is_client=True`.
        """
        self.reader = reader
        self.writer = writer
        self.is_client = is_client          # This is redundant but avoids
        self.is_server = not is_client      # confusing negations.
        self.local_closed = False
        self.remote_closed = False

    @tulip.coroutine
    def recv(self):
        """
        Receive the next message.

        A text frame is returned as a `str`, a binary frame as `bytes`.

        This coroutine returns `None` once the connection is closed.
        """
        # RFC 6455 - 5.4. Fragmentation
        frame = yield from self.read_data_frame()
        if frame is None:
            return
        text = (frame.opcode == 1)
        data = [frame.data]
        while not frame.fin:
            frame = yield from self.read_data_frame()
            assert frame.opcode == 0
            data.append(frame.data)
        data = b''.join(data)
        return data.decode('utf-8') if text else data

    def send(self, data):
        """
        Write a message.

        A str is sent as a text frame, bytes as a binary frame.
        """
        if isinstance(data, str):
            opcode = 1
            data = data.encode('utf-8')
        elif isinstance(data, bytes):
            opcode = 2
        else:
            raise TypeError("data must be bytes or str")
        self.write_frame(opcode, data)

    @tulip.coroutine
    def close(self, data=b''):
        """
        Close the connection.

        This coroutine waits for the other end to complete the close
        handshake. It doesn't do anything once the connection is closed.

        Status codes aren't implemented, but they can be passed in `data`.
        """
        if self.is_client:
            warnings.warn("Clients SHOULD NOT close the WebSocket connection "
                          "arbitrarily (RFC 6455, 7.3).")
        if not self.local_closed:
            self.write_frame(8, data)
            self.local_closed = True
            # Discard unprocessed messages until we get the other end's close.
            while (yield from self.recv()) is not None:
                pass
            self.writer.close()

    def ping(self, data=b''):
        """
        Send a Ping.
        """
        self.write_frame(9, data)

    def pong(self, data=b''):
        """
        Send a Pong.
        """
        self.write_frame(10, data)

    @tulip.coroutine
    def read_data_frame(self):
        # RFC 6455 - 6.2. Receiving Data
        while not self.remote_closed:
            frame = yield from self.read_frame()
            # RFC 6455 - 5.5. Control Frames
            if frame.opcode & 0b1000:
                assert 8 <= frame.opcode <= 10
                if frame.opcode == 8:
                    self.remote_closed = True
                    self.close()
                elif frame.opcode == 9:
                    self.pong(frame.data)
                elif frame.opcode == 10:
                    pass                    # unsolicited Pong
            # RFC 6455 - 5.6. Data Frames
            else:
                assert 0 <= frame.opcode <= 2
                return frame

    @tulip.coroutine
    def read_frame(self):
        if self.remote_closed:
            raise IOError("Cannot read from a closed WebSocket")

        # Read the header
        data = yield from self.reader.readexactly(2)
        head1, head2 = struct.unpack('!BB', data)
        fin = bool(head1 & 0b10000000)
        assert not head1 & 0b01110000, "reserved bits must be 0"
        opcode = head1 & 0b00001111
        assert bool(head2 & 0b10000000) == self.is_server, "invalid masking"
        length = head2 & 0b01111111
        if length == 126:
            data = yield from self.reader.readexactly(2)
            length, = struct.unpack('!H', data)
        elif length == 127:
            data = yield from self.reader.readexactly(8)
            length, = struct.unpack('!Q', data)
        if self.is_server:
            mask = yield from self.reader.readexactly(4)

        # Read the data
        data = yield from self.reader.readexactly(length)
        if self.is_server:
            data = bytes(b ^ mask[i % 4] for i, b in enumerate(data))

        return Frame(fin, opcode, data)

    def write_frame(self, opcode, data=b''):
        if self.local_closed:
            raise IOError("Cannot write to a closed WebSocket")

        # Write the header
        header = io.BytesIO()
        header.write(struct.pack('!B', 0b10000000 | opcode))
        if self.is_server:
            mask_bit = 0b00000000
        else:
            mask_bit = 0b10000000
            mask = struct.pack('!I', random.getrandbits(32))
        length = len(data)
        if length < 0x7e:
            header.write(struct.pack('!B', mask_bit | length))
        elif length < 0x7fff:
            header.write(struct.pack('!BH', mask_bit | 126, length))
        else:
            header.write(struct.pack('!BQ', mask_bit | 127, length))
        if self.is_client:
            header.write(mask)
        self.writer.write(header.getvalue())

        # Write the data
        if self.is_client:
            data = bytes(b ^ mask[i % 4] for i, b in enumerate(data))
        self.writer.write(data)


class WebSocketProtocol(WebSocket, tulip.Protocol):
    """
    WebSocket implementation as a Tulip protocol.
    """

    def __init__(self, *args, **kwargs):
        # The reader and writer will be set by connection_made.
        super().__init__(None, None, *args, **kwargs)

    def connection_made(self, transport):
        self.writer = transport
        self.reader = tulip.StreamReader()

    def data_received(self, data):
        self.reader.feed_data(data)

    def eof_received(self):
        self.reader.feed_eof()

    def connection_lost(self, exc):
        pass
