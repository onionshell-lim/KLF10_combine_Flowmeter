# -*- coding: utf-8 -*-

from __future__ import annotations

import os
import threading
import time
import tkinter as tk
import tkinter.font as tkfont
from tkinter import ttk, messagebox
from datetime import datetime
"""  """
import submode
import X10_comm
from device_comm_frame import AUTO_MONITOR_ITEMS, read_single_monitor_value

POPULAR_BAUDS = [4800, 9600, 38400, 115200]


def _xonic10_log_columns() -> list[str]:
    """Return the last Xonic10 instant flow/velocity for appending to a CSV log line.

    Returns:
        A 2-item list [instant_flow, velocity] formatted as floats, or empty
        strings when no Xonic10 packet has been parsed yet.
    """
    reading = X10_comm.get_last_reading()
    if reading is None:
        return ["", ""]
    return [f"{reading.instant_flow:.6f}", f"{reading.velocity:.6f}"]


def _poll_modbus_monitor_values(
    channel: int, device_id: int, timeout_sec: float, on_progress=None
) -> list[tuple[str, str]]:
    """Poll the Modbus-based flowmeter monitor items (FC4 reads) for one channel.

    Args:
        channel: Serial channel number to communicate on.
        device_id: Modbus slave ID to query.
        timeout_sec: Maximum time to wait for each register response.
        on_progress: Unused; accepted for interface parity with X10_comm.poll_monitor_values.

    Returns:
        A list of (title, formatted_value) pairs matching AUTO_MONITOR_ITEMS.
    """
    values: list[tuple[str, str]] = []
    for address, title in AUTO_MONITOR_ITEMS:
        value = read_single_monitor_value(device_id, address, timeout_sec=timeout_sec, channel=channel)
        values.append((title, f"{value:.6f}"))
        time.sleep(0.05)
    return values


