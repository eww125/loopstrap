#!/usr/bin/env python3
"""loopstrap controller v1 - 8-track looper buttons + LEDs.

Hardware: Raspberry Pi Zero 2 W + Raspberry Pi Codec Zero.
  - 8x momentary pushbuttons, one per loop track
  - 1x momentary mode button (hold to enter effects shift-mode)
  - 8x WS2812B addressable LEDs, one per track, on a single SPI pin

Track state machine (per button):
    empty --tap--> RECORDING --tap--> PLAYING --tap--> PARKED --tap--> PLAYING
    hold on any non-empty track -> ERASE -> empty

LED colors: empty=dark, recording=red, playing=green, parked=blue.

Audio is NOT handled here. This script emits engine events through the
LoopEngine interface below. v1 ships a PrintEngine that just logs; the
real-time audio engine plugs in later without touching button logic.
"""

import argparse
import signal
import sys
import time
from enum import Enum, auto

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
# GPIO pins free on the Pi when the Codec Zero is stacked on top
# (codec uses 0,1,2,3,18,19,20,21,23,24,27 - do not touch those).
TRACK_BUTTON_PINS = [4, 5, 6, 13, 16, 17, 22, 26]
MODE_BUTTON_PIN = 25
LED_COUNT = 8
LED_SPI_PIN = 10  # SPI0 MOSI; rpi_ws281x drives the strip in SPI mode

HOLD_TIME = 0.6    # press longer than this = hold (erase / shift)
BOUNCE_TIME = 0.02

COLORS = {
    "empty":     (0, 0, 0),
    "recording": (255, 0, 0),
    "playing":   (0, 255, 0),
    "parked":    (0, 0, 255),
    "shift":     (255, 255, 255),
}


class TrackState(Enum):
    EMPTY = auto()
    RECORDING = auto()
    PLAYING = auto()
    PARKED = auto()


# ---------------------------------------------------------------------------
# Audio engine interface (implemented for real later)
# ---------------------------------------------------------------------------
class LoopEngine:
    """What the button layer needs from the audio engine."""

    def start_recording(self, track: int): raise NotImplementedError
    def stop_and_play(self, track: int): raise NotImplementedError
    def park(self, track: int): raise NotImplementedError
    def resume(self, track: int): raise NotImplementedError
    def erase(self, track: int): raise NotImplementedError
    def effect_toggle(self, slot: int): raise NotImplementedError


class PrintEngine(LoopEngine):
    """v1 stand-in: logs what WOULD happen so buttons/LEDs can be tested
    on the bench before the audio engine exists."""

    def _log(self, action: str, n: int):
        print(f"[engine] track {n + 1}: {action}", flush=True)

    def start_recording(self, track): self._log("start recording", track)
    def stop_and_play(self, track):   self._log("close loop, playing", track)
    def park(self, track):            self._log("parked", track)
    def resume(self, track):          self._log("resumed", track)
    def erase(self, track):           self._log("erased", track)
    def effect_toggle(self, slot):
        print(f"[engine] effect slot {slot + 1}: toggled", flush=True)


# ---------------------------------------------------------------------------
# LED strip (real hardware, with a mock fallback)
# ---------------------------------------------------------------------------
class LedStrip:
    def __init__(self, count: int, mock: bool = False):
        self.count = count
        self._strip = None
        if not mock:
            try:
                from rpi_ws281x import PixelStrip, Color
                # pin=10 -> library drives the strip via SPI0
                self._strip = PixelStrip(count, LED_SPI_PIN)
                self._strip.begin()
                self._Color = Color
            except Exception as e:  # not on a Pi, or lib missing
                print(f"[leds] hardware strip unavailable ({e}), using mock",
                      flush=True)
        if self._strip is None:
            self._Color = lambda r, g, b: (r, g, b)  # noqa: E731

    def set(self, index: int, color: tuple):
        if self._strip is not None:
            r, g, b = color
            self._strip.setPixelColor(index, self._Color(r, g, b))
            self._strip.show()
        else:
            print(f"[leds] led {index + 1}: rgb{color}", flush=True)

    def all(self, color: tuple):
        for i in range(self.count):
            self.set(i, color)


