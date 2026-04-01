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
        self.geometry("980x760")
        self.minsize(900, 700)

        self.weapons_var = tk.StringVar()
        self.armor_var = tk.StringVar()
        self.loadouts_var = tk.StringVar()
        self.output_var = tk.StringVar(value=str(Path.cwd() / "output"))
        self.question_var = tk.StringVar()

        self._build_ui()

    def _build_ui(self) -> None:
        root = ttk.Frame(self, padding=12)
        root.pack(fill="both", expand=True)

        title = ttk.Label(root, text="Warmind", font=("Segoe UI", 20, "bold"))
        title.pack(anchor="w")
        subtitle = ttk.Label(root, text="Destiny Intelligence Engine | GUI Wrapper v1")
        subtitle.pack(anchor="w", pady=(0, 12))

        files = ttk.LabelFrame(root, text="DIM Inputs", padding=12)
        files.pack(fill="x", pady=(0, 12))

        self._file_row(files, 0, "Weapons CSV", self.weapons_var)
        self._file_row(files, 1, "Armor CSV", self.armor_var)
        self._file_row(files, 2, "Loadouts CSV", self.loadouts_var, required=False)
        self._file_row(files, 3, "Output Folder", self.output_var, folder=True)

        qf = ttk.LabelFrame(root, text="Interactive Question", padding=12)
        qf.pack(fill="x", pady=(0, 12))
        ttk.Label(qf, text="Ask Warmind something specific about the build").grid(row=0, column=0, sticky="w")
        ttk.Entry(qf, textvariable=self.question_var, width=90).grid(row=1, column=0, sticky="ew", pady=(6, 0))
        qf.columnconfigure(0, weight=1)

        actions = ttk.Frame(root)
        actions.pack(fill="x", pady=(0, 12))
        ttk.Button(actions, text="Run Interactive Analysis", command=self.run_analysis).pack(side="left")
        ttk.Button(actions, text="Open Build QA.md", command=lambda: self.open_output_file("Build QA.md")).pack(side="left", padx=(8, 0))
        ttk.Button(actions, text="Open qa_context.json", command=lambda: self.open_output_file("qa_context.json")).pack(side="left", padx=(8, 0))
        ttk.Button(actions, text="Open output folder", command=self.open_output_folder).pack(side="left", padx=(8, 0))

        results = ttk.LabelFrame(root, text="Warmind Output", padding=12)
        results.pack(fill="both", expand=True)
        self.output_box = scrolledtext.ScrolledText(results, wrap="word", font=("Consolas", 10))
        self.output_box.pack(fill="both", expand=True)
        self.output_box.insert("end", "Warmind GUI ready. Select your DIM exports, optionally ask a question, then run analysis.\n")
        self.output_box.configure(state="disabled")

    def _file_row(self, parent: ttk.LabelFrame, row: int, label: str, variable: tk.StringVar, folder: bool = False, required: bool = True) -> None:
        suffix = " *" if required else ""
        ttk.Label(parent, text=label + suffix).grid(row=row, column=0, sticky="w", padx=(0, 8), pady=4)
        entry = ttk.Entry(parent, textvariable=variable, width=85)
        entry.grid(row=row, column=1, sticky="ew", pady=4)
        browse_cmd = (lambda v=variable: self.pick_folder(v)) if folder else (lambda v=variable: self.pick_file(v))
        ttk.Button(parent, text="Browse", command=browse_cmd).grid(row=row, column=2, padx=(8, 0), pady=4)
        parent.columnconfigure(1, weight=1)

    def pick_file(self, variable: tk.StringVar) -> None:
        path = filedialog.askopenfilename(filetypes=[("CSV files", "*.csv"), ("All files", "*.*")])
        if path:
            variable.set(path)

    def pick_folder(self, variable: tk.StringVar) -> None:
        path = filedialog.askdirectory()
        if path:
            variable.set(path)

    def append_output(self, text: str) -> None:
        self.output_box.configure(state="normal")
        self.output_box.insert("end", text + "\n")
        self.output_box.see("end")
        self.output_box.configure(state="disabled")
        self.update_idletasks()

    def validate_inputs(self) -> bool:
        weapons = Path(self.weapons_var.get().strip())
        armor = Path(self.armor_var.get().strip())
        loadouts = self.loadouts_var.get().strip()
        output = Path(self.output_var.get().strip())

        missing = []
        if not weapons.exists():
            missing.append("Weapons CSV")
        if not armor.exists():
            missing.append("Armor CSV")
        if loadouts and not Path(loadouts).exists():
            missing.append("Loadouts CSV")
        if not output:
            missing.append("Output folder")

        if missing:
            messagebox.showerror("Warmind", "Missing or invalid inputs: " + ", ".join(missing))
            return False
        return True

    def run_analysis(self) -> None:
        if not self.validate_inputs():
            return

        weapons = self.weapons_var.get().strip()
        armor = self.armor_var.get().strip()
        loadouts = self.loadouts_var.get().strip()
        output = self.output_var.get().strip()
        question = self.question_var.get().strip()

        cmd = [
            sys.executable,
            "-m",
            "dim_enrichment_engine.phase43_interactive",
            "--weapons", weapons,
            "--armor", armor,
            "--output-dir", output,
        ]
        if loadouts:
            cmd.extend(["--loadouts", loadouts])
        if question:
            cmd.extend(["--question", question])

        self.append_output("=" * 80)
        self.append_output("Running Warmind interactive analysis...")
        self.append_output("Command: " + " ".join(f'\"{c}\"' if ' ' in c else c for c in cmd))

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                cwd=str(Path.cwd()),
                check=False,
            )
        except Exception as exc:
            messagebox.showerror("Warmind", f"Failed to run Warmind: {exc}")
            self.append_output(f"ERROR: {exc}")
            return

        if result.stdout.strip():
            self.append_output("STDOUT:\n" + result.stdout.strip())
        if result.stderr.strip():
            self.append_output("STDERR:\n" + result.stderr.strip())

        if result.returncode != 0:
            self.append_output(f"Warmind failed with exit code {result.returncode}.")
            messagebox.showerror("Warmind", f"Warmind failed with exit code {result.returncode}. See output log.")
            return

        self.append_output("Warmind completed successfully.")
        self.load_generated_outputs(Path(output), question)

    def load_generated_outputs(self, output_dir: Path, question: str) -> None:
        qa_md = output_dir / "Build QA.md"
        qa_txt = output_dir / "Question Answer.txt"
        qa_json = output_dir / "qa_context.json"

        if qa_md.exists():
            self.append_output("Loaded Build QA.md")
            self.append_output("-" * 80)
            self.append_output(qa_md.read_text(encoding="utf-8", errors="ignore"))
        if question and qa_txt.exists():
            self.append_output("-" * 80)
            self.append_output("Direct answer:")
            self.append_output(qa_txt.read_text(encoding="utf-8", errors="ignore").strip())
        if qa_json.exists():
            self.append_output("-" * 80)
            self.append_output(f"qa_context.json saved to: {qa_json}")

    def open_output_file(self, filename: str) -> None:
        path = Path(self.output_var.get().strip()) / filename
        if not path.exists():
            messagebox.showwarning("Warmind", f"File not found: {path}")
            return
        self._open_path(path)

    def open_output_folder(self) -> None:
        path = Path(self.output_var.get().strip())
        if not path.exists():
            path.mkdir(parents=True, exist_ok=True)
        self._open_path(path)

    def _open_path(self, path: Path) -> None:
        try:
            if sys.platform.startswith("win"):
                os.startfile(str(path))  # type: ignore[attr-defined]
            elif sys.platform == "darwin":
                subprocess.Popen(["open", str(path)])
            else:
                subprocess.Popen(["xdg-open", str(path)])
        except Exception as exc:
            messagebox.showerror("Warmind", f"Could not open path: {exc}")


def main() -> None:
    app = WarmindGUI()
    app.mainloop()


if __name__ == "__main__":
    main()
