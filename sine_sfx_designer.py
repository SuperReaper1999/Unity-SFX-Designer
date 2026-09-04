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

import numpy as np

from dialogue_studio import DialogueStudio

try:
    import tkinter as tk
    from tkinter import filedialog, messagebox, simpledialog, ttk
except ImportError:  # pragma: no cover - only relevant to unusual Python installs
    tk = None

try:
    import winsound
except ImportError:  # pragma: no cover - enables non-Windows self-tests
    winsound = None


APP_TITLE = "Unity SFX Designer"
PROJECT_VERSION = 2
DEFAULT_SAMPLE_RATE = 44100
MAX_DURATION_SECONDS = 12.0
PIANO_LOW_MIDI = 48   # C3
PIANO_HIGH_MIDI = 71  # B4
MUSIC_TRACK_COUNT = 4


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
    fm_frequency: float = 0.0
    fm_depth_hz: float = 0.0
    lfo_frequency: float = 0.0
    lfo_depth: float = 0.0
    attack: float = 0.0
    decay: float = 0.0
    sustain: float = 1.0
    release: float = 0.0
    waveform: str = "sine"


def default_state() -> dict[str, Any]:
    return {
        "version": PROJECT_VERSION,
        "name": "NewSound",
        "duration": 0.75,
        "sample_rate": DEFAULT_SAMPLE_RATE,
        "master_gain": 0.8,
        "variation_amount": 0.12,
        "attack": 0.01,
        "decay": 0.08,
        "sustain": 0.7,
        "release": 0.16,
        "noise_enabled": False,
        "noise_color": "white",
        "noise_gain": 0.0,
        "noise_seed": 1337,
        "lowpass_hz": 0.0,
        "distortion": 0.0,
        "delay_time": 0.0,
        "delay_feedback": 0.25,
        "delay_mix": 0.0,
        "reverb_mix": 0.0,
        "render_quality": "high",
        "filter_mode": "lowpass",
        "filter_cutoff_hz": 0.0,
        "filter_resonance": 0.0,
        "filter_envelope_amount": 0.0,
        "transient_gain": 0.0,
        "transient_decay": 0.025,
        "pitch_drift_hz": 0.0,
        "pitch_jitter_hz": 0.0,
        "formant_low_hz": 0.0,
        "formant_high_hz": 0.0,
        "normalize": True,
        "preset": "Custom",
        "music_tempo_bpm": 120,
        "music_steps": 16,
        "music_notes": [],  # Kept in the recipe as a convenient Track 1 alias.
        "music_tracks": default_music_tracks(),
        "layers": [asdict(Layer(enabled=index == 0)) for index in range(4)],
    }


