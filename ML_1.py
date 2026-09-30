# -*- coding: utf-8 -*-

from __future__ import annotations

import csv
import math
import os
import queue
import threading
import tkinter as tk
from statistics import fmean, pvariance
from tkinter import filedialog, ttk


FEATURE_ITEMS = [
    "Real-time velocity",
    "Avg. velocity",
    "Instant. flow rate",
    "Cumulative flow",
    "Water level",
]
TARGET_ITEM = "펌프"
SEQUENCE_LENGTH = 50
MAX_FILES = 5


class SimpleRNN:
    """Small tanh RNN trained with BPTT and SGD using only the standard library."""

    def __init__(self, input_size: int, hidden_size: int = 16, learning_rate: float = 0.001):
        self.input_size = input_size
        self.hidden_size = hidden_size
        self.learning_rate = learning_rate
        self.w_xh = [[self._weight() for _ in range(input_size)] for _ in range(hidden_size)]
        self.w_hh = [[self._weight() for _ in range(hidden_size)] for _ in range(hidden_size)]
        self.b_h = [0.0 for _ in range(hidden_size)]
        self.w_hy = [self._weight() for _ in range(hidden_size)]
        self.b_y = 0.0

    @staticmethod
    def _weight() -> float:
        return (hash(object()) % 2001 - 1000) / 100000.0

    def _forward(self, sequence: list[list[float]]) -> tuple[list[list[float]], float]:
        states: list[list[float]] = [[0.0] * self.hidden_size]
        for inputs in sequence:
            previous = states[-1]
            current = []
            for hidden_idx in range(self.hidden_size):
                total = self.b_h[hidden_idx]
                total += sum(self.w_xh[hidden_idx][input_idx] * inputs[input_idx] for input_idx in range(self.input_size))
                total += sum(self.w_hh[hidden_idx][prev_idx] * previous[prev_idx] for prev_idx in range(self.hidden_size))
                current.append(math.tanh(total))
            states.append(current)
        prediction = self.b_y + sum(self.w_hy[idx] * states[-1][idx] for idx in range(self.hidden_size))
        return states, prediction

    def train_one(self, sequence: list[list[float]], target: float) -> float:
        states, prediction = self._forward(sequence)
        error = prediction - target
        loss = error * error
        grad_w_xh = [[0.0] * self.input_size for _ in range(self.hidden_size)]
        grad_w_hh = [[0.0] * self.hidden_size for _ in range(self.hidden_size)]
        grad_b_h = [0.0] * self.hidden_size
        grad_w_hy = [error * value for value in states[-1]]
        grad_b_y = error
        gradient_next = [error * value for value in self.w_hy]

        for time_idx in range(len(sequence), 0, -1):
            current = states[time_idx]
            previous = states[time_idx - 1]
            derivative = [gradient_next[idx] * (1.0 - current[idx] * current[idx]) for idx in range(self.hidden_size)]
            for hidden_idx in range(self.hidden_size):
                grad_b_h[hidden_idx] += derivative[hidden_idx]
                for input_idx in range(self.input_size):
                    grad_w_xh[hidden_idx][input_idx] += derivative[hidden_idx] * sequence[time_idx - 1][input_idx]
                for prev_idx in range(self.hidden_size):
                    grad_w_hh[hidden_idx][prev_idx] += derivative[hidden_idx] * previous[prev_idx]
            gradient_next = [
                sum(derivative[hidden_idx] * self.w_hh[hidden_idx][prev_idx] for hidden_idx in range(self.hidden_size))
                for prev_idx in range(self.hidden_size)
            ]

        rate = self.learning_rate
        for hidden_idx in range(self.hidden_size):
            for input_idx in range(self.input_size):
                self.w_xh[hidden_idx][input_idx] -= rate * grad_w_xh[hidden_idx][input_idx]
            for prev_idx in range(self.hidden_size):
                self.w_hh[hidden_idx][prev_idx] -= rate * grad_w_hh[hidden_idx][prev_idx]
            self.b_h[hidden_idx] -= rate * grad_b_h[hidden_idx]
            self.w_hy[hidden_idx] -= rate * grad_w_hy[hidden_idx]
        self.b_y -= rate * grad_b_y
        return loss

    def predict(self, sequence: list[list[float]]) -> float:
        return self._forward(sequence)[1]


