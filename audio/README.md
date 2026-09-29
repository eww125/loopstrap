# Audio engine (roadmap)

The real-time audio side of loopstrap will live here. Not started yet —
the button/LED controller in `../controller` is being proven on the bench first.

Plan:
- Language: C or C++ (Python can't do per-sample DSP on 8 tracks at low latency).
- Input: Codec Zero over I2S (guitar pickup + electret mic).
- 8 mono loop tracks in RAM; click track private to headphones; PA mix excludes click.
- Effects: one shared reverb/delay send bus + per-track simple inserts
  (distortion, filter, echo). Heavy per-track convolution is out of scope
  for the Zero 2 W until measured.
- USB audio gadget mode: Pi presents itself to the Mac as a USB audio
  interface for Ableton.

The controller talks to this engine through the `LoopEngine` interface
defined in `controller/looper.py` — button logic won't change when the
engine lands.
