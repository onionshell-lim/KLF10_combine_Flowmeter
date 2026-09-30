import math
import os
import tkinter as tk
from tkinter import filedialog, ttk

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.ticker import FuncFormatter


METRICS = [
    "Real-time velocity",
    "Avg. velocity",
    "Instant. flow rate",
    "Water level",
]

COLORS = {
    "Real-time velocity": "#1f77b4",
    "Avg. velocity": "#ff7f0e",
    "Instant. flow rate": "#2ca02c",
    "Water level": "#d62728",
}


def compute_axis_scale(max_value: float):
    """Return a six-point ascending y-axis scale with max rounded up to a 5-multiple."""
    if not np.isfinite(max_value) or max_value <= 0:
        max_value = 0.005

    target = float(max_value)
    if target <= 0.005:
        upper = 0.005
    elif target <= 0.01:
        upper = 0.01
    elif target <= 0.05:
        upper = 0.05
    elif target <= 0.1:
        upper = 0.1
    elif target <= 0.5:
        upper = 0.5
    elif target <= 1.0:
        upper = 1.0
    elif target <= 5.0:
        upper = 5.0
    else:
        upper = float(math.ceil(target / 5.0) * 5.0)

    ratios = [0.0, 0.2, 0.4, 0.6, 0.8, 1.0]
    ticks = [upper * ratio for ratio in ratios]
    return upper, 0.0, np.array(ticks, dtype=float)


def safe_time_label(xvalue):
    """Convert matplotlib float-date values into a readable timestamp."""
    if xvalue is None or not np.isfinite(xvalue):
        return "N/A"
    try:
        dt = mdates.num2date(xvalue)
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return str(xvalue)


