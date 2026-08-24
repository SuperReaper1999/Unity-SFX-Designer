"""Standalone procedural SFX designer with Unity-ready WAV export.

Requires Python 3 on Windows. The audio engine deliberately uses only the
standard library so the tool can travel with the Unity project.
"""

from __future__ import annotations

import argparse
import copy
import json
import math
import os
import random
import struct
import sys
import tempfile
import wave
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any

try:
    import tkinter as tk
    from tkinter import filedialog, messagebox, ttk
except ImportError:  # pragma: no cover - only relevant to unusual Python installs
    tk = None

try:
    import winsound
except ImportError:  # pragma: no cover - enables non-Windows self-tests
    winsound = None


APP_TITLE = "Unity SFX Designer"
PROJECT_VERSION = 1
DEFAULT_SAMPLE_RATE = 44100
MAX_DURATION_SECONDS = 12.0


@dataclass
class Layer:
    enabled: bool = False
    frequency: float = 440.0
    gain: float = 0.25
    phase_degrees: float = 0.0
    sweep_start: float = 0.0
    sweep_end: float = 0.0
    start_time: float = 0.0
    end_time: float = 1.0


def default_state() -> dict[str, Any]:
    return {
        "version": PROJECT_VERSION,
        "name": "NewSound",
        "duration": 0.75,
        "sample_rate": DEFAULT_SAMPLE_RATE,
        "master_gain": 0.8,
        "attack": 0.01,
        "decay": 0.08,
        "sustain": 0.7,
        "release": 0.16,
        "noise_enabled": False,
        "noise_gain": 0.0,
        "noise_seed": 1337,
        "lowpass_hz": 0.0,
        "distortion": 0.0,
        "normalize": True,
        "preset": "Custom",
        "layers": [asdict(Layer(enabled=index == 0)) for index in range(4)],
    }


def make_preset(preset_name: str, **changes: Any) -> dict[str, Any]:
    state = default_state()
    state.update(changes)
    state["preset"] = preset_name
    return state