class _ChannelPanel(ttk.LabelFrame):
    """UI panel for opening/closing a single serial channel and auto-logging its values."""

    def __init__(
        self,
        master,
        channel: int,
        title: str,
        monitor_titles: list[str],
        poll_values,
        on_status_change,
        show_auto_buttons: bool = True,
        auto_start_on_open: bool = False,
        tx_row_label: str = "송신 패킷 (HEX)",
        ascii_rx_source=None,
        rx_hex_source=None,
        poll_timeout_sec: float = 0.2,
        loop_interval_sec: float = 0.1,
        extra_log_columns=None,
        create_log_file: bool = True,
        log_header: str | None = None,
    ):
        """Initialize the channel panel UI.

        Args:
            master: Parent widget for this panel.
            channel: Channel number (1 or 2) this panel controls.
            title: Display title shown on the panel's border.
            monitor_titles: Display titles for the auto-logged monitor rows.
            poll_values: Callable(channel, device_id, timeout_sec) -> list[(title, value_str)]
                used to fetch one round of monitor values for auto-logging.
            on_status_change: Callback invoked as on_status_change(channel, is_open)
                when this channel's open state changes.
            show_auto_buttons: Whether to show manual Auto Start/Auto Stop buttons.
            auto_start_on_open: Whether to automatically start auto-logging as soon
                as the port is opened, instead of requiring a manual Auto Start click.
            tx_row_label: Label text for the first debug row (defaults to the
                transmitted HEX packet row; can be repurposed via ascii_rx_source).
            ascii_rx_source: Optional callable() -> str returning the last raw ASCII
                line received. When provided, the first debug row shows this text
                instead of the transmitted HEX frame (used for ASCII-only protocols).
            rx_hex_source: Optional callable() -> str overriding the "수신 패킷 (HEX)"
                row content (e.g. a growing pending-bytes hex string) instead of the
                default last-read-chunk hex from submode.
            poll_timeout_sec: Maximum time to wait for a response/line on each
                auto-logging poll.
            loop_interval_sec: Delay between the end of one poll and the start of
                the next; use a small value for high-speed/async reception.
            extra_log_columns: Optional callable() -> list[str] returning additional
                CSV fields appended to the end of every logged line.
            create_log_file: Whether Auto Start should create/write a CSV log file
                for this channel. Set False for channels whose data is only used
                by another channel's log (e.g. an ASCII-only sensor feed).
            log_header: Optional comment line written as the first line of a newly
                created CSV log file (only written when the file did not already
                exist before opening).
        """
        super().__init__(master, text=title)
        self.channel = channel
        self.monitor_titles = monitor_titles
        self.poll_values = poll_values
        self.on_status_change = on_status_change
        self.auto_start_on_open = auto_start_on_open
        self.ascii_rx_source = ascii_rx_source
        self.rx_hex_source = rx_hex_source
        self.poll_timeout_sec = poll_timeout_sec
        self.loop_interval_sec = loop_interval_sec
        self.extra_log_columns = extra_log_columns
        self.create_log_file = create_log_file
        self.log_header = log_header

        self.port_var = tk.StringVar()
        self.baud_var = tk.StringVar(value=str(9600))

        # UI
        row = 0
        ttk.Label(self, text="Serial Port").grid(row=row, column=0, sticky="w", padx=6, pady=6)
        self.port_combo = ttk.Combobox(self, textvariable=self.port_var, state="readonly", width=20)
        self.port_combo.grid(row=row, column=1, sticky="w", padx=6, pady=6)
        row += 1

        ttk.Label(self, text="Baudrate").grid(row=row, column=0, sticky="w", padx=6, pady=6)
        self.baud_combo = ttk.Combobox(
            self, textvariable=self.baud_var, state="readonly", width=20,
            values=[str(b) for b in POPULAR_BAUDS]
        )
        self.baud_combo.grid(row=row, column=1, sticky="w", padx=6, pady=6)
        row += 1

        self.open_btn = ttk.Button(self, text="포트 열기", command=self.open_port)
        self.open_btn.grid(row=row, column=0, padx=6, pady=6, sticky="we")

        self.close_btn = ttk.Button(self, text="포트 닫기", command=self.close_port)
        self.close_btn.grid(row=row, column=1, padx=6, pady=6, sticky="we")
        row += 1

        if show_auto_buttons:
            self.auto_start_btn = ttk.Button(self, text="Auto Start", command=self.start_auto_logging)
            self.auto_start_btn.grid(row=row, column=0, padx=6, pady=6, sticky="we")

            self.auto_stop_btn = ttk.Button(self, text="Auto Stop", command=self.stop_auto_logging)
            self.auto_stop_btn.grid(row=row, column=1, padx=6, pady=6, sticky="we")
            row += 1
        else:
            self.auto_start_btn = None
            self.auto_stop_btn = None

        ttk.Label(self, text="통신 상태").grid(row=row, column=0, sticky="w", padx=6, pady=6)
        self.status_lbl = ttk.Label(self, text="닫힘", width=20)
        self.status_lbl.grid(row=row, column=1, sticky="w", padx=6, pady=6)
        row += 1

        self.monitor_value_vars: dict[str, tk.StringVar] = {}
        self.success_count = 0
        self.fail_count = 0
        self.success_count_var = tk.StringVar(value="0")
        self.fail_count_var = tk.StringVar(value="0")

        for title in self.monitor_titles:
            ttk.Label(self, text=title).grid(row=row, column=0, sticky="w", padx=6, pady=2)
            value_var = tk.StringVar(value="--")
            self.monitor_value_vars[title] = value_var
            ttk.Label(self, textvariable=value_var, width=24, anchor="w").grid(
                row=row, column=1, sticky="w", padx=6, pady=2
            )
            row += 1

        ttk.Label(self, text="성공 카운터").grid(row=row, column=0, sticky="w", padx=6, pady=6)
        ttk.Label(self, textvariable=self.success_count_var, width=12, anchor="w").grid(
            row=row, column=1, sticky="w", padx=6, pady=6
        )
        row += 1

        ttk.Label(self, text="실패 카운터").grid(row=row, column=0, sticky="w", padx=6, pady=6)
        ttk.Label(self, textvariable=self.fail_count_var, width=12, anchor="w").grid(
            row=row, column=1, sticky="w", padx=6, pady=6
        )
        row += 1

        ttk.Label(self, text=tx_row_label).grid(row=row, column=0, sticky="w", padx=6, pady=(8, 2))
        self.tx_packet_var = tk.StringVar(value="--")
        ttk.Label(self, textvariable=self.tx_packet_var, width=60, anchor="w", wraplength=420).grid(
            row=row, column=1, sticky="w", padx=6, pady=(8, 2)
        )
        row += 1

        ttk.Label(self, text="수신 패킷 (HEX)").grid(row=row, column=0, sticky="w", padx=6, pady=(2, 6))
        self.rx_packet_var = tk.StringVar(value="--")
        ttk.Label(self, textvariable=self.rx_packet_var, width=60, anchor="w", wraplength=420).grid(
            row=row, column=1, sticky="w", padx=6, pady=(2, 6)
        )
        row += 1

        self.refresh_ports()

        self._auto_running = False
        self._auto_thread: threading.Thread | None = None
        self._auto_file = None
        self._auto_device_id = 1
        self._poll_status_after = None

        # 주기적 상태 업데이트
        self._schedule_poll_status()

    def destroy(self):
        """Cancel pending polling callbacks before destroying the panel."""
        if getattr(self, "_poll_status_after", None) is not None:
            try:
                self.after_cancel(self._poll_status_after)
            except Exception:
                pass
            self._poll_status_after = None
        super().destroy()

    def _schedule_poll_status(self):
        """Schedule the next connection-status update only while the widget remains alive."""
        if not self.winfo_exists():
            return
        self._poll_status_after = self.after(500, self._poll_status)

    def refresh_ports(self):
        """Refresh the available port list from the submode layer."""
        ports = submode.Get_Active_SerialPort()
        self.port_combo["values"] = ports
        if ports and not self.port_var.get():
            self.port_var.set(ports[0])

    def open_port(self):
        """Open the selected serial port using the current UI settings."""
        self.refresh_ports()
        port = self.port_var.get().strip()
        if not port:
            messagebox.showerror("오류", "Serial Port를 선택하세요.")
            return

        baud = int(self.baud_var.get())
        ok = submode.Set_SerialPort(baud, "N", 1, channel=self.channel)
        if not ok:
            messagebox.showerror("오류", "Baud/Parity/StopBit 설정값이 유효하지 않습니다.")
            return

        opened = submode.Open_SerialPort(port, channel=self.channel)
        if not opened:
            err = submode.Get_Last_Serial_Error(self.channel) if hasattr(submode, "Get_Last_Serial_Error") else ""
            messagebox.showerror("오류", f"포트 열기 실패: {port}\n{err}")

        self._update_status()

        if opened and self.auto_start_on_open:
            self.start_auto_logging()

    def close_port(self):
        """Close the currently open serial port and refresh the UI state."""
        self.stop_auto_logging()
        submode.Close_SerialPort(channel=self.channel)
        self._update_status()

    def start_auto_logging(self):
        """Start repeated polling of the monitored values and save them to a CSV file."""
        if not submode.Is_SerialPort_Open(self.channel):
            messagebox.showerror("오류", "먼저 포트를 열어주세요.")
            return
        if self._auto_running:
            return

        self.success_count = 0
        self.fail_count = 0
        self.success_count_var.set("0")
        self.fail_count_var.set("0")
        self.tx_packet_var.set("--")
        self.rx_packet_var.set("--")
        for title in self.monitor_value_vars:
            self.monitor_value_vars[title].set("--")

        if self.create_log_file:
            timestamp = datetime.now().strftime("%Y-%m-%d-%H-%M-%S")
            filename = f"KLF-CH{self.channel}-{timestamp}.csv"
            is_new_file = not os.path.exists(filename)
            self._auto_file = open(filename, "a", encoding="utf-8")
            if is_new_file and self.log_header:
                self._auto_file.write(self.log_header + "\n")
                self._auto_file.flush()
        else:
            self._auto_file = None
        self._auto_running = True
        if self.auto_start_btn is not None:
            self.auto_start_btn.config(state="disabled")
        if self.auto_stop_btn is not None:
            self.auto_stop_btn.config(state="normal")

        self._auto_thread = threading.Thread(target=self._auto_logging_loop, daemon=True)
        self._auto_thread.start()

    def stop_auto_logging(self):
        """Stop the repeated polling loop and close the CSV file."""
        if not self._auto_running:
            return

        self._auto_running = False
        if self._auto_thread is not None:
            self._auto_thread.join(timeout=0.5)
        if self._auto_file is not None:
            self._auto_file.close()
            self._auto_file = None
        if self.auto_start_btn is not None:
            self.auto_start_btn.config(state="normal")
        if self.auto_stop_btn is not None:
            self.auto_stop_btn.config(state="disabled")

    def _auto_logging_loop(self):
        """Repeatedly read the monitored values and update the UI counters and CSV file."""
        while self._auto_running:
            if not submode.Is_SerialPort_Open(self.channel):
                break

            try:
                read_values = self.poll_values(
                    self.channel, self._auto_device_id, self.poll_timeout_sec,
                    on_progress=self._schedule_packet_debug_update,
                )
                self.success_count += 1
                self._schedule_monitor_update(read_values, self.success_count, self.fail_count)
            except Exception:
                self.fail_count += 1
                failed_values = [(title, "ERROR") for title in self.monitor_titles]
                self._schedule_monitor_update(failed_values, self.success_count, self.fail_count)

            self._schedule_packet_debug_update()

            if self._auto_file is not None:
                ts = datetime.now()
                values_text = ",".join(value for _, value in read_values) if 'read_values' in locals() else ",".join("ERROR" for _ in self.monitor_titles)
                if self.extra_log_columns is not None:
                    try:
                        extra_values = self.extra_log_columns()
                    except Exception:
                        extra_values = []
                    if extra_values:
                        values_text += "," + ",".join(extra_values)
                line = f"{ts.strftime('%Y-%m-%d')},{ts.strftime('%H:%M:%S')},{values_text}\n"
                self._auto_file.write(line)
                self._auto_file.flush()

            time.sleep(self.loop_interval_sec)

        if self._auto_file is not None:
            try:
                self._auto_file.close()
            except Exception:
                pass
            self._auto_file = None

    def _schedule_monitor_update(self, values: list[tuple[str, str]], success_count: int, fail_count: int):
        """Schedule UI updates from the background thread on the main Tkinter thread."""
        self.after(0, lambda: self._apply_monitor_update(values, success_count, fail_count))

    def _apply_monitor_update(self, values: list[tuple[str, str]], success_count: int, fail_count: int):
        """Apply the latest monitoring values and counters to the UI widgets."""
        for title, value in values:
            if title in self.monitor_value_vars:
                self.monitor_value_vars[title].set(value)
        self.success_count_var.set(str(success_count))
        self.fail_count_var.set(str(fail_count))

    def _schedule_packet_debug_update(self):
        """Schedule the packet debug labels to refresh from the shared serial wrapper."""
        self.after(0, self._apply_packet_debug_update)

    def _apply_packet_debug_update(self):
        """Apply the latest transmit/receive debug info to the debug labels."""
        if self.ascii_rx_source is not None:
            self.tx_packet_var.set(self.ascii_rx_source() or "--")
        else:
            self.update_packet_debug(tx_frame=submode.Get_Last_Tx_Frame(self.channel))

        if self.rx_hex_source is not None:
            self.rx_packet_var.set(self.rx_hex_source() or "--")
        else:
            self.update_packet_debug(rx_frame=submode.Get_Last_Rx_Frame(self.channel))

    def update_packet_debug(self, tx_frame: bytes | None = None, rx_frame: bytes | None = None):
        """Update the debug packet display with hexadecimal data."""
        if tx_frame is not None:
            self.tx_packet_var.set(tx_frame.hex().upper())
        if rx_frame is not None:
            self.rx_packet_var.set(rx_frame.hex().upper())

    def _update_status(self):
        """Update the displayed connection state and notify the parent callback."""
        is_open = submode.Is_SerialPort_Open(self.channel)
        self.status_lbl.config(text="열림" if is_open else "닫힘")
        self.on_status_change(self.channel, is_open)

    def _poll_status(self):
        """Periodically refresh the connection status label."""
        if not self.winfo_exists():
            return
        self._update_status()
        self._schedule_poll_status()


