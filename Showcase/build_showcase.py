"""Render the editable Unity SFX Designer showcase pack."""

from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sine_sfx_designer import PRESETS, default_state, generate_music_samples, generate_samples, write_wav

OUTPUT = ROOT / "Showcase" / "Audio"


def track(name: str, preset: str, volume: float, notes: list[tuple[int, int, int, float]]) -> dict:
    return {
        "name": name,
        "preset": preset,
        "volume": volume,
        "muted": False,
        "notes": [{"step": step, "midi": midi, "length": length, "velocity": velocity} for step, midi, length, velocity in notes],
    }


def make_night_patrol() -> dict:
    state = default_state()
    state.update({"name": "Night_Patrol", "music_tempo_bpm": 96, "music_steps": 32, "reverb_mix": .16})
    state["music_tracks"] = [
        track("Lead", "Pickup", 1.0, [(0, 69, 2, .8), (4, 72, 2, .8), (8, 76, 3, .85), (14, 74, 2, .75), (16, 69, 2, .8), (20, 72, 2, .8), (24, 77, 3, .85), (30, 76, 2, .75)]),
        track("Pad", "Ambient Hum", 1.15, [(0, 57, 8, .7), (0, 60, 8, .7), (0, 64, 8, .7), (8, 53, 8, .7), (8, 57, 8, .7), (8, 60, 8, .7), (16, 55, 8, .7), (16, 59, 8, .7), (16, 62, 8, .7), (24, 52, 8, .7), (24, 55, 8, .7), (24, 59, 8, .7)]),
        track("Pulse", "Ricochet", .42, [(0, 45, 1, .5), (4, 45, 1, .5), (8, 41, 1, .5), (12, 41, 1, .5), (16, 43, 1, .5), (20, 43, 1, .5), (24, 40, 1, .5), (28, 40, 1, .5)]),
        track("Unused", "Custom", 0, []),
    ]
    return state


def make_safehouse() -> dict:
    state = default_state()
    state.update({"name": "Safehouse_Morning", "music_tempo_bpm": 108, "music_steps": 16, "delay_time": .08, "delay_feedback": .22, "delay_mix": .15})
    state["music_tracks"] = [
        track("Pluck", "Pickup", 1.0, [(0, 60, 1, .9), (2, 64, 1, .75), (4, 67, 1, .85), (6, 64, 1, .7), (8, 62, 1, .9), (10, 65, 1, .75), (12, 69, 1, .85), (14, 65, 1, .7)]),
        track("Warmth", "Ambient Hum", 1.25, [(0, 48, 8, .65), (0, 55, 8, .65), (0, 60, 8, .65), (8, 50, 8, .65), (8, 57, 8, .65), (8, 62, 8, .65)]),
        track("Low Pulse", "Custom", .75, [(0, 36, 3, .85), (4, 36, 3, .85), (8, 38, 3, .85), (12, 38, 3, .85)]),
        track("Unused", "Custom", 0, []),
    ]
    return state


def make_sawtooth_showcase() -> dict:
    state = default_state()
    state.update({"name": "Sawtooth_Synth_Loop", "music_tempo_bpm": 124, "music_steps": 16, "master_gain": .9,
                  "attack": .006, "decay": .09, "sustain": .58, "release": .12,
                  "lowpass_hz": 3200, "distortion": .08, "delay_time": .09, "delay_feedback": .24, "delay_mix": .16})
    state["layers"][0].update({"enabled": True, "waveform": "sawtooth", "frequency": 440, "gain": .6})
    state["layers"][1].update({"enabled": True, "waveform": "sawtooth", "frequency": 880, "gain": .16})
    state["layers"][2].update({"enabled": False})
    state["music_tracks"] = [
        track("Saw Lead", "Custom", 1.0, [(0, 60, 2, .9), (2, 64, 2, .8), (4, 67, 2, .9), (6, 72, 2, .85), (8, 69, 2, .9), (10, 67, 2, .8), (12, 64, 2, .85), (14, 60, 2, .8)]),
        track("Saw Bass", "Custom", .72, [(0, 36, 4, .85), (4, 41, 4, .85), (8, 43, 4, .85), (12, 40, 4, .85)]),
        track("Unused", "Custom", 0, []),
        track("Unused", "Custom", 0, []),
    ]
    return state


def make_sfx() -> dict[str, dict]:
    return {
        "Loot_Pickup": copy.deepcopy(PRESETS["Pickup"]),
        "Wooden_Melee_Impact": {**copy.deepcopy(PRESETS["Melee Impact"]), "name": "Wooden_Melee_Impact", "noise_color": "brown", "filter_cutoff_hz": 1250, "layers": [
            {**copy.deepcopy(PRESETS["Melee Impact"])["layers"][0], "frequency": 105, "gain": .82},
            {**copy.deepcopy(PRESETS["Melee Impact"])["layers"][1], "enabled": True, "frequency": 330, "gain": .16, "end_time": .12},
            copy.deepcopy(PRESETS["Melee Impact"])["layers"][2], copy.deepcopy(PRESETS["Melee Impact"])["layers"][3],
        ]},
        "Zombie_Alert": {**copy.deepcopy(PRESETS["Zombie Scream"]), "name": "Zombie_Alert", "duration": .95, "pitch_drift_hz": 24, "formant_low_hz": 620, "formant_high_hz": 1540},
        "Rifle_Shot": copy.deepcopy(PRESETS["Rifle"]),
    }


def render(name: str, state: dict, music: bool) -> None:
    samples, normalized = generate_music_samples(state) if music else generate_samples(state)
    normalized["name"] = name
    (OUTPUT / f"{name}.sfx.json").write_text(json.dumps(normalized, indent=2), encoding="utf-8")
    write_wav(OUTPUT / f"{name}.wav", samples, normalized["sample_rate"])


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    render("Night_Patrol", make_night_patrol(), music=True)
    render("Safehouse_Morning", make_safehouse(), music=True)
    render("Sawtooth_Synth_Loop", make_sawtooth_showcase(), music=True)
    for name, state in make_sfx().items():
        state["name"] = name
        render(name, state, music=False)
    print(f"Rendered 7 editable showcase sounds to {OUTPUT}")


if __name__ == "__main__":
    main()