# ---------------------------------------------------------------------------
# Looper: buttons -> state machine -> engine + LEDs
# ---------------------------------------------------------------------------
class Looper:
    def __init__(self, engine: LoopEngine, leds: LedStrip, mock: bool = False):
        self.engine = engine
        self.leds = leds
        self.states = [TrackState.EMPTY] * len(TRACK_BUTTON_PINS)
        self.shift_mode = False
        self._held = {}  # pin -> True once hold_time elapsed

        if mock:
            from gpiozero import Device
            from gpiozero.pins.mock import MockFactory
            Device.pin_factory = MockFactory()
        from gpiozero import Button

        self.track_buttons = []
        for i, pin in enumerate(TRACK_BUTTON_PINS):
            btn = Button(pin, pull_up=True, bounce_time=BOUNCE_TIME,
                         hold_time=HOLD_TIME, hold_repeat=False)
            btn.when_held = self._make_hold(i)
            btn.when_released = self._make_release(i)
            self._held[pin] = False
            self.track_buttons.append(btn)

        mode = Button(MODE_BUTTON_PIN, pull_up=True, bounce_time=BOUNCE_TIME,
                      hold_time=HOLD_TIME, hold_repeat=False)
        mode.when_held = self._on_mode_hold
        mode.when_released = self._on_mode_release
        self._held[MODE_BUTTON_PIN] = False
        self.mode_button = mode

        self._refresh_leds()
        print("[looper] ready: 8 tracks, tap/hold per button. "
              "hold MODE for effects shift-mode.", flush=True)

    # -- gpiozero callbacks -------------------------------------------------
    def _make_hold(self, i):
        def on_hold(btn):
            self._held[btn.pin.number] = True
            self._on_track_hold(i)
        return on_hold

    def _make_release(self, i):
        def on_release(btn):
            pin = btn.pin.number
            was_hold = self._held[pin]
            self._held[pin] = False
            if not was_hold:
                self._on_track_tap(i)
        return on_release

    def _on_mode_hold(self, btn):
        self._held[btn.pin.number] = True
        self.shift_mode = True
        self.leds.all(COLORS["shift"])
        print("[looper] SHIFT mode: buttons are effect slots", flush=True)

    def _on_mode_release(self, btn):
        pin = btn.pin.number
        was_hold = self._held[pin]
        self._held[pin] = False
        if was_hold and self.shift_mode:
            self.shift_mode = False
            self._refresh_leds()
            print("[looper] back to loop transport", flush=True)

    # -- state machine ------------------------------------------------------
    def _on_track_tap(self, i):
        if self.shift_mode:
            self.engine.effect_toggle(i)
            return
        state = self.states[i]
        if state == TrackState.EMPTY:
            self.states[i] = TrackState.RECORDING
            self.engine.start_recording(i)
        elif state == TrackState.RECORDING:
            self.states[i] = TrackState.PLAYING
            self.engine.stop_and_play(i)
        elif state == TrackState.PLAYING:
            self.states[i] = TrackState.PARKED
            self.engine.park(i)
        elif state == TrackState.PARKED:
            self.states[i] = TrackState.PLAYING
            self.engine.resume(i)
        self._refresh_leds()

    def _on_track_hold(self, i):
        if self.shift_mode:
            return  # reserved: hold in shift-mode = effect level cycle (later)
        if self.states[i] != TrackState.EMPTY:
            self.states[i] = TrackState.EMPTY
            self.engine.erase(i)
            self._refresh_leds()

    def _refresh_leds(self):
        for i, state in enumerate(self.states):
            self.leds.set(i, COLORS[state.name.lower()])


def main():
    parser = argparse.ArgumentParser(description="loopstrap 8-track controller")
    parser.add_argument("--mock", action="store_true",
                        help="run without Pi hardware (mock GPIO + LEDs)")
    args = parser.parse_args()

    leds = LedStrip(LED_COUNT, mock=args.mock)
    looper = Looper(PrintEngine(), leds, mock=args.mock)

    stop = False

    def handle_signal(signum, frame):
        nonlocal stop
        stop = True

    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)
    while not stop:
        time.sleep(0.1)
    leds.all(COLORS["empty"])
    print("[looper] stopped", flush=True)


if __name__ == "__main__":
    sys.exit(main())