PRESETS: dict[str, dict[str, Any]] = {
    "Custom": default_state(),
    "UI Click": make_preset(
        "UI Click", name="UI_Click", duration=0.12, attack=0.001, decay=0.03,
        sustain=0.0, release=0.05, layers=[
            asdict(Layer(True, 1200, 0.42, 0, -400, 0, 0, 0.12)),
            asdict(Layer(True, 1800, 0.18, 0, -700, 0, 0, 0.07)),
            asdict(Layer()), asdict(Layer()),
        ],
    ),
    "Pickup": make_preset(
        "Pickup", name="Pickup", duration=0.36, attack=0.004, decay=0.06,
        sustain=0.5, release=0.11, layers=[
            asdict(Layer(True, 440, 0.28, 0, 0, 640, 0, 0.36)),
            asdict(Layer(True, 880, 0.14, 0, 0, 420, 0.05, 0.34)),
            asdict(Layer()), asdict(Layer()),
        ],
    ),
    "Hit": make_preset(
        "Hit", name="Hit", duration=0.22, attack=0.001, decay=0.04,
        sustain=0.0, release=0.08, noise_enabled=True, noise_gain=0.13,
        lowpass_hz=3800, distortion=0.18, layers=[
            asdict(Layer(True, 210, 0.6, 0, -150, 0, 0, 0.2)),
            asdict(Layer(True, 580, 0.13, 0, -420, 0, 0, 0.08)),
            asdict(Layer()), asdict(Layer()),
        ],
    ),
    "Gunshot Impact": make_preset(
        "Gunshot Impact", name="Gunshot_Impact", duration=0.42, attack=0.001,
        decay=0.03, sustain=0.0, release=0.22, noise_enabled=True, noise_gain=0.42,
        lowpass_hz=5400, distortion=0.45, layers=[
            asdict(Layer(True, 95, 0.72, 0, -65, 0, 0, 0.32)),
            asdict(Layer(True, 185, 0.3, 0, -100, 0, 0, 0.2)),
            asdict(Layer(True, 1350, 0.11, 0, -900, 0, 0, 0.07)),
            asdict(Layer()),
        ],
    ),
    "Explosion Burst": make_preset(
        "Explosion Burst", name="Explosion_Burst", duration=1.25, attack=0.002,
        decay=0.18, sustain=0.28, release=0.44, noise_enabled=True, noise_gain=0.5,
        lowpass_hz=2200, distortion=0.35, layers=[
            asdict(Layer(True, 58, 0.75, 0, -36, 0, 0, 0.9)),
            asdict(Layer(True, 112, 0.28, 0, -80, 0, 0, 0.55)),
            asdict(Layer(True, 260, 0.1, 0, -170, 0, 0, 0.2)),
            asdict(Layer()),
        ],
    ),
    "Zombie Groan": make_preset(
        "Zombie Groan", name="Zombie_Groan", duration=1.8, attack=0.12, decay=0.16,
        sustain=0.72, release=0.4, lowpass_hz=1250, distortion=0.12, layers=[
            asdict(Layer(True, 110, 0.38, 0, -12, 8, 0, 1.8)),
            asdict(Layer(True, 164, 0.2, 70, -18, 5, 0.1, 1.6)),
            asdict(Layer(True, 55, 0.12, 0, 0, 0, 0, 1.8)),
            asdict(Layer()),
        ],
    ),
    "Ambient Hum": make_preset(
        "Ambient Hum", name="Ambient_Hum", duration=3.0, attack=0.5, decay=0.2,
        sustain=0.85, release=0.65, lowpass_hz=1500, layers=[
            asdict(Layer(True, 60, 0.33, 0, 0, 0, 0, 3.0)),
            asdict(Layer(True, 120, 0.14, 0, 0, 0, 0, 3.0)),
            asdict(Layer(True, 180, 0.08, 0, 0, 0, 0, 3.0)),
            asdict(Layer()),
        ],
    ),
}


def clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, value))


def validate_state(state: dict[str, Any]) -> dict[str, Any]:
    """Return a normalized copy suitable for synthesis or persistence."""
    result = default_state()
    result.update({key: value for key, value in state.items() if key != "layers"})
    result["name"] = str(result["name"]).strip() or "NewSound"
    result["duration"] = clamp(float(result["duration"]), 0.01, MAX_DURATION_SECONDS)
    result["sample_rate"] = int(result["sample_rate"])
    if result["sample_rate"] not in (22050, 44100, 48000):
        result["sample_rate"] = DEFAULT_SAMPLE_RATE
    result["master_gain"] = clamp(float(result["master_gain"]), 0.0, 2.0)
    result["attack"] = max(0.0, float(result["attack"]))
    result["decay"] = max(0.0, float(result["decay"]))
    result["sustain"] = clamp(float(result["sustain"]), 0.0, 1.0)
    result["release"] = max(0.0, float(result["release"]))
    result["noise_gain"] = clamp(float(result["noise_gain"]), 0.0, 1.0)
    result["noise_seed"] = int(result["noise_seed"])
    result["lowpass_hz"] = max(0.0, float(result["lowpass_hz"]))
    result["distortion"] = clamp(float(result["distortion"]), 0.0, 1.0)
    result["noise_enabled"] = bool(result["noise_enabled"])
    result["normalize"] = bool(result["normalize"])

    supplied_layers = state.get("layers", [])
    result["layers"] = []
    for index in range(4):
        raw = supplied_layers[index] if index < len(supplied_layers) else {}
        layer = asdict(Layer())
        layer.update(raw)
        layer["enabled"] = bool(layer["enabled"])
        layer["frequency"] = clamp(float(layer["frequency"]), 1.0, 20000.0)
        layer["gain"] = clamp(float(layer["gain"]), 0.0, 2.0)
        layer["phase_degrees"] = float(layer["phase_degrees"])
        layer["sweep_start"] = clamp(float(layer["sweep_start"]), -19000.0, 19000.0)
        layer["sweep_end"] = clamp(float(layer["sweep_end"]), -19000.0, 19000.0)
        layer["start_time"] = clamp(float(layer["start_time"]), 0.0, result["duration"])
        layer["end_time"] = clamp(float(layer["end_time"]), layer["start_time"], result["duration"])
        result["layers"].append(layer)
    result["version"] = PROJECT_VERSION
    return result


