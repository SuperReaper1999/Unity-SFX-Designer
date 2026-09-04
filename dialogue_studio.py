"""Local Kokoro dialogue authoring panel for Unity SFX Designer."""

import json
import os
import re
import subprocess
import sys
import threading
from pathlib import Path
from typing import Callable

import tkinter as tk
from tkinter import filedialog, messagebox, ttk

KOKORO_VOICES = (
    "bf_emma", "bf_isabella", "bf_lily", "bm_daniel", "bm_fable", "bm_george", "bm_lewis",
    "af_heart", "af_bella", "af_nicole", "am_fenrir", "am_michael", "am_onyx",
)
SPEAKER_PROFILES = {
    "Autumn": {"voice": "bf_emma", "notes": "Young adult woman; guarded but compassionate."},
    "Reeves": {"voice": "bm_george", "notes": "Adult man; weary, practical, dry survivor humour."},
    "Summer": {"voice": "bf_isabella", "notes": "Adult woman; reassuring, capable and warm."},
    "Narrator": {"voice": "bm_fable", "notes": "Measured, cinematic post-apocalyptic narration."},
    "Custom": {"voice": "bf_emma", "notes": ""},
}


def safe_filename(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_-]+", "_", value.strip())
    return cleaned.strip("_") or "dialogue_line"


def kokoro_language_for_voice(voice: str) -> str:
    return "b" if voice.startswith("b") else "a"


def generate_kokoro_wav(text: str, voice: str, speed: float, output_path: Path) -> None:
    if not text.strip():
        raise ValueError("Enter dialogue text before generating speech.")
    if not 0.5 <= speed <= 1.5:
        raise ValueError("Speech speed must be between 0.5 and 1.5.")
    tool_root = Path(__file__).resolve().parent
    local_python = tool_root / ".python312" / "python.exe"
    python_executable = str(local_python) if local_python.is_file() else sys.executable
    command = [
        python_executable, "-m", "kokoro", "--text", text, "--voice", voice,
        "--language", kokoro_language_for_voice(voice), "--speed", str(speed),
        "--output-file", str(output_path),
    ]
    package_dir = tool_root / ".local-tts"
    cache_dir = tool_root / ".kokoro-cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    environment = os.environ.copy()
    existing_python_path = environment.get("PYTHONPATH", "")
    environment["PYTHONPATH"] = str(package_dir) + (os.pathsep + existing_python_path if existing_python_path else "")
    environment["HF_HOME"] = str(cache_dir)
    environment["HF_HUB_CACHE"] = str(cache_dir / "huggingface")
    environment["TORCH_HOME"] = str(cache_dir / "torch")
    environment["XDG_CACHE_HOME"] = str(cache_dir)
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=600, check=False, env=environment)
    except FileNotFoundError as error:
        raise RuntimeError("Python could not be found for the local Kokoro generator.") from error
    except subprocess.TimeoutExpired as error:
        raise RuntimeError("Kokoro took too long to generate this line.") from error
    if result.returncode != 0:
        output = (result.stderr or result.stdout).strip()
        if "No module named kokoro" in output or "No module named 'kokoro'" in output:
            raise RuntimeError("Kokoro is not installed. Run Install Local Kokoro TTS.bat from this tool folder")
        raise RuntimeError(f"Kokoro generation failed:\n{output or 'No details returned.'}")
    if not output_path.is_file() or output_path.stat().st_size < 44:
        raise RuntimeError("Kokoro did not produce a valid WAV file.")


