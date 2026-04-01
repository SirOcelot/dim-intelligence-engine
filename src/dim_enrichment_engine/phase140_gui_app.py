from __future__ import annotations

import os
import subprocess
import sys
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, scrolledtext, ttk


class WarmindGUI(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Warmind - Destiny Intelligence Engine")
        self.geometry("1180x860")
        self.minsize(1040, 760)

        self.weapons_var = tk.StringVar()
        self.armor_var = tk.StringVar()
        self.loadouts_var = tk.StringVar()
        self.output_var = tk.StringVar(value=str(Path.cwd() / "output"))
        self.question_var = tk.StringVar()
        self.mode_var = tk.StringVar(value="safe")
        self.feedback_var = tk.StringVar(value="better")
        self.direct_equip_var = tk.BooleanVar(value=False)
        self.confirm_var = tk.BooleanVar(value=False)

        self._build_ui()

    def _build_ui(self) -> None:
        root = ttk.Frame(self, padding=12)
        root.pack(fill="both", expand=True)

        title = ttk.Label(root, text="Warmind", font=("Segoe UI", 22, "bold"))
        title.pack(anchor="w")
        subtitle = ttk.Label(root, text="Unified GUI | Analyze, adapt, score, simulate, and execute")
        subtitle.pack(anchor="w", pady=(0, 12))

        top = ttk.Frame(root)
        top.pack(fill="x", pady=(0, 12))

        left = ttk.LabelFrame(top, text="DIM / Warmind Inputs", padding=12)
        left.pack(side="left", fill="both", expand=True, padx=(0, 8))
        self._file_row(left, 0, "Weapons CSV", self.weapons_var)
        self._file_row(left, 1, "Armor CSV", self.armor_var)
        self._file_row(left, 2, "Loadouts CSV", self.loadouts_var, required=False)
        self._file_row(left, 3, "Output Folder", self.output_var, folder=True)

        right = ttk.LabelFrame(top, text="Controls", padding=12)
        right.pack(side="left", fill="y")

        ttk.Label(right, text="Interactive question").grid(row=0, column=0, sticky="w")
        ttk.Entry(right, textvariable=self.question_var, width=42).grid(row=1, column=0, sticky="ew", pady=(4, 10))

        ttk.Label(right, text="Adaptive mode").grid(row=2, column=0, sticky="w")
        ttk.Combobox(right, textvariable=self.mode_var, values=["safe", "aggressive", "comfort", "anti-champion", "economy"], state="readonly", width=24).grid(row=3, column=0, sticky="w", pady=(4, 10))

        ttk.Label(right, text="Feedback result").grid(row=4, column=0, sticky="w")
        ttk.Combobox(right, textvariable=self.feedback_var, values=["better", "same", "still_bad"], state="readonly", width=24).grid(row=5, column=0, sticky="w", pady=(4, 10))

        ttk.Checkbutton(right, text="Direct equip", variable=self.direct_equip_var).grid(row=6, column=0, sticky="w")
        ttk.Checkbutton(right, text="I confirm changes", variable=self.confirm_var).grid(row=7, column=0, sticky="w", pady=(4, 0))

        actions = ttk.LabelFrame(root, text="Actions", padding=12)
        actions.pack(fill="x", pady=(0, 12))

        ttk.Button(actions, text="Analyze / Q&A", command=self.run_analyze).pack(side="left")
        ttk.Button(actions, text="Simulation / Scoring", command=self.run_scoring).pack(side="left", padx=(8, 0))
        ttk.Button(actions, text="Mode Adaptation", command=self.run_mode).pack(side="left", padx=(8, 0))
        ttk.Button(actions, text="Feedback Loop", command=self.run_feedback).pack(side="left", padx=(8, 0))
        ttk.Button(actions, text="Item Selection", command=self.run_refinement).pack(side="left", padx=(8, 0))
        ttk.Button(actions, text="Execution Preview", command=self.run_execute).pack(side="left", padx=(8, 0))
        ttk.Button(actions, text="Open Output Folder", command=self.open_output_folder).pack(side="left", padx=(8, 0))

        tabs = ttk.Notebook(root)
        tabs.pack(fill="both", expand=True)

        self.log_box = self._make_text_tab(tabs, "Console")
        self.summary_box = self._make_text_tab(tabs, "Summary")
        self.diff_box = self._make_text_tab(tabs, "Diff / Preview")
        self.qa_box = self._make_text_tab(tabs, "Q&A / Adaptive")

        self._append(self.log_box, "Warmind GUI ready. Select your inputs, then run the action you want.\n")

    def _make_text_tab(self, notebook: ttk.Notebook, title: str):
        frame = ttk.Frame(notebook)
        notebook.add(frame, text=title)
        box = scrolledtext.ScrolledText(frame, wrap="word", font=("Consolas", 10))
        box.pack(fill="both", expand=True)
        box.configure(state="disabled")
        return box

    def _file_row(self, parent: ttk.LabelFrame, row: int, label: str, variable: tk.StringVar, folder: bool = False, required: bool = True) -> None:
        suffix = " *" if required else ""
        ttk.Label(parent, text=label + suffix).grid(row=row, column=0, sticky="w", padx=(0, 8), pady=4)
        entry = ttk.Entry(parent, textvariable=variable, width=75)
        entry.grid(row=row, column=1, sticky="ew", pady=4)
        if folder:
            cmd = lambda v=variable: self.pick_folder(v)
        else:
            cmd = lambda v=variable: self.pick_file(v)
        ttk.Button(parent, text="Browse", command=cmd).grid(row=row, column=2, padx=(8, 0), pady=4)
        parent.columnconfigure(1, weight=1)

    def _append(self, box, text: str) -> None:
        box.configure(state="normal")
        box.insert("end", text)
        box.see("end")
        box.configure(state="disabled")
        self.update_idletasks()

    def _set_text(self, box, text: str) -> None:
        box.configure(state="normal")
        box.delete("1.0", "end")
        box.insert("1.0", text)
        box.configure(state="disabled")

    def pick_file(self, variable: tk.StringVar) -> None:
        path = filedialog.askopenfilename(filetypes=[("CSV files", "*.csv"), ("All files", "*.*")])
        if path:
            variable.set(path)

    def pick_folder(self, variable: tk.StringVar) -> None:
        path = filedialog.askdirectory()
        if path:
            variable.set(path)

    def validate_inputs(self, need_csv: bool = True) -> bool:
        missing = []
        if need_csv and not Path(self.weapons_var.get().strip()).exists():
            missing.append("Weapons CSV")
        if need_csv and not Path(self.armor_var.get().strip()).exists():
            missing.append("Armor CSV")
        loadouts = self.loadouts_var.get().strip()
        if loadouts and not Path(loadouts).exists():
            missing.append("Loadouts CSV")
        if not self.output_var.get().strip():
            missing.append("Output folder")
        if missing:
            messagebox.showerror("Warmind", "Missing or invalid inputs: " + ", ".join(missing))
            return False
        return True

    def common_args(self, include_loadouts: bool = True) -> list[str]:
        args = [
            "--weapons", self.weapons_var.get().strip(),
            "--armor", self.armor_var.get().strip(),
            "--output-dir", self.output_var.get().strip(),
        ]
        loadouts = self.loadouts_var.get().strip()
        if include_loadouts and loadouts:
            args.extend(["--loadouts", loadouts])
        return args

    def run_module(self, module: str, extra_args: list[str] | None = None) -> tuple[int, str, str]:
        cmd = [sys.executable, "-m", module] + (extra_args or [])
        self._append(self.log_box, "=" * 100 + "\n")
        self._append(self.log_box, "Running: " + " ".join(f'\"{c}\"' if ' ' in c else c for c in cmd) + "\n")
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, cwd=str(Path.cwd()), check=False)
        except Exception as exc:
            messagebox.showerror("Warmind", f"Failed to run {module}: {exc}")
            self._append(self.log_box, f"ERROR: {exc}\n")
            return 1, "", str(exc)
        if result.stdout.strip():
            self._append(self.log_box, "STDOUT:\n" + result.stdout.strip() + "\n")
        if result.stderr.strip():
            self._append(self.log_box, "STDERR:\n" + result.stderr.strip() + "\n")
        if result.returncode != 0:
            messagebox.showerror("Warmind", f"{module} failed with exit code {result.returncode}")
        return result.returncode, result.stdout, result.stderr

    def load_file_to_box(self, filename: str, box) -> None:
        path = Path(self.output_var.get().strip()) / filename
        if path.exists():
            self._set_text(box, path.read_text(encoding="utf-8", errors="ignore"))

    def run_analyze(self) -> None:
        if not self.validate_inputs(True):
            return
        args = self.common_args()
        question = self.question_var.get().strip()
        if question:
            args.extend(["--question", question])
        code, _, _ = self.run_module("dim_enrichment_engine.phase43_interactive", args)
        if code == 0:
            self.load_file_to_box("Build QA.md", self.qa_box)
            self.load_file_to_box("Question Answer.txt", self.summary_box)

    def run_scoring(self) -> None:
        if not self.validate_inputs(True):
            return
        args = self.common_args()
        question = self.question_var.get().strip() or "score this build"
        args.extend(["--question", question])
        code, _, _ = self.run_module("dim_enrichment_engine.phase70_scoring", args)
        if code == 0:
            self.load_file_to_box("Scoring.md", self.summary_box)
            self.load_file_to_box("Scoring Answer.txt", self.diff_box)

    def run_mode(self) -> None:
        if not self.validate_inputs(True):
            return
        args = self.common_args()
        args.extend(["--mode", self.mode_var.get()])
        code, _, _ = self.run_module("dim_enrichment_engine.phase132_modes", args)
        if code == 0:
            self.load_file_to_box("Phase132 Modes.md", self.qa_box)
            self.load_file_to_box("Phase132 Modes.md", self.summary_box)

    def run_feedback(self) -> None:
        if not self.validate_inputs(True):
            return
        args = self.common_args()
        args.extend(["--mode", self.mode_var.get(), "--feedback-result", self.feedback_var.get()])
        code, _, _ = self.run_module("dim_enrichment_engine.phase133_feedback", args)
        if code == 0:
            self.load_file_to_box("Phase133 Feedback.md", self.qa_box)
            self.load_file_to_box("Phase133 Feedback.md", self.summary_box)

    def run_refinement(self) -> None:
        if not self.validate_inputs(True):
            return
        args = self.common_args()
        code, _, _ = self.run_module("dim_enrichment_engine.phase115_refinement", args)
        if code == 0:
            self.load_file_to_box("Phase115 Refinement.md", self.summary_box)

    def run_execute(self) -> None:
        if not self.validate_inputs(False):
            return
        output_dir = self.output_var.get().strip()
        precheck = Path(output_dir) / "phase115_refinement.json"
        if not precheck.exists():
            messagebox.showwarning("Warmind", "Run Item Selection / Refinement first so Phase 12 has a selection payload.")
            return
        args = ["--output-dir", output_dir]
        if self.direct_equip_var.get():
            args.append("--direct-equip")
        if self.confirm_var.get():
            args.append("--confirm")
        code, _, _ = self.run_module("dim_enrichment_engine.phase120_execute", args)
        if code == 0:
            self.load_file_to_box("Phase120 Diff.md", self.diff_box)
            self.load_file_to_box("Phase120 Diff.md", self.summary_box)

    def open_output_folder(self) -> None:
        path = Path(self.output_var.get().strip())
        path.mkdir(parents=True, exist_ok=True)
        try:
            if sys.platform.startswith("win"):
                os.startfile(str(path))  # type: ignore[attr-defined]
            elif sys.platform == "darwin":
                subprocess.Popen(["open", str(path)])
            else:
                subprocess.Popen(["xdg-open", str(path)])
        except Exception as exc:
            messagebox.showerror("Warmind", f"Could not open output folder: {exc}")


def main() -> None:
    app = WarmindGUI()
    app.mainloop()


if __name__ == "__main__":
    main()
