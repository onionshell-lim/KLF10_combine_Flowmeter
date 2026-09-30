# modbus_crc.py
# -*- coding: utf-8 -*-

# (CRC 계산)

from __future__ import annotations


def crc16_modbus(data: bytes) -> int:
    """Calculate the Modbus CRC-16 value for a byte sequence.

    Args:
        data: Payload bytes to hash.

    Returns:
        The CRC-16/Modbus value as a 16-bit integer.
    """
    crc = 0xFFFF
    for b in data:
        crc ^= b
        for _ in range(8):
            lsb = crc & 0x0001
            crc >>= 1
            if lsb:
                crc ^= 0xA001
        crc &= 0xFFFF  # keep 16-bit
    return crc


def crc_bytes_le(data: bytes) -> bytes:
    """Return the CRC bytes in little-endian Modbus RTU order.

    Args:
        data: Payload bytes for which the CRC is computed.

    Returns:
        Two CRC bytes in low-byte/high-byte order.
    """
    crc = crc16_modbus(data)
    return bytes([crc & 0xFF, (crc >> 8) & 0xFF])


def append_crc(data: bytes) -> bytes:
    """Append the Modbus CRC bytes to a payload.

    Args:
        data: Payload bytes without CRC.

    Returns:
        The payload with CRC bytes appended.
    """
    return data + crc_bytes_le(data)


def verify_crc(frame: bytes) -> bool:
    """Validate the CRC of a Modbus RTU frame.

    Args:
        frame: Complete RTU frame including CRC bytes.

    Returns:
        True if the CRC is valid, otherwise False.
    """
    if len(frame) < 4:
        return False
    body = frame[:-2]
    return frame[-2:] == crc_bytes_le(body)


def _self_test() -> None:
    # Case 1
    req = bytes([0x01, 0x04, 0x01, 0x02, 0x00, 0x02])
    expect1 = bytes([0xD1, 0xF7])
    got1 = crc_bytes_le(req)
    assert got1 == expect1, f"CASE1 FAIL: got {got1.hex()} expected {expect1.hex()}"

    # Case 2
    resp_body = bytes([0x01, 0x04, 0x04, 0x81, 0xB3, 0x41, 0xCF])
    expect2 = bytes([0x52, 0x5B])
    got2 = crc_bytes_le(resp_body)
    assert got2 == expect2, f"CASE2 FAIL: got {got2.hex()} expected {expect2.hex()}"

    # Full-frame verify
    frame1 = req + expect1
    frame2 = resp_body + expect2
    assert verify_crc(frame1), "FRAME1 verify_crc FAIL"
    assert verify_crc(frame2), "FRAME2 verify_crc FAIL"

    print("CRC self-test OK")
    print("CASE1 CRC =", f"0x{crc16_modbus(req):04X}", "bytes(Lo,Hi)=", got1.hex().upper())
    print("CASE2 CRC =", f"0x{crc16_modbus(resp_body):04X}", "bytes(Lo,Hi)=", got2.hex().upper())


if __name__ == "__main__":
    _self_test()
