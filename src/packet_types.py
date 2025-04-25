import pickle
import struct
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, TypeAlias

import cv2
import numpy as np

cv2.setNumThreads(cv2.getNumberOfCPUs())


@dataclass
class PacketAddress:
    """Packet address information"""

    ip: tuple[int, ...]
    """IP address"""
    port: int
    """Socket port"""

    def __init__(self, ip: tuple[int, ...] | str, port: int):
        """Construct a PacketAddress

        Args:
            ip: IP, either as a string of xxx.xxx.xxx.xxx or a four-tuple
            port: Packet port

        Raises:
            ValueError: If IP is not a valid tuple or string
        """
        if isinstance(ip, tuple) and len(ip) == 4:
            self.ip = ip
        elif isinstance(ip, str):
            try:
                self.ip = tuple([int(segment) for segment in ip.split(".")])
            except Exception:
                raise ValueError("Invalid string ip - must be in the form of 'xxx.xxx.xxx.xxx'")
        else:
            raise ValueError("Invalid ip - must be tuple or str")
        self.port = port

    def __hash__(self):
        return hash(hash(self.ip) + hash(self.port))


BROADCAST_DEST = PacketAddress("0.0.0.0", 0)


class PacketType(Enum):
    """Types of packets"""

    CONTROL = 0
    """Control message from client to server"""
    IMAGE = 1
    """Packet containing image data"""
    ACK = 2
    """Acknowledgement of control packet"""
    INTERNAL = 3
    """Internal communication packet"""


Payload: TypeAlias = dict | np.ndarray | int | str
"""Payload type definitions.
dict is expected for CONTROL packets
np.ndarray image is expected for IMAGE packets,
int is expected for ACK
str is expected for INTERNAL communication signals
"""


@dataclass
class Packet:
    """Packet of data to transfer between clients and server"""

    packet_type: PacketType
    """Type of packet"""
    packet_address: PacketAddress
    """Address of packet. For an incoming packet, this will be the source address
    For an outgoing packet, this will be the destination address
    This is only for internal use to identify which clients are being communicated with
    Internally, the sockets do not care about this field and it does not affect transmission"""
    payload: Payload
    """Packet payload"""
    timestamp: float = field(default_factory=time.time)
    """Packet timestamp"""
    # 1 byte for type, 4 bytes for IP address, 4 byte int for port,
    # 8 bytes for payload length, 8 byte double for timestamp
    # big-endian
    HEADER_FORMAT = "!BBBBBiQd"
    HEADER_SIZE = struct.calcsize(HEADER_FORMAT)

    @classmethod
    def pack(cls, packet: "Packet") -> bytes:
        """Serialize the packet into a binary format

        Args:
            packet: The packet to pack

        Returns:
            Packet serialized into bytes
        """
        if isinstance(packet.payload, int):
            payload_data = packet.payload.to_bytes()
        elif isinstance(packet.payload, np.ndarray):
            payload_data = cv2.imencode(".bmp", packet.payload)[1].tobytes()
        elif isinstance(packet.payload, dict):
            payload_data = pickle.dumps(packet.payload)
        else:
            payload_data = packet.payload.encode()

        # Pack the header (type + payload length)
        header = struct.pack(
            cls.HEADER_FORMAT,
            packet.packet_type.value,
            *packet.packet_address.ip,
            packet.packet_address.port,
            len(payload_data),
            time.time(),
        )

        # Combine the header and payload
        return header + payload_data

    @classmethod
    def unpack(cls, data: bytes) -> tuple[Optional["Packet"], bytes]:
        """Deserialize binary data into a Packet instance

        Args:
            data: Bytes string to unpack into a packet. The first valid packet will be
                  parsed out of data and any extra data will be returned back (see return values)

        Returns:
            Tuple of (parsed and unpacked Packet,
                      or None if no valid packet, remaining unparsed bytes).
        """
        if len(data) < cls.HEADER_SIZE:
            return (None, data)

        # Unpack the header
        (packet_type_value, ip_0, ip_1, ip_2, ip_3, source_port, payload_length, timestamp) = (
            struct.unpack(cls.HEADER_FORMAT, data[: cls.HEADER_SIZE])
        )

        source_ip = (ip_0, ip_1, ip_2, ip_3)

        # Validate and extract payload
        if len(data) < cls.HEADER_SIZE + payload_length:
            return (None, data)

        payload_data = data[cls.HEADER_SIZE : cls.HEADER_SIZE + payload_length]
        remaining_data = data[cls.HEADER_SIZE + payload_length :]

        payload_type = PacketType(packet_type_value)
        if payload_type == PacketType.CONTROL:
            payload = pickle.loads(payload_data)
        elif payload_type == PacketType.IMAGE:
            frame_mat = np.frombuffer(payload_data, dtype=np.uint8)
            payload = cv2.imdecode(frame_mat, cv2.IMREAD_COLOR)
        elif payload_type == PacketType.ACK:
            payload = int.from_bytes(payload_data)
        else:
            payload = payload_data.decode()

        return (
            cls(
                packet_type=PacketType(packet_type_value),
                packet_address=PacketAddress(source_ip, source_port),
                payload=payload,
                timestamp=timestamp,
            ),
            remaining_data,
        )