def envelope(time_seconds: float, duration: float, state: dict[str, Any]) -> float:
    attack = state["attack"]
    decay = state["decay"]
    release = state["release"]
    sustain = state["sustain"]
    release_start = max(0.0, duration - release)
    if attack > 0 and time_seconds < attack:
        return time_seconds / attack
    if decay > 0 and time_seconds < attack + decay:
        return 1.0 - (1.0 - sustain) * ((time_seconds - attack) / decay)
    if release > 0 and time_seconds >= release_start:
        return sustain * clamp((duration - time_seconds) / release, 0.0, 1.0)
    return sustain


def generate_samples(raw_state: dict[str, Any]) -> tuple[list[float], dict[str, Any]]:
    """Synthesize a deterministic mono floating-point buffer."""
    state = validate_state(raw_state)
    sample_rate = state["sample_rate"]
    count = max(1, int(state["duration"] * sample_rate))
    duration = state["duration"]
    samples = [0.0] * count
    random_source = random.Random(state["noise_seed"])

    for sample_index in range(count):
        time_seconds = sample_index / sample_rate
        value = 0.0
        for layer in state["layers"]:
            if not layer["enabled"] or not (layer["start_time"] <= time_seconds <= layer["end_time"]):
                continue
            layer_duration = max(0.0001, layer["end_time"] - layer["start_time"])
            progress = clamp((time_seconds - layer["start_time"]) / layer_duration, 0.0, 1.0)
            frequency = layer["frequency"] + layer["sweep_start"] * (1.0 - progress) + layer["sweep_end"] * progress
            frequency = clamp(frequency, 1.0, sample_rate * 0.45)
            phase = math.radians(layer["phase_degrees"])
            value += math.sin(math.tau * frequency * time_seconds + phase) * layer["gain"]
        if state["noise_enabled"]:
            value += random_source.uniform(-1.0, 1.0) * state["noise_gain"]
        samples[sample_index] = value * envelope(time_seconds, duration, state)

    if state["lowpass_hz"] > 0.0:
        cutoff = min(state["lowpass_hz"], sample_rate * 0.45)
        alpha = (math.tau * cutoff) / (sample_rate + math.tau * cutoff)
        filtered = 0.0
        for index, value in enumerate(samples):
            filtered += alpha * (value - filtered)
            samples[index] = filtered

    if state["distortion"] > 0.0:
        drive = 1.0 + state["distortion"] * 14.0
        for index, value in enumerate(samples):
            samples[index] = math.tanh(value * drive) / math.tanh(drive)

    peak = max((abs(value) for value in samples), default=0.0)
    if state["normalize"] and peak > 0.000001:
        scale = min(1.0 / peak, 4.0) * state["master_gain"]
    else:
        scale = state["master_gain"]
    return [clamp(value * scale, -1.0, 1.0) for value in samples], state


def write_wav(path: str | Path, samples: list[float], sample_rate: int) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    pcm = bytearray()
    for sample in samples:
        value = int(clamp(sample, -1.0, 1.0) * 32767)
        pcm.extend(struct.pack("<h", value))
    with wave.open(str(path), "wb") as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(sample_rate)
        output.writeframes(pcm)


