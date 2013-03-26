import collections
import io
import random
import struct

import tulip


class WebSocket:
    """
    Basic WebSocket protocol implementation on top of Tulip.
    """

    server = True

    def __init__(self, reader, writer):
        """
        Create a WebSocket handler.

        reader must be a tulip.StreamReader, writer a tulip.WriteTransport.
        """
        self.reader = reader
        self.writer = writer
        self.local_closed = False
        self.remote_closed = False

    @tulip.coroutine
    def read_message(self):
        """
        Read the next message from the client.

        A text frame is returned as str, a binary frame as bytes, None if the
        end of the message stream was reached.
        """
        # Handle fragmentation
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

    def write_message(self, data, opcode=None):
        """
        Write a message to the client.

        By default, str is sent as a text frame, bytes as a binary frame.
        """
        self.write_frame(data, opcode)

    def close(self, data=b''):
        """
        Close the connection with the client.
        """
        if not self.local_closed:
            self.write_frame(data, opcode=8)
            self.local_closed = True
            self.writer.close()

    def ping(self, data=b''):
        """
        Send a Ping.
        """
        self.write_frame(data, opcode=9)

    def pong(self, data=b''):
        """
        Send a Pong.
        """
        self.write_frame(data, opcode=10)

    @tulip.coroutine
    def read_data_frame(self):
        while not self.remote_closed:
            frame = yield from self.read_frame()
            if frame.opcode & 0b1000:       # control frame
                assert 8 <= frame.opcode <= 10
                if frame.opcode == 8:
                    self.remote_closed = True
                    self.close()
                    raise StopIteration     # could use a specific exception
                elif frame.opcode == 9:
                    self.pong(frame.data)
                elif frame.opcode == 10:
                    pass                    # unsolicited Pong
            else:                           # data frame
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
        assert bool(head2 & 0b10000000) == self.server, "invalid masking"
        length = head2 & 0b01111111
        if length == 126:
            data = yield from self.reader.readexactly(2)
            length, = struct.unpack('!H', data)
        elif length == 127:
            data = yield from self.reader.readexactly(8)
            length, = struct.unpack('!Q', data)
        if self.server:
            mask = yield from self.reader.readexactly(4)

        # Read the data
        data = yield from self.reader.readexactly(length)
        if self.server:
            data = bytes(b ^ mask[i % 4] for i, b in enumerate(data))

        return Frame(fin, opcode, data)

    def write_frame(self, data=b'', opcode=None):
        if self.local_closed:
            raise IOError("Cannot write to a closed WebSocket")

        # Encode text and set default opcodes
        if isinstance(data, str):
            if opcode is None:
                opcode = 1
            data = data.encode('utf-8')
        elif isinstance(data, bytes):
            if opcode is None:
                opcode = 2
        else:
            raise TypeError("data must be bytes or str")

        # Write the header
        header = io.BytesIO()
        header.write(struct.pack('!B', 0b10000000 | opcode))
        if self.server:
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
        if not self.server:
            header.write(mask)
        self.writer.write(header.getvalue())

        # Write the data
        if not self.server:
            data = bytes(b ^ mask[i % 4] for i, b in enumerate(data))
        self.writer.write(data)


class ClientWebSocket(WebSocket):
    """Client-side WebSocket implementation, for testing."""

    server = False


Frame = collections.namedtuple('Frame', ('fin', 'opcode', 'data'))
