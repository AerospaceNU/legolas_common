import numpy as np
from cv2.typing import MatLike

from packet_types import Packet, PacketAddress, PacketType


def test_pack_control() -> None:
    payload = {"control1": "control1_setting", "control2": "control2_setting"}
    pkt = Packet(PacketType.CONTROL, PacketAddress("127.0.0.1", 2445), payload)
    packed = Packet.pack(pkt)

    assert isinstance(packed, bytes)

    unpacked, remaining = Packet.unpack(packed)

    assert isinstance(unpacked, Packet)
    assert isinstance(remaining, bytes)
    assert len(remaining) == 0

    assert unpacked.packet_type == PacketType.CONTROL
    assert isinstance(unpacked.payload, dict)
    assert unpacked.packet_address == PacketAddress("127.0.0.1", 2445)
    assert unpacked.payload["control1"] == "control1_setting"
    assert unpacked.payload["control2"] == "control2_setting"


def test_pack_image() -> None:
    width, height = 640, 480
    channels = 3
    sample_image = np.zeros((height, width, channels), dtype=np.uint8)

    sample_image[:] = (255, 255, 0)

    payload: MatLike = sample_image
    assert payload.shape == (480, 640, 3)

    pkt = Packet(PacketType.IMAGE, PacketAddress("127.0.0.1", 2445), payload)
    packed = Packet.pack(pkt)

    assert isinstance(packed, bytes)

    unpacked, remaining = Packet.unpack(packed)
    assert isinstance(remaining, bytes)
    assert len(remaining) == 0

    assert isinstance(unpacked, Packet)

    assert unpacked.packet_type == PacketType.IMAGE
    assert isinstance(unpacked.payload, np.ndarray)
    assert np.all(unpacked.payload == (255, 255, 0))
    assert unpacked.packet_address == PacketAddress("127.0.0.1", 2445)
    assert unpacked.payload.shape == (480, 640, 3)


def test_pack_ack() -> None:
    pkt = Packet(PacketType.ACK, PacketAddress("127.0.0.1", 2445), 13)
    packed = Packet.pack(pkt)

    assert isinstance(packed, bytes)

    unpacked, remaining = Packet.unpack(packed)
    assert isinstance(unpacked, Packet)
    assert isinstance(remaining, bytes)
    assert len(remaining) == 0

    assert unpacked.packet_type == PacketType.ACK
    assert isinstance(unpacked.payload, int)
    assert unpacked.packet_address == PacketAddress("127.0.0.1", 2445)
    assert unpacked.payload == 13


def test_pack_internal() -> None:
    pkt = Packet(PacketType.INTERNAL, PacketAddress("127.0.0.1", 2445), "Internal message")
    packed = Packet.pack(pkt)

    assert isinstance(packed, bytes)

    unpacked, remaining = Packet.unpack(packed)
    assert isinstance(unpacked, Packet)
    assert isinstance(remaining, bytes)
    assert len(remaining) == 0

    assert unpacked.packet_type == PacketType.INTERNAL
    assert isinstance(unpacked.payload, str)
    assert unpacked.packet_address == PacketAddress("127.0.0.1", 2445)
    assert unpacked.payload == "Internal message"


def test_pack_extra() -> None:
    pkt = Packet(PacketType.INTERNAL, PacketAddress("127.0.0.1", 2445), "Internal message")
    packed = Packet.pack(pkt)

    extra_bytes = b"12345"
    assert len(extra_bytes) == 5
    packed += extra_bytes

    assert isinstance(packed, bytes)

    unpacked, remaining = Packet.unpack(packed)
    assert isinstance(unpacked, Packet)
    assert isinstance(remaining, bytes)
    assert len(remaining) == 5
    assert remaining == b"12345"

    assert unpacked.packet_type == PacketType.INTERNAL
    assert isinstance(unpacked.payload, str)
    assert unpacked.packet_address == PacketAddress("127.0.0.1", 2445)
    assert unpacked.payload == "Internal message"