class DialogueStudio:
    """A Tk panel which queues and exports fully local Kokoro WAV dialogue."""

    def __init__(self, root: tk.Tk, set_status: Callable[[str], None]):
        self.root = root
        self.set_status = set_status
        self.lines: list[dict[str, str]] = []
        self.output_dir = tk.StringVar(value=str(Path.cwd() / "GeneratedDialogue"))
        self.speaker = tk.StringVar(value="Autumn")
        self.voice = tk.StringVar(value=SPEAKER_PROFILES["Autumn"]["voice"])
        self.line_id = tk.StringVar(value="autumn_intro_01")
        self.notes = tk.StringVar(value=SPEAKER_PROFILES["Autumn"]["notes"])
        self.speed = tk.StringVar(value="1.0")
        self.tree: ttk.Treeview | None = None
        self.text: tk.Text | None = None
        self.generate_current_button: ttk.Button | None = None
        self.generate_queue_button: ttk.Button | None = None

    def build(self, parent: ttk.Frame) -> None:
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(3, weight=1)

        info = ttk.LabelFrame(parent, text="Local Dialogue to WAV", padding=10)
        info.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        info.columnconfigure(0, weight=1)
        ttk.Label(
            info,
            text=("Runs Kokoro TTS locally: no API key, account, or per-line cost. The first generated line downloads "
                  "the model files once; later dialogue generation is offline. Character notes are kept in the manifest "
                  "for your authoring reference."),
            justify="left", wraplength=760,
        ).grid(row=0, column=0, sticky="w")

        form = ttk.LabelFrame(parent, text="Line", padding=10)
        form.grid(row=1, column=0, sticky="ew", pady=(0, 8))
        for column in (1, 3):
            form.columnconfigure(column, weight=1)

        ttk.Label(form, text="Speaker profile").grid(row=0, column=0, sticky="w", padx=(0, 6), pady=3)
        profile = ttk.Combobox(form, textvariable=self.speaker, values=tuple(SPEAKER_PROFILES), state="readonly", width=18)
        profile.grid(row=0, column=1, sticky="ew", pady=3)
        profile.bind("<<ComboboxSelected>>", self._apply_profile)
        ttk.Label(form, text="Kokoro voice").grid(row=0, column=2, sticky="w", padx=(12, 6), pady=3)
        ttk.Combobox(form, textvariable=self.voice, values=KOKORO_VOICES, state="readonly", width=16).grid(row=0, column=3, sticky="ew", pady=3)

        ttk.Label(form, text="Line ID").grid(row=1, column=0, sticky="w", padx=(0, 6), pady=3)
        ttk.Entry(form, textvariable=self.line_id).grid(row=1, column=1, sticky="ew", pady=3)
        ttk.Label(form, text="Speech speed (0.5–1.5)").grid(row=1, column=2, sticky="w", padx=(12, 6), pady=3)
        ttk.Entry(form, textvariable=self.speed).grid(row=1, column=3, sticky="ew", pady=3)

        ttk.Label(form, text="Character notes").grid(row=2, column=0, sticky="nw", padx=(0, 6), pady=(6, 3))
        ttk.Entry(form, textvariable=self.notes).grid(row=2, column=1, columnspan=3, sticky="ew", pady=(6, 3))
        ttk.Label(form, text="Dialogue text").grid(row=3, column=0, sticky="nw", padx=(0, 6), pady=(6, 3))
        self.text = tk.Text(form, height=5, wrap="word", undo=True)
        self.text.grid(row=3, column=1, columnspan=3, sticky="ew", pady=(6, 3))

        output = ttk.Frame(parent)
        output.grid(row=2, column=0, sticky="ew", pady=(0, 8))
        output.columnconfigure(1, weight=1)
        ttk.Label(output, text="Output folder").grid(row=0, column=0, sticky="w", padx=(0, 6))
        ttk.Entry(output, textvariable=self.output_dir).grid(row=0, column=1, sticky="ew")
        ttk.Button(output, text="Browse…", command=self._choose_output).grid(row=0, column=2, padx=(6, 0))
        ttk.Button(output, text="Add Current Line", command=self._add_current).grid(row=1, column=0, pady=(8, 0), sticky="w")
        self.generate_current_button = ttk.Button(output, text="Generate Current WAV", command=self._generate_current)
        self.generate_current_button.grid(row=1, column=1, pady=(8, 0), sticky="w")

        queue = ttk.LabelFrame(parent, text="Generation Queue", padding=8)
        queue.grid(row=3, column=0, sticky="nsew")
        queue.columnconfigure(0, weight=1)
        queue.rowconfigure(0, weight=1)
        self.tree = ttk.Treeview(queue, columns=("speaker", "line_id", "voice", "preview"), show="headings", height=9, selectmode="extended")
        for name, heading, width in (("speaker", "Speaker", 120), ("line_id", "Line ID", 190), ("voice", "Voice", 100), ("preview", "Text", 340)):
            self.tree.heading(name, text=heading)
            self.tree.column(name, width=width, stretch=name == "preview")
        self.tree.grid(row=0, column=0, sticky="nsew")
        scrollbar = ttk.Scrollbar(queue, orient="vertical", command=self.tree.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.tree.configure(yscrollcommand=scrollbar.set)
        actions = ttk.Frame(queue)
        actions.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(8, 0))
        ttk.Button(actions, text="Remove Selected", command=self._remove_selected).pack(side="left")
        ttk.Button(actions, text="Preview Selected WAV", command=self._preview_selected).pack(side="left", padx=6)
        ttk.Button(actions, text="Export Manifest", command=self._write_manifest).pack(side="right")
        self.generate_queue_button = ttk.Button(actions, text="Generate Queue", command=self._generate_queue)
        self.generate_queue_button.pack(side="right", padx=(0, 6))

    def _apply_profile(self, _event: object = None) -> None:
        profile = SPEAKER_PROFILES[self.speaker.get()]
        self.voice.set(profile["voice"])
        self.notes.set(profile["notes"])
        self.line_id.set(f"{self.speaker.get().lower()}_line_01")

    def _choose_output(self) -> None:
        selected = filedialog.askdirectory(initialdir=self.output_dir.get() or str(Path.cwd()))
        if selected:
            self.output_dir.set(selected)

    def _current_line(self) -> dict[str, str]:
        assert self.text is not None
        try:
            speed = float(self.speed.get())
        except ValueError as error:
            raise ValueError("Speech speed must be a number between 0.5 and 1.5.") from error
        if not 0.5 <= speed <= 1.5:
            raise ValueError("Speech speed must be between 0.5 and 1.5.")
        return {
            "speaker": self.speaker.get(), "voice": self.voice.get(), "line_id": safe_filename(self.line_id.get()),
            "text": self.text.get("1.0", "end-1c").strip(), "notes": self.notes.get().strip(), "speed": str(speed),
        }

    def _add_current(self) -> None:
        try:
            line = self._current_line()
        except ValueError as error:
            messagebox.showwarning("Dialogue Studio", str(error)); return
        if not line["text"]:
            messagebox.showwarning("Dialogue Studio", "Enter dialogue text before adding it to the queue."); return
        self.lines.append(line); self._refresh_queue(); self.set_status(f"Queued dialogue line: {line['line_id']}")

    def _refresh_queue(self) -> None:
        assert self.tree is not None
        self.tree.delete(*self.tree.get_children())
        for index, line in enumerate(self.lines):
            self.tree.insert("", "end", iid=str(index), values=(line["speaker"], line["line_id"], line["voice"], line["text"].replace("\n", " ")[:70]))

    def _remove_selected(self) -> None:
        assert self.tree is not None
        for index in sorted((int(item) for item in self.tree.selection()), reverse=True): self.lines.pop(index)
        self._refresh_queue()

    def _generate_current(self) -> None:
        try:
            line = self._current_line()
        except ValueError as error:
            messagebox.showwarning("Dialogue Studio", str(error)); return
        if not line["text"]:
            messagebox.showwarning("Dialogue Studio", "Enter dialogue text before generating it."); return
        self._start_generation([line])

    def _generate_queue(self) -> None:
        if not self.lines:
            messagebox.showwarning("Dialogue Studio", "Add at least one line to the generation queue."); return
        self._start_generation(list(self.lines))

    def _start_generation(self, lines: list[dict[str, str]]) -> None:
        self._set_busy(True); self.set_status(f"Generating {len(lines)} local Kokoro WAV file(s)…")
        threading.Thread(target=self._generate_worker, args=(lines,), daemon=True).start()

    def _generate_worker(self, lines: list[dict[str, str]]) -> None:
        try:
            directory = Path(self.output_dir.get()).expanduser(); directory.mkdir(parents=True, exist_ok=True)
            generated: list[dict[str, str]] = []
            for index, line in enumerate(lines, start=1):
                self.root.after(0, self.set_status, f"Generating {index}/{len(lines)} locally: {line['line_id']}")
                filename = f"{safe_filename(line['speaker'])}_{safe_filename(line['line_id'])}.wav"
                generate_kokoro_wav(line["text"], line["voice"], float(line["speed"]), directory / filename)
                generated.append({**line, "file": filename})
            self._write_manifest_file(directory, generated)
            self.root.after(0, self._generation_complete, directory, len(generated))
        except Exception as error:
            self.root.after(0, self._generation_failed, str(error))

    def _generation_complete(self, directory: Path, count: int) -> None:
        self._set_busy(False); self.set_status(f"Generated {count} local dialogue WAV file(s) in {directory}")
        messagebox.showinfo("Dialogue Studio", f"Generated {count} WAV file(s).\n\n{directory}")

    def _generation_failed(self, error: str) -> None:
        self._set_busy(False); self.set_status("Local dialogue generation failed."); messagebox.showerror("Dialogue Studio", error)

    def _set_busy(self, busy: bool) -> None:
        state = "disabled" if busy else "normal"
        if self.generate_current_button is not None: self.generate_current_button.configure(state=state)
        if self.generate_queue_button is not None: self.generate_queue_button.configure(state=state)

    def _write_manifest_file(self, directory: Path, lines: list[dict[str, str]]) -> Path:
        path = directory / "dialogue_manifest.json"
        path.write_text(json.dumps({"format": "unity-dialogue-manifest-v1", "engine": "kokoro-local", "notes": "Assign generated WAV clips to matching DialogueNode voice clip slots.", "lines": lines}, indent=2, ensure_ascii=False), encoding="utf-8")
        return path

    def _write_manifest(self) -> None:
        if not self.lines:
            messagebox.showwarning("Dialogue Studio", "Add dialogue lines before exporting a manifest."); return
        directory = Path(self.output_dir.get()).expanduser(); directory.mkdir(parents=True, exist_ok=True)
        self.set_status(f"Exported dialogue manifest: {self._write_manifest_file(directory, self.lines)}")

    def _preview_selected(self) -> None:
        assert self.tree is not None
        selected = self.tree.selection()
        if not selected:
            messagebox.showwarning("Dialogue Studio", "Select a queued line to preview its generated WAV file."); return
        line = self.lines[int(selected[0])]
        path = Path(self.output_dir.get()) / f"{safe_filename(line['speaker'])}_{safe_filename(line['line_id'])}.wav"
        if not path.is_file():
            messagebox.showwarning("Dialogue Studio", f"No generated WAV found yet for {line['line_id']}."); return
        try:
            import winsound
            winsound.PlaySound(str(path), winsound.SND_FILENAME | winsound.SND_ASYNC)
        except Exception as error:
            messagebox.showerror("Dialogue Studio", f"Could not preview WAV:\n{error}")