class PortConfigFrame(ttk.Frame):
    """Tkinter frame hosting two independent serial-port channel panels."""

    def __init__(self, master, on_status_change):
        """Initialize the port configuration UI with two selectable serial channels.

        Args:
            master: Parent widget for this frame.
            on_status_change: Callback invoked as on_status_change(is_open) where
                is_open is True when at least one of the two channels is open.
        """
        super().__init__(master)
        self.on_status_change = on_status_change
        self._channel_open_state: dict[int, bool] = {1: False, 2: False}

        self._apply_font_scaling()

        self.channel1 = _ChannelPanel(
            self,
            channel=1,
            title="Radar Flowmeter",
            monitor_titles=[title for _, title in AUTO_MONITOR_ITEMS],
            poll_values=_poll_modbus_monitor_values,
            on_status_change=self._on_channel_status_change,
            extra_log_columns=_xonic10_log_columns,
            log_header=(
                "# 순서: 날짜,시간,Real-time velocity, Avg. velocity, "
                "Instant. flow rate, Cumulative flow, Water level, X10 Flow, X10 Velocity"
            ),
        )
        self.channel1.grid(row=0, column=0, sticky="nsew", padx=8, pady=8)

        self.channel2 = _ChannelPanel(
            self,
            channel=2,
            title="Xonic10",
            monitor_titles=[title for _, title in X10_comm.MONITOR_ITEMS],
            poll_values=X10_comm.poll_monitor_values,
            on_status_change=self._on_channel_status_change,
            show_auto_buttons=False,
            auto_start_on_open=True,
            tx_row_label="수신",
            ascii_rx_source=X10_comm.get_last_rx_text,
            rx_hex_source=X10_comm.get_pending_hex,
            poll_timeout_sec=10.0,
            loop_interval_sec=0.0,
            create_log_file=False,
        )
        self.channel2.grid(row=0, column=1, sticky="nsew", padx=8, pady=8)

        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)

    def _apply_font_scaling(self):
        """Increase the default Tk/ttk font size after the root window exists."""
        default_font = tkfont.nametofont("TkDefaultFont")
        size = max(10, int(default_font.cget("size") * 1.5))
        default_font.configure(size=size)

        style = ttk.Style(self)
        family = default_font.cget("family")
        style.configure(".", font=(family, size))
        style.configure("TLabel", font=(family, size))
        style.configure("TButton", font=(family, size))
        style.configure("TCombobox", font=(family, size))

    def _on_channel_status_change(self, channel: int, is_open: bool):
        """Track per-channel open state and notify the parent when any state changes.

        Args:
            channel: Channel number (1 or 2) whose state changed.
            is_open: True when that channel's port is now open.
        """
        self._channel_open_state[channel] = is_open
        self.on_status_change(any(self._channel_open_state.values()))
