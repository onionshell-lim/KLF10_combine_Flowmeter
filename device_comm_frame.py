# -*- coding: utf-8 -*-

from __future__ import annotations

import queue
import struct
import threading
import time
import tkinter as tk
from tkinter import ttk, messagebox

import submode
from modbus_protocol import try_extract_response_any, to_hex_string

FC_MENU = [
    ("0x01:Read Coil Status", 0x01),
    ("0x02:Read Input Status", 0x02),
    ("0x03:Read Holding Reg", 0x03),
    ("0x04:Read Input Reg.", 0x04),
    ("0x06:Write Integer", 0x06),
    ("0x10:Write Floating Point", 0x10),
    ("0x41:Clear the Cumulative", 0x41),
]

COMMON_FLOAT_TITLE = {
    0x0001: "Real-time velocity",
    0x0003: "Average velocity",
    0x0102: "Instantaneous flow rate",
    0x0105: "Cumulative flow",
    0x010B: "Empty height",
    0x010D: "Water level",
    0x2251: "Water level sensor range",
    0x2253: "Low level adjustment",
    0x2255: "High level adjustment",
    0x2257: "Blind zone",
    0x2259: "Distance offset",
}

AUTO_MONITOR_ITEMS = [
    (0x0001, "Real-time velocity"),
    (0x0003, "Average velocity"),
    (0x0102, "Instantaneous flow rate"),
    (0x0105, "Cumulative flow"),
    (0x010D, "Water level"),
]

CHANNEL_MODEL_ADDR = 0x220F
CHANNEL_MODEL_TITLE = "Channel flowcalculationmodel"

CHANNEL_MODEL_VALUE_TITLE = {
    0: "Rectangular",
    1: "Trapezoidal",
    2: "Rectangular–Trapezoidal",
    3: "DoubleTrapezoidal",
    4: "U-shaped",
    5: "Irregula",
}


def _mk_map(*pairs):
    """Create an address-to-title mapping that allows duplicate addresses.

    Args:
        *pairs: Address/title pairs to include in the mapping.

    Returns:
        A dictionary mapping each address to a list of titles.
    """
    m: dict[int, list[str]] = {}
    for addr, title in pairs:
        m.setdefault(addr, []).append(title)
    return m


MODEL_FLOAT_TITLE: dict[int, dict[int, list[str]]] = {
    0: _mk_map(
        (0x2201, "Rectangular-channel width"),
        (0x2205, "Rectangular-channel height"),
        (0x2203, "Rectangular-distance from flow meter to channel wall"),
    ),
    1: _mk_map(
        (0x2201, "Trapezoidal channel top width"),
        (0x2203, "Trapezoidal channel bottom width"),
        (0x2205, "Trapezoidal channel height"),
        (0x2207, "Trapezoidal-distance from flowmeter to channel wall"),
    ),
    2: _mk_map(
        (0x2201, "Rectangular-trapezoidal channel top width"),
        (0x2203, "Rectangular-trapezoidal channel bottom width"),
        (0x2205, "Rectangular-trapezoidal channel upper height"),
        (0x2207, "Rectangular-trapezoidal channel lower height"),
        (0x2209, "Rectangular-trapezoidal-distance from flowmeter to channel wall"),
    ),
    3: _mk_map(
        (0x2201, "Double trapezoidal channel top width"),
        (0x2203, "Double trapezoidal channel middle width"),
        (0x2205, "Double trapezoidal channel bottom width"),
        (0x2207, "Double trapezoidal channel upper height"),
        (0x2209, "Double trapezoidal channel lower height"),
        (0x220B, "Double trapezoidal-distance from flowmeter to channel wall"),
    ),
    4: _mk_map(
        (0x2201, "U-shaped channel width"),
        (0x2203, "U-shaped channel height"),
        (0x2201, "Distance from flow meter to irregular channel wall"),
    ),
    5: _mk_map(
        (0x2203, "Irregular channel width"),
        (0x2271, "Irregular-bottom elevation"),
    ),
}


