# manage_files.py
# -*- coding: utf-8 -*-

from __future__ import annotations

import os
import re
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, ttk

import pandas as pd

BASE_FIELDS = [
    "date",
    "time",
    "Real-time velocity",
    "Avg. velocity",
    "Instant. flow rate",
    "Cumulative flow",
    "Water level",
]

EXTRA_FIELDS = ["펌프", "Label Velocity", "Label Flow"]


class ManageFilesFrame(ttk.Frame):
    """UI for selecting, filtering, and saving CSV datasets."""

    def __init__(self, master):
        super().__init__(master)
        self.pack(fill="both", expand=True, padx=8, pady=8)

        self.current_csv_path = ""
        self.base_check_vars = {}
        self.extra_check_vars = {}
        self.header_comment_lines = []

        self.source_var = tk.StringVar(value="")
        self.start_var = tk.StringVar(value="0")
        self.end_var = tk.StringVar(value="")
        self.status_var = tk.StringVar(value="")

        self.pump_value_var = tk.StringVar(value="0")
        self.label_velocity_var = tk.StringVar(value="")
        self.label_flow_var = tk.StringVar(value="")

        top_bar = ttk.Frame(self)
        top_bar.pack(fill="x")

        ttk.Button(top_bar, text="CSV 선택", command=self.select_csv).pack(side="left")
        ttk.Label(top_bar, textvariable=self.source_var, wraplength=800).pack(side="left", padx=(10, 0))

        range_frame = ttk.Frame(self)
        range_frame.pack(fill="x", pady=(12, 0))

        ttk.Label(range_frame, text="시작 위치").pack(side="left")
        ttk.Entry(range_frame, textvariable=self.start_var, width=10).pack(side="left", padx=(4, 12))

        ttk.Label(range_frame, text="마지막 위치").pack(side="left")
        ttk.Entry(range_frame, textvariable=self.end_var, width=10).pack(side="left", padx=(4, 12))

        ttk.Separator(self, orient="horizontal").pack(fill="x", pady=(12, 8))

        label_frame = ttk.Frame(self)
        label_frame.pack(fill="both", expand=True)

        ttk.Label(label_frame, text="데이터 항목").pack(anchor="w")
        for field in BASE_FIELDS:
            var = tk.BooleanVar(value=False)
            self.base_check_vars[field] = var
            cb = tk.Checkbutton(label_frame, text=field, variable=var, anchor="w")
            cb.pack(anchor="w", padx=6)

        ttk.Separator(self, orient="horizontal").pack(fill="x", pady=(10, 6))

        ttk.Label(self, text="Water level 아래 항목").pack(anchor="w")
        for field in EXTRA_FIELDS:
            var = tk.BooleanVar(value=False)
            self.extra_check_vars[field] = var
            cb = tk.Checkbutton(self, text=field, variable=var, anchor="w")
            cb.pack(anchor="w", padx=6)

        ttk.Separator(self, orient="horizontal").pack(fill="x", pady=(10, 6))

        extra_frame = ttk.Frame(self)
        extra_frame.pack(fill="x")

        for field, var in [
            ("펌프", self.pump_value_var),
            ("Label Velocity", self.label_velocity_var),
            ("Label Flow", self.label_flow_var),
        ]:
            row = ttk.Frame(extra_frame)
            row.pack(fill="x", pady=2)
            ttk.Label(row, text=field, width=18, anchor="w").pack(side="left")
            ttk.Entry(row, textvariable=var, width=24).pack(side="left", padx=(4, 0))

        ttk.Separator(self, orient="horizontal").pack(fill="x", pady=(12, 8))

        footer = ttk.Frame(self)
        footer.pack(fill="x")
        ttk.Label(footer, textvariable=self.status_var, foreground="#444444").pack(side="left")
        ttk.Button(footer, text="저장하기", command=self.save_selected_csv).pack(side="right")

    def _parse_range(self):
        """Return the selected start/end row positions as integers."""
        start_text = self.start_var.get().strip()
        end_text = self.end_var.get().strip()

        start_idx = 0 if start_text == "" else int(start_text)
        start_idx = max(0, start_idx)

        if end_text == "":
            end_idx = None
        else:
            end_idx = int(end_text)
            end_idx = max(start_idx, end_idx)

        return start_idx, end_idx

    def select_csv(self):
        """Choose a CSV file and populate default values from its header comments."""
        path = filedialog.askopenfilename(
            title="CSV 파일 선택",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
            initialdir=os.getcwd(),
        )
        if not path:
            return

        self.current_csv_path = path
        self.source_var.set(path)
        self.start_var.set("0")
        self.status_var.set("")

        self.header_comment_lines = self._read_comment_lines(path)
        pump_value = self._extract_pump_value(path)
        self.pump_value_var.set(pump_value)
        self.label_velocity_var.set("")
        self.label_flow_var.set("")

        df = pd.read_csv(path, comment="#", header=None)
        if df.empty:
            self.end_var.set("0")
            for field in BASE_FIELDS:
                if field in self.base_check_vars:
                    self.base_check_vars[field].set(False)
            return

        data_count = len(df)
        self.end_var.set(str(data_count - 1))
        for field in BASE_FIELDS:
            if field in self.base_check_vars:
                self.base_check_vars[field].set(True)

    def _read_comment_lines(self, csv_path: str):
        """Return all comment lines before the first data row."""
        comments = []
        try:
            with open(csv_path, "r", encoding="utf-8") as f:
                for line in f:
                    stripped = line.strip()
                    if stripped.startswith("#"):
                        comments.append(stripped)
                    elif stripped:
                        break
        except Exception:
            pass
        return comments

    def _extract_pump_value(self, csv_path: str) -> str:
        """Read the first comment lines and extract a pump count from '# 펌프 N개 ...'."""
        try:
            with open(csv_path, "r", encoding="utf-8") as f:
                for line in f:
                    stripped = line.strip()
                    if stripped.startswith("#"):
                        match = re.search(r"펌프\s+(\d+)", stripped, re.IGNORECASE)
                        if match:
                            return match.group(1)
                    elif stripped:
                        break
        except Exception:
            pass
        return "0"

    def _selected_base_fields(self):
        return [field for field in BASE_FIELDS if self.base_check_vars.get(field, tk.BooleanVar(value=True)).get()]

    def _selected_extra_fields(self):
        return [field for field in EXTRA_FIELDS if self.extra_check_vars.get(field, tk.BooleanVar(value=False)).get()]

    def save_selected_csv(self):
        """Save a filtered CSV file based on the selected fields and input values."""
        if not self.current_csv_path:
            return

        start_idx, end_idx = self._parse_range()
        source_path = Path(self.current_csv_path)
        file_stem = source_path.stem

        # Choose a unique output file name like 'filename-001.csv'
        output_path = source_path.with_name(f"{file_stem}-001.csv")
        idx = 1
        while output_path.exists():
            idx += 1
            output_path = source_path.with_name(f"{file_stem}-{idx:03d}.csv")

        df = pd.read_csv(
            self.current_csv_path,
            comment="#",
            header=None,
            names=[
                "date",
                "time",
                "Real-time velocity",
                "Avg. velocity",
                "Instant. flow rate",
                "Cumulative flow",
                "Water level",
            ],
        )

        if df.empty:
            return

        start_idx = max(0, int(start_idx))
        if end_idx is None:
            end_idx = len(df) - 1
        else:
            end_idx = max(start_idx, int(end_idx))
        end_idx = min(len(df) - 1, end_idx)

        selected_df = df.iloc[start_idx:end_idx + 1].copy()
        base_fields = self._selected_base_fields()
        if not base_fields:
            base_fields = BASE_FIELDS

        selected_extra_fields = self._selected_extra_fields()
        output_fields = list(base_fields)
        for field in EXTRA_FIELDS:
            if field in selected_extra_fields:
                output_fields.append(field)

        output_rows = []
        for _, row in selected_df.iterrows():
            output_row = [row[field] if field in row.index else "" for field in base_fields]
            for field in EXTRA_FIELDS:
                if field in selected_extra_fields:
                    if field == "펌프":
                        output_row.append(self.pump_value_var.get().strip())
                    elif field == "Label Velocity":
                        output_row.append(self.label_velocity_var.get().strip())
                    elif field == "Label Flow":
                        output_row.append(self.label_flow_var.get().strip())
            output_rows.append(output_row)

        comment_lines = list(self.header_comment_lines)
        comment_lines = [line for line in comment_lines if not line.strip().startswith("# 순서:")]
        comment_lines = [line for line in comment_lines if not line.strip().startswith("# Label Velocity")]
        comment_lines = [line for line in comment_lines if not line.strip().startswith("# Label Flow")]
        comment_lines = [line for line in comment_lines if line.strip() != "# 펌프"]

        comment_lines.append("# 순서: " + ", ".join(output_fields))

        with open(output_path, "w", encoding="utf-8", newline="") as f:
            for line in comment_lines:
                if not line.startswith("#"):
                    f.write("# " + line + "\n")
                else:
                    f.write(line + "\n")

            # f.write(",".join(output_fields) + "\n")
            for row in output_rows:
                f.write(",".join(str(value) for value in row) + "\n")

        self.status_var.set(f"저장 완료: {output_path.name}")


if __name__ == "__main__":
    root = tk.Tk()
    root.title("Manage Files")
    root.geometry("900x700")
    frame = ManageFilesFrame(root)
    frame.pack(fill="both", expand=True)
    root.mainloop()
