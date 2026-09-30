# -*- coding: utf-8 -*-

from __future__ import annotations

import csv
import os
import re
import tkinter as tk
from statistics import fmean, pvariance
from tkinter import filedialog, ttk

import matplotlib
matplotlib.use("TkAgg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from mpl_toolkits.mplot3d import Axes3D  # noqa: F401


DEFAULT_ITEMS = [
    "date",
    "time",
    "Real-time velocity",
    "Avg. velocity",
    "Instant. flow rate",
    "Cumulative flow",
    "Water level",
    "펌프",
    "Label Velocity",
    "Label Flow",
]


class MultiGraphFrame(ttk.Frame):
    """Multi-file CSV selection, stat summary, and normalized charting UI."""

    def __init__(self, master):
        super().__init__(master)
        self.pack(fill="both", expand=True, padx=8, pady=8)

        self.file_count_var = tk.IntVar(value=1)
        self.file_paths = ["" for _ in range(5)]
        self.file_path_vars: list[tk.StringVar] = []
        self.item_vars: dict[str, tk.BooleanVar] = {}
        self.checkbox_widgets: dict[str, ttk.Checkbutton] = {}
        self.data_item_names: list[str] = list(DEFAULT_ITEMS)
        self.normalized_data: list[dict] = []
        self.normalized_csv_path = os.path.join(os.getcwd(), "multi_graph_normalized.csv")

        self.start_var = tk.StringVar(value="0")
        self.end_var = tk.StringVar(value="")
        self.status_var = tk.StringVar(value="CSV 파일을 선택하세요.")

        count_frame = ttk.Frame(self)
        count_frame.pack(fill="x", pady=(0, 8))
        ttk.Label(count_frame, text="File Count").pack(side="left")
        for count in range(1, 6):
            ttk.Radiobutton(
                count_frame,
                text=str(count),
                variable=self.file_count_var,
                value=count,
                command=self._refresh_file_rows,
            ).pack(side="left", padx=(8, 0))

        self.file_rows_frame = ttk.Frame(self)
        self.file_rows_frame.pack(fill="x")
        self._refresh_file_rows()

        ttk.Separator(self, orient="horizontal").pack(fill="x", pady=(12, 8))

        range_frame = ttk.Frame(self)
        range_frame.pack(fill="x")
        ttk.Label(range_frame, text="시작 위치").pack(side="left")
        ttk.Entry(range_frame, textvariable=self.start_var, width=10).pack(side="left", padx=(4, 12))
        ttk.Label(range_frame, text="마지막 위치").pack(side="left")
        ttk.Entry(range_frame, textvariable=self.end_var, width=10).pack(side="left", padx=(4, 12))

        ttk.Separator(self, orient="horizontal").pack(fill="x", pady=(12, 8))

        self.data_items_frame = ttk.Frame(self)
        self.data_items_frame.pack(fill="both", expand=True, pady=(0, 3))
        self._build_data_item_checkboxes()

        self.info_label = ttk.Label(self, text="멀티 그래프 준비 중입니다.")
        self.info_label.pack(pady=(12, 0), anchor="w")

        self.graph_frame = ttk.Frame(self)
        self.graph_frame.pack(fill="both", expand=True, pady=(3, 0))

        self._set_default_item_states()

    def _build_data_item_checkboxes(self):
        for child in list(self.data_items_frame.winfo_children()):
            child.destroy()
        self.checkbox_widgets.clear()
        self.item_vars.clear()

        ttk.Label(self.data_items_frame, text="데이터 항목").pack(anchor="w")
        for item in self.data_item_names:
            var = tk.BooleanVar(value=False)
            self.item_vars[item] = var
            cb = ttk.Checkbutton(self.data_items_frame, text=item, variable=var, command=self._draw_selected_graphs)
            cb.pack(anchor="w", padx=6)
            self.checkbox_widgets[item] = cb

    def _refresh_file_rows(self):
        for child in self.file_rows_frame.winfo_children():
            child.destroy()

        self.file_path_vars = []
        file_count = self.file_count_var.get()
        for idx in range(file_count):
            row = ttk.Frame(self.file_rows_frame)
            row.pack(fill="x", pady=2)
            ttk.Label(row, text=f"파일 {idx + 1}").pack(side="left", padx=(0, 8))
            ttk.Button(row, text="CSV 선택", command=lambda row_idx=idx: self.select_csv(row_idx)).pack(side="left")
            var = tk.StringVar(value=self.file_paths[idx])
            self.file_path_vars.append(var)
            ttk.Label(row, textvariable=var, wraplength=500).pack(side="left", padx=(8, 0))

    def _set_default_item_states(self):
        for item in self.data_item_names:
            if item in self.item_vars:
                self.item_vars[item].set(False)

    def _normalize_item_name(self, name: str) -> str:
        return name.strip()

    def _read_ordered_items(self, csv_path: str) -> list[str]:
        try:
            with open(csv_path, "r", encoding="utf-8") as f:
                for line in f:
                    stripped = line.strip()
                    if not stripped or not stripped.startswith("#"):
                        continue
                    if "순서:" in stripped:
                        candidate = stripped.split(":", 1)[1].strip()
                        items = [self._normalize_item_name(item) for item in candidate.split(",") if item.strip()]
                        if items:
                            return items
        except Exception:
            pass
        return list(DEFAULT_ITEMS)

    def _is_valid_data_row(self, line: str) -> bool:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            return False

        parts = [part.strip() for part in stripped.split(",")]
        if len(parts) < 2:
            return False

        first = parts[0]
        if first == "":
            return False

        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", first):
            return True
        if re.fullmatch(r"\d{2}:\d{2}:\d{2}", first):
            return False
        if re.fullmatch(r"[-+]?\d+(?:\.\d+)?", first):
            return True
        return False

    def _collect_values_by_item(self, csv_path: str) -> tuple[list[str], dict[str, list[float]]]:
        order = self._read_ordered_items(csv_path)
        values: dict[str, list[float]] = {item: [] for item in order if item not in {"date", "time"}}

        try:
            with open(csv_path, "r", encoding="utf-8") as f:
                for line in f:
                    if not self._is_valid_data_row(line):
                        continue
                    row = [part.strip() for part in line.strip().split(",")]
                    if len(row) < len(order):
                        continue
                    for idx, item in enumerate(order):
                        if item in {"date", "time"}:
                            continue
                        if idx >= len(row):
                            continue
                        value_text = row[idx]
                        try:
                            values[item].append(float(value_text))
                        except ValueError:
                            pass
        except Exception:
            pass

        return order, values

    def _apply_checkbox_texts(self, stats_by_item: dict[str, tuple[float, float]]):
        for item, cb in self.checkbox_widgets.items():
            if item in stats_by_item:
                mean_value, variance_value = stats_by_item[item]
                cb.configure(text=f"{item}   평균:{mean_value:.6f} 분산:{variance_value:.6f}")
            else:
                cb.configure(text=item)

    def _refresh_stats_for_all_files(self):
        combined_values: dict[str, list[float]] = {}
        ordered_names: list[str] = []

        for path in self.file_paths:
            if not path:
                continue
            order, values = self._collect_values_by_item(path)
            ordered_names = order

            for item in order:
                if item in {"date", "time"}:
                    continue
                combined_values.setdefault(item, [])
                combined_values[item].extend(values.get(item, []))

        if ordered_names:
            self.data_item_names = ordered_names
            self._build_data_item_checkboxes()
            self._set_default_item_states()

        stats_by_item: dict[str, tuple[float, float]] = {}
        for item, values in combined_values.items():
            if not values:
                continue
            mean_value = fmean(values)
            variance_value = pvariance(values) if len(values) > 1 else 0.0
            stats_by_item[item] = (mean_value, variance_value)

        self._apply_checkbox_texts(stats_by_item)
        self._save_normalized_values()
        self._draw_selected_graphs()

    def _combined_item_values(self) -> dict[str, list[float]]:
        combined: dict[str, list[float]] = {}
        for path in self.file_paths:
            if not path:
                continue
            _, values = self._collect_values_by_item(path)
            for item, item_values in values.items():
                if item in {"date", "time"}:
                    continue
                combined.setdefault(item, [])
                combined[item].extend(float(value) for value in item_values)
        return combined

    def _global_item_normalization_stats(self) -> dict[str, dict[str, float]]:
        stats: dict[str, dict[str, float]] = {}
        for item, values in self._combined_item_values().items():
            if not values:
                continue
            arr = np.asarray(values, dtype=float)
            stats[item] = {
                "mean": float(arr.mean()),
                "max": float(arr.max()),
            }
        return stats

    def _normalize_values_for_item(self, item: str, values: list[float]) -> np.ndarray:
        if not values:
            return np.asarray([], dtype=float)

        arr = np.asarray(values, dtype=float)
        global_stats = self._global_item_normalization_stats().get(item)
        if not global_stats:
            return arr

        max_value = global_stats["max"]
        mean_value = global_stats["mean"]
        if np.isclose(max_value, mean_value):
            return np.full_like(arr, 1.0, dtype=float)

        norm = ((arr - mean_value) / (max_value - mean_value + 1e-9)) * 0.5 + 0.5 + 1e-6
        return np.clip(norm, 1e-6, None)

    def _save_normalized_values(self):
        rows: list[dict] = []
        selected_files = [path for path in self.file_paths if path]
        if not selected_files:
            self.normalized_data = []
            return

        global_stats = self._global_item_normalization_stats()
        for file_idx, path in enumerate(selected_files):
            order, values = self._collect_values_by_item(path)
            for item in order:
                if item in {"date", "time"}:
                    continue
                if not values.get(item):
                    continue
                stats = global_stats.get(item)
                if not stats:
                    continue
                arr = np.asarray(values[item], dtype=float)
                max_value = stats["max"]
                mean_value = stats["mean"]
                if np.isclose(max_value, mean_value):
                    norm = np.full_like(arr, 1.0, dtype=float)
                else:
                    norm = ((arr - mean_value) / (max_value - mean_value + 1e-9)) * 0.5 + 0.5 + 1e-6
                    norm = np.clip(norm, 1e-6, None)
                for seq_idx, value in enumerate(norm):
                    rows.append({
                        "file_index": file_idx,
                        "file": os.path.basename(path),
                        "item": item,
                        "order": seq_idx,
                        "normalized_value": float(value),
                        "raw_value": float(values[item][seq_idx]),
                    })

        self.normalized_data = rows
        fieldnames = ["file_index", "file", "item", "order", "normalized_value", "raw_value"]
        with open(self.normalized_csv_path, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)

    def _selected_items(self) -> list[str]:
        return [item for item in self.data_item_names if self.item_vars.get(item, tk.BooleanVar(value=False)).get()]

    def _normalized_series_for(self, csv_path: str, item: str) -> np.ndarray:
        file_name = os.path.basename(csv_path)
        if self.normalized_data:
            matched = [entry["normalized_value"] for entry in self.normalized_data if entry.get("file") == file_name and entry.get("item") == item]
            if matched:
                return np.asarray(matched, dtype=float)

        _, values = self._collect_values_by_item(csv_path)
        return self._normalize_values_for_item(item, values.get(item, []))

    def _draw_selected_graphs(self):
        for child in list(self.graph_frame.winfo_children()):
            child.destroy()

        selected_items = self._selected_items()
        if not selected_items:
            lbl = ttk.Label(self.graph_frame, text="선택된 데이터 항목이 없습니다.")
            lbl.pack(anchor="w")
            return

        color_cycle = [
            "#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd",
            "#8c564b", "#e377c2", "#7f7f7f", "#bcbd22", "#17becf",
        ]

        selected_files = [path for path in self.file_paths if path]
        if not selected_files:
            lbl = ttk.Label(self.graph_frame, text="CSV 파일을 먼저 선택하세요.")
            lbl.pack(anchor="w")
            return

        legend_font_size = 14

        self.graph_frame.grid_columnconfigure(0, weight=2)
        self.graph_frame.grid_columnconfigure(1, weight=1)
        self.graph_frame.grid_rowconfigure(0, weight=1)

        two_d_frame = ttk.Frame(self.graph_frame)
        two_d_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 6))
        two_d_figure, two_d_ax = plt.subplots(figsize=(8, 4.8))
        for file_idx, path in enumerate(selected_files):
            for item in selected_items:
                norm = self._normalized_series_for(path, item)
                if norm.size == 0:
                    continue
                color = color_cycle[(file_idx + selected_items.index(item)) % len(color_cycle)]
                two_d_ax.plot(np.arange(len(norm)), norm, label=f"{os.path.basename(path)}::{item}", color=color, linewidth=1.5)
        two_d_ax.set_title("2D Normalized Graph")
        two_d_ax.set_xlabel("순서")
        two_d_ax.set_ylabel("Normalized Value")
        two_d_ax.grid(True, linestyle="--", alpha=0.4)
        if two_d_ax.lines:
            two_d_ax.legend(loc="upper right", bbox_to_anchor=(1.02, 1.0), fontsize=legend_font_size)
        two_d_canvas = FigureCanvasTkAgg(two_d_figure, master=two_d_frame)
        two_d_canvas.draw()
        two_d_canvas.get_tk_widget().pack(fill="both", expand=True)

        three_d_frame = ttk.Frame(self.graph_frame)
        three_d_frame.grid(row=0, column=1, sticky="nsew", padx=(6, 0))
        three_d_figure = plt.figure(figsize=(4, 4.8))
        three_d_figure.subplots_adjust(right=0.68)
        three_d_ax = three_d_figure.add_subplot(111, projection="3d")
        for file_idx, path in enumerate(selected_files):
            for item in selected_items:
                norm = self._normalized_series_for(path, item)
                if norm.size == 0:
                    continue
                color = color_cycle[(file_idx + selected_items.index(item)) % len(color_cycle)]
                three_d_ax.plot(
                    np.arange(len(norm)),
                    np.full(len(norm), file_idx),
                    norm,
                    color=color,
                    linewidth=1.5,
                    label=f"{os.path.basename(path)}::{item}",
                )
        three_d_ax.set_title("3D Normalized Graph")
        three_d_ax.set_xlabel("순서")
        three_d_ax.set_ylabel("파일")
        three_d_ax.set_zlabel("Normalized Value")
        if three_d_ax.lines:
            three_d_ax.legend(loc="upper left", bbox_to_anchor=(1.02, 1.0), fontsize=legend_font_size)
        three_d_canvas = FigureCanvasTkAgg(three_d_figure, master=three_d_frame)
        three_d_canvas.draw()
        three_d_canvas.get_tk_widget().pack(fill="both", expand=True)

    def _parse_range(self):
        try:
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
        except ValueError:
            raise ValueError("시작/마지막 위치는 정수 인덱스만 허용합니다.")

    def select_csv(self, row_idx: int):
        path = filedialog.askopenfilename(
            title="CSV 파일 선택",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
            initialdir=os.getcwd(),
        )
        if not path:
            return

        self.file_paths[row_idx] = path
        if row_idx < len(self.file_path_vars):
            self.file_path_vars[row_idx].set(path)

        self.status_var.set(path)
        try:
            self._refresh_stats_for_all_files()
            self.info_label.config(text="CSV 파일을 읽어 통계를 계산했습니다.")
        except Exception as exc:
            self.status_var.set(f"오류: {exc}")


if __name__ == "__main__":
    root = tk.Tk()
    root.title("Multi Graph")
    root.geometry("1400x1000")
    frame = MultiGraphFrame(root)
    frame.pack(fill="both", expand=True)
    root.mainloop()
