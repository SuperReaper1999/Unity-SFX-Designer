# Third-Party Notices

The original source code in this repository is licensed under the MIT License. The following third-party components are used by the project and remain under their own licences.

## NumPy

- Package: numpy
- Licence: BSD 3-Clause
- Used for: numerical array operations and audio signal processing.
- Project: https://numpy.org/
- Licence text: https://numpy.org/doc/stable/license.html

When redistributing NumPy, retain its copyright notice, licence conditions, and disclaimer.

## SoundFile

- Package: soundfile
- Licence: BSD 3-Clause
- Used for: writing generated audio as WAV files.
- Project: https://python-soundfile.readthedocs.io/
- Licence text: https://python-soundfile.readthedocs.io/en/latest/index.html

When redistributing SoundFile, retain its copyright notice, licence conditions, and disclaimer.

## Kokoro

- Package: kokoro
- Licence: Apache License 2.0
- Used for: optional local dialogue text-to-speech generation.
- Project: https://github.com/hexgrad/kokoro

When redistributing Kokoro itself, retain the Apache 2.0 licence and applicable notices supplied by the package.

## Kokoro model

- Licence: Apache License 2.0, as documented by this project and the upstream model distribution.
- Used for: optional local dialogue voice generation.
- The model is downloaded at runtime and is not included in this repository.

If distributing the model or generated packages that include it, retain the upstream Apache 2.0 notices and follow the model distributor's current terms.

## Other dependencies

The optional Kokoro installation pulls additional dependencies, including PyTorch, Transformers, Hugging Face tooling, and Misaki. Those packages are installed separately and are not bundled in this repository. Their licences remain their own; consult the installed package metadata before redistributing a bundled application.
