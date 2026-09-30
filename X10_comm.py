# -*- coding: utf-8 -*-

"""Serial communication helper for the Xonic10 flowmeter ASCII text protocol.

The Xonic10 device streams comma-separated ASCII lines instead of Modbus RTU
frames, for example:

    DEFAULT,+   0.417,+      76.419,0100000000, 0.042

Fields (in order): label, instantaneous flow, accumulated flow, status bits, velocity.
"""

from __future__ import annotations

import time
from dataclasses import dataclass

import submode

XONIC10_CHANNEL = 2

_rx_buffer: bytes = b""
_last_rx_text: str = ""
_last_activity_ts: float | None = None
_last_packet_hex: str = ""
_last_reading: Xonic10Reading | None = None

MONITOR_ITEMS = [
    ("label", "Name"),
    ("instant_flow", "Instant Flow"),
    ("accumulated_flow", "Accumulated Flow"),
    ("status", "Status"),
    ("velocity", "Velocity"),
]


@dataclass
class Xonic10Reading:
    """One parsed line of Xonic10 ASCII telemetry."""

    label: str
    instant_flow: float
    accumulated_flow: float
    status: str
    velocity: float


def parse_line(line: str) -> Xonic10Reading:
    """Parse a single Xonic10 ASCII telemetry line.

    Numeric fields are fixed-width, sign-padded (e.g. "+   0.417"), so any
    internal whitespace between the sign and the digits is stripped before
    conversion to float (str.strip() alone only removes leading/trailing spaces).

    Args:
        line: Raw text line received from the Xonic10 device, e.g.
            "DEFAULT,+   0.417,+      76.419,0100000000, 0.042".

    Returns:
        The parsed Xonic10Reading.

    Raises:
        ValueError: If the line does not contain exactly 5 comma-separated fields.
    """
    parts = [p.strip() for p in line.strip().split(",")]
    if len(parts) != 5:
        raise ValueError(f"Unexpected Xonic10 line format: {line!r}")

    label, instant_flow_s, accumulated_flow_s, status_s, velocity_s = parts
    return Xonic10Reading(
        label=label,
        instant_flow=float(instant_flow_s.replace(" ", "")),
        accumulated_flow=float(accumulated_flow_s.replace(" ", "")),
        status=status_s,
        velocity=float(velocity_s.replace(" ", "")),
    )


def reset_buffer() -> None:
    """Discard any partially received line data and the retained packet display."""
    global _rx_buffer, _last_packet_hex
    _rx_buffer = b""
    _last_packet_hex = ""


def get_last_rx_text() -> str:
    """Return the most recently received raw ASCII line from the Xonic10 device.

    Returns:
        The last complete line of text received, or an empty string if none yet.
    """
    return _last_rx_text


def get_last_reading() -> Xonic10Reading | None:
    """Return the last successfully parsed Xonic10 reading, if any.

    Returns:
        The most recent Xonic10Reading, or None if no packet has parsed yet.
    """
    return _last_reading


def get_pending_hex() -> str:
    """Return the HEX bytes to display for the receive-packet debug view.

    While a new packet is still arriving (no terminator seen yet), this grows
    with each received byte. Once a packet is completed, its HEX is retained
    as-is until the next packet starts arriving.

    Returns:
        Upper-case hexadecimal string of the in-progress or last completed packet.
    """
    if _rx_buffer:
        return _rx_buffer.hex().upper()
    return _last_packet_hex