def default_music_tracks() -> list[dict[str, Any]]:
    return [
        {"name": f"Track {index + 1}", "preset": "Custom", "volume": 0.8, "muted": False, "notes": []}
        for index in range(MUSIC_TRACK_COUNT)
    ]


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
        lowpass_hz=2200, distortion=0.35, reverb_mix=0.18, layers=[
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

PRESET_CATEGORIES: dict[str, tuple[str, ...]] = {
    "Custom": ("Custom",),
    "UI": ("UI Click", "Pickup"),
    "Combat": ("Hit", "Gunshot Impact", "Explosion Burst"),
    "Creatures": ("Zombie Groan",),
    "Ambience": ("Ambient Hum",),
}

PRESETS.update({
    "Pistol": make_preset("Pistol", name="Pistol", duration=.34, attack=.001, decay=.02, sustain=0, release=.16, noise_enabled=True, noise_color="band", noise_gain=.36, transient_gain=.7, transient_decay=.012, filter_cutoff_hz=5200, distortion=.32, layers=[asdict(Layer(True, 135, .7, 0, -90, 0, 0, .22)), asdict(Layer(True, 930, .14, 0, -650, 0, 0, .06)), asdict(Layer()), asdict(Layer())]),
    "Rifle": make_preset("Rifle", name="Rifle", duration=.52, attack=.001, decay=.03, sustain=0, release=.24, noise_enabled=True, noise_color="band", noise_gain=.48, transient_gain=.82, transient_decay=.009, filter_cutoff_hz=6800, distortion=.42, layers=[asdict(Layer(True, 95, .75, 0, -70, 0, 0, .3)), asdict(Layer(True, 210, .24, 0, -130, 0, 0, .18)), asdict(Layer()), asdict(Layer())]),
    "Shotgun": make_preset("Shotgun", name="Shotgun", duration=.8, attack=.001, decay=.04, sustain=0, release=.38, noise_enabled=True, noise_color="brown", noise_gain=.7, transient_gain=1.1, transient_decay=.02, filter_cutoff_hz=2600, distortion=.5, reverb_mix=.12, layers=[asdict(Layer(True, 65, .8, 0, -48, 0, 0, .45)), asdict(Layer()), asdict(Layer()), asdict(Layer())]),
    "Melee Impact": make_preset("Melee Impact", name="Melee_Impact", duration=.3, attack=.001, decay=.025, sustain=0, release=.12, noise_enabled=True, noise_color="band", noise_gain=.3, transient_gain=.5, transient_decay=.016, filter_mode="bandpass", filter_cutoff_hz=1800, layers=[asdict(Layer(True, 165, .68, 0, -110, 0, 0, .22)), asdict(Layer()), asdict(Layer()), asdict(Layer())]),
    "Ricochet": make_preset("Ricochet", name="Ricochet", duration=.48, attack=.001, decay=.04, sustain=0, release=.25, pitch_drift_hz=30, reverb_mix=.15, layers=[asdict(Layer(True, 1600, .3, 0, 1200, -500, 0, .45)), asdict(Layer(True, 2800, .12, 0, 400, -1100, 0, .25)), asdict(Layer()), asdict(Layer())]),
    "Zombie Scream": make_preset("Zombie Scream", name="Zombie_Scream", duration=1.45, attack=.06, decay=.11, sustain=.6, release=.34, pitch_drift_hz=16, formant_low_hz=700, formant_high_hz=1800, distortion=.16, layers=[asdict(Layer(True, 260, .36, 0, -30, 85, 0, 1.45)), asdict(Layer(True, 390, .17, 0, -20, 65, 0, 1.2)), asdict(Layer()), asdict(Layer())]),
    "Zombie Attack": make_preset("Zombie Attack", name="Zombie_Attack", duration=.62, attack=.01, decay=.07, sustain=.2, release=.24, noise_enabled=True, noise_color="pink", noise_gain=.14, formant_low_hz=520, formant_high_hz=1300, transient_gain=.18, layers=[asdict(Layer(True, 145, .42, 0, -45, 25, 0, .62)), asdict(Layer()), asdict(Layer()), asdict(Layer())]),
})
PRESET_CATEGORIES["Combat"] += ("Pistol", "Rifle", "Shotgun", "Melee Impact", "Ricochet")
PRESET_CATEGORIES["Creatures"] += ("Zombie Scream", "Zombie Attack")

PRESETS.update({
    "Kick": make_preset("Kick", name="Kick", duration=.4, attack=.001, decay=.06, sustain=0, release=.24, noise_enabled=True, noise_color="brown", noise_gain=.1, transient_gain=.85, transient_decay=.01, filter_cutoff_hz=1200, distortion=.14, layers=[asdict(Layer(True, 58, .85, 0, 150, -20, 0, .22)), asdict(Layer(True, 42, .3, 0, 0, 0, .03, .4)), asdict(Layer()), asdict(Layer())]),
    "Snare": make_preset("Snare", name="Snare", duration=.28, attack=.001, decay=.03, sustain=0, release=.14, noise_enabled=True, noise_color="white", noise_gain=.55, filter_mode="bandpass", filter_cutoff_hz=2200, filter_resonance=.2, transient_gain=.5, transient_decay=.012, layers=[asdict(Layer(True, 195, .45, 0, -40, 0, 0, .1)), asdict(Layer(True, 330, .18, 0, -60, 0, 0, .08)), asdict(Layer()), asdict(Layer())]),
    "Closed Hi-Hat": make_preset("Closed Hi-Hat", name="Closed_Hi_Hat", duration=.09, attack=.0005, decay=.015, sustain=0, release=.05, noise_enabled=True, noise_color="white", noise_gain=.55, filter_mode="highpass", filter_cutoff_hz=7500, layers=[asdict(Layer(True, 5200, .08, 0, 0, 0, 0, .08)), asdict(Layer(True, 8200, .05, 0, 0, 0, 0, .06)), asdict(Layer()), asdict(Layer())]),
    "Open Hi-Hat": make_preset("Open Hi-Hat", name="Open_Hi_Hat", duration=.55, attack=.0005, decay=.05, sustain=.25, release=.4, noise_enabled=True, noise_color="white", noise_gain=.5, filter_mode="highpass", filter_cutoff_hz=7000, layers=[asdict(Layer(True, 5200, .07, 0, 0, 0, 0, .5)), asdict(Layer(True, 8200, .045, 0, 0, 0, 0, .45)), asdict(Layer()), asdict(Layer())]),
    "Clap": make_preset("Clap", name="Clap", duration=.32, attack=.001, decay=.05, sustain=.05, release=.2, noise_enabled=True, noise_color="pink", noise_gain=.6, filter_mode="bandpass", filter_cutoff_hz=1700, filter_resonance=.25, reverb_mix=.12, transient_gain=.4, transient_decay=.02, layers=[asdict(Layer()), asdict(Layer()), asdict(Layer()), asdict(Layer())]),
    "Rim Shot": make_preset("Rim Shot", name="Rim_Shot", duration=.14, attack=.0005, decay=.02, sustain=0, release=.08, noise_enabled=True, noise_color="band", noise_gain=.25, filter_mode="bandpass", filter_cutoff_hz=3200, transient_gain=.6, transient_decay=.006, layers=[asdict(Layer(True, 850, .5, 0, 300, -100, 0, .07)), asdict(Layer()), asdict(Layer()), asdict(Layer())]),
    "Tom Low": make_preset("Tom Low", name="Tom_Low", duration=.42, attack=.001, decay=.08, sustain=.15, release=.28, lowpass_hz=1800, layers=[asdict(Layer(True, 110, .7, 0, 60, -15, 0, .3)), asdict(Layer(True, 90, .25, 0, 0, 0, .02, .4)), asdict(Layer()), asdict(Layer())]),
    "Tom High": make_preset("Tom High", name="Tom_High", duration=.34, attack=.001, decay=.06, sustain=.12, release=.22, lowpass_hz=2400, layers=[asdict(Layer(True, 175, .7, 0, 80, -20, 0, .24)), asdict(Layer(True, 140, .22, 0, 0, 0, .02, .3)), asdict(Layer()), asdict(Layer())]),
    "Crash Cymbal": make_preset("Crash Cymbal", name="Crash_Cymbal", duration=1.6, attack=.002, decay=.3, sustain=.35, release=1.1, noise_enabled=True, noise_color="white", noise_gain=.55, filter_mode="highpass", filter_cutoff_hz=4200, reverb_mix=.2, layers=[asdict(Layer(True, 3400, .05, 0, 0, 0, 0, 1.6)), asdict(Layer(True, 5200, .035, 0, 0, 0, 0, 1.5)), asdict(Layer(True, 7600, .02, 0, 0, 0, 0, 1.4)), asdict(Layer())]),
    "Cowbell": make_preset("Cowbell", name="Cowbell", duration=.3, attack=.001, decay=.05, sustain=.2, release=.2, layers=[asdict(Layer(True, 540, .55, 0, 0, 0, 0, .28, waveform="square")), asdict(Layer(True, 800, .35, 0, 0, 0, 0, .24, waveform="square")), asdict(Layer()), asdict(Layer())]),
    "Bass Pluck": make_preset("Bass Pluck", name="Bass_Pluck", duration=.5, attack=.002, decay=.12, sustain=.3, release=.28, filter_mode="lowpass", filter_cutoff_hz=900, filter_envelope_amount=.4, layers=[asdict(Layer(True, 82, .8, 0, 0, 0, 0, .5, waveform="triangle")), asdict(Layer(True, 165, .2, 0, 0, 0, 0, .4, waveform="triangle")), asdict(Layer()), asdict(Layer())]),
    "Bass Sub": make_preset("Bass Sub", name="Bass_Sub", duration=1.1, attack=.03, decay=.15, sustain=.85, release=.3, layers=[asdict(Layer(True, 55, .8, 0, 0, 0, 0, 1.1)), asdict(Layer(True, 110, .15, 0, 0, 0, 0, 1.1)), asdict(Layer()), asdict(Layer())]),
    "Synth Stab": make_preset("Synth Stab", name="Synth_Stab", duration=.5, attack=.003, decay=.08, sustain=.35, release=.22, distortion=.08, filter_cutoff_hz=3200, layers=[asdict(Layer(True, 220, .4, 0, 0, 0, 0, .45, waveform="sawtooth")), asdict(Layer(True, 261.63, .32, 0, 0, 0, 0, .45, waveform="sawtooth")), asdict(Layer(True, 329.63, .28, 0, 0, 0, 0, .45, waveform="sawtooth")), asdict(Layer())]),
    "Pluck Lead": make_preset("Pluck Lead", name="Pluck_Lead", duration=.4, attack=.001, decay=.1, sustain=.2, release=.2, filter_cutoff_hz=4500, filter_envelope_amount=.5, layers=[asdict(Layer(True, 440, .5, 0, 0, 0, 0, .35, waveform="triangle")), asdict(Layer(True, 880, .15, 0, 0, 0, 0, .25, waveform="triangle")), asdict(Layer()), asdict(Layer())]),
})
PRESET_CATEGORIES["Drums"] = ("Kick", "Snare", "Closed Hi-Hat", "Open Hi-Hat", "Clap", "Rim Shot", "Tom Low", "Tom High", "Crash Cymbal", "Cowbell")
PRESET_CATEGORIES["Bass & Lead"] = ("Bass Pluck", "Bass Sub", "Synth Stab", "Pluck Lead")


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
    result["variation_amount"] = clamp(float(result["variation_amount"]), 0.0, 0.5)
    result["attack"] = max(0.0, float(result["attack"]))
    result["decay"] = max(0.0, float(result["decay"]))
    result["sustain"] = clamp(float(result["sustain"]), 0.0, 1.0)
    result["release"] = max(0.0, float(result["release"]))
    result["noise_gain"] = clamp(float(result["noise_gain"]), 0.0, 1.0)
    result["noise_color"] = str(result["noise_color"]).lower()
    if result["noise_color"] not in ("white", "pink", "brown", "band"):
        result["noise_color"] = "white"
    result["noise_seed"] = int(result["noise_seed"])
    result["lowpass_hz"] = max(0.0, float(result["lowpass_hz"]))
    result["distortion"] = clamp(float(result["distortion"]), 0.0, 1.0)
    result["delay_time"] = clamp(float(result["delay_time"]), 0.0, 2.0)
    result["delay_feedback"] = clamp(float(result["delay_feedback"]), 0.0, 0.95)
    result["delay_mix"] = clamp(float(result["delay_mix"]), 0.0, 1.0)
    result["reverb_mix"] = clamp(float(result["reverb_mix"]), 0.0, 1.0)
    result["render_quality"] = str(result["render_quality"]).lower()
    if result["render_quality"] not in ("draft", "high"):
        result["render_quality"] = "high"
    result["filter_mode"] = str(result["filter_mode"]).lower()
    if result["filter_mode"] not in ("lowpass", "highpass", "bandpass", "notch"):
        result["filter_mode"] = "lowpass"
    result["filter_cutoff_hz"] = clamp(float(result["filter_cutoff_hz"]), 0.0, 20000.0)
    result["filter_resonance"] = clamp(float(result["filter_resonance"]), 0.0, 0.99)
    result["filter_envelope_amount"] = clamp(float(result["filter_envelope_amount"]), -1.0, 1.0)
    result["transient_gain"] = clamp(float(result["transient_gain"]), 0.0, 2.0)
    result["transient_decay"] = clamp(float(result["transient_decay"]), 0.001, 1.0)
    result["pitch_drift_hz"] = clamp(float(result["pitch_drift_hz"]), 0.0, 2000.0)
    result["pitch_jitter_hz"] = clamp(float(result["pitch_jitter_hz"]), 0.0, 2000.0)
    result["formant_low_hz"] = clamp(float(result["formant_low_hz"]), 0.0, 10000.0)
    result["formant_high_hz"] = clamp(float(result["formant_high_hz"]), 0.0, 10000.0)
    result["noise_enabled"] = bool(result["noise_enabled"])
    result["normalize"] = bool(result["normalize"])
    result["music_tempo_bpm"] = int(clamp(float(result["music_tempo_bpm"]), 40, 300))
    result["music_steps"] = int(result["music_steps"])
    if result["music_steps"] not in (8, 16, 32):
        result["music_steps"] = 16
    def validated_notes(raw_notes: Any) -> list[dict[str, Any]]:
        notes: list[dict[str, Any]] = []
        for raw_note in raw_notes if isinstance(raw_notes, list) else []:
            if not isinstance(raw_note, dict):
                continue
            try:
                step = int(raw_note.get("step", 0))
                midi = int(raw_note.get("midi", PIANO_LOW_MIDI))
                length = int(raw_note.get("length", 1))
                velocity = float(raw_note.get("velocity", 0.75))
            except (TypeError, ValueError):
                continue
            if 0 <= step < result["music_steps"] and PIANO_LOW_MIDI <= midi <= PIANO_HIGH_MIDI:
                notes.append({"step": step, "midi": midi, "length": int(clamp(length, 1, result["music_steps"] - step)), "velocity": clamp(velocity, 0.05, 1.0)})
        return notes

    supplied_tracks = state.get("music_tracks")
    if not isinstance(supplied_tracks, list):
        supplied_tracks = [{"name": "Track 1", "preset": "Custom", "volume": 0.8, "muted": False, "notes": state.get("music_notes", [])}]
    result["music_tracks"] = []
    defaults = default_music_tracks()
    for index, fallback in enumerate(defaults):
        raw_track = supplied_tracks[index] if index < len(supplied_tracks) and isinstance(supplied_tracks[index], dict) else {}
        preset = str(raw_track.get("preset", fallback["preset"]))
        result["music_tracks"].append({
            "name": str(raw_track.get("name", fallback["name"])).strip() or fallback["name"],
            "preset": preset if preset in PRESETS else "Custom",
            "volume": clamp(float(raw_track.get("volume", fallback["volume"])), 0.0, 2.0),
            "muted": bool(raw_track.get("muted", False)),
            "notes": validated_notes(raw_track.get("notes", [])),
        })
    result["music_notes"] = copy.deepcopy(result["music_tracks"][0]["notes"])

    supplied_layers = state.get("layers", [])
    result["layers"] = []
    for index in range(4):
        raw = supplied_layers[index] if index < len(supplied_layers) else {}
        layer = asdict(Layer())
        layer.update(raw)
        layer["enabled"] = bool(layer["enabled"])
        layer["waveform"] = str(layer["waveform"]).lower()
        if layer["waveform"] not in ("sine", "square", "triangle", "sawtooth"):
            layer["waveform"] = "sine"
        layer["frequency"] = clamp(float(layer["frequency"]), 1.0, 20000.0)
        layer["gain"] = clamp(float(layer["gain"]), 0.0, 2.0)
        layer["phase_degrees"] = float(layer["phase_degrees"])
        layer["sweep_start"] = clamp(float(layer["sweep_start"]), -19000.0, 19000.0)
        layer["sweep_end"] = clamp(float(layer["sweep_end"]), -19000.0, 19000.0)
        layer["start_time"] = clamp(float(layer["start_time"]), 0.0, result["duration"])
        layer["end_time"] = clamp(float(layer["end_time"]), layer["start_time"], result["duration"])
        layer["fm_frequency"] = clamp(float(layer["fm_frequency"]), 0.0, 20000.0)
        layer["fm_depth_hz"] = clamp(float(layer["fm_depth_hz"]), 0.0, 19000.0)
        layer["lfo_frequency"] = clamp(float(layer["lfo_frequency"]), 0.0, 100.0)
        layer["lfo_depth"] = clamp(float(layer["lfo_depth"]), 0.0, 1.0)
        layer["attack"] = max(0.0, float(layer["attack"]))
        layer["decay"] = max(0.0, float(layer["decay"]))
        layer["sustain"] = clamp(float(layer["sustain"]), 0.0, 1.0)
        layer["release"] = max(0.0, float(layer["release"]))
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


def oscillator(waveform: str, phase: float) -> float:
    """Return a band-unlimited oscillator sample for SFX design previews."""
    if waveform == "square":
        return 1.0 if math.sin(phase) >= 0.0 else -1.0
    if waveform == "triangle":
        return (2.0 / math.pi) * math.asin(math.sin(phase))
    if waveform == "sawtooth":
        cycle = (phase / math.tau) % 1.0
        return cycle * 2.0 - 1.0
    return math.sin(phase)


def layer_envelope(time_seconds: float, layer: dict[str, Any]) -> float:
    layer_time = time_seconds - layer["start_time"]
    return envelope(layer_time, max(0.0001, layer["end_time"] - layer["start_time"]), layer)


def generate_samples(raw_state: dict[str, Any]) -> tuple[list[float], dict[str, Any]]:
    """Synthesize deterministic high-quality mono audio, then downsample for Unity."""
    state = validate_state(raw_state)
    factor = 4 if state["render_quality"] == "high" else 1
    output_rate = state["sample_rate"]
    rate = output_rate * factor
    count = max(1, int(state["duration"] * rate))
    time = np.arange(count, dtype=np.float64) / rate
    random_source = np.random.default_rng(state["noise_seed"])
    samples = np.zeros(count, dtype=np.float64)

    def adsr(t: np.ndarray, duration: float, values: dict[str, Any]) -> np.ndarray:
        attack, decay, release, sustain = values["attack"], values["decay"], values["release"], values["sustain"]
        result = np.full_like(t, sustain)
        if attack > 0: result = np.where(t < attack, t / attack, result)
        if decay > 0: result = np.where((t >= attack) & (t < attack + decay), 1 - (1 - sustain) * ((t - attack) / decay), result)
        if release > 0: result = np.where(t >= duration - release, sustain * np.clip((duration - t) / release, 0, 1), result)
        return np.clip(result, 0, 1)

    for layer in state["layers"]:
        if not layer["enabled"] or layer["end_time"] <= layer["start_time"]: continue
        mask = (time >= layer["start_time"]) & (time <= layer["end_time"])
        local = np.clip((time - layer["start_time"]) / max(.0001, layer["end_time"] - layer["start_time"]), 0, 1)
        frequency = layer["frequency"] + layer["sweep_start"] * (1 - local) + layer["sweep_end"] * local
        frequency += np.sin(math.tau * layer["fm_frequency"] * time) * layer["fm_depth_hz"]
        if state["pitch_drift_hz"]: frequency += np.sin(math.tau * 0.31 * time) * state["pitch_drift_hz"]
        if state["pitch_jitter_hz"]: frequency += random_source.normal(0, state["pitch_jitter_hz"], count)
        frequency = np.clip(frequency, 1, rate * .45)
        phase = math.radians(layer["phase_degrees"]) + math.tau * np.cumsum(frequency) / rate
        if layer["waveform"] == "square": signal = np.sign(np.sin(phase))
        elif layer["waveform"] == "triangle": signal = 2 / math.pi * np.arcsin(np.sin(phase))
        elif layer["waveform"] == "sawtooth": signal = 2 * ((phase / math.tau) % 1) - 1
        else: signal = np.sin(phase)
        amplitude = 1 - layer["lfo_depth"] * .5 + np.sin(math.tau * layer["lfo_frequency"] * time) * layer["lfo_depth"] * .5
        samples += signal * layer["gain"] * amplitude * adsr(time - layer["start_time"], layer["end_time"] - layer["start_time"], layer) * mask

    if state["noise_enabled"]:
        noise = random_source.normal(0, 1, count)
        if state["noise_color"] in ("pink", "brown"):
            noise = np.cumsum(noise)
            noise /= max(np.max(np.abs(noise)), 1e-9)
            if state["noise_color"] == "pink": noise = np.diff(noise, prepend=noise[0]) * 20
        if state["noise_color"] == "band": noise = np.convolve(noise, np.ones(9) / 9, mode="same")
        samples += noise * state["noise_gain"]

    master = adsr(time, state["duration"], state)
    samples *= master
    if state["transient_gain"]: samples += random_source.normal(0, 1, count) * state["transient_gain"] * np.exp(-time / state["transient_decay"])

    cutoff = (state["filter_cutoff_hz"] or state["lowpass_hz"]) * (1 + state["filter_envelope_amount"] * (state["sustain"] - .5))
    if cutoff > 0:
        alpha = min(.99, math.tau * cutoff / (rate + math.tau * cutoff))
        low = np.empty_like(samples); low[0] = samples[0]
        for i in range(1, count): low[i] = low[i-1] + alpha * (samples[i] - low[i-1])
        high = samples - low
        if state["filter_mode"] == "highpass": samples = high
        elif state["filter_mode"] == "bandpass": samples = high * low * (1 + state["filter_resonance"] * 8)
        elif state["filter_mode"] == "notch": samples = samples - high * state["filter_resonance"]
        else: samples = low
    for formant in (state["formant_low_hz"], state["formant_high_hz"]):
        if formant > 0:
            carrier = np.sin(math.tau * formant * time)
            samples += samples * carrier * .18
    if state["distortion"]:
        drive = 1 + state["distortion"] * 14
        samples = np.tanh(samples * drive) / math.tanh(drive)
    if state["delay_time"] and state["delay_mix"]:
        delay = max(1, int(state["delay_time"] * rate)); wet = np.zeros_like(samples)
        for i in range(delay, count): wet[i] = samples[i-delay] + wet[i-delay] * state["delay_feedback"]
        samples = samples * (1 - state["delay_mix"]) + wet * state["delay_mix"]
    if state["reverb_mix"]:
        wet = samples.copy()
        for seconds, gain in ((.029,.38),(.047,.27),(.071,.19),(.113,.13)):
            delay = int(seconds * rate); wet[delay:] += samples[:-delay] * gain
        samples = samples * (1-state["reverb_mix"]) + wet * state["reverb_mix"]
    if factor > 1:
        kernel = np.hanning(17); kernel /= kernel.sum(); samples = np.convolve(samples, kernel, mode="same")[::factor]
    peak = max(float(np.max(np.abs(samples))), 1e-9)
    scale = min(1 / peak, 4) * state["master_gain"] if state["normalize"] else state["master_gain"]
    return np.clip(samples * scale, -1, 1).tolist(), state


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


def midi_frequency(midi: int) -> float:
    return 440.0 * (2.0 ** ((midi - 69) / 12.0))


def generate_music_samples(raw_state: dict[str, Any]) -> tuple[list[float], dict[str, Any]]:
    """Render the piano roll with the current SFX design acting as its instrument."""
    state = validate_state(raw_state)
    step_seconds = 60.0 / state["music_tempo_bpm"] / 4.0
    total_seconds = state["music_steps"] * step_seconds
    total_count = max(1, int(total_seconds * state["sample_rate"]))
    mix = np.zeros(total_count, dtype=np.float64)
    for track_index, track in enumerate(state["music_tracks"]):
        if track["muted"]:
            continue
        instrument_source = state if track["preset"] == "Custom" else PRESETS[track["preset"]]
        for note_index, note in enumerate(track["notes"]):
            note_seconds = min(total_seconds - note["step"] * step_seconds, note["length"] * step_seconds)
            if note_seconds <= 0:
                continue
            instrument = copy.deepcopy(instrument_source)
            instrument["sample_rate"] = state["sample_rate"]
            instrument["render_quality"] = state["render_quality"]
            instrument["duration"] = note_seconds
            instrument["normalize"] = False
            instrument["master_gain"] *= track["volume"] * note["velocity"]
            instrument["noise_seed"] = state["noise_seed"] + track_index * 104729 + note_index * 7919
            ratio = midi_frequency(note["midi"]) / 440.0
            for layer in instrument["layers"]:
                layer["frequency"] *= ratio
                layer["sweep_start"] *= ratio
                layer["sweep_end"] *= ratio
                layer["start_time"] = 0.0
                layer["end_time"] = note_seconds
            note_samples, _ = generate_samples(instrument)
            start = int(note["step"] * step_seconds * state["sample_rate"])
            end = min(total_count, start + len(note_samples))
            mix[start:end] += np.asarray(note_samples[:end - start])
    peak = float(np.max(np.abs(mix))) if len(mix) else 0.0
    # Music is a complete mix rather than a one-shot layer: bring valid quiet
    # loops up to a predictable Unity-friendly level while preserving silence.
    if peak > 1e-9:
        mix *= 0.9 / peak
    return np.clip(mix, -1, 1).tolist(), state


def safe_filename(name: str) -> str:
    cleaned = "".join(character if character.isalnum() or character in "-_ " else "_" for character in name).strip(" .")
    return cleaned or "NewSound"


def export_unity_pack(destination: str | Path, source: dict[str, Any], variation_count: int = 1) -> list[Path]:
    """Write Unity-ready WAVs and their editable recipe into one folder."""
    if not 1 <= variation_count <= 50:
        raise ValueError("Variation count must be between 1 and 50.")
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=True)
    state = validate_state(source)
    base_name = safe_filename(state["name"])
    recipe_path = destination / f"{base_name}.sfx.json"
    with recipe_path.open("w", encoding="utf-8") as output:
        json.dump(state, output, indent=2)

    output_paths = [recipe_path]
    rendered_states = [state] if variation_count == 1 else [make_variation(state, index) for index in range(variation_count)]
    for rendered_state in rendered_states:
        samples, normalized = generate_samples(rendered_state)
        wav_path = destination / f"{safe_filename(normalized['name'])}.wav"
        write_wav(wav_path, samples, normalized["sample_rate"])
        output_paths.append(wav_path)
    return output_paths