class ML1Frame(ttk.Frame):
    def __init__(self, master):
        super().__init__(master)
        self.pack(fill="both", expand=True, padx=8, pady=8)
        self.file_count_var = tk.IntVar(value=1)
        self.file_paths = ["" for _ in range(MAX_FILES)]
        self.file_path_vars: list[tk.StringVar] = []
        self.data_item_names: list[str] = []
        self.item_vars: dict[str, tk.BooleanVar] = {}
        self.checkbox_widgets: dict[str, ttk.Checkbutton] = {}
        self.start_var = tk.StringVar(value="0")
        self.end_var = tk.StringVar(value="")
        self.ml_button: ttk.Button
        self.log_text: tk.Text
        self.log_queue: queue.Queue[str] = queue.Queue()

        count_frame = ttk.Frame(self)
        count_frame.pack(fill="x", pady=(0, 8))
        ttk.Label(count_frame, text="File Count").pack(side="left")
        for count in range(1, MAX_FILES + 1):
            ttk.Radiobutton(count_frame, text=str(count), variable=self.file_count_var, value=count, command=self._refresh_file_rows).pack(side="left", padx=(8, 0))

        self.ml_button = ttk.Button(self, text="ML 실행", command=self._start_training, state="disabled")
        self.file_rows_frame = ttk.Frame(self)
        self.file_rows_frame.pack(fill="x")
        self._refresh_file_rows()

        range_frame = ttk.Frame(self)
        range_frame.pack(fill="x", pady=(12, 0))
        ttk.Label(range_frame, text="시작 위치").pack(side="left")
        ttk.Entry(range_frame, textvariable=self.start_var, width=10).pack(side="left", padx=(4, 12))
        ttk.Label(range_frame, text="마지막 위치").pack(side="left")
        ttk.Entry(range_frame, textvariable=self.end_var, width=10).pack(side="left", padx=(4, 12))

        self.data_items_frame = ttk.Frame(self)
        self.data_items_frame.pack(fill="x", pady=(12, 0))
        self._build_data_item_checkboxes([])

        self.ml_button.pack(anchor="w", pady=(8, 8))

        ttk.Label(self, text="머신러닝 실행 상태").pack(anchor="w")
        log_frame = ttk.Frame(self)
        log_frame.pack(fill="both", expand=True)
        self.log_text = tk.Text(log_frame, height=30, state="disabled", wrap="none")
        scrollbar = ttk.Scrollbar(log_frame, orient="vertical", command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=scrollbar.set)
        self.log_text.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        self.after(100, self._drain_log_queue)

    def _refresh_file_rows(self):
        for child in self.file_rows_frame.winfo_children():
            child.destroy()
        self.file_path_vars = []
        for idx in range(self.file_count_var.get()):
            row = ttk.Frame(self.file_rows_frame)
            row.pack(fill="x", pady=2)
            ttk.Label(row, text=f"파일 {idx + 1}").pack(side="left", padx=(0, 8))
            ttk.Button(row, text="CSV 선택", command=lambda row_idx=idx: self.select_csv(row_idx)).pack(side="left")
            var = tk.StringVar(value=self.file_paths[idx])
            self.file_path_vars.append(var)
            ttk.Label(row, textvariable=var, wraplength=700).pack(side="left", padx=(8, 0))
        self._update_ml_button()

    def _build_data_item_checkboxes(self, item_names: list[str]):
        for child in self.data_items_frame.winfo_children():
            child.destroy()
        self.item_vars.clear()
        self.checkbox_widgets.clear()
        ttk.Label(self.data_items_frame, text="데이터 항목").pack(anchor="w")
        self.data_item_names = list(item_names)
        for item in self.data_item_names:
            var = tk.BooleanVar(value=False)
            checkbox = ttk.Checkbutton(self.data_items_frame, text=item, variable=var)
            checkbox.pack(anchor="w", padx=6)
            self.item_vars[item] = var
            self.checkbox_widgets[item] = checkbox

    @staticmethod
    def _parse_order(csv_path: str) -> list[str]:
        with open(csv_path, "r", encoding="utf-8") as source:
            for line in source:
                if line.startswith("#") and "순서:" in line:
                    return [item.strip() for item in line.split("순서:", 1)[1].split(",") if item.strip()]
        return []

    @staticmethod
    def _is_numeric_data_line(line: str) -> bool:
        if not line.strip() or line.lstrip().startswith("#"):
            return False
        try:
            float(line.split(",", 1)[0].strip())
            return True
        except (ValueError, IndexError):
            return False

    def _parse_range(self) -> tuple[int, int | None]:
        try:
            start = max(0, int(self.start_var.get().strip() or "0"))
            end_text = self.end_var.get().strip()
            end = None if not end_text else max(start, int(end_text))
            return start, end
        except ValueError as exc:
            raise ValueError("시작/마지막 위치는 정수 인덱스만 허용합니다.") from exc

    def _read_file(self, csv_path: str) -> tuple[list[str], list[list[float]]]:
        order = self._parse_order(csv_path)
        rows: list[list[float]] = []
        with open(csv_path, "r", encoding="utf-8") as source:
            for line in source:
                if not self._is_numeric_data_line(line):
                    continue
                values = [part.strip() for part in next(csv.reader([line]))]
                if len(values) < len(order):
                    continue
                try:
                    rows.append([float(value) for value in values[:len(order)]])
                except ValueError:
                    continue
        start, end = self._parse_range()
        return order, rows[start:end]

    def _refresh_stats(self):
        combined: dict[str, list[float]] = {}
        first_order: list[str] = []
        skipped = 0
        for path in self.file_paths:
            if not path:
                continue
            order, rows = self._read_file(path)
            if not first_order:
                first_order = order
            for row in rows:
                for index, item in enumerate(order):
                    combined.setdefault(item, []).append(row[index])
        if first_order:
            self._build_data_item_checkboxes(first_order)
        for item, checkbox in self.checkbox_widgets.items():
            values = combined.get(item, [])
            if values:
                mean = fmean(values)
                variance = pvariance(values) if len(values) > 1 else 0.0
                checkbox.configure(text=f"{item}   평균:{mean:.6f} 분산:{variance:.6f}")
            else:
                checkbox.configure(text=item)
        self._update_ml_button()
        self._log(f"통계 갱신 완료: {len(combined)}개 항목")
        if not combined and any(self.file_paths):
            self._log("첫 번째 항목이 숫자가 아닌 데이터 행은 주석으로 처리되어 제외되었습니다.")

    def _update_ml_button(self):
        selected_count = sum(bool(path) for path in self.file_paths)
        self.ml_button.configure(state="normal" if selected_count >= 3 else "disabled")

    def select_csv(self, row_idx: int):
        path = filedialog.askopenfilename(title="CSV 파일 선택", filetypes=[("CSV files", "*.csv"), ("All files", "*.*")], initialdir=os.getcwd())
        if not path:
            return
        self.file_paths[row_idx] = path
        self.file_path_vars[row_idx].set(path)
        try:
            self._refresh_stats()
        except Exception as exc:
            self._log(f"파일 읽기 오류: {exc}")

    def _log(self, message: str):
        self.log_queue.put(message)

    def _drain_log_queue(self):
        if not hasattr(self, "log_text"):
            self.after(100, self._drain_log_queue)
            return
        self.log_text.configure(state="normal")
        while True:
            try:
                message = self.log_queue.get_nowait()
            except queue.Empty:
                break
            self.log_text.insert("end", message + "\n")
        self.log_text.see("end")
        self.log_text.configure(state="disabled")
        self.after(100, self._drain_log_queue)

    def _start_training(self):
        self.ml_button.configure(state="disabled")
        threading.Thread(target=self._train_model, daemon=True).start()

    def _train_model(self):
        try:
            files = [path for path in self.file_paths if path]
            datasets = []
            for path in files:
                order, rows = self._read_file(path)
                indexes = {name: order.index(name) for name in FEATURE_ITEMS + [TARGET_ITEM]}
                if len(rows) < SEQUENCE_LENGTH + 1:
                    raise ValueError(f"{os.path.basename(path)}: 숫자 데이터가 {SEQUENCE_LENGTH + 1}행보다 적습니다.")
                features = [[row[indexes[item]] for item in FEATURE_ITEMS] for row in rows]
                targets = [row[indexes[TARGET_ITEM]] for row in rows]
                datasets.append((os.path.basename(path), features, targets))

            self._log(f"학습 시작: {len(datasets)}개 파일, 시퀀스 길이 {SEQUENCE_LENGTH}")
            model = SimpleRNN(len(FEATURE_ITEMS))
            total_train = 0
            total_eval = 0
            total_error = 0.0
            for file_name, features, targets in datasets:
                split = max(SEQUENCE_LENGTH, int(len(features) * 2 / 3))
                split = min(split, len(features) - 1)
                train_sequences = []
                for end in range(SEQUENCE_LENGTH, split + 1):
                    train_sequences.append((features[end - SEQUENCE_LENGTH:end], targets[end]))
                for epoch in range(5):
                    epoch_loss = sum(model.train_one(sequence, target) for sequence, target in train_sequences)
                    if train_sequences:
                        epoch_loss /= len(train_sequences)
                    self._log(f"{file_name} 학습 {epoch + 1}/5 loss={epoch_loss:.6f}")
                total_train += len(train_sequences)
                eval_count = 0
                for end in range(split, len(features)):
                    sequence = features[end - SEQUENCE_LENGTH:end]
                    prediction = model.predict(sequence)
                    total_error += abs(prediction - targets[end])
                    eval_count += 1
                total_eval += eval_count
                self._log(f"{file_name} 평가 완료: {eval_count}개")

            mae = total_error / total_eval if total_eval else 0.0
            self._log(f"ML 완료: 학습 시퀀스 {total_train}개, 평가 시퀀스 {total_eval}개, MAE={mae:.6f}")
        except Exception as exc:
            self._log(f"ML 실행 오류: {exc}")
        finally:
            self.after(0, self._update_ml_button)


if __name__ == "__main__":
    root = tk.Tk()
    root.title("ML-1")
    root.geometry("1400x1000")
    ML1Frame(root)
    root.mainloop()
