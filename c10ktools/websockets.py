import collections
import io
import struct

import tulip


class WebSocket:
    """
    Basic WebSocket protocol implementation on top of Tulip.
    """

    def __init__(self, reader, writer):
        """
        Create a WebSocket handler.

        reader must be a tulip.StreamReader, writer a tulip.WriteTransport.
        """
        self.reader = reader
        self.writer = writer

    @tulip.coroutine
    def read_message(self):
        """
        Read the next message from the client.

        A text frame is returned as str, a binary frame as bytes.
        """
        # Handle fragmentation
        frame = yield from self.read_data_frame()
        data = [frame.data]
        text = (frame.opcode == 1)
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

    def close(self):
        """
        Close the connection with the client.
        """
        self.write_frame(opcode=8)

    @tulip.coroutine
    def read_data_frame(self):
        while True:
            frame = yield from self.read_frame()
            if frame.opcode & 0b1000:       # control frame
                assert 8 <= frame.opcode <= 10
                if frame.opcode == 8:
                    self.write_frame(8, frame.data)
                    raise StopIteration     # could use a specific exception
                elif frame.opcode == 9:
                    self.write_frame(10, frame.data)
                elif frame.opcode == 10:
                    pass                    # unsolicited Pong
            else:                           # data frame
                assert 0 <= frame.opcode <= 2
                return frame

    @tulip.coroutine
    def read_frame(self):
        # Read and parse the header
        data = yield from self.reader.readexactly(2)
        head1, head2 = struct.unpack('!BB', data)
        fin = bool(head1 & 0b10000000)
        assert not head1 & 0b01110000, "reserved bits must be 0"
        opcode = head1 & 0b00001111
        assert head2 & 0b10000000, "packets sent by the client must be masked"
        length = head2 & 0b01111111
        if length == 126:
            data = yield from self.reader.readexactly(2)
            length, = struct.unpack('!H', data)
        elif length == 127:
            data = yield from self.reader.readexactly(8)
            length, = struct.unpack('!Q', data)
        # Read an unmask the data
        mask = yield from self.reader.readexactly(4)
        data = yield from self.reader.readexactly(length)
        data = bytes(b ^ mask[i % 4] for i, b in enumerate(data))
        return Frame(fin, opcode, data)

    def write_frame(self, data=b'', opcode=None):
        # Encode text frames
        if isinstance(data, str):
            if opcode is None:
                opcode = 1
            data = data.encode('utf-8')
        elif isinstance(data, bytes):
            if opcode is None:
                opcode = 2
        else:
            raise TypeError("data must be bytes or str")
        # Create the header in a buffer
        header = io.BytesIO()
        header.write(struct.pack('!B', 0b10000000 | opcode))
        length = len(data)
        if length < 0x7e:
            format = '!B'
        elif length < 0x7fff:
            format = '!H'
            header.write(b'\x7e')
        else:
            format = '!Q'
            header.write(b'\x7f')
        header.write(struct.pack(format, length))
        # Write the payload
        self.writer.write(header.getvalue())
        self.writer.write(data)


Frame = collections.namedtuple('Frame', ('fin', 'opcode', 'data'))
