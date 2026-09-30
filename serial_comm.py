# serial_comm.py
# -*- coding: utf-8 -*-

"""Serial communication helpers for RS485/Modbus data transfer."""

from __future__ import annotations

import threading
import time
from typing import Optional

try:
    import serial
except Exception:  # pragma: no cover - defensive for broken environments
    serial = None

try:
    from serial.rs485 import RS485Settings  # pyserial의 RS485 지원
except Exception:  # pragma: no cover - defensive for broken environments
    RS485Settings = None


class CircularBuffer:
    """Fixed-size circular buffer for temporarily storing incoming serial bytes.

    Args:
        size: Buffer capacity in bytes.
    """

    def __init__(self, size: int = 1024):
        """Initialize the circular buffer with a fixed size.

        Args:
            size: Capacity of the buffer in bytes.
        """
        self._buf = bytearray(size)
        self._size = size
        self._head = 0
        self._tail = 0
        self._count = 0
        self._lock = threading.Lock()

    def write(self, data: bytes) -> None:
        """Write bytes into the buffer, overwriting oldest data when full.

        Args:
            data: Incoming bytes to append.
        """
        with self._lock:
            for b in data:
                self._buf[self._head] = b
                self._head = (self._head + 1) % self._size
                if self._count < self._size:
                    self._count += 1
                else:
                    self._tail = (self._tail + 1) % self._size

    def read_all(self) -> bytes:
        """Consume and return all buffered bytes.

        Returns:
            All available bytes from the buffer.
        """
        with self._lock:
            if self._count == 0:
                return b""
            out = bytearray()
            for _ in range(self._count):
                out.append(self._buf[self._tail])
                self._tail = (self._tail + 1) % self._size
            self._count = 0
            return bytes(out)

    def clear(self) -> None:
        """Clear all buffered bytes and reset indices."""
        with self._lock:
            self._head = 0
            self._tail = 0
            self._count = 0


class SerialManager:
    """High-level wrapper around pyserial with background RX handling."""

    def __init__(self):
        """Initialize serial state and runtime members."""
        self.ser = None
        self.rx_buffer: Optional[CircularBuffer] = None
        self._rx_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._lock = threading.Lock()
        self.last_error: str = ""

    def is_open(self) -> bool:
        """Check whether the serial port is currently open.

        Returns:
            True when a serial port is open, otherwise False.
        """
        return self.ser is not None and self.ser.is_open

    def open(
        self,
        port: str,
        baudrate: int,
        parity: str,
        stopbits: float,
        timeout: float = 0.05,
        enable_rs485_mode: bool = True,
    ) -> bool:
        """Open the serial port and start the RX reader thread.

        Args:
            port: COM port or tty device name.
            baudrate: Communication speed.
            parity: Serial parity setting.
            stopbits: Stop bit setting.
            timeout: Read timeout in seconds.
            enable_rs485_mode: Whether to enable RS485-specific settings if supported.

        Returns:
            True when opening succeeds, otherwise False.
        """
        with self._lock:
            self.last_error = ""
            if self.is_open():
                return True

            if serial is None or not hasattr(serial, "Serial"):
                self.last_error = "pyserial is not available in this Python environment"
                return False

            try:
                self.ser = serial.Serial(
                    port=port,
                    baudrate=baudrate,
                    parity=parity,
                    stopbits=stopbits,
                    bytesize=8,
                    timeout=timeout,
                    write_timeout=1.0,
                    xonxoff=False,
                    rtscts=False,
                    dsrdtr=False,
                )

                if enable_rs485_mode and RS485Settings is not None:
                    try:
                        self.ser.rs485_mode = RS485Settings(
                            rts_level_for_tx=True,
                            rts_level_for_rx=False,
                            delay_before_tx=0.0,
                            delay_before_rx=0.0,
                        )
                    except Exception:
                        # 지원 안 되는 환경/드라이버면 무시
                        pass

                # 버퍼 초기화
                try:
                    self.ser.reset_input_buffer()
                    self.ser.reset_output_buffer()
                except Exception:
                    pass

                self.rx_buffer = CircularBuffer(1024)
                self._stop_event.clear()
                self._rx_thread = threading.Thread(target=self._rx_loop, daemon=True)
                self._rx_thread.start()
                return True

            except Exception as e:
                self.last_error = f"open failed: {e}"
                self.ser = None
                self.rx_buffer = None
                return False

    def close(self) -> None:
        """Close the serial port and stop the background reader thread."""
        with self._lock:
            self._stop_event.set()
            try:
                if self._rx_thread and self._rx_thread.is_alive():
                    self._rx_thread.join(timeout=1.0)
            except Exception:
                pass

            try:
                if self.ser and self.ser.is_open:
                    self.ser.close()
            except Exception:
                pass

            self.ser = None
            self.rx_buffer = None
            self._rx_thread = None

    def _rx_loop(self) -> None:
        """Background loop that reads incoming serial data into the circular buffer."""
        while not self._stop_event.is_set():
            try:
                if not self.ser or not self.ser.is_open:
                    time.sleep(0.05)
                    continue

                n = self.ser.in_waiting
                if n <= 0:
                    # 최소 1바이트 읽기 (timeout으로 빠르게 반환)
                    chunk = self.ser.read(1)
                else:
                    chunk = self.ser.read(n)

                if chunk and self.rx_buffer:
                    self.rx_buffer.write(chunk)

            except Exception:
                # 예외 발생 시 약간 쉬었다가 계속
                time.sleep(0.1)

    def read_received_all(self) -> bytes:
        """Return and clear all data currently buffered from the RX thread.

        Returns:
            All bytes read so far from the port.
        """
        if not self.rx_buffer:
            return b""
        return self.rx_buffer.read_all()

    def clear_rx(self) -> None:
        """Clear the receive buffer contents."""
        if self.rx_buffer:
            self.rx_buffer.clear()

    def write(self, data: bytes) -> bool:
        """Write a byte sequence to the serial port.

        Args:
            data: Bytes to send.

        Returns:
            True when the full payload was written, otherwise False.
        """
        self.last_error = ""
        try:
            if not self.ser or not self.ser.is_open:
                self.last_error = "write failed: port not open"
                return False

            # 실제로 몇 바이트가 써졌는지 확인
            n = self.ser.write(data)
            self.ser.flush()

            if n != len(data):
                self.last_error = f"write short: wrote {n}/{len(data)} bytes"
                return False
            return True

        except Exception as e:
            self.last_error = f"write failed: {e}"
            return False

#
# end of file
#