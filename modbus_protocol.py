# modbus_protocol.py
# -*- coding: utf-8 -*-

"""Helpers for parsing and building Modbus RTU request/response frames."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import List, Tuple, Optional

from modbus_crc import verify_crc


@dataclass(frozen=True)
class ParsedResponse:
    """Structured result of a parsed Modbus response frame.

    Attributes:
        raw_frame: Original RTU bytes received.
        is_exception: True for Modbus exception responses.
        exception_code: Exception code when present.
        items: Parsed address/value pairs.
    """

    raw_frame: bytes
    is_exception: bool
    exception_code: Optional[int]
    items: List[Tuple[int, int]]  # (address, value)


def to_hex_string(b: bytes) -> str:
    """Convert a byte sequence into a space-separated uppercase hex string.

    Args:
        b: Bytes to format.

    Returns:
        Hex string formatted as "XX XX".
    """
    return " ".join(f"{x:02X}" for x in b)


def build_read_request_payload(device_id: int, function_code: int, address: int, length: int) -> bytes:
    """Build a Modbus read request payload without CRC.

    Args:
        device_id: Target Modbus slave ID.
        function_code: Read function code (1 to 4).
        address: Start address to read from.
        length: Number of coils/registers to request.

    Returns:
        A payload byte sequence in the format [id][fc][addr_hi][addr_lo][len_hi][len_lo].
    """
    if not (1 <= device_id <= 247):
        raise ValueError("device_id must be 1..247 (typical range)")
    if function_code not in (1, 2, 3, 4):
        raise ValueError("function_code must be 1,2,3,4")
    if not (0 <= address <= 0xFFFF):
        raise ValueError("address must be 0x0000..0xFFFF")
    if not (1 <= length <= 0x07D0):  # 2000 typical max depending on device/spec
        raise ValueError("length must be 1..2000 (typical upper bound)")
    return bytes([
        device_id & 0xFF,
        function_code & 0xFF,
        (address >> 8) & 0xFF,
        address & 0xFF,
        (length >> 8) & 0xFF,
        length & 0xFF,
    ])


def _expected_data_byte_count(function_code: int, length: int) -> int:
    """Compute the expected payload byte count for a read response.

    Args:
        function_code: Modbus function code.
        length: Requested coil/register quantity.

    Returns:
        The expected data byte count.
    """
    if function_code in (1, 2):
        return int(math.ceil(length / 8.0))
    if function_code in (3, 4):
        return length * 2
    raise ValueError("unsupported function_code")


def try_extract_response_any(buffer: bytes, device_id: int, function_code: int) -> Tuple[Optional[bytes], bytes]:
    """Find a valid Modbus response frame within a byte buffer.

    Args:
        buffer: Raw bytes that may contain one or more RTU responses.
        device_id: Expected slave ID.
        function_code: Expected function code.

    Returns:
        A tuple of (frame, remaining_buffer) where frame is the parsed response frame if found.
    """
    if len(buffer) < 5:
        return None, buffer

    expected_fc = function_code & 0xFF
    expected_exc_fc = expected_fc | 0x80

    WRITE_FCS = {0x06, 0x10, 0x41}
    READ_FCS = {0x01, 0x02, 0x03, 0x04}

    for start in range(0, len(buffer) - 4):
        if buffer[start] != (device_id & 0xFF):
            continue

        fc = buffer[start + 1]
        if fc not in (expected_fc, expected_exc_fc):
            continue

        # 예외 응답
        if fc == expected_exc_fc:
            if start + 5 <= len(buffer):
                frame = buffer[start:start + 5]
                if verify_crc(frame):
                    return frame, buffer[start + 5:]
            continue

        # 정상 응답
        if fc in WRITE_FCS:
            if start + 8 <= len(buffer):
                frame = buffer[start:start + 8]
                if verify_crc(frame):
                    return frame, buffer[start + 8:]
            continue

        if fc in READ_FCS:
            if start + 3 <= len(buffer):
                byte_count = buffer[start + 2]
                total_len = 3 + byte_count + 2
                if start + total_len <= len(buffer):
                    frame = buffer[start:start + total_len]
                    if verify_crc(frame):
                        return frame, buffer[start + total_len:]
            continue

    return None, buffer


def parse_response_auto(frame: bytes, start_address: int) -> ParsedResponse:
    """Parse a Modbus response into address/value items without requiring a requested length.

    Args:
        frame: RTU response bytes including CRC.
        start_address: Starting address used for item numbering.

    Returns:
        A ParsedResponse object with the parsed items.
    """
    if not verify_crc(frame):
        raise ValueError("CRC mismatch")
    if len(frame) < 5:
        raise ValueError("Frame too short")

    fc = frame[1]

    # 예외 응답
    if fc & 0x80:
        exc = frame[2]
        return ParsedResponse(raw_frame=frame, is_exception=True, exception_code=exc, items=[])

    byte_count = frame[2]
    data = frame[3:-2]
    if len(data) != byte_count:
        raise ValueError("Byte count mismatch")

    items: List[Tuple[int, int]] = []

    if fc in (1, 2):
        # bit packed, LSB first
        bit_len = byte_count * 8
        for i in range(bit_len):
            b = data[i // 8]
            bit = (b >> (i % 8)) & 0x01
            items.append((start_address + i, bit))

    elif fc in (3, 4):
        if byte_count % 2 != 0:
            raise ValueError("Register response byte_count must be even")
        reg_len = byte_count // 2
        for i in range(reg_len):
            hi = data[2 * i]
            lo = data[2 * i + 1]
            val = (hi << 8) | lo
            items.append((start_address + i, val))
    else:
        raise ValueError("Unsupported function code (expected 1~4)")

    return ParsedResponse(raw_frame=frame, is_exception=False, exception_code=None, items=items)


def to_hex_string(b: bytes) -> str:
    return " ".join(f"{x:02X}" for x in b)

#
# end of file
#