# Unity SFX Designer

A standalone Windows utility for building procedural combat, creature, UI, and ambience sound effects and exporting them as Unity-ready WAV files.

Created by [SuperReaper1999](https://github.com/SuperReaper1999) with OpenAI Codex.

## Run

Double-click `Run Sine SFX Designer.bat`, or run:

```powershell
python sine_sfx_designer.py
```

Python 3 must be installed and available on your `PATH`. Install the single DSP dependency once:

```powershell
python -m pip install -r requirements.txt
```

If the window does not open, check that your Python installation includes Tcl/Tk:

```powershell
python -m tkinter
```

That command should open a small Tk demo window. If it reports an `init.tcl` or Tcl/Tk error, repair or reinstall Python with the **tcl/tk and IDLE** optional feature selected; the designer itself needs no Python packages beyond that standard component.

## Workflow

1. Use the **Design**, **Realism**, and **Mix & Export** tabs to shape the sound.
2. Choose a preset category and preset, or configure the oscillator-layer fields.
3. The waveform and spectrum update automatically after you pause editing briefly; **Refresh waveform** is still available on demand.
4. Select **Preview** to hear it, then **Stop** to stop playback.
5. Use **Save Project** to retain all editable settings in JSON.
6. Use **Export WAV** and choose any folder. The resulting file is a 44.1 kHz, 16-bit, mono PCM WAV.

Each of the four layers has its own sine, square, triangle, or sawtooth oscillator, frequency, gain, phase, pitch sweep, active start/end time, FM modulation, amplitude LFO, and ADSR envelope. This allows a sharp transient layer to sit above a sustained body or tail.

Use the **Quick global sliders** for fast shaping and the **Quick selected-layer sliders** for frequency, gain, FM depth, and LFO depth. Numeric fields remain available alongside them for exact values; the frequency slider uses a logarithmic scale so low and high frequencies are both practical to adjust.

The Realism tab adds 4× oversampled rendering, white/pink/brown/band-limited noise, resonant filter modes, transient bursts, pitch drift/jitter, formant bands, soft distortion, feedback delay, and a compact mono room tail. These are tuned for weapon impacts and zombie vocalisations while retaining Unity-friendly mono positional audio.

## Variations

Use **Export Variations** to build 2–50 related WAVs from the current design. The **Variation %** setting controls how much pitch, gain, timing, sweep, phase, and noise seed differ. This is ideal for avoiding repetitive footsteps, impacts, gunshot layers, and zombie sounds while keeping a coherent sound family.

## Unity Packs

Use **Export Unity Pack** to write one or more Unity-ready WAVs and a matching `.sfx.json` recipe to one folder. Keep the JSON next to its exported audio to make future tuning reproducible; either folder can then be copied directly beneath a Unity project's `Assets` folder.

## Validate without opening the UI

```powershell
python sine_sfx_designer.py --self-test
```

This exports every built-in preset to a temporary location and verifies the required Unity WAV format.