def make_variation(source: dict[str, Any], index: int) -> dict[str, Any]:
    """Make a subtle, deterministic game-ready variation of a source sound."""
    variation = validate_state(copy.deepcopy(source))
    amount = variation["variation_amount"]
    random_source = random.Random(variation["noise_seed"] + (index + 1) * 7919)
    variation["name"] = f"{source['name']}_{index + 1:02d}"
    variation["noise_seed"] += (index + 1) * 7919
    variation["duration"] *= 1.0 + random_source.uniform(-amount * 0.35, amount * 0.35)
    for layer in variation["layers"]:
        if not layer["enabled"]:
            continue
        layer["frequency"] *= 1.0 + random_source.uniform(-amount, amount)
        layer["gain"] *= 1.0 + random_source.uniform(-amount * 0.45, amount * 0.45)
        layer["phase_degrees"] += random_source.uniform(-amount * 180.0, amount * 180.0)
        layer["sweep_start"] *= 1.0 + random_source.uniform(-amount, amount)
        layer["sweep_end"] *= 1.0 + random_source.uniform(-amount, amount)
    return validate_state(variation)


class SfxDesigner:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title(APP_TITLE)
        self.root.minsize(1320, 860)
        self.state = default_state()
        self.preview_file: str | None = None
        self._waveform_job: str | None = None
        self.global_vars: dict[str, Any] = {}
        self.layer_vars: list[dict[str, Any]] = []
        self.selected_layer_var = tk.IntVar(value=0)
        self.quick_layer_scales: dict[str, tk.Scale] = {}
        self.quick_layer_values: dict[str, tk.StringVar] = {}
        self.preset_var = tk.StringVar(value="Custom")
        self.preset_category_filter = tk.StringVar(value="All categories")
        self.preset_search_var = tk.StringVar()
        self.favourites_only_var = tk.BooleanVar(value=False)
        self.favorite_presets = self._load_favorite_presets()
        self.music_vars: dict[str, tk.StringVar] = {}
        self.music_track_vars: list[dict[str, Any]] = []
        self.selected_music_track_var = tk.IntVar(value=0)
        self.piano_waveform_var = tk.StringVar(value="sine")
        self._piano_drag_start: tuple[int, int] | None = None
        self.piano_canvas: tk.Canvas | None = None
        self.status = tk.StringVar(value="Ready")
        self.dialogue_studio = DialogueStudio(self.root, self.status.set)
        self._build_ui()
        self._load_state_into_ui(self.state)
        self._watch_waveform_controls()
        self.refresh_waveform()

    def _build_ui(self) -> None:
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(1, weight=1)
        toolbar = ttk.Frame(self.root, padding=10)
        toolbar.grid(row=0, column=0, sticky="ew")
        toolbar.columnconfigure(2, weight=1)
        ttk.Button(toolbar, text="New", command=self.new_project).grid(row=0, column=0, padx=3)
        ttk.Button(toolbar, text="Open Project", command=self.open_project).grid(row=0, column=1, padx=3)
        ttk.Button(toolbar, text="Save Project", command=self.save_project).grid(row=0, column=2, padx=3, sticky="w")
        ttk.Button(toolbar, text="Preview", command=self.preview).grid(row=0, column=3, padx=3)
        ttk.Button(toolbar, text="Stop", command=self.stop_preview).grid(row=0, column=4, padx=3)
        ttk.Button(toolbar, text="Export WAV", command=self.export_wav).grid(row=0, column=5, padx=3)
        ttk.Button(toolbar, text="Export Variations", command=self.export_variations).grid(row=0, column=6, padx=3)
        ttk.Button(toolbar, text="Export Unity Pack", command=self.export_pack).grid(row=0, column=7, padx=3)

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
        ttk.Label(preview, text="Frequency spectrum", font=("Segoe UI", 11, "bold")).pack(anchor="w")
        self.spectrum_canvas = tk.Canvas(preview, height=145, background="#10131a", highlightthickness=0)
        self.spectrum_canvas.pack(fill="x", pady=(8, 12))
        self.spectrum_canvas.bind("<Configure>", lambda _event: self.refresh_waveform())
        ttk.Label(preview, text="Output is 16-bit mono PCM WAV. Unity imports it directly as an AudioClip.", wraplength=330).pack(anchor="w")
        ttk.Label(self.root, textvariable=self.status, relief=tk.SUNKEN, anchor="w", padding=(8, 4)).grid(row=2, column=0, sticky="ew")

    def _add_quick_slider(self, parent: ttk.Frame, row: int, column: int, label: str, key: str, minimum: float, maximum: float, resolution: float) -> None:
        ttk.Label(parent, text=label).grid(row=row, column=column, sticky="w", padx=(0, 4), pady=2)
        slider = tk.Scale(parent, from_=minimum, to=maximum, orient=tk.HORIZONTAL, resolution=resolution, showvalue=False, length=128,
                          command=lambda value, field=key: self.global_vars[field].set(f"{float(value):.4g}"))
        slider.grid(row=row, column=column + 1, sticky="ew", padx=(0, 4), pady=2)
        ttk.Entry(parent, textvariable=self.global_vars[key], width=7).grid(row=row, column=column + 2, sticky="w", padx=(0, 10), pady=2)
        try:
            slider.set(float(self.global_vars[key].get()))
        except ValueError:
            slider.set(minimum)

    def _add_field(self, parent: ttk.Frame, row: int, column: int, label: str, key: str, default: Any, width: int = 9) -> None:
        variable = tk.StringVar(value=str(default))
        self.global_vars[key] = variable
        ttk.Label(parent, text=label).grid(row=row, column=column, sticky="w", padx=(0, 4), pady=2)
        ttk.Entry(parent, textvariable=variable, width=width).grid(row=row, column=column + 1, sticky="w", padx=(0, 10), pady=2)

    @staticmethod
    def _favourites_path() -> Path:
        app_data = Path(os.environ.get("APPDATA", str(Path.home()))) / "UnitySfxDesigner"
        return app_data / "preset_favourites.json"

    def _load_favorite_presets(self) -> set[str]:
        try:
            saved = json.loads(self._favourites_path().read_text(encoding="utf-8"))
            return {name for name in saved if name in PRESETS and name != "Custom"}
        except (OSError, json.JSONDecodeError, TypeError):
            return set()

    def _save_favorite_presets(self) -> None:
        try:
            path = self._favourites_path()
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(sorted(self.favorite_presets), indent=2), encoding="utf-8")
        except OSError as error:
            self.status.set(f"Could not save favourites: {error}")

    def _build_preset_browser(self, parent: ttk.Frame) -> None:
        browser = ttk.LabelFrame(parent, text="Preset browser", padding=8)
        browser.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        browser.columnconfigure(1, weight=1)
        browser.columnconfigure(3, weight=1)
        ttk.Label(browser, text="Category").grid(row=0, column=0, sticky="w", padx=(0, 4))
        category = ttk.Combobox(browser, textvariable=self.preset_category_filter,
                                values=("All categories", *PRESET_CATEGORIES.keys()), state="readonly", width=16)
        category.grid(row=0, column=1, sticky="ew", padx=(0, 10))
        category.bind("<<ComboboxSelected>>", lambda _event: self._refresh_preset_browser())
        ttk.Label(browser, text="Search").grid(row=0, column=2, sticky="w", padx=(0, 4))
        ttk.Entry(browser, textvariable=self.preset_search_var, width=20).grid(row=0, column=3, sticky="ew", padx=(0, 10))
        ttk.Checkbutton(browser, text="Favourites only", variable=self.favourites_only_var,
                        command=self._refresh_preset_browser).grid(row=0, column=4, sticky="w")

        table_frame = ttk.Frame(browser)
        table_frame.grid(row=1, column=0, columnspan=5, sticky="ew", pady=(7, 6))
        table_frame.columnconfigure(0, weight=1)
        self.preset_tree = ttk.Treeview(table_frame, columns=("category", "favourite"), show="tree headings", height=5,
                                        selectmode="browse")
        self.preset_tree.heading("#0", text="Preset")
        self.preset_tree.heading("category", text="Category")
        self.preset_tree.heading("favourite", text="Favourite")
        self.preset_tree.column("#0", width=190, stretch=True)
        self.preset_tree.column("category", width=105, stretch=False)
        self.preset_tree.column("favourite", width=75, stretch=False, anchor="center")
        self.preset_tree.grid(row=0, column=0, sticky="ew")
        scrollbar = ttk.Scrollbar(table_frame, orient="vertical", command=self.preset_tree.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.preset_tree.configure(yscrollcommand=scrollbar.set)
        self.preset_tree.bind("<Double-1>", lambda _event: self.load_selected_preset())
        self.preset_tree.bind("<Return>", lambda _event: self.load_selected_preset())
        self.preset_tree.bind("<<TreeviewSelect>>", lambda _event: self._update_favourite_button())
        self.preset_search_var.trace_add("write", lambda *_arguments: self._refresh_preset_browser())

        actions = ttk.Frame(browser)
        actions.grid(row=2, column=0, columnspan=5, sticky="ew")
        ttk.Button(actions, text="Load selected", command=self.load_selected_preset).pack(side="left")
        ttk.Button(actions, text="Preview selected", command=self.preview_selected_preset).pack(side="left", padx=(6, 0))
        self.favourite_button = ttk.Button(actions, text="Add favourite", command=self.toggle_selected_favourite)
        self.favourite_button.pack(side="left", padx=(6, 0))
        ttk.Label(actions, text="Double-click loads a preset. Favourites are saved locally.").pack(side="right")
        self._refresh_preset_browser()

    def _filtered_presets(self) -> list[tuple[str, str]]:
        category_filter = self.preset_category_filter.get()
        query = self.preset_search_var.get().strip().lower()
        matches: list[tuple[str, str]] = []
        for category, presets in PRESET_CATEGORIES.items():
            if category == "Custom" or (category_filter != "All categories" and category != category_filter):
                continue
            for name in presets:
                if self.favourites_only_var.get() and name not in self.favorite_presets:
                    continue
                if query and query not in name.lower() and query not in category.lower():
                    continue
                matches.append((name, category))
        return matches

    def _refresh_preset_browser(self) -> None:
        if not hasattr(self, "preset_tree"):
            return
        selected = self._selected_preset_name()
        self.preset_tree.delete(*self.preset_tree.get_children())
        for name, category in self._filtered_presets():
            favourite = "★" if name in self.favorite_presets else ""
            self.preset_tree.insert("", "end", iid=name, text=name, values=(category, favourite))
        if selected and self.preset_tree.exists(selected):
            self.preset_tree.selection_set(selected)
            self.preset_tree.focus(selected)
        elif self.preset_tree.get_children():
            first = self.preset_tree.get_children()[0]
            self.preset_tree.selection_set(first)
            self.preset_tree.focus(first)
        self._update_favourite_button()

    def _selected_preset_name(self) -> str | None:
        if not hasattr(self, "preset_tree"):
            return None
        selection = self.preset_tree.selection()
        return selection[0] if selection else None

    def _update_favourite_button(self) -> None:
        if not hasattr(self, "favourite_button"):
            return
        name = self._selected_preset_name()
        if not name:
            self.favourite_button.configure(text="Add favourite", state="disabled")
            return
        self.favourite_button.configure(
            text="Remove favourite" if name in self.favorite_presets else "Add favourite", state="normal")

    def load_selected_preset(self) -> None:
        name = self._selected_preset_name()
        if not name:
            self.status.set("Choose a preset first.")
            return
        self.preset_var.set(name)
        self.apply_preset()

    def preview_selected_preset(self) -> None:
        if not self._selected_preset_name():
            self.status.set("Choose a preset first.")
            return
        self.load_selected_preset()
        self.preview()

    def toggle_selected_favourite(self) -> None:
        name = self._selected_preset_name()
        if not name:
            return
        if name in self.favorite_presets:
            self.favorite_presets.remove(name)
        else:
            self.favorite_presets.add(name)
        self._save_favorite_presets()
        self._refresh_preset_browser()

    def _build_controls(self, parent: ttk.Frame) -> None:
        notebook = ttk.Notebook(parent)
        notebook.grid(row=0, column=0, sticky="nsew")
        design_tab = ttk.Frame(notebook, padding=6)
        realism_tab = ttk.Frame(notebook, padding=6)
        piano_tab = ttk.Frame(notebook, padding=6)
        mix_tab = ttk.Frame(notebook, padding=6)
        dialogue_tab = ttk.Frame(notebook, padding=6)
        notebook.add(design_tab, text="Design")
        notebook.add(realism_tab, text="Realism")
        notebook.add(piano_tab, text="Piano")
        notebook.add(mix_tab, text="Mix & Export")
        notebook.add(dialogue_tab, text="Dialogue Studio")
        self.dialogue_studio.build(dialogue_tab)
        parent = design_tab
        parent.columnconfigure(0, weight=1)
        self._build_preset_browser(parent)
        global_frame = ttk.LabelFrame(parent, text="Global output", padding=8)
        global_frame.grid(row=1, column=0, sticky="ew", pady=(0, 8))
        self._add_field(global_frame, 0, 0, "Name", "name", "NewSound", 16)
        self._add_field(global_frame, 0, 2, "Duration (s)", "duration", 0.75)
        self._add_field(global_frame, 0, 4, "Master gain", "master_gain", 0.8)
        self._add_field(global_frame, 1, 2, "Variation %", "variation_amount", 12.0)
        ttk.Label(global_frame, text="Sample rate").grid(row=1, column=0, sticky="w", padx=(0, 4), pady=2)
        self.global_vars["sample_rate"] = tk.StringVar(value=str(DEFAULT_SAMPLE_RATE))
        ttk.Combobox(global_frame, textvariable=self.global_vars["sample_rate"], values=(22050, 44100, 48000), state="readonly", width=13).grid(row=1, column=1, sticky="w", padx=(0, 10), pady=2)
        self.global_vars["normalize"] = tk.BooleanVar(value=True)
        ttk.Checkbutton(global_frame, text="Normalize", variable=self.global_vars["normalize"]).grid(row=1, column=4, sticky="w", pady=2)
        ttk.Button(global_frame, text="Refresh waveform", command=self.refresh_waveform).grid(row=1, column=5, sticky="w", pady=2)

        envelope_frame = ttk.LabelFrame(parent, text="Master envelope (ADSR)", padding=8)
        envelope_frame.grid(row=2, column=0, sticky="ew", pady=(0, 8))
        self._add_field(envelope_frame, 0, 0, "Attack", "attack", 0.01)
        self._add_field(envelope_frame, 0, 2, "Decay", "decay", 0.08)
        self._add_field(envelope_frame, 0, 4, "Sustain", "sustain", 0.7)
        self._add_field(envelope_frame, 0, 6, "Release", "release", 0.16)

        effects_frame = ttk.LabelFrame(realism_tab, text="Noise and master effects", padding=8)
        effects_frame.grid(row=2, column=0, sticky="ew", pady=(0, 8))
        self.global_vars["noise_enabled"] = tk.BooleanVar(value=False)
        ttk.Checkbutton(effects_frame, text="Noise", variable=self.global_vars["noise_enabled"]).grid(row=0, column=0, sticky="w", padx=(0, 8))
        self.global_vars["noise_color"] = tk.StringVar(value="white")
        ttk.Combobox(effects_frame, textvariable=self.global_vars["noise_color"], values=("white", "pink", "brown", "band"), state="readonly", width=8).grid(row=0, column=1, sticky="w", padx=(0, 8))
        self._add_field(effects_frame, 0, 2, "Noise gain", "noise_gain", 0.0)
        self._add_field(effects_frame, 0, 4, "Seed", "noise_seed", 1337)
        self._add_field(effects_frame, 1, 0, "Low-pass Hz (0 off)", "lowpass_hz", 0.0, 12)
        self._add_field(effects_frame, 1, 2, "Distortion", "distortion", 0.0)
        self._add_field(effects_frame, 1, 4, "Delay seconds", "delay_time", 0.0)
        self._add_field(effects_frame, 1, 6, "Delay feedback", "delay_feedback", 0.25)
        self._add_field(effects_frame, 2, 0, "Delay mix", "delay_mix", 0.0)
        self._add_field(effects_frame, 2, 2, "Reverb mix", "reverb_mix", 0.0)

        realism_frame = ttk.LabelFrame(realism_tab, text="Realism DSP", padding=8)
        realism_frame.grid(row=3, column=0, sticky="ew", pady=(0, 8))
        ttk.Label(realism_frame, text="Quality").grid(row=0, column=0, sticky="w", padx=(0, 4))
        self.global_vars["render_quality"] = tk.StringVar(value="high")
        ttk.Combobox(realism_frame, textvariable=self.global_vars["render_quality"], values=("draft", "high"), state="readonly", width=8).grid(row=0, column=1, sticky="w", padx=(0, 10))
        ttk.Label(realism_frame, text="Filter").grid(row=0, column=2, sticky="w", padx=(0, 4))
        self.global_vars["filter_mode"] = tk.StringVar(value="lowpass")
        ttk.Combobox(realism_frame, textvariable=self.global_vars["filter_mode"], values=("lowpass", "highpass", "bandpass", "notch"), state="readonly", width=10).grid(row=0, column=3, sticky="w", padx=(0, 10))
        self._add_field(realism_frame, 0, 4, "Cutoff Hz", "filter_cutoff_hz", 0.0)
        self._add_field(realism_frame, 0, 6, "Resonance", "filter_resonance", 0.0)
        self._add_field(realism_frame, 1, 0, "Filter envelope", "filter_envelope_amount", 0.0)
        self._add_field(realism_frame, 1, 2, "Transient", "transient_gain", 0.0)
        self._add_field(realism_frame, 1, 4, "Transient decay", "transient_decay", 0.025)
        self._add_field(realism_frame, 1, 6, "Pitch drift Hz", "pitch_drift_hz", 0.0)
        self._add_field(realism_frame, 2, 0, "Pitch jitter Hz", "pitch_jitter_hz", 0.0)
        self._add_field(realism_frame, 2, 2, "Formant low Hz", "formant_low_hz", 0.0)
        self._add_field(realism_frame, 2, 4, "Formant high Hz", "formant_high_hz", 0.0)

        self._build_piano_tab(piano_tab)

        quick_global_frame = ttk.LabelFrame(mix_tab, text="Quick global sliders", padding=8)
        quick_global_frame.grid(row=4, column=0, sticky="ew", pady=(0, 8))
        quick_global_frame.columnconfigure(1, weight=1)
        quick_global_frame.columnconfigure(4, weight=1)
        self._add_quick_slider(quick_global_frame, 0, 0, "Duration", "duration", 0.01, MAX_DURATION_SECONDS, 0.01)
        self._add_quick_slider(quick_global_frame, 0, 3, "Master", "master_gain", 0.0, 1.5, 0.01)
        self._add_quick_slider(quick_global_frame, 1, 0, "Attack", "attack", 0.0, 1.0, 0.01)
        self._add_quick_slider(quick_global_frame, 1, 3, "Release", "release", 0.0, 2.0, 0.01)
        self._add_quick_slider(quick_global_frame, 2, 0, "Distortion", "distortion", 0.0, 1.0, 0.01)
        self._add_quick_slider(quick_global_frame, 2, 3, "Reverb", "reverb_mix", 0.0, 1.0, 0.01)
        ttk.Label(mix_tab, text="Preview, WAV export, variations, and Unity Pack export are available in the top toolbar.", wraplength=600).grid(row=1, column=0, sticky="w", pady=(12, 0))

        layers_frame = ttk.LabelFrame(parent, text="Oscillator layers", padding=8)
        layers_frame.grid(row=5, column=0, sticky="nsew")
        headers = ("On", "Wave", "Frequency", "Gain", "Phase°", "Sweep start", "Sweep end", "Start", "End")
        for column, title in enumerate(headers):
            ttk.Label(layers_frame, text=title, font=("Segoe UI", 9, "bold")).grid(row=0, column=column, padx=3, pady=(0, 4), sticky="w")
        for index in range(4):
            values: dict[str, Any] = {"enabled": tk.BooleanVar(value=index == 0)}
            ttk.Checkbutton(layers_frame, text=f"L{index + 1}", variable=values["enabled"]).grid(row=index + 1, column=0, sticky="w", padx=3, pady=2)
            values["waveform"] = tk.StringVar(value="sine")
            ttk.Combobox(layers_frame, textvariable=values["waveform"], values=("sine", "square", "triangle", "sawtooth"), state="readonly", width=10).grid(row=index + 1, column=1, padx=3, pady=2)
            for column, key, default in (
                (2, "frequency", 440.0), (3, "gain", 0.25), (4, "phase_degrees", 0.0),
                (5, "sweep_start", 0.0), (6, "sweep_end", 0.0), (7, "start_time", 0.0), (8, "end_time", 0.75),
            ):
                values[key] = tk.StringVar(value=str(default))
                ttk.Entry(layers_frame, textvariable=values[key], width=10).grid(row=index + 1, column=column, padx=3, pady=2)
            self.layer_vars.append(values)

        shaping_frame = ttk.LabelFrame(parent, text="Per-layer modulation and envelope", padding=8)
        shaping_frame.grid(row=6, column=0, sticky="ew", pady=(8, 0))
        headers = ("FM Hz", "FM depth Hz", "LFO Hz", "LFO depth", "Attack", "Decay", "Sustain", "Release")
        for column, title in enumerate(headers):
            ttk.Label(shaping_frame, text=title, font=("Segoe UI", 9, "bold")).grid(row=0, column=column + 1, padx=3, pady=(0, 4), sticky="w")
        for index, values in enumerate(self.layer_vars):
            ttk.Label(shaping_frame, text=f"L{index + 1}").grid(row=index + 1, column=0, padx=(0, 3), pady=2, sticky="w")
            for column, key, default in (
                (1, "fm_frequency", 0.0), (2, "fm_depth_hz", 0.0), (3, "lfo_frequency", 0.0), (4, "lfo_depth", 0.0),
                (5, "attack", 0.0), (6, "decay", 0.0), (7, "sustain", 1.0), (8, "release", 0.0),
            ):
                values[key] = tk.StringVar(value=str(default))
                ttk.Entry(shaping_frame, textvariable=values[key], width=9).grid(row=index + 1, column=column, padx=3, pady=2)

        quick_layer_frame = ttk.LabelFrame(parent, text="Quick selected-layer sliders", padding=8)
        quick_layer_frame.grid(row=7, column=0, sticky="ew", pady=(8, 0))
        for index in range(4):
            ttk.Radiobutton(quick_layer_frame, text=f"Layer {index + 1}", variable=self.selected_layer_var, value=index,
                            command=self._refresh_quick_layer_sliders).grid(row=0, column=index, padx=(0, 8), sticky="w")
        for row, (label, key, minimum, maximum, resolution, logarithmic) in enumerate((
            ("Frequency", "frequency", 20.0, 20000.0, 0.001, True),
            ("Gain", "gain", 0.0, 2.0, 0.01, False),
            ("FM depth", "fm_depth_hz", 0.0, 2000.0, 1.0, False),
            ("LFO depth", "lfo_depth", 0.0, 1.0, 0.01, False),
        ), start=1):
            ttk.Label(quick_layer_frame, text=label).grid(row=row, column=0, sticky="w", padx=(0, 4), pady=2)
            slider = tk.Scale(quick_layer_frame, from_=0.0 if logarithmic else minimum, to=1.0 if logarithmic else maximum,
                              orient=tk.HORIZONTAL, resolution=resolution, showvalue=False, length=190,
                              command=lambda value, field=key, is_log=logarithmic: self._set_selected_layer_from_slider(field, float(value), is_log))
            slider.grid(row=row, column=1, columnspan=2, sticky="ew", padx=(0, 4), pady=2)
            value_var = tk.StringVar()
            self.quick_layer_scales[key] = slider
            self.quick_layer_values[key] = value_var
            ttk.Label(quick_layer_frame, textvariable=value_var, width=10).grid(row=row, column=3, sticky="w", pady=2)
        self._refresh_quick_layer_sliders()

    def _build_piano_tab(self, parent: ttk.Frame) -> None:
        parent.columnconfigure(0, weight=1)
        controls = ttk.LabelFrame(parent, text="Piano roll", padding=8)
        controls.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        ttk.Label(controls, text="Tempo (BPM)").grid(row=0, column=0, sticky="w", padx=(0, 4))
        self.music_vars["music_tempo_bpm"] = tk.StringVar(value="120")
        ttk.Spinbox(controls, from_=40, to=300, textvariable=self.music_vars["music_tempo_bpm"], width=8).grid(row=0, column=1, sticky="w", padx=(0, 12))
        ttk.Label(controls, text="Steps").grid(row=0, column=2, sticky="w", padx=(0, 4))
        self.music_vars["music_steps"] = tk.StringVar(value="16")
        steps = ttk.Combobox(controls, textvariable=self.music_vars["music_steps"], values=(8, 16, 32), state="readonly", width=6)
        steps.grid(row=0, column=3, sticky="w", padx=(0, 12))
        steps.bind("<<ComboboxSelected>>", lambda _event: self._change_music_steps())
        ttk.Label(controls, text="Current-design wave").grid(row=1, column=0, sticky="w", padx=(0, 4), pady=(6, 0))
        quick_wave = ttk.Combobox(controls, textvariable=self.piano_waveform_var,
                                  values=("sine", "square", "triangle", "sawtooth"), state="readonly", width=10)
        quick_wave.grid(row=1, column=1, sticky="w", padx=(0, 12), pady=(6, 0))
        quick_wave.bind("<<ComboboxSelected>>", lambda _event: self.apply_piano_waveform())
        ttk.Label(controls, text="Applies to enabled layers used by Custom tracks.").grid(row=1, column=2, columnspan=4, sticky="w", pady=(6, 0))
        track_frame = ttk.LabelFrame(parent, text="Tracks", padding=8)
        track_frame.grid(row=1, column=0, sticky="ew", pady=(0, 8))
        ttk.Label(track_frame, text="Edit", font=("Segoe UI", 9, "bold")).grid(row=0, column=0, padx=3)
        ttk.Label(track_frame, text="Show", font=("Segoe UI", 9, "bold")).grid(row=0, column=1, padx=3)
        ttk.Label(track_frame, text="Name", font=("Segoe UI", 9, "bold")).grid(row=0, column=2, padx=3, sticky="w")
        ttk.Label(track_frame, text="Instrument", font=("Segoe UI", 9, "bold")).grid(row=0, column=3, padx=3, sticky="w")
        ttk.Label(track_frame, text="Volume", font=("Segoe UI", 9, "bold")).grid(row=0, column=4, padx=3, sticky="w")
        ttk.Label(track_frame, text="Mute", font=("Segoe UI", 9, "bold")).grid(row=0, column=5, padx=3)
        for index in range(MUSIC_TRACK_COUNT):
            values: dict[str, Any] = {
                "name": tk.StringVar(value=f"Track {index + 1}"),
                "preset": tk.StringVar(value="Custom"),
                "volume": tk.StringVar(value="0.8"),
                "muted": tk.BooleanVar(value=False),
                "visible": tk.BooleanVar(value=True),
                "notes": [],
            }
            ttk.Radiobutton(track_frame, variable=self.selected_music_track_var, value=index, command=self.draw_piano_roll).grid(row=index + 1, column=0, padx=3)
            ttk.Checkbutton(track_frame, variable=values["visible"], command=self.draw_piano_roll).grid(row=index + 1, column=1, padx=3)
            ttk.Entry(track_frame, textvariable=values["name"], width=15).grid(row=index + 1, column=2, padx=3, pady=2, sticky="ew")
            ttk.Combobox(track_frame, textvariable=values["preset"], values=tuple(PRESETS), state="readonly", width=20).grid(row=index + 1, column=3, padx=3, pady=2, sticky="ew")
            ttk.Spinbox(track_frame, from_=0, to=2, increment=.05, textvariable=values["volume"], width=7).grid(row=index + 1, column=4, padx=3, pady=2)
            ttk.Checkbutton(track_frame, variable=values["muted"]).grid(row=index + 1, column=5, padx=3)
            self.music_track_vars.append(values)
        ttk.Button(controls, text="Clear", command=self.clear_music_notes).grid(row=0, column=4, padx=(0, 6))
        ttk.Button(controls, text="Load minor loop", command=self.load_minor_loop).grid(row=0, column=5, padx=(0, 6))
        ttk.Button(controls, text="Load major loop", command=self.load_major_loop).grid(row=0, column=6, padx=(0, 6))
        ttk.Button(controls, text="Preview song", command=self.preview_music).grid(row=0, column=7, padx=(0, 6))
        ttk.Button(controls, text="Export song WAV", command=self.export_music).grid(row=0, column=8)
        ttk.Label(parent, text="Use Edit to choose the track you are changing; tick Show on any tracks you want overlaid. Click to add/remove notes or drag across cells to set note length.", wraplength=780).grid(row=2, column=0, sticky="w", pady=(0, 6))
        self.piano_canvas = tk.Canvas(parent, height=432, background="#10131a", highlightthickness=0)
        self.piano_canvas.grid(row=3, column=0, sticky="ew")
        self.piano_canvas.bind("<ButtonPress-1>", self._begin_piano_note)
        self.piano_canvas.bind("<ButtonRelease-1>", self._finish_piano_note)
        self.piano_canvas.bind("<Configure>", lambda _event: self.draw_piano_roll())
        self.draw_piano_roll()

    @staticmethod
    def _midi_name(midi: int) -> str:
        names = ("C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B")
        return f"{names[midi % 12]}{midi // 12 - 1}"

    def _music_step_count(self) -> int:
        try:
            return int(self.music_vars["music_steps"].get())
        except (KeyError, ValueError):
            return 16

    def _selected_music_track(self) -> dict[str, Any]:
        return self.music_track_vars[self.selected_music_track_var.get()]

    def apply_piano_waveform(self) -> None:
        waveform = self.piano_waveform_var.get()
        for layer in self.layer_vars:
            if layer["enabled"].get():
                layer["waveform"].set(waveform)
        self.status.set(f"Current-design instrument set to {waveform} wave")

    def _piano_cell_at(self, event: tk.Event) -> tuple[int, int] | None:
        if self.piano_canvas is None or event.x < 48:
            return None
        steps = self._music_step_count()
        width, height = max(10, self.piano_canvas.winfo_width()), max(10, self.piano_canvas.winfo_height())
        step = min(steps - 1, max(0, int((event.x - 48) / max(1, (width - 48) / steps))))
        row_count = PIANO_HIGH_MIDI - PIANO_LOW_MIDI + 1
        row = min(row_count - 1, max(0, int(event.y / max(1, height / row_count))))
        return step, PIANO_HIGH_MIDI - row

    def draw_piano_roll(self) -> None:
        if self.piano_canvas is None:
            return
        canvas = self.piano_canvas
        canvas.delete("all")
        width, height = max(10, canvas.winfo_width()), max(10, canvas.winfo_height())
        label_width = 48
        steps = self._music_step_count()
        row_count = PIANO_HIGH_MIDI - PIANO_LOW_MIDI + 1
        cell_width = max(1, (width - label_width) / steps)
        cell_height = height / row_count
        active: dict[tuple[int, int], list[tuple[dict[str, Any], int]]] = {}
        for track_index, track in enumerate(self.music_track_vars):
            if not track["visible"].get():
                continue
            for note in track["notes"]:
                active.setdefault((note["step"], note["midi"]), []).append((note, track_index))
        black_keys = {1, 3, 6, 8, 10}
        track_colours = ("#63c5ff", "#f0b35f", "#b884f5", "#72d394")
        for row, midi in enumerate(range(PIANO_HIGH_MIDI, PIANO_LOW_MIDI - 1, -1)):
            y0, y1 = row * cell_height, (row + 1) * cell_height
            base = "#1b2130" if midi % 12 in black_keys else "#252d3d"
            canvas.create_rectangle(0, y0, label_width, y1, fill="#161b27", outline="#384153")
            if midi % 12 == 0 or midi == PIANO_HIGH_MIDI:
                canvas.create_text(4, (y0 + y1) / 2, text=self._midi_name(midi), anchor="w", fill="#d9e2f1", font=("Segoe UI", 8))
            for step in range(steps):
                x0, x1 = label_width + step * cell_width, label_width + (step + 1) * cell_width
                colour = "#315888" if step % 4 == 0 else base
                canvas.create_rectangle(x0, y0, x1, y1, fill=colour, outline="#354054")
                notes = active.get((step, midi), [])
                for note, track_index in notes:
                    end = min(steps, step + note["length"])
                    is_edit_track = track_index == self.selected_music_track_var.get()
                    canvas.create_rectangle(x0 + 2, y0 + 2, label_width + end * cell_width - 2, y1 - 2,
                                            fill=track_colours[track_index], outline="#ffffff" if is_edit_track else "")

    def _begin_piano_note(self, event: tk.Event) -> None:
        self._piano_drag_start = self._piano_cell_at(event)

    def _finish_piano_note(self, event: tk.Event) -> None:
        start = self._piano_drag_start
        end = self._piano_cell_at(event)
        self._piano_drag_start = None
        if start is None or end is None or start[1] != end[1]:
            return
        step, midi = min(start[0], end[0]), start[1]
        length = abs(end[0] - start[0]) + 1
        notes = self._selected_music_track()["notes"]
        existing = next((note for note in notes if note["step"] == step and note["midi"] == midi), None)
        if existing and length == 1:
            notes.remove(existing)
        elif existing:
            existing["length"] = length
        else:
            notes.append({"step": step, "midi": midi, "length": length, "velocity": 0.75})
        self.draw_piano_roll()

    def _change_music_steps(self) -> None:
        steps = self._music_step_count()
        for track in self.music_track_vars:
            track["notes"] = [note for note in track["notes"] if note["step"] < steps]
        self.draw_piano_roll()

    def clear_music_notes(self) -> None:
        self._selected_music_track()["notes"].clear()
        self.draw_piano_roll()
        self.status.set("Piano roll cleared")

    def load_minor_loop(self) -> None:
        self._load_chord_loop(((57, 60, 64), (53, 57, 60), (55, 59, 62), (52, 55, 59)), "minor")

    def load_major_loop(self) -> None:
        self._load_chord_loop(((60, 64, 67), (55, 59, 62), (57, 60, 64), (53, 57, 60)), "major")

    def _load_chord_loop(self, chords: tuple[tuple[int, ...], ...], label: str) -> None:
        steps = self._music_step_count()
        note_length = max(1, steps // (len(chords) * 2))
        selected_track = self._selected_music_track()
        selected_track["notes"] = [
            {"step": (chord_index * steps) // len(chords), "midi": midi, "length": note_length, "velocity": 0.92}
            for chord_index, chord in enumerate(chords)
            for midi in chord
        ]
        self.draw_piano_roll()
        self.status.set(f"Loaded {label} loop notes into {selected_track['name'].get()}")

    def _set_selected_layer_from_slider(self, key: str, value: float, logarithmic: bool) -> None:
        if logarithmic:
            value = 20.0 * (1000.0 ** value)
        variable = self.layer_vars[self.selected_layer_var.get()][key]
        variable.set(f"{value:.4g}")
        self.quick_layer_values[key].set(f"{value:.3g}")

    def _refresh_quick_layer_sliders(self) -> None:
        if not self.layer_vars:
            return
        layer = self.layer_vars[self.selected_layer_var.get()]
        for key, slider in self.quick_layer_scales.items():
            try:
                value = float(layer[key].get())
            except ValueError:
                value = 0.0
            if key == "frequency":
                slider.set(clamp(math.log(max(20.0, value) / 20.0, 1000.0), 0.0, 1.0))
            else:
                slider.set(value)
            self.quick_layer_values[key].set(f"{value:.3g}")

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
        for key in ("duration", "master_gain", "attack", "decay", "sustain", "release", "noise_gain", "lowpass_hz", "distortion", "delay_time", "delay_feedback", "delay_mix", "reverb_mix", "filter_cutoff_hz", "filter_resonance", "filter_envelope_amount", "transient_gain", "transient_decay", "pitch_drift_hz", "pitch_jitter_hz", "formant_low_hz", "formant_high_hz"):
            state[key] = self._number(self.global_vars[key], key.replace("_", " "))
        state["variation_amount"] = self._number(self.global_vars["variation_amount"], "variation percentage") / 100.0
        state["sample_rate"] = int(self.global_vars["sample_rate"].get())
        state["noise_seed"] = int(self._number(self.global_vars["noise_seed"], "noise seed"))
        state["noise_enabled"] = self.global_vars["noise_enabled"].get()
        state["noise_color"] = self.global_vars["noise_color"].get()
        state["render_quality"] = self.global_vars["render_quality"].get()
        state["filter_mode"] = self.global_vars["filter_mode"].get()
        state["normalize"] = self.global_vars["normalize"].get()
        state["preset"] = self.preset_var.get()
        state["music_tempo_bpm"] = self._number(self.music_vars["music_tempo_bpm"], "music tempo")
        state["music_steps"] = int(self.music_vars["music_steps"].get())
        state["music_tracks"] = [
            {
                "name": track["name"].get(), "preset": track["preset"].get(),
                "volume": self._number(track["volume"], "track volume"), "muted": track["muted"].get(),
                "notes": copy.deepcopy(track["notes"]),
            }
            for track in self.music_track_vars
        ]
        state["music_notes"] = copy.deepcopy(state["music_tracks"][0]["notes"])
        state["layers"] = []
        for variables in self.layer_vars:
            state["layers"].append({
                "enabled": variables["enabled"].get(),
                "waveform": variables["waveform"].get(),
                **{key: self._number(variables[key], key.replace("_", " ")) for key in variables if key not in ("enabled", "waveform")},
            })
        return validate_state(state)

    def _load_state_into_ui(self, raw_state: dict[str, Any]) -> None:
        state = validate_state(raw_state)
        preset = state.get("preset", "Custom")
        self.preset_var.set(preset if preset in PRESETS else "Custom")
        for key, variable in self.global_vars.items():
            if key in ("noise_enabled", "normalize"):
                variable.set(state[key])
            elif key == "variation_amount":
                variable.set(str(state[key] * 100.0))
            else:
                variable.set(str(state[key]))
        for layer_state, variables in zip(state["layers"], self.layer_vars):
            for key, variable in variables.items():
                variable.set(layer_state[key] if key == "enabled" else str(layer_state[key]))
        for key, variable in self.music_vars.items():
            variable.set(str(state[key]))
        for track_state, variables in zip(state["music_tracks"], self.music_track_vars):
            variables["name"].set(track_state["name"])
            variables["preset"].set(track_state["preset"])
            variables["volume"].set(str(track_state["volume"]))
            variables["muted"].set(track_state["muted"])
            variables["notes"] = copy.deepcopy(track_state["notes"])
        if self.layer_vars:
            self.piano_waveform_var.set(self.layer_vars[0]["waveform"].get())
        self.state = state
        self._refresh_quick_layer_sliders()
        self._refresh_preset_browser()
        self.draw_piano_roll()

    def _watch_waveform_controls(self) -> None:
        for variable in self.global_vars.values():
            variable.trace_add("write", self._schedule_waveform_refresh)
        for layer in self.layer_vars:
            for variable in layer.values():
                variable.trace_add("write", self._schedule_waveform_refresh)

    def _schedule_waveform_refresh(self, *_arguments: Any) -> None:
        if self._waveform_job is not None:
            self.root.after_cancel(self._waveform_job)
        self._waveform_job = self.root.after(250, self.refresh_waveform)

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
        self._waveform_job = None
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
        self._draw_spectrum(samples)
        self.status.set(f"Generated {len(samples):,} samples at {_state['sample_rate']:,} Hz")

    def _draw_spectrum(self, samples: list[float]) -> None:
        canvas = self.spectrum_canvas
        canvas.delete("all")
        width, height = max(10, canvas.winfo_width()), max(10, canvas.winfo_height())
        window = samples[:min(1024, len(samples))]
        if not window:
            return
        bins = 40
        magnitudes: list[float] = []
        for bin_index in range(bins):
            frequency_bin = bin_index + 1
            real = sum(value * math.cos(math.tau * frequency_bin * index / len(window)) for index, value in enumerate(window))
            imaginary = sum(value * math.sin(math.tau * frequency_bin * index / len(window)) for index, value in enumerate(window))
            magnitudes.append(math.sqrt(real * real + imaginary * imaginary) / len(window))
        peak = max(magnitudes, default=1.0) or 1.0
        bar_width = width / bins
        for index, magnitude in enumerate(magnitudes):
            bar_height = (magnitude / peak) * (height - 14)
            x0 = index * bar_width + 1
            canvas.create_rectangle(x0, height - bar_height - 1, x0 + bar_width - 2, height - 1, fill="#7ee787", outline="")

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

    def preview_music(self) -> None:
        try:
            samples, state = generate_music_samples(self._state_from_ui())
            if not any(track["notes"] for track in state["music_tracks"]):
                self.status.set("Add notes to the piano roll before previewing.")
                return
            self.stop_preview()
            file_handle = tempfile.NamedTemporaryFile(prefix="unity_music_", suffix=".wav", delete=False)
            file_handle.close()
            self.preview_file = file_handle.name
            write_wav(self.preview_file, samples, state["sample_rate"])
            if winsound is not None:
                winsound.PlaySound(self.preview_file, winsound.SND_FILENAME | winsound.SND_ASYNC)
                self.status.set("Song preview playing")
            else:
                self.status.set("Song preview rendered; playback is only available on Windows.")
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

    def export_music(self) -> None:
        try:
            samples, state = generate_music_samples(self._state_from_ui())
            if not any(track["notes"] for track in state["music_tracks"]):
                self.status.set("Add notes to the piano roll before exporting.")
                return
            filename = filedialog.asksaveasfilename(
                title="Export Unity-ready music WAV", defaultextension=".wav",
                initialfile=f"{state['name']}_Music.wav", filetypes=(("WAV audio", "*.wav"),),
            )
            if not filename:
                return
            write_wav(filename, samples, state["sample_rate"])
            self.status.set(f"Exported song {Path(filename).name}")
            messagebox.showinfo(APP_TITLE, "Exported Unity-ready 16-bit mono music WAV.")
        except (ValueError, OSError, OverflowError) as error:
            messagebox.showerror(APP_TITLE, str(error))

    def export_variations(self) -> None:
        try:
            source = self._state_from_ui()
            count = simpledialog.askinteger(APP_TITLE, "How many variations?", parent=self.root, initialvalue=8, minvalue=2, maxvalue=50)
            if count is None:
                return
            destination = filedialog.askdirectory(title="Choose a folder for WAV variations")
            if not destination:
                return
            for index in range(count):
                variation = make_variation(source, index)
                samples, normalized = generate_samples(variation)
                write_wav(Path(destination) / f"{normalized['name']}.wav", samples, normalized["sample_rate"])
            self.status.set(f"Exported {count} deterministic variations to {Path(destination).name}")
            messagebox.showinfo(APP_TITLE, f"Exported {count} Unity-ready WAV variations.")
        except (ValueError, OSError, OverflowError) as error:
            messagebox.showerror(APP_TITLE, str(error))

    def export_pack(self) -> None:
        try:
            source = self._state_from_ui()
            count = simpledialog.askinteger(APP_TITLE, "How many WAVs in this Unity Pack?", parent=self.root, initialvalue=1, minvalue=1, maxvalue=50)
            if count is None:
                return
            destination = filedialog.askdirectory(title="Choose a folder for the Unity Pack")
            if not destination:
                return
            output_paths = export_unity_pack(destination, source, count)
            self.status.set(f"Exported Unity Pack: {len(output_paths) - 1} WAV(s) plus recipe JSON")
            messagebox.showinfo(APP_TITLE, f"Exported {len(output_paths) - 1} Unity-ready WAV(s) and an editable .sfx.json recipe.")
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

    waveform_samples = []
    for waveform in ("sine", "square", "triangle", "sawtooth"):
        waveform_state = default_state()
        waveform_state["layers"][0]["waveform"] = waveform
        waveform_samples.append(generate_samples(waveform_state)[0])
    if len({tuple(samples[:256]) for samples in waveform_samples}) != 4:
        failures.append("Waveform choices did not create distinct audio")

    advanced_state = default_state()
    advanced_state["layers"][0].update({"fm_frequency": 37, "fm_depth_hz": 180, "lfo_frequency": 5, "lfo_depth": 0.7, "attack": 0.05, "release": 0.1})
    advanced_state.update({"noise_enabled": True, "noise_color": "pink", "noise_gain": 0.1, "delay_time": 0.04, "delay_feedback": 0.35, "delay_mix": 0.25, "reverb_mix": 0.2})
    advanced_samples, _ = generate_samples(advanced_state)
    plain_samples, _ = generate_samples(default_state())
    if advanced_samples == plain_samples or not any(advanced_samples):
        failures.append("Advanced modulation or effects did not alter generated audio")

    variation_source = validate_state(copy.deepcopy(PRESETS["Pickup"]))
    variation_a = make_variation(variation_source, 0)
    variation_b = make_variation(variation_source, 0)
    if generate_samples(variation_a)[0] != generate_samples(variation_b)[0]:
        failures.append("Batch variation generation is not deterministic")

    music_state = default_state()
    music_state["music_notes"] = [
        {"step": 0, "midi": 60, "length": 2, "velocity": .75},
        {"step": 4, "midi": 64, "length": 2, "velocity": .75},
    ]
    music_state["music_tracks"][0]["notes"] = copy.deepcopy(music_state["music_notes"])
    music_a, normalized_music = generate_music_samples(music_state)
    music_b, _ = generate_music_samples(copy.deepcopy(music_state))
    expected_music_samples = int(normalized_music["music_steps"] * 60 / normalized_music["music_tempo_bpm"] / 4 * normalized_music["sample_rate"])
    if music_a != music_b or len(music_a) != expected_music_samples or not any(music_a):
        failures.append("Piano-roll music generation was invalid or non-deterministic")

    with tempfile.TemporaryDirectory(prefix="sfx_designer_pack_") as folder:
        output_paths = export_unity_pack(folder, PRESETS["Pickup"], 3)
        if len(output_paths) != 4 or not all(path.exists() for path in output_paths):
            failures.append("Unity Pack export did not write recipe and variations")
        elif json.loads(output_paths[0].read_text(encoding="utf-8"))["name"] != "Pickup":
            failures.append("Unity Pack recipe did not preserve editable state")

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
    print(f"Self-test passed: {len(PRESETS)} presets plus piano-roll music exported as 44.1 kHz 16-bit mono WAV; deterministic, waveform, modulation, effects, variation, Unity Pack, silence, and input-clamping checks passed.")
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
