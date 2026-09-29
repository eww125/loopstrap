# loopstrap

An 8-track clip-on looper for a Taylor nylon-string guitar. Strap-mounted
electronics, soundhole controller, no mods to the guitar.

## Hardware

- Raspberry Pi Zero 2 W (the **WH** version — header pre-soldered)
- Raspberry Pi Codec Zero (audio in/out over I2S, stacks on the 40-pin header)
- 8x momentary pushbuttons + 1x mode button (breadboard prototype: whatever
  you've got, as long as they spring back)
- 8x WS2812B addressable LEDs, one per track, single data pin
- Electret mic capsule soldered to a 3.5mm plug -> Codec Zero mic jack
- USB power bank for stage; wall wart for the bench; Mac powers it over USB
  when used as an audio interface

## Wiring (prototype)

Codec Zero uses GPIO 0,1,2,3,18,19,20,21,23,24,27 — everything else on the
stacking header is free:

| Function            | GPIO                        |
|---------------------|-----------------------------|
| Track buttons 1–8   | 4, 5, 6, 13, 16, 17, 22, 26 |
| Mode button         | 25                          |
| LED strip data      | 10 (SPI0 MOSI)              |

Buttons wire pin -> GND (internal pull-ups on). LEDs: one strip of 8,
data in on GPIO 10.

## Button behavior

Each track: tap empty -> **record** (red), tap -> **play** (green),
tap -> **park** (blue), tap -> **resume** (green), hold -> **erase**.
Hold MODE -> shift mode: the 8 buttons become effect slots (stub for now).

## Quickstart (on the Pi)

```bash
git clone <repo> /home/pi/loopstrap
cd /home/pi/loopstrap
bash pi-setup/install.sh        # one-time: deps + boot auto-update
.venv/bin/python controller/looper.py
```

On any other machine: `python3 controller/looper.py --mock` exercises the
state machine without Pi hardware.

Every boot, the Pi `git pull`s this repo, so pushed fixes land on their own.

## Layout

- `controller/` — button/LED logic (Python, runs today)
- `audio/` — real-time engine roadmap (C/C++, comes next)
- `pi-setup/` — install script + boot auto-update service
