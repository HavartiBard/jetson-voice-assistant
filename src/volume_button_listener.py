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


def _amixer_scontrols(card_index: int) -> list[str]:
    r = _run(["amixer", "-c", str(card_index), "scontrols"])
    if r.returncode != 0:
        return []

    names: list[str] = []
    for line in (r.stdout or "").splitlines():
        line = line.strip()
        if not line.startswith("Simple mixer control"):
            continue
        # Simple mixer control 'Master',0
        start = line.find("'")
        end = line.rfind("'")
        if start != -1 and end != -1 and end > start:
            names.append(line[start + 1 : end])
    return names


def _choose_control(card_index: int) -> str:
    prefer = ["Anker PowerConf S330", "Master", "PCM", "Speaker"]
    controls = _amixer_scontrols(card_index)
    if not controls:
        raise RuntimeError("No mixer controls found")

    lower_map = {c.lower(): c for c in controls}
    for p in prefer:
        if p.lower() in lower_map:
            return lower_map[p.lower()]

    # Fallback: choose first control (best-effort)
    return controls[0]


def _amixer_sget(card_index: int, control: str) -> subprocess.CompletedProcess:
    return _run(["amixer", "-c", str(card_index), "sget", control])


def _parse_percent(stdout: str) -> int | None:
    m = re.search(r"\[(\d+)%\]", stdout)
    if not m:
        return None
    try:
        return int(m.group(1))
    except Exception:
        return None


def _parse_switch_on(stdout: str) -> bool | None:
    m = re.search(r"\[(on|off)\]", stdout, flags=re.IGNORECASE)
    if not m:
        return None
    return m.group(1).lower() == "on"


def _amixer_get_volume_percent(card_index: int, control: str) -> int:
    r = _amixer_sget(card_index, control)
    if r.returncode != 0:
        raise RuntimeError(r.stderr.strip() or r.stdout.strip())
    pct = _parse_percent(r.stdout)
    if pct is None:
        raise RuntimeError("Unable to parse current volume percent")
    return pct


def _amixer_set_volume_percent(card_index: int, control: str, percent: int) -> None:
    percent = max(0, min(100, int(percent)))
    r = _run(["amixer", "-c", str(card_index), "sset", control, f"{percent}%"])
    if r.returncode != 0:
        raise RuntimeError(r.stderr.strip() or r.stdout.strip())


def _amixer_toggle_mute(card_index: int, control: str) -> None:
    # Many controls support toggle directly.
    r = _run(["amixer", "-c", str(card_index), "sset", control, "toggle"])
    if r.returncode == 0:
        return

    # Fallback: read on/off then mute/unmute
    g = _amixer_sget(card_index, control)
    if g.returncode != 0:
        raise RuntimeError(g.stderr.strip() or g.stdout.strip())
    cur = _parse_switch_on(g.stdout)
    if cur is None:
        raise RuntimeError(r.stderr.strip() or r.stdout.strip() or "Mute toggle failed")

    r2 = _run(["amixer", "-c", str(card_index), "sset", control, "mute" if cur else "unmute"])
    if r2.returncode != 0:
        raise RuntimeError(r2.stderr.strip() or r2.stdout.strip())


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

    control = _choose_control(card_index)
    step = 5  # percent

    path = _find_input_device_path()
    dev = InputDevice(path)
    print(f"Listening for volume keys on {path} (card {card_index}, control '{control}')", flush=True)

    # Avoid key-repeat spam: only act on key-down events
    for event in dev.read_loop():
        if event.type != ecodes.EV_KEY:
            continue

        if event.value != 1:
            continue

        if event.code == ecodes.KEY_VOLUMEUP:
            cur = _amixer_get_volume_percent(card_index, control)
            nxt = min(100, cur + step)
            _amixer_set_volume_percent(card_index, control, nxt)
            print(f"VOL+ {cur}%->{nxt}%", flush=True)

        elif event.code == ecodes.KEY_VOLUMEDOWN:
            cur = _amixer_get_volume_percent(card_index, control)
            nxt = max(0, cur - step)
            _amixer_set_volume_percent(card_index, control, nxt)
            print(f"VOL- {cur}%->{nxt}%", flush=True)

        elif event.code == ecodes.KEY_MUTE:
            _amixer_toggle_mute(card_index, control)
            print("MUTE toggle", flush=True)

        time.sleep(0.01)


if __name__ == "__main__":
    main()