class SfxDesigner:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title(APP_TITLE)
        self.root.minsize(1120, 720)
        self.state = default_state()
        self.preview_file: str | None = None
        self.global_vars: dict[str, Any] = {}
        self.layer_vars: list[dict[str, Any]] = []
        self._build_ui()
        self._load_state_into_ui(self.state)
        self.refresh_waveform()

    def _build_ui(self) -> None:
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(1, weight=1)
        toolbar = ttk.Frame(self.root, padding=10)
        toolbar.grid(row=0, column=0, sticky="ew")
        toolbar.columnconfigure(5, weight=1)

        self.preset_var = tk.StringVar(value="Custom")
        ttk.Label(toolbar, text="Preset").grid(row=0, column=0, padx=(0, 5))
        preset_box = ttk.Combobox(toolbar, textvariable=self.preset_var, values=list(PRESETS), state="readonly", width=20)
        preset_box.grid(row=0, column=1, padx=(0, 10))
        preset_box.bind("<<ComboboxSelected>>", lambda _event: self.apply_preset())
        ttk.Button(toolbar, text="New", command=self.new_project).grid(row=0, column=2, padx=3)
        ttk.Button(toolbar, text="Open Project", command=self.open_project).grid(row=0, column=3, padx=3)
        ttk.Button(toolbar, text="Save Project", command=self.save_project).grid(row=0, column=4, padx=3)
        ttk.Button(toolbar, text="Preview", command=self.preview).grid(row=0, column=6, padx=3)
        ttk.Button(toolbar, text="Stop", command=self.stop_preview).grid(row=0, column=7, padx=3)
        ttk.Button(toolbar, text="Export WAV", command=self.export_wav).grid(row=0, column=8, padx=3)

        content = ttk.Panedwindow(self.root, orient=tk.HORIZONTAL)
        content.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 10))
        controls = ttk.Frame(content, padding=6)
        preview = ttk.Frame(content, padding=6)
        content.add(controls, weight=3)
        content.add(preview, weight=2)

        self._build_controls(controls)
        ttk.Label(preview, text="Generated waveform", font=("Segoe UI", 11, "bold")).pack(anchor="w")
        self.canvas = tk.Canvas(preview, height=240, background="#10131a", highlightthickness=0)
        self.canvas.pack(fill="x", pady=(8, 12))
        self.canvas.bind("<Configure>", lambda _event: self.refresh_waveform())
        ttk.Label(preview, text="Output is 16-bit mono PCM WAV. Unity imports it directly as an AudioClip.", wraplength=330).pack(anchor="w")
        self.status = tk.StringVar(value="Ready")
        ttk.Label(self.root, textvariable=self.status, relief=tk.SUNKEN, anchor="w", padding=(8, 4)).grid(row=2, column=0, sticky="ew")

    def _add_field(self, parent: ttk.Frame, row: int, column: int, label: str, key: str, default: Any, width: int = 9) -> None:
        variable = tk.StringVar(value=str(default))
        self.global_vars[key] = variable
        ttk.Label(parent, text=label).grid(row=row, column=column, sticky="w", padx=(0, 4), pady=2)
        ttk.Entry(parent, textvariable=variable, width=width).grid(row=row, column=column + 1, sticky="w", padx=(0, 10), pady=2)

    def _build_controls(self, parent: ttk.Frame) -> None:
        parent.columnconfigure(0, weight=1)
        global_frame = ttk.LabelFrame(parent, text="Global output", padding=8)
        global_frame.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        self._add_field(global_frame, 0, 0, "Name", "name", "NewSound", 16)
        self._add_field(global_frame, 0, 2, "Duration (s)", "duration", 0.75)
        self._add_field(global_frame, 0, 4, "Master gain", "master_gain", 0.8)
        ttk.Label(global_frame, text="Sample rate").grid(row=1, column=0, sticky="w", padx=(0, 4), pady=2)
        self.global_vars["sample_rate"] = tk.StringVar(value=str(DEFAULT_SAMPLE_RATE))
        ttk.Combobox(global_frame, textvariable=self.global_vars["sample_rate"], values=(22050, 44100, 48000), state="readonly", width=13).grid(row=1, column=1, sticky="w", padx=(0, 10), pady=2)
        self.global_vars["normalize"] = tk.BooleanVar(value=True)
        ttk.Checkbutton(global_frame, text="Normalize", variable=self.global_vars["normalize"]).grid(row=1, column=2, sticky="w", pady=2)
        ttk.Button(global_frame, text="Refresh waveform", command=self.refresh_waveform).grid(row=1, column=4, columnspan=2, sticky="w", pady=2)

        envelope_frame = ttk.LabelFrame(parent, text="Master envelope (ADSR)", padding=8)
        envelope_frame.grid(row=1, column=0, sticky="ew", pady=(0, 8))
        self._add_field(envelope_frame, 0, 0, "Attack", "attack", 0.01)
        self._add_field(envelope_frame, 0, 2, "Decay", "decay", 0.08)
        self._add_field(envelope_frame, 0, 4, "Sustain", "sustain", 0.7)
        self._add_field(envelope_frame, 0, 6, "Release", "release", 0.16)

        effects_frame = ttk.LabelFrame(parent, text="Noise and master effects", padding=8)
        effects_frame.grid(row=2, column=0, sticky="ew", pady=(0, 8))
        self.global_vars["noise_enabled"] = tk.BooleanVar(value=False)
        ttk.Checkbutton(effects_frame, text="White noise", variable=self.global_vars["noise_enabled"]).grid(row=0, column=0, sticky="w", padx=(0, 8))
        self._add_field(effects_frame, 0, 1, "Noise gain", "noise_gain", 0.0)
        self._add_field(effects_frame, 0, 3, "Seed", "noise_seed", 1337)
        self._add_field(effects_frame, 1, 0, "Low-pass Hz (0 off)", "lowpass_hz", 0.0, 12)
        self._add_field(effects_frame, 1, 2, "Distortion", "distortion", 0.0)

        layers_frame = ttk.LabelFrame(parent, text="Sine-wave layers", padding=8)
        layers_frame.grid(row=3, column=0, sticky="nsew")
        headers = ("On", "Frequency", "Gain", "Phase°", "Sweep start", "Sweep end", "Start", "End")
        for column, title in enumerate(headers):
            ttk.Label(layers_frame, text=title, font=("Segoe UI", 9, "bold")).grid(row=0, column=column, padx=3, pady=(0, 4), sticky="w")
        for index in range(4):
            values: dict[str, Any] = {"enabled": tk.BooleanVar(value=index == 0)}
            ttk.Checkbutton(layers_frame, text=f"L{index + 1}", variable=values["enabled"]).grid(row=index + 1, column=0, sticky="w", padx=3, pady=2)
            for column, key, default in (
                (1, "frequency", 440.0), (2, "gain", 0.25), (3, "phase_degrees", 0.0),
                (4, "sweep_start", 0.0), (5, "sweep_end", 0.0), (6, "start_time", 0.0), (7, "end_time", 0.75),
            ):
                values[key] = tk.StringVar(value=str(default))
                ttk.Entry(layers_frame, textvariable=values[key], width=10).grid(row=index + 1, column=column, padx=3, pady=2)
            self.layer_vars.append(values)

    @staticmethod
    def _number(variable: tk.StringVar, label: str) -> float:
        try:
            return float(variable.get())
        except ValueError as error:
            raise ValueError(f"{label} must be a number.") from error

    def _state_from_ui(self) -> dict[str, Any]:
        state = default_state()
        for key in ("name",):
            state[key] = self.global_vars[key].get()
        for key in ("duration", "master_gain", "attack", "decay", "sustain", "release", "noise_gain", "lowpass_hz", "distortion"):
            state[key] = self._number(self.global_vars[key], key.replace("_", " "))
        state["sample_rate"] = int(self.global_vars["sample_rate"].get())
        state["noise_seed"] = int(self._number(self.global_vars["noise_seed"], "noise seed"))
        state["noise_enabled"] = self.global_vars["noise_enabled"].get()
        state["normalize"] = self.global_vars["normalize"].get()
        state["preset"] = self.preset_var.get()
        state["layers"] = []
        for variables in self.layer_vars:
            state["layers"].append({
                "enabled": variables["enabled"].get(),
                **{key: self._number(variables[key], key.replace("_", " ")) for key in variables if key != "enabled"},
            })
        return validate_state(state)

    def _load_state_into_ui(self, raw_state: dict[str, Any]) -> None:
        state = validate_state(raw_state)
        self.preset_var.set(state.get("preset", "Custom"))
        for key, variable in self.global_vars.items():
            if key in ("noise_enabled", "normalize"):
                variable.set(state[key])
            else:
                variable.set(str(state[key]))
        for layer_state, variables in zip(state["layers"], self.layer_vars):
            for key, variable in variables.items():
                variable.set(layer_state[key] if key == "enabled" else str(layer_state[key]))
        self.state = state

    def _generate(self) -> tuple[list[float], dict[str, Any]]:
        state = self._state_from_ui()
        samples, normalized = generate_samples(state)
        self.state = normalized
        return samples, normalized

    def refresh_waveform(self) -> None:
        if not hasattr(self, "canvas"):
            return
        try:
            samples, _state = self._generate()
        except (ValueError, OverflowError) as error:
            self.status.set(str(error))
            return
        canvas = self.canvas
        canvas.delete("all")
        width, height = max(10, canvas.winfo_width()), max(10, canvas.winfo_height())
        middle = height / 2
        canvas.create_line(0, middle, width, middle, fill="#35445c")
        points: list[float] = []
        for pixel in range(width):
            start = int(pixel * len(samples) / width)
            end = max(start + 1, int((pixel + 1) * len(samples) / width))
            section = samples[start:end]
            value = sum(section) / len(section)
            points.extend((pixel, middle - value * (height * 0.42)))
        if len(points) >= 4:
            canvas.create_line(*points, fill="#63c5ff", width=1.4, smooth=True)
        self.status.set(f"Generated {len(samples):,} samples at {_state['sample_rate']:,} Hz")

    def apply_preset(self) -> None:
        self._load_state_into_ui(copy.deepcopy(PRESETS[self.preset_var.get()]))
        self.refresh_waveform()

    def new_project(self) -> None:
        self.stop_preview()
        self._load_state_into_ui(default_state())
        self.refresh_waveform()

    def preview(self) -> None:
        try:
            samples, state = self._generate()
            self.stop_preview()
            file_handle = tempfile.NamedTemporaryFile(prefix="unity_sfx_", suffix=".wav", delete=False)
            file_handle.close()
            self.preview_file = file_handle.name
            write_wav(self.preview_file, samples, state["sample_rate"])
            if winsound is None:
                self.status.set("Preview is only available on Windows. WAV was generated successfully.")
                return
            winsound.PlaySound(self.preview_file, winsound.SND_FILENAME | winsound.SND_ASYNC)
            self.status.set("Preview playing")
        except (ValueError, OSError, OverflowError) as error:
            messagebox.showerror(APP_TITLE, str(error))

    def stop_preview(self) -> None:
        if winsound is not None:
            winsound.PlaySound(None, 0)
        if self.preview_file:
            try:
                os.unlink(self.preview_file)
            except OSError:
                pass
            self.preview_file = None

    def export_wav(self) -> None:
        try:
            samples, state = self._generate()
            filename = filedialog.asksaveasfilename(
                title="Export Unity-ready WAV",
                defaultextension=".wav",
                initialfile=f"{state['name']}.wav",
                filetypes=(("WAV audio", "*.wav"),),
            )
            if not filename:
                return
            write_wav(filename, samples, state["sample_rate"])
            self.status.set(f"Exported {Path(filename).name}")
            messagebox.showinfo(APP_TITLE, "Exported Unity-ready 16-bit mono WAV.\n\nDrag it into your Unity Assets folder or choose it in the Project window.")
        except (ValueError, OSError, OverflowError) as error:
            messagebox.showerror(APP_TITLE, str(error))

    def save_project(self) -> None:
        try:
            state = self._state_from_ui()
            filename = filedialog.asksaveasfilename(
                title="Save SFX project", defaultextension=".json",
                initialfile=f"{state['name']}.json", filetypes=(("SFX project", "*.json"),),
            )
            if not filename:
                return
            with open(filename, "w", encoding="utf-8") as output:
                json.dump(state, output, indent=2)
            self.status.set(f"Saved {Path(filename).name}")
        except (ValueError, OSError) as error:
            messagebox.showerror(APP_TITLE, str(error))

    def open_project(self) -> None:
        filename = filedialog.askopenfilename(title="Open SFX project", filetypes=(("SFX project", "*.json"), ("JSON", "*.json")))
        if not filename:
            return
        try:
            with open(filename, "r", encoding="utf-8") as source:
                state = json.load(source)
            if not isinstance(state, dict):
                raise ValueError("The project file must contain an object.")
            self.stop_preview()
            self._load_state_into_ui(state)
            self.refresh_waveform()
            self.status.set(f"Opened {Path(filename).name}")
        except (ValueError, OSError, json.JSONDecodeError) as error:
            messagebox.showerror(APP_TITLE, f"Could not open project:\n{error}")