def _parse_hex_u16(s: str) -> int:
    """Parse a hexadecimal string into an unsigned 16-bit integer.

    Args:
        s: Hexadecimal text such as "0102" or "0x0102".

    Returns:
        The parsed unsigned 16-bit integer.
    """
    s = s.strip()
    v = int(s, 16) if not s.lower().startswith("0x") else int(s, 16)
    if not (0 <= v <= 0xFFFF):
        raise ValueError("u16 out of range")
    return v


def _parse_hex_byte(s: str) -> int:
    """Parse a hexadecimal string into an unsigned 8-bit integer.

    Args:
        s: Hexadecimal text such as "FF" or "0x0A".

    Returns:
        The parsed unsigned 8-bit integer.
    """
    s = s.strip()
    v = int(s, 16) if not s.lower().startswith("0x") else int(s, 16)
    if not (0 <= v <= 0xFF):
        raise ValueError("byte out of range")
    return v


def _float_from_4bytes_reorder(b4: bytes) -> float:
    """
    value: 수신 데이터 4byte를 32-bit float로 변환
    변환 순서: [2][3][0][1]
    """
    if len(b4) != 4:
        raise ValueError("need 4 bytes")
    reordered = bytes([b4[2], b4[3], b4[0], b4[1]])
    return struct.unpack(">f", reordered)[0]


def _double_from_8bytes_reorder(b8: bytes) -> float:
    """Convert 8-byte Modbus input-register data into a 64-bit double.

    The device encodes the 64-bit floating-point value in a non-standard byte
    order when returned over Modbus: [7,8,5,6,3,4,1,2] in 1-based indexing,
    which corresponds to the sequence [b8[6], b8[7], b8[4], b8[5], b8[2],
    b8[3], b8[0], b8[1]].

    Args:
        b8: Raw 8-byte register payload.

    Returns:
        The decoded 64-bit float value.
    """
    if len(b8) != 8:
        raise ValueError("need 8 bytes")
    reordered = bytes([b8[6], b8[7], b8[4], b8[5], b8[2], b8[3], b8[0], b8[1]])
    return struct.unpack(">d", reordered)[0]


def _get_data_region_from_rtu_frame(frame: bytes) -> tuple[int, bytes]:
    """
    정상 응답: [id][fc][byte_count][data...][crc_lo][crc_hi]
    반환: (fc, data)
    """
    if len(frame) < 5:
        raise ValueError("frame too short")
    fc = frame[1]
    if fc & 0x80:
        return fc, b""
    byte_count = frame[2]
    data = frame[3:-2]
    if len(data) != byte_count:
        raise ValueError("byte_count mismatch")
    return fc, data


def read_single_monitor_value(device_id: int, address: int, timeout_sec: float = 1.5, channel: int = 1) -> float:
    """Read a single floating-point value from the device via Modbus FC4.

    Args:
        device_id: Target slave ID.
        address: Register address to read from AUTO_MONITOR_ITEMS.
        timeout_sec: Maximum time to wait for a response.
        channel: Serial channel number (1 or 2) to communicate on.

    Returns:
        The parsed float value.
    """
    if not submode.Is_SerialPort_Open(channel):
        raise RuntimeError("Serial port is not open")

    if address == 0x0105:
        quantity = 0x0004
    else:
        quantity = 0x0002

    tx_payload = bytes([
        device_id & 0xFF,
        0x04,
        (address >> 8) & 0xFF,
        address & 0xFF,
        (quantity >> 8) & 0xFF,
        quantity & 0xFF,
    ])

    while True:
        _, n = submode.Get_Modbus_Reveive_Data(channel)
        if n == 0:
            break

    ok, _ = submode.Send_Modbus_Transmit_Data(6, tx_payload, channel)
    if not ok:
        raise RuntimeError(submode.Get_Last_Serial_Error(channel) if hasattr(submode, "Get_Last_Serial_Error") else "Send failed")

    start = time.time()
    buf = b""
    frame = None
    while time.time() - start < timeout_sec:
        chunk, n = submode.Get_Modbus_Reveive_Data(channel)
        if n > 0:
            buf += chunk
            found, remain = try_extract_response_any(buf, device_id, 0x04)
            if found is not None:
                frame = found
                buf = remain
                break
        time.sleep(0.02)

    if frame is None:
        raise TimeoutError("No response received")

    fc, data = _get_data_region_from_rtu_frame(frame)
    if fc not in (0x04,):
        raise ValueError(f"Unexpected function code: 0x{fc:02X}")

    if address == 0x0105:
        if len(data) < 8:
            raise ValueError("Response data too short for a double")
        return _double_from_8bytes_reorder(data[:8])

    if len(data) < 4:
        raise ValueError("Response data too short for a float")

    return _float_from_4bytes_reorder(data[:4])


