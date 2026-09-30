# submode.py
# -*- coding: utf-8 -*-

"""Submode helper functions that wrap serial access and Modbus RTU transmission."""

from __future__ import annotations

from typing import List, Tuple, Optional

try:
    from serial.tools import list_ports
    import serial
except Exception:  # pragma: no cover - defensive for broken environments
    list_ports = None
    serial = None

from serial_comm import SerialManager
from modbus_crc import append_crc


class _ChannelState:
    """Holds the serial manager and settings for a single independent channel."""

    def __init__(self):
        self.manager = SerialManager()
        self.baudrate: int = 9600
        self.parity: str = "N"     # "N", "E", "O"
        self.stopbits: int = 1     # 1 or 2
        self.selected_port: Optional[str] = None
        self.last_tx_frame: bytes = b""
        self.last_rx_frame: bytes = b""


# 채널별 내부 상태 저장 (1, 2 두 개의 독립적인 Serial Port를 지원)
_channels: dict[int, _ChannelState] = {1: _ChannelState(), 2: _ChannelState()}


def _get_channel(channel: int) -> _ChannelState:
    """Return the internal state object for the given channel number.

    Args:
        channel: Channel number, 1 or 2.

    Returns:
        The `_ChannelState` instance associated with the channel.
    """
    if channel not in _channels:
        raise ValueError(f"Unsupported channel: {channel}")
    return _channels[channel]


def Get_Active_SerialPort() -> List[str]:
    """Return a list of available serial port names.

    Returns:
        A list of detected COM/TTY port device names.
    """
    ports = []
    if list_ports is None:
        return ports
    for p in list_ports.comports():
        # p.device: Windows -> "COM3", Linux -> "/dev/ttyUSB0"
        ports.append(p.device)
    return ports


def Set_SerialPort(baud_rate: int, Parity: str, Stop_Bit: int, channel: int = 1) -> bool:
    """Store the serial communication settings after validating them.

    Args:
        baud_rate: Baud rate value such as 4800, 9600, 38400, or 115200.
        Parity: One of "N", "E", or "O".
        Stop_Bit: One of 1 or 2.
        channel: Channel number (1 or 2) whose settings are being configured.

    Returns:
        True when the settings are accepted, otherwise False.
    """
    state = _get_channel(channel)

    popular = {4800, 9600, 19200, 38400, 57600, 115200}
    if baud_rate not in popular:
        return False

    if Parity not in ("N", "E", "O"):
        return False

    if Stop_Bit not in (1, 2):
        return False

    state.baudrate = int(baud_rate)
    state.parity = Parity
    state.stopbits = int(Stop_Bit)
    return True


def Open_SerialPort(SerialPort_No: str, channel: int = 1) -> bool:
    """Open the selected serial port using the stored communication settings.

    Args:
        SerialPort_No: The serial port name to open.
        channel: Channel number (1 or 2) to open the port on.

    Returns:
        True when the port is opened successfully, otherwise False.
    """
    state = _get_channel(channel)
    state.selected_port = SerialPort_No

    if state.manager.is_open():
        return True

    parity_map = {
        "N": "N",
        "E": "E",
        "O": "O",
    }
    stop_map = {
        1: 1,
        2: 2,
    }

    parity = parity_map.get(state.parity, "N")
    stopbits = stop_map.get(state.stopbits, 1)

    return state.manager.open(
        port=state.selected_port,
        baudrate=state.baudrate,
        parity=parity,
        stopbits=stopbits,
        timeout=0.05,
    )


def Get_Modbus_Reveive_Data(channel: int = 1) -> Tuple[bytes, int]:
    """Read and consume all currently buffered serial bytes.

    Args:
        channel: Channel number (1 or 2) to read from.

    Returns:
        A tuple of (data, byte_count).
    """
    state = _get_channel(channel)
    data = state.manager.read_received_all()
    if data:
        state.last_rx_frame = data
    return data, len(data)


def Send_Modbus_Transmit_Data(arg1, arg2, channel: int = 1) -> Tuple[bool, bytes]:
    """
    송신할 data와 byte 수를 받아 Modbus RTU(binary) 프레임으로 변환(CRC 추가) 후 송신
    - 입력 data는 'CRC 없는 payload'로 가정
    - 반환: (성공여부, 실제 송신 프레임(bytes))
    요구사항 반영:
      - GUI에서 Send_Modbus_Transmit_Data(Length, Payload) 로 호출
    동시에 기존 호환:
      - Send_Modbus_Transmit_Data(data, byte_count) 형태도 허용

    동작:
      - Payload(=CRC 없는 바이트열)에서 Length 바이트만 취해서 CRC 추가 후 송신
    """
    state = _get_channel(channel)

    # (Length, Payload) 형태
    if isinstance(arg1, int):
        byte_count = int(arg1)
        data = arg2
    else:
        # (data, byte_count) 형태 (기존)
        data = arg1
        byte_count = int(arg2)

    if isinstance(data, list):
        payload = bytes(data[:byte_count])
    else:
        payload = bytes(data[:byte_count])

    frame = append_crc(payload)
    ok = state.manager.write(frame)
    if ok:
        state.last_tx_frame = frame
    return ok, frame


def Close_SerialPort(channel: int = 1) -> None:
    """Port 닫고 수신 쓰레드 종료하고 Circular buffer free

    Args:
        channel: Channel number (1 or 2) to close.
    """
    state = _get_channel(channel)
    state.manager.close()
    state.selected_port = None
    state.last_tx_frame = b""
    state.last_rx_frame = b""


# (GUI 상태 표시용) - 요구사항 외 추가 헬퍼지만 독립모드에서 상태 표시가 필요하여 제공
def Is_SerialPort_Open(channel: int = 1) -> bool:
    """Report whether the serial port is currently open.

    Args:
        channel: Channel number (1 or 2) to check.

    Returns:
        True when the port is open, otherwise False.
    """
    return _get_channel(channel).manager.is_open()


def Get_Last_Tx_Frame(channel: int = 1) -> bytes:
    """Return the last transmitted RTU frame bytes.

    Args:
        channel: Channel number (1 or 2) to query.

    Returns:
        The most recent transmitted frame, or empty bytes if none.
    """
    return _get_channel(channel).last_tx_frame


def Get_Last_Rx_Frame(channel: int = 1) -> bytes:
    """Return the most recently read receive bytes.

    Args:
        channel: Channel number (1 or 2) to query.

    Returns:
        The latest bytes read from the serial port, or empty bytes if none.
    """
    return _get_channel(channel).last_rx_frame


def Get_Last_Serial_Error(channel: int = 1) -> str:
    """Return the most recent serial communication error string.

    Args:
        channel: Channel number (1 or 2) to query.

    Returns:
        The latest error message from the serial manager.
    """
    return _get_channel(channel).manager.last_error

#
# end of file
#