def run_self_test() -> int:
    """Validate all built-in presets and the exact Unity WAV contract."""
    failures: list[str] = []
    # Synthesis must be deterministic: project save/load must never subtly
    # alter the resulting audio, especially when white noise is enabled.
    deterministic_state = copy.deepcopy(PRESETS["Gunshot Impact"])
    first, normalized = generate_samples(deterministic_state)
    second, _ = generate_samples(copy.deepcopy(normalized))
    if first != second:
        failures.append("Deterministic noise/synthesis mismatch")

    # A project with every sound source disabled must be valid silence.
    silent_state = default_state()
    silent_state["noise_enabled"] = False
    for layer in silent_state["layers"]:
        layer["enabled"] = False
    silence, _ = generate_samples(silent_state)
    if any(silence):
        failures.append("Disabled layers generated non-silent audio")

    # Invalid project values are safely clamped rather than producing a bad WAV.
    invalid_state = default_state()
    invalid_state.update({"duration": -4, "sample_rate": 123, "master_gain": 99})
    clamped = validate_state(invalid_state)
    if clamped["duration"] != 0.01 or clamped["sample_rate"] != DEFAULT_SAMPLE_RATE or clamped["master_gain"] != 2.0:
        failures.append("Invalid state was not clamped safely")

    with tempfile.TemporaryDirectory(prefix="sfx_designer_test_") as folder:
        for name, preset in PRESETS.items():
            samples, state = generate_samples(copy.deepcopy(preset))
            path = Path(folder) / f"{name.replace(' ', '_')}.wav"
            write_wav(path, samples, state["sample_rate"])
            try:
                with wave.open(str(path), "rb") as audio:
                    valid = audio.getnchannels() == 1 and audio.getsampwidth() == 2 and audio.getframerate() == DEFAULT_SAMPLE_RATE and audio.getnframes() > 0
                if not valid:
                    failures.append(f"{name}: WAV format mismatch")
            except wave.Error as error:
                failures.append(f"{name}: {error}")
    if failures:
        print("Self-test failed:\n" + "\n".join(failures))
        return 1
    print(f"Self-test passed: {len(PRESETS)} presets exported as 44.1 kHz 16-bit mono WAV; deterministic, silence, and input-clamping checks passed.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=APP_TITLE)
    parser.add_argument("--self-test", action="store_true", help="Validate all preset exports without opening the UI.")
    args = parser.parse_args()
    if args.self_test:
        return run_self_test()
    if tk is None:
        print("Tkinter is unavailable in this Python installation.", file=sys.stderr)
        return 1
    root = tk.Tk()
    app = SfxDesigner(root)
    root.protocol("WM_DELETE_WINDOW", lambda: (app.stop_preview(), root.destroy()))
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