class DeviceCommFrame(ttk.Frame):
    """Tkinter frame for sending Modbus requests and displaying responses."""

    def __init__(self, master):
        """Initialize the communication UI and internal state.

        Args:
            master: Parent widget for this frame.
        """
        super().__init__(master)

        self.Device_ID = 1
        self.Function_Code = 1
        self.Address = 0x0000
        self.Length = 6
        self.Payload = [0x00, 0x02]
        self.request_length = 0x0002

        self.channel_model: int | None = None

        self.device_id_var = tk.StringVar(value="1")
        self.fc_var = tk.StringVar(value=FC_MENU[2][0])
        self.addr_var = tk.StringVar(value="0000")
        self.len_var = tk.StringVar(value="6")
        self.p1_var = tk.StringVar(value="00")
        self.p2_var = tk.StringVar(value="02")

        self.tx_var = tk.StringVar(value="--")
        self.rx_var = tk.StringVar(value="--")

        self._result_q: "queue.Queue[tuple]" = queue.Queue()

        ttk.Label(self, text="장치 번호").grid(row=0, column=0, sticky="w", padx=6, pady=6)
        ttk.Combobox(
            self, textvariable=self.device_id_var, state="readonly", width=18,
            values=[str(i) for i in range(1, 17)]
        ).grid(row=0, column=1, sticky="w", padx=6, pady=6)

        ttk.Label(self, text="function code").grid(row=0, column=2, sticky="w", padx=6, pady=6)
        ttk.Combobox(
            self, textvariable=self.fc_var, state="readonly", width=22,
            values=[name for name, _ in FC_MENU]
        ).grid(row=0, column=3, sticky="w", padx=6, pady=6)

        ttk.Label(self, text="주소(HEX)").grid(row=1, column=0, sticky="w", padx=6, pady=6)
        ttk.Entry(self, textvariable=self.addr_var, width=20).grid(row=1, column=1, sticky="w", padx=6, pady=6)

        ttk.Label(self, text="길이(DEC)").grid(row=1, column=2, sticky="w", padx=6, pady=6)
        ttk.Entry(self, textvariable=self.len_var, width=20).grid(row=1, column=3, sticky="w", padx=6, pady=6)

        ttk.Label(self, text="Write 데이터(HEX byte) 2개").grid(row=2, column=0, sticky="w", padx=6, pady=6)
        pf = ttk.Frame(self)
        pf.grid(row=2, column=1, columnspan=3, sticky="w", padx=6, pady=6)
        ttk.Label(pf, text="P1").grid(row=0, column=0, padx=3)
        ttk.Entry(pf, textvariable=self.p1_var, width=8).grid(row=0, column=1, padx=3)
        ttk.Label(pf, text="P2").grid(row=0, column=2, padx=3)
        ttk.Entry(pf, textvariable=self.p2_var, width=8).grid(row=0, column=3, padx=3)

        ttk.Button(self, text="요청 전송", command=self.send_request).grid(
            row=3, column=0, columnspan=4, sticky="we", padx=6, pady=6
        )

        ttk.Label(self, text="송신(HEX)").grid(row=4, column=0, sticky="w", padx=6, pady=6)
        ttk.Entry(self, textvariable=self.tx_var, width=90, state="readonly").grid(
            row=4, column=1, columnspan=3, sticky="we", padx=6, pady=6
        )

        ttk.Label(self, text="수신(HEX)").grid(row=5, column=0, sticky="w", padx=6, pady=6)
        ttk.Entry(self, textvariable=self.rx_var, width=90, state="readonly").grid(
            row=5, column=1, columnspan=3, sticky="we", padx=6, pady=6
        )

        ttk.Label(self, text='데이터 표시 (address:data)  / data는 16bit HEX').grid(row=6, column=0, sticky="w", padx=6, pady=6)
        self.data_text = tk.Text(self, height=10, width=90)
        self.data_text.grid(row=7, column=0, columnspan=4, sticky="nsew", padx=6, pady=6)

        ttk.Label(self, text='항목 표시 (title:value)').grid(row=8, column=0, sticky="w", padx=6, pady=6)
        self.item_text = tk.Text(self, height=10, width=90)
        self.item_text.grid(row=9, column=0, columnspan=4, sticky="nsew", padx=6, pady=6)

        self.grid_columnconfigure(1, weight=1)
        self.grid_columnconfigure(3, weight=1)
        self.grid_rowconfigure(7, weight=1)
        self.grid_rowconfigure(9, weight=1)

        self._poll_results_after = None
        self._schedule_poll_results()

    def destroy(self):
        """Cancel queued polling callbacks before the frame is destroyed."""
        if getattr(self, "_poll_results_after", None) is not None:
            try:
                self.after_cancel(self._poll_results_after)
            except Exception:
                pass
            self._poll_results_after = None
        super().destroy()

    def _schedule_poll_results(self):
        """Schedule the result poll loop while the widget still exists."""
        if not self.winfo_exists():
            return
        self._poll_results_after = self.after(100, self._poll_results)

    def send_request(self):
        """Build and send a Modbus request based on the current UI values."""
        if not submode.Is_SerialPort_Open():
            messagebox.showerror("오류", "먼저 포트를 열어주세요.")
            return

        try:
            self.Device_ID = int(self.device_id_var.get())
            self.Function_Code = dict(FC_MENU)[self.fc_var.get()]
            self.Address = _parse_hex_u16(self.addr_var.get())

            self.Length = int(self.len_var.get().strip())
            if self.Length <= 0:
                raise ValueError

            p1 = _parse_hex_byte(self.p1_var.get())
            p2 = _parse_hex_byte(self.p2_var.get())
            self.Payload = [p1, p2]
            self.request_length = (p1 << 8) | p2

        except Exception:
            messagebox.showerror(
                "오류",
                "입력값을 확인하세요.\n"
                "- 주소: HEX (예: 0102 또는 0x0102)\n"
                "- 길이: DEC (보통 6)\n"
                "- Payload: HEX byte 2개(00~FF). (request_length=Payload big-endian)"
            )
            return

        fc = self.Function_Code

        if fc in (0x01, 0x02, 0x03, 0x04):
            tx_payload = bytes([
                self.Device_ID & 0xFF,
                fc & 0xFF,
                (self.Address >> 8) & 0xFF,
                self.Address & 0xFF,
                self.Payload[0],
                self.Payload[1],
            ])

        elif fc in (0x05, 0x06):
            tx_payload = bytes([
                self.Device_ID & 0xFF,
                fc & 0xFF,
                (self.Address >> 8) & 0xFF,
                self.Address & 0xFF,
                self.Payload[0],
                self.Payload[1],
            ])

        elif fc in (0x15, 0x16, 0x0F, 0x10):
            messagebox.showerror(
                "미지원",
                "Write Multiple(0x15/0x16)은 현재 UI 입력(2바이트 Payload)만으로는 데이터 블록이 부족합니다.\n"
                "추가 입력(Quantity, ByteCount, Data bytes)을 UI에 추가한 뒤 구현하는 것을 권장합니다."
            )
            return
        else:
            messagebox.showerror("오류", f"지원하지 않는 function code: 0x{fc:02X}")
            return

        if self.Length < 4:
            messagebox.showerror("오류", "길이(DEC)는 최소 4 이상이어야 합니다.")
            return
        if self.Length > len(tx_payload):
            messagebox.showerror("오류", f"길이(DEC)={self.Length} 이(가) payload 길이({len(tx_payload)})보다 큽니다.")
            return

        self.rx_var.set("--")
        self.data_text.delete("1.0", "end")
        self.item_text.delete("1.0", "end")

        while True:
            _, n = submode.Get_Modbus_Reveive_Data()
            if n == 0:
                break

        ok, tx_frame = submode.Send_Modbus_Transmit_Data(self.Length, tx_payload)
        if not ok:
            err = submode.Get_Last_Serial_Error() if hasattr(submode, "Get_Last_Serial_Error") else ""
            messagebox.showerror("오류", f"송신 실패\n{err}")
            return

        self.tx_var.set(to_hex_string(tx_frame))

        threading.Thread(
            target=self._wait_response_worker,
            args=(self.Device_ID, self.Function_Code, self.Address, self.request_length),
            daemon=True
        ).start()

    def _wait_response_worker(self, device_id: int, fc: int, address: int, request_length: int):
        """Background worker that waits for a matching RTU response.

        Args:
            device_id: Expected slave device ID.
            fc: Expected Modbus function code.
            address: Start address used for the request.
            request_length: Requested quantity or payload length.
        """
        timeout_sec = 1.5
        start = time.time()
        buf = b""
        frame = None

        while time.time() - start < timeout_sec:
            chunk, n = submode.Get_Modbus_Reveive_Data()
            if n > 0:
                buf += chunk
                found, remain = try_extract_response_any(buf, device_id, fc)
                if found is not None:
                    frame = found
                    buf = remain
                    break
            time.sleep(0.02)

        if frame is None:
            self._result_q.put(("no_response", None, None, None))
            return

        self._result_q.put(("ok", frame, address, request_length))

    def _poll_results(self):
        """Process queued response results and update the UI widgets."""
        try:
            while True:
                kind, frame, address, request_length = self._result_q.get_nowait()

                if kind == "no_response":
                    self.rx_var.set("--")
                    continue

                self.rx_var.set(to_hex_string(frame))

                fc = frame[1] & 0xFF
                if fc & 0x80:
                    exc = frame[2] if len(frame) > 2 else 0
                    self.data_text.delete("1.0", "end")
                    self.item_text.delete("1.0", "end")
                    self.data_text.insert("end", f"EXCEPTION: code=0x{exc:02X}\n")
                    self.item_text.insert("end", f"EXCEPTION: code=0x{exc:02X}\n")
                    continue

                WRITE_FCS = {0x06, 0x10, 0x41}
                if fc in WRITE_FCS:
                    self.data_text.delete("1.0", "end")
                    self.item_text.delete("1.0", "end")

                    if len(frame) < 8:
                        self.data_text.insert("end", "WRITE 응답 길이 오류(8바이트 미만)\n")
                        self.item_text.insert("end", "WRITE 응답 길이 오류(8바이트 미만)\n")
                        continue

                    addr = (frame[2] << 8) | frame[3]
                    val_or_qty = (frame[4] << 8) | frame[5]

                    self.data_text.insert("end", f"0x{addr:04X}:0x{val_or_qty:04X}\n")
                    self.item_text.insert(
                        "end",
                        f"WRITE_OK: FC=0x{fc:02X} ADDR=0x{addr:04X} VALUE/QTY=0x{val_or_qty:04X}\n"
                    )
                    continue

                try:
                    fc2, data = _get_data_region_from_rtu_frame(frame)
                except Exception as e:
                    self.data_text.delete("1.0", "end")
                    self.item_text.delete("1.0", "end")
                    self.data_text.insert("end", f"Parse error: {e}\n")
                    self.item_text.insert("end", f"Parse error: {e}\n")
                    continue

                self._render_data_hex16(fc2, address, data, request_length)
                self._render_items(fc2, address, data, request_length)

        except queue.Empty:
            pass

        if self.winfo_exists():
            self._schedule_poll_results()

    def _render_data_hex16(self, fc: int, start_addr: int, data: bytes, request_length: int):
        """Render parsed read-data values into the data display area.

        Args:
            fc: Modbus function code.
            start_addr: Starting register/coil address.
            data: Raw response data bytes.
            request_length: Requested quantity.
        """
        self.data_text.delete("1.0", "end")

        if fc in (3, 4):
            max_regs = min(request_length, len(data) // 2)
            for i in range(max_regs):
                hi = data[2*i]
                lo = data[2*i+1]
                val = (hi << 8) | lo
                self.data_text.insert("end", f"0x{(start_addr+i)&0xFFFF:04X}:0x{val:04X}\n")

        elif fc in (1, 2):
            bit_count = min(request_length, len(data) * 8)
            for i in range(bit_count):
                b = data[i // 8]
                bit = (b >> (i % 8)) & 0x01
                self.data_text.insert("end", f"0x{(start_addr+i)&0xFFFF:04X}:0x{bit:04X}\n")

        else:
            self.data_text.insert("end", "(지원하지 않는 function code)\n")

    def _render_items(self, fc: int, start_addr: int, data: bytes, request_length: int):
        """Render human-readable items and derived titles from response data.

        Args:
            fc: Modbus function code.
            start_addr: Starting register/coil address.
            data: Raw response data bytes.
            request_length: Requested quantity.
        """
        self.item_text.delete("1.0", "end")

        if fc not in (3, 4):
            self.item_text.insert("end", "(항목 표시: FC3/FC4에서만 동작)\n")
            return

        if start_addr == CHANNEL_MODEL_ADDR and len(data) >= 2:
            model_val = (data[0] << 8) | data[1]
            model_val = int(model_val) & 0xFFFF
            if model_val in CHANNEL_MODEL_VALUE_TITLE:
                self.channel_model = model_val
                self.item_text.insert("end", f"{CHANNEL_MODEL_TITLE}:{CHANNEL_MODEL_VALUE_TITLE[model_val]}\n")
            else:
                self.channel_model = None
                self.item_text.insert("end", f"{CHANNEL_MODEL_TITLE}:UNKNOWN({model_val})\n")
            return

        if start_addr == 0x0105:
            if len(data) < 8:
                self.item_text.insert("end", "(cumulative flow용 데이터 8바이트 부족)\n")
                return
            try:
                value = _double_from_8bytes_reorder(data[:8])
                self.item_text.insert("end", f"Cumulative flow:{value}\n")
            except Exception:
                self.item_text.insert("end", "(cumulative flow 변환 실패)\n")
            return

        if len(data) < 4:
            self.item_text.insert("end", "(float 변환용 데이터 4바이트 부족)\n")
            return

        float_groups = min(len(data) // 4, request_length // 2 if request_length >= 2 else len(data)//4)

        if self.channel_model is None and (start_addr & 0xFF00) == 0x2200:
            self.item_text.insert("end", "(Channel flowcalculationmodel 미확정: 0x220F를 먼저 읽으세요)\n")

        for i in range(float_groups):
            addr = (start_addr + i*2) & 0xFFFF
            chunk = data[i*4:(i+1)*4]

            try:
                fval = _float_from_4bytes_reorder(chunk)
            except Exception:
                continue

            title = None
            if addr in COMMON_FLOAT_TITLE:
                title = COMMON_FLOAT_TITLE[addr]
            else:
                if self.channel_model in MODEL_FLOAT_TITLE:
                    titles = MODEL_FLOAT_TITLE[self.channel_model].get(addr)
                    if titles:
                        title = " / ".join(titles)

            if title is None:
                title = f"0x{addr:04X}"

            self.item_text.insert("end", f"{title}:{fval}\n")
