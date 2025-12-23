import os
import re
import time
import subprocess

from settings_store import load_settings

try:
    from evdev import InputDevice, ecodes
except Exception:
    InputDevice = None
    ecodes = None


def _parse_card_index(device_id: str):
    m = re.match(r"^(?:plug)?hw:(\d+)(?:,\d+)?$", (device_id or "").strip())
    if not m:
        return None
    try:
        return int(m.group(1))
    except Exception:
        return None


def _run(cmd):
    return subprocess.run(cmd, capture_output=True, text=True)


def _amixer_get_numid(card_index: int, numid: int) -> int:
    r = _run(["amixer", "-c", str(card_index), "cget", f"numid={numid}"])
    if r.returncode != 0:
        raise RuntimeError(r.stderr.strip() or r.stdout.strip())
    m = re.search(r"\bvalues=([0-9]+)", r.stdout)
    if not m:
        raise RuntimeError("Unable to parse amixer output")
    return int(m.group(1))


def _amixer_set_numid(card_index: int, numid: int, value: int) -> None:
    r = _run(["amixer", "-c", str(card_index), "cset", f"numid={numid}", str(value)])
    if r.returncode != 0:
        raise RuntimeError(r.stderr.strip() or r.stdout.strip())


def _amixer_toggle_playback_switch(card_index: int, numid: int) -> None:
    r = _run(["amixer", "-c", str(card_index), "cget", f"numid={numid}"])
    if r.returncode != 0:
        raise RuntimeError(r.stderr.strip() or r.stdout.strip())
    # Most controls show: values=on/off or values=0/1
    if "values=on" in r.stdout:
        _amixer_set_numid(card_index, numid, 0)
    elif "values=off" in r.stdout:
        _amixer_set_numid(card_index, numid, 1)
    else:
        m = re.search(r"\bvalues=([01])\b", r.stdout)
        if not m:
            raise RuntimeError("Unable to parse playback switch")
        cur = int(m.group(1))
        _amixer_set_numid(card_index, numid, 0 if cur else 1)


def _find_input_device_path() -> str:
    """Find an input event device that actually emits volume key events.

    The S330 exposes multiple HID interfaces; only the "Consumer Control" one
    emits KEY_VOLUMEUP/DOWN/MUTE.
    """
    # Best approach: scan event devices and pick the one with volume keys.
    candidates = []
    for i in range(0, 64):
        path = f"/dev/input/event{i}"
        if not os.path.exists(path):
            continue
        try:
            dev = InputDevice(path)
            name = (getattr(dev, 'name', '') or '').lower()
            if 'anker' not in name or 'powerconf' not in name or 's330' not in name:
                continue
            caps = dev.capabilities(verbose=False)
            keys = set(caps.get(ecodes.EV_KEY, []))
            if ecodes.KEY_VOLUMEUP in keys or ecodes.KEY_VOLUMEDOWN in keys or ecodes.KEY_MUTE in keys:
                candidates.append(path)
        except Exception:
            continue

    if candidates:
        # Prefer the first found; usually only one matches.
        return candidates[0]

    # Fallback: scan /proc/bus/input/devices for a handler with Consumer Control
    try:
        with open("/proc/bus/input/devices", "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
        blocks = content.split("\n\n")
        for b in blocks:
            if "ANKER Anker PowerConf S330" in b and "Consumer Control" in b:
                m = re.search(r"Handlers=.*\b(event\d+)\b", b)
                if m:
                    return os.path.join("/dev/input", m.group(1))
    except Exception:
        pass

    raise RuntimeError("Unable to locate Anker S330 consumer control input device")


def main():
    if InputDevice is None or ecodes is None:
        raise RuntimeError("python-evdev is not installed")

    settings = load_settings()
    out_dev = settings.get("audio_output_device") or ""
    card_index = _parse_card_index(out_dev)
    if card_index is None:
        raise RuntimeError(f"Unable to determine ALSA card index from audio_output_device='{out_dev}'")

    # Anker S330 controls (confirmed via amixer -c <card> contents)
    playback_volume_numid = 3
    playback_switch_numid = 2
    max_vol = 127
    step = max(1, int(round(max_vol * 0.05)))  # ~5%

    path = _find_input_device_path()
    dev = InputDevice(path)
    print(f"Listening for volume keys on {path} (card {card_index})", flush=True)

    # Avoid key-repeat spam: only act on key-down events
    for event in dev.read_loop():
        if event.type != ecodes.EV_KEY:
            continue

        if event.value != 1:
            continue

        if event.code == ecodes.KEY_VOLUMEUP:
            cur = _amixer_get_numid(card_index, playback_volume_numid)
            nxt = min(max_vol, cur + step)
            _amixer_set_numid(card_index, playback_volume_numid, nxt)
            print(f"VOL+ {cur}->{nxt}", flush=True)

        elif event.code == ecodes.KEY_VOLUMEDOWN:
            cur = _amixer_get_numid(card_index, playback_volume_numid)
            nxt = max(0, cur - step)
            _amixer_set_numid(card_index, playback_volume_numid, nxt)
            print(f"VOL- {cur}->{nxt}", flush=True)

        elif event.code == ecodes.KEY_MUTE:
            _amixer_toggle_playback_switch(card_index, playback_switch_numid)
            print("MUTE toggle", flush=True)

        time.sleep(0.01)


if __name__ == "__main__":
    main()