def _consume_buffer(channel: int) -> list[tuple[str, Xonic10Reading | None]]:
    """Read newly received bytes and split off all complete Xonic10 packets.

    Lines may be terminated by CR, LF, or CRLF. Incomplete trailing bytes (no
    terminator yet) are kept internally and combined with data from the next
    call. An empty line (a terminator with no data before it) is discarded
    silently and never treated as a packet.

    Args:
        channel: Serial channel number the Xonic10 device is connected to.

    Returns:
        A list of (raw_text, reading) pairs for every completed packet, oldest
        first. reading is None when the packet text failed to parse, but the
        packet still counts as "received" (updates _last_rx_text/_last_packet_hex).
    """
    global _rx_buffer, _last_rx_text, _last_activity_ts, _last_packet_hex, _last_reading

    chunk, n = submode.Get_Modbus_Reveive_Data(channel)
    if n > 0:
        _rx_buffer += chunk
        _last_activity_ts = time.time()

    packets: list[tuple[str, Xonic10Reading | None]] = []
    while True:
        idx_lf = _rx_buffer.find(b"\n")
        idx_cr = _rx_buffer.find(b"\r")
        candidates = [i for i in (idx_lf, idx_cr) if i != -1]
        if not candidates:
            break

        idx = min(candidates)
        terminator_len = 1
        line = _rx_buffer[:idx]
        rest = _rx_buffer[idx + 1:]
        if _rx_buffer[idx:idx + 1] == b"\r" and rest[:1] == b"\n":
            rest = rest[1:]
            terminator_len = 2

        raw_packet = _rx_buffer[:idx + terminator_len]
        _rx_buffer = rest

        text = line.decode("ascii", errors="ignore").strip()
        if not text:
            # Bare CR/LF with nothing before it: discard, not a packet or error.
            continue

        _last_packet_hex = raw_packet.hex().upper()
        _last_rx_text = text
        try:
            reading = parse_line(text)
            _last_reading = reading
            packets.append((text, reading))
        except ValueError:
            packets.append((text, None))

    return packets


def read_available_readings(channel: int = XONIC10_CHANNEL) -> list[Xonic10Reading]:
    """Read newly received bytes and parse all complete Xonic10 lines.

    Lines that fail to parse are skipped silently.

    Args:
        channel: Serial channel number the Xonic10 device is connected to.

    Returns:
        A list of readings parsed from newly completed lines, oldest first.
    """
    return [reading for _, reading in _consume_buffer(channel) if reading is not None]


def read_latest_reading(channel: int = XONIC10_CHANNEL) -> Xonic10Reading | None:
    """Read and return only the most recent complete Xonic10 reading, if any.

    Args:
        channel: Serial channel number the Xonic10 device is connected to.

    Returns:
        The latest parsed reading, or None when no complete line arrived.
    """
    readings = read_available_readings(channel)
    return readings[-1] if readings else None


def poll_monitor_values(
    channel: int = XONIC10_CHANNEL,
    device_id: int | None = None,
    timeout_sec: float = 10.0,
    on_progress=None,
) -> list[tuple[str, str]]:
    """Wait for the next complete Xonic10 packet and format it for UI display/logging.

    The timeout is measured from the last time any byte was received, not from
    the start of the call: as long as data keeps arriving at least once every
    timeout_sec seconds, waiting continues even past timeout_sec in total.

    As soon as any CR/LF-terminated packet is received, this call resolves
    immediately: it returns formatted values on a successful parse, or raises
    ValueError if the packet text could not be parsed. It never keeps waiting
    for a "good" packet while discarding unparseable ones.

    Args:
        channel: Serial channel number the Xonic10 device is connected to.
        device_id: Unused; accepted so callers can poll every channel through the
            same (channel, device_id, timeout_sec) -> values interface.
        timeout_sec: Maximum time to wait without receiving any byte before giving up.
        on_progress: Optional callable() invoked immediately every time new bytes
            are received, so callers can refresh a live "pending hex" display
            without waiting for the whole line to complete.

    Returns:
        A list of (title, formatted_value) pairs matching MONITOR_ITEMS.

    Raises:
        TimeoutError: If no byte is received for timeout_sec seconds.
        ValueError: If a complete packet was received but could not be parsed.
    """
    last_seen = time.time()
    packets: list[tuple[str, Xonic10Reading | None]] = []
    while time.time() - last_seen < timeout_sec:
        packets = _consume_buffer(channel)
        if _last_activity_ts is not None and _last_activity_ts > last_seen:
            last_seen = _last_activity_ts
            if on_progress is not None:
                on_progress()
        if packets:
            break
        time.sleep(0.002)

    if not packets:
        raise TimeoutError("No Xonic10 data received")

    text, reading = packets[-1]
    if reading is None:
        raise ValueError(f"Failed to parse Xonic10 packet: {text!r}")

    values: list[tuple[str, str]] = []
    for field_name, title in MONITOR_ITEMS:
        raw = getattr(reading, field_name)
        values.append((title, f"{raw:.6f}" if isinstance(raw, float) else str(raw)))
    return values
