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
2. In the **Preset browser**, filter by category, search by name, or save commonly used sounds as favourites. Double-click to load; use **Preview selected** to load and audition a sound in one click.
3. The waveform and spectrum update automatically after you pause editing briefly; **Refresh waveform** is still available on demand.
4. Select **Preview** to hear it, then **Stop** to stop playback.
5. Use **Save Project** to retain all editable settings in JSON.
6. Use **Export WAV** and choose any folder. The resulting file is a 44.1 kHz, 16-bit, mono PCM WAV.

Each of the four layers has its own sine, square, triangle, or sawtooth oscillator, frequency, gain, phase, pitch sweep, active start/end time, FM modulation, amplitude LFO, and ADSR envelope. This allows a sharp transient layer to sit above a sustained body or tail.

Use the **Quick global sliders** for fast shaping and the **Quick selected-layer sliders** for frequency, gain, FM depth, and LFO depth. Numeric fields remain available alongside them for exact values; the frequency slider uses a logarithmic scale so low and high frequencies are both practical to adjust.

The Realism tab adds 4× oversampled rendering, white/pink/brown/band-limited noise, resonant filter modes, transient bursts, pitch drift/jitter, formant bands, soft distortion, feedback delay, and a compact mono room tail. These are tuned for weapon impacts and zombie vocalisations while retaining Unity-friendly mono positional audio.

## Preset browser

The preset browser keeps the built-in library out of the way of the design controls while making it quick to reuse. Filter by category, type part of a preset or category name, and use **Add favourite** for frequently used sounds. Favourites are stored locally in your Windows app-data folder, so updating the tool does not alter your project files or Git working tree.

## Piano roll

The **Piano** tab turns the current sound design into a simple game-music instrument. Click cells in the 16th-note grid to add notes, set the BPM, choose an 8-, 16-, or 32-step loop, then preview or export the complete loop as a Unity-ready WAV. The included **Load minor loop** button provides an editable starting phrase.

Music notes, tempo, and loop length are saved in normal project JSON files alongside the synth settings. This is deliberately a compact sequencer for loops, stings, and menu music—not a replacement for a full DAW. Exported music remains mono to suit Unity positional or UI playback; use the same project’s effects controls to shape the instrument and room tail.

## Variations

Use **Export Variations** to build 2–50 related WAVs from the current design. The **Variation %** setting controls how much pitch, gain, timing, sweep, phase, and noise seed differ. This is ideal for avoiding repetitive footsteps, impacts, gunshot layers, and zombie sounds while keeping a coherent sound family.

## Unity Packs

Use **Export Unity Pack** to write one or more Unity-ready WAVs and a matching `.sfx.json` recipe to one folder. Keep the JSON next to its exported audio to make future tuning reproducible; either folder can then be copied directly beneath a Unity project's `Assets` folder.

## Validate without opening the UI

```powershell
python sine_sfx_designer.py --self-test
```

This exports every built-in preset to a temporary location and verifies the required Unity WAV format.