class RawDrawFrame(ttk.Frame):
    """Tkinter frame for plotting normalized monitor values from a CSV file."""

    def __init__(self, master):
        super().__init__(master)
        self.pack(fill="both", expand=True)

        toolbar = ttk.Frame(self)
        toolbar.pack(fill="x", padx=8, pady=(8, 4))

        ttk.Button(toolbar, text="CSV 선택", command=self.select_csv).pack(side="left")

        self.status_var = tk.StringVar(value="CSV 파일을 선택하세요.")
        ttk.Label(toolbar, textvariable=self.status_var).pack(side="left", padx=(10, 0))

        self.comment_var = tk.StringVar(value="")
        self.comment_label = ttk.Label(
            toolbar,
            textvariable=self.comment_var,
            foreground="#444444",
            font=("TkDefaultFont", 14, "italic"),
            justify="left",
            anchor="w",
        )
        self.comment_label.pack(side="right", padx=(0, 10))

        range_frame = ttk.Frame(self)
        range_frame.pack(fill="x", padx=8, pady=(0, 8))

        ttk.Label(range_frame, text="시작 위치").pack(side="left")
        self.start_var = tk.StringVar(value="0")
        ttk.Entry(range_frame, textvariable=self.start_var, width=8).pack(side="left", padx=(4, 12))

        ttk.Label(range_frame, text="마지막 위치").pack(side="left")
        self.end_var = tk.StringVar(value="")
        ttk.Entry(range_frame, textvariable=self.end_var, width=8).pack(side="left", padx=(4, 12))

        ttk.Button(range_frame, text="적용", command=self.apply_range).pack(side="left")

        self.figure, self.ax = plt.subplots(figsize=(12, 6))
        self.canvas = FigureCanvasTkAgg(self.figure, master=self)
        self.canvas.get_tk_widget().pack(fill="both", expand=True, padx=8, pady=8)

    def _parse_range(self):
        """Parse and validate the range from the UI fields."""
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

    def select_csv(self):
        """Open a file dialog and draw the selected CSV file."""
        path = filedialog.askopenfilename(
            title="CSV 파일 선택",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
            initialdir=os.getcwd(),
        )
        if not path:
            return

        self.status_var.set(path)
        try:
            start_idx, end_idx = self._parse_range()
            self.plot_csv(path, start_idx=start_idx, end_idx=end_idx)
        except ValueError as exc:
            self.status_var.set(str(exc))

    def apply_range(self):
        """Replot the current CSV using the user-defined start/end index range."""
        if not hasattr(self, "_current_csv_path"):
            return

        try:
            start_idx, end_idx = self._parse_range()
            self.plot_csv(self._current_csv_path, start_idx=start_idx, end_idx=end_idx)
        except ValueError as exc:
            self.status_var.set(str(exc))

    def _read_comment_lines(self, csv_path: str):
        """Return comment lines beginning with '#' from the CSV header area."""
        comments = []
        try:
            with open(csv_path, "r", encoding="utf-8") as f:
                for line in f:
                    stripped = line.strip()
                    if stripped.startswith("#"):
                        comments.append(stripped[1:].strip())
                    elif stripped:
                        break
        except Exception:
            pass
        return comments

    def plot_csv(self, csv_path: str, start_idx: int = 0, end_idx: int | None = None):
        """Read a CSV export and draw the normalized monitoring values."""
        self._current_csv_path = csv_path
        comment_lines = self._read_comment_lines(csv_path)
        if comment_lines:
            self.comment_var.set("\n".join(comment_lines))
            self.comment_label.configure(anchor="w")
        else:
            self.comment_var.set("")
            self.comment_label.configure(anchor="w")

        df = pd.read_csv(
            csv_path,
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
            self.status_var.set("선택한 CSV에 데이터가 없습니다.")
            return

        start_idx = max(0, int(start_idx))
        if end_idx is None:
            end_idx = len(df) - 1
        else:
            end_idx = max(start_idx, int(end_idx))

        if end_idx < start_idx:
            end_idx = start_idx

        end_idx = min(len(df) - 1, end_idx)
        df = df.iloc[start_idx:end_idx + 1].copy()
        df["timestamp"] = pd.to_datetime(
            df["date"] + " " + df["time"], format="%Y-%m-%d %H:%M:%S"
        )
        
        print(f"Plotting CSV: {csv_path}, rows {start_idx} to {end_idx}, total {len(df)} rows")
        #print first time and last time in the range
        if not df.empty:
            print(f"First timestamp: {df['timestamp'].iloc[0]}, Last timestamp: {df['timestamp'].iloc[-1]}")

        self.figure.clf()
        self.ax = self.figure.add_subplot(111)
        self.ax.set_title("Monitor Values (raw values, ascending y-axis)", fontsize=14)
        self.ax.set_xlabel("Time")
        self.ax.set_ylabel("Value")
        self.ax.grid(True, linestyle="--", alpha=0.35)

        handles = []
        labels = []

        range_start = 0
        range_end = max(0, len(df) - 1)
        selected_times = df["timestamp"].iloc[range_start:range_end + 1]

        self.ax.xaxis.set_major_formatter(FuncFormatter(lambda x, pos: safe_time_label(x)))

        for idx, metric in enumerate(METRICS):
            metric_series = df[metric].iloc[range_start:range_end + 1].astype(float)
            raw = metric_series.to_numpy()
            max_raw = float(np.nanmax(raw)) if raw.size else 0.0
            upper, _, ticks = compute_axis_scale(max_raw)

            ax2 = self.ax.twinx()
            ax2.spines["right"].set_position(("axes", 1.0 + idx * 0.06))
            ax2.set_ylim(0, upper)
            ax2.set_yticks(ticks)
            ax2.yaxis.set_major_formatter(FuncFormatter(lambda value, _pos: f"{value:g}"))
            ax2.set_ylabel(f"{metric} (raw)", color=COLORS[metric])
            ax2.tick_params(axis="y", colors=COLORS[metric], labelsize=9)

            line, = ax2.plot(selected_times, raw, label=metric, color=COLORS[metric], linewidth=2)
            handles.append(line)
            labels.append(metric)

            ax2.xaxis.set_major_formatter(FuncFormatter(lambda x, pos: safe_time_label(x)))

            def aux_format_coord(x, y, metric_name=metric):
                if x is None or y is None:
                    return ""
                try:
                    ts = safe_time_label(x)
                    return f"time={ts}, {metric_name}={y:.6g}"
                except Exception:
                    return ""

            ax2.format_coord = aux_format_coord

        if handles:
            self.ax.legend(handles, labels, loc="upper left", bbox_to_anchor=(1.02, 1.0), frameon=False)

        if not selected_times.empty:
            self.ax.set_xlim(selected_times.iloc[0], selected_times.iloc[-1])

        self.status_var.set(f"{start_idx} ~ {end_idx} 범위 표시 ({csv_path})")
        self.figure.tight_layout()
        self.canvas.draw()


if __name__ == "__main__":
    root = tk.Tk()
    root.title("CSV Raw Draw")
    root.geometry("1200x700")
    frame = RawDrawFrame(root)
    frame.pack(fill="both", expand=True)
    root.mainloop()