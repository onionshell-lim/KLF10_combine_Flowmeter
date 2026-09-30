# -*- coding: utf-8 -*-

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

import submode
from device_comm_frame import DeviceCommFrame
from manage_files import ManageFilesFrame
from ML_1 import ML1Frame
from multi_graph import MultiGraphFrame
from port_config_frame import PortConfigFrame
from raw_draw import RawDrawFrame


class ModbusToolApp(tk.Tk):
    """Main Tkinter application window for the KLF110 Modbus RTU Collector."""

    def __init__(self):
        """Create the main notebook-based GUI and register the child frames."""
        super().__init__()
        self.title("KLF110 Modbus RTU Collector(RS485)")

        nb = ttk.Notebook(self)
        nb.pack(fill="both", expand=True)

        nb.add(PortConfigFrame(nb, on_status_change=self.on_status_change), text=" 포트 설정 ")
        nb.add(DeviceCommFrame(nb), text=" 장치 통신 ")
        nb.add(RawDrawFrame(nb), text=" 싱글 그래프 ")
        nb.add(ManageFilesFrame(nb), text=" Manage Files ")
        nb.add(MultiGraphFrame(nb), text=" 멀티 그래프 ")
        nb.add(ML1Frame(nb), text=" ML-1 ")

        self.geometry("2352x1480")
        self.protocol("WM_DELETE_WINDOW", self.on_close)

    def on_status_change(self, is_open: bool):
        """Handle serial connection state changes from the child frame.

        Args:
            is_open: True when the serial port is open.
        """
        pass

    def on_close(self):
        """Close the serial port and force the entire application to exit."""
        submode.Close_SerialPort(channel=1)
        submode.Close_SerialPort(channel=2)
        try:
            self.quit()
        except Exception:
            pass
        self.destroy()
