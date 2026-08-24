# Unity SFX Designer

A standalone Windows utility for building procedural, layered sine-wave sound effects and exporting them as Unity-ready WAV files. It uses only Python's standard library.

Created by [SuperReaper1999](https://github.com/SuperReaper1999) with OpenAI Codex.

## Run

Double-click `Run Sine SFX Designer.bat`, or run:

```powershell
python sine_sfx_designer.py
```

Python 3 must be installed and available on your `PATH`.

If the window does not open, check that your Python installation includes Tcl/Tk:

```powershell
python -m tkinter
```

That command should open a small Tk demo window. If it reports an `init.tcl` or Tcl/Tk error, repair or reinstall Python with the **tcl/tk and IDLE** optional feature selected; the designer itself needs no Python packages beyond that standard component.

## Workflow

1. Choose a preset or configure the global, envelope, noise/effect, and sine-wave layer fields.
2. Select **Refresh waveform** to inspect the current result.
3. Select **Preview** to hear it, then **Stop** to stop playback.
4. Use **Save Project** to retain all editable settings in JSON.
5. Use **Export WAV** and choose any folder. The resulting file is a 44.1 kHz, 16-bit, mono PCM WAV.
6. Drag the WAV into the Unity Project window or save it directly beneath `Assets`.

Each of the four layers has its own frequency, gain, phase, pitch sweep, and active start/end time. The white-noise seed is deterministic, so the same project always renders the same sound.

## Validate without opening the UI

```powershell
python sine_sfx_designer.py --self-test
```

This exports every built-in preset to a temporary location and verifies the required Unity WAV format.
