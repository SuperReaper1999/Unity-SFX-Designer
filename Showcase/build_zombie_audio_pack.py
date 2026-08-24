"""Render editable procedural zombie clips for Open World Prototype.

Usage:
  python build_zombie_audio_pack.py --output S:\\Repos\\OpenWorldPrototype\\Assets\\Audio\\Zombies
"""

from __future__ import annotations

import argparse
import copy
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sine_sfx_designer import PRESETS, generate_samples, write_wav


def build_states() -> dict[str, dict]:
    def clone(name: str, preset: str, **changes: object) -> dict:
        state = copy.deepcopy(PRESETS[preset])
        state.update(changes)
        state["name"] = name
        return state

    return {
        "Zombie_Idle_Moan": clone("Zombie_Idle_Moan", "Zombie Groan", duration=1.25, master_gain=.72, pitch_drift_hz=7, formant_low_hz=380, formant_high_hz=920, noise_seed=1101, reverb_mix=.06),
        "Zombie_Alert": clone("Zombie_Alert", "Zombie Scream", duration=.95, master_gain=.84, pitch_drift_hz=23, formant_low_hz=610, formant_high_hz=1580, noise_seed=1102),
        "Zombie_Attack": clone("Zombie_Attack", "Zombie Attack", duration=.58, master_gain=.8, pitch_drift_hz=12, noise_seed=1103),
        "Zombie_Hurt": clone("Zombie_Hurt", "Zombie Scream", duration=.36, master_gain=.67, attack=.01, decay=.05, sustain=.08, release=.13, pitch_drift_hz=10, formant_low_hz=500, formant_high_hz=1250, noise_seed=1104),
        "Zombie_Death": clone("Zombie_Death", "Zombie Scream", duration=1.18, master_gain=.88, pitch_drift_hz=18, formant_low_hz=430, formant_high_hz=1120, noise_seed=1105, reverb_mix=.1),
        "Player_Damage": clone("Player_Damage", "Hit", duration=.2, master_gain=.48, noise_color="pink", filter_cutoff_hz=2400, distortion=.1, noise_seed=1106),
    }


def render(output: Path) -> None:
    output.mkdir(parents=True, exist_ok=True)
    for name, state in build_states().items():
        samples, normalized = generate_samples(state)
        normalized["name"] = name
        write_wav(output / f"{name}.wav", samples, normalized["sample_rate"])
        (output / f"{name}.sfx.json").write_text(json.dumps(normalized, indent=2), encoding="utf-8")
    print(f"Rendered {len(build_states())} Unity-ready sound effects to {output}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    render(parser.parse_args().output)
