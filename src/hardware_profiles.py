import os
import re
from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class HardwareProfile:
    name: str
    prefer_capture_channels: Optional[int] = None
    mute_detection: str = "none"  # "none" | "amplitude_zero"


def _parse_card_index(device_id: str) -> Optional[int]:
    m = re.match(r"^(?:plug)?hw:(\d+)(?:,\d+)?$", (device_id or "").strip())
    if not m:
        return None
    try:
        return int(m.group(1))
    except Exception:
        return None


def _read_text(path: str) -> str:
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            return (f.read() or "").strip()
    except Exception:
        return ""


def get_device_identity(device_id: str) -> dict:
    """Best-effort device identity for an ALSA hw:X,Y device."""
    idx = _parse_card_index(device_id)
    ident = {
        "device_id": device_id,
        "card_index": idx,
        "alsa_card_name": "",
        "usb_manufacturer": "",
        "usb_product": "",
        "usb_vendor_id": "",
        "usb_product_id": "",
    }

    if idx is None:
        return ident

    # ALSA card name from /proc/asound/cards
    try:
        with open("/proc/asound/cards", "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
        # Each card starts with: " 4 [S330           ]: ..."
        for line in content.splitlines():
            m = re.match(rf"^\s*{idx}\s*\[(.*?)\]", line)
            if m:
                ident["alsa_card_name"] = m.group(1).strip()
                break
    except Exception:
        pass

    sys_base = f"/sys/class/sound/card{idx}/device"
    ident["usb_manufacturer"] = _read_text(os.path.join(sys_base, "manufacturer"))
    ident["usb_product"] = _read_text(os.path.join(sys_base, "product"))
    ident["usb_vendor_id"] = _read_text(os.path.join(sys_base, "idVendor"))
    ident["usb_product_id"] = _read_text(os.path.join(sys_base, "idProduct"))

    return ident


def get_hardware_profile(device_id: str) -> HardwareProfile:
    """Return a profile describing known quirks for the device."""
    ident = get_device_identity(device_id)
    blob = " ".join(
        [
            ident.get("alsa_card_name", ""),
            ident.get("usb_manufacturer", ""),
            ident.get("usb_product", ""),
        ]
    ).lower()

    if "jabra" in blob and "speak" in blob:
        # Jabra SPEAK mutes by outputting literal zeros on capture.
        return HardwareProfile(
            name="jabra_speak",
            prefer_capture_channels=1,
            mute_detection="amplitude_zero",
        )

    if "anker" in blob and ("powerconf" in blob or "s330" in blob):
        # Anker PowerConf often exposes capture as stereo; we'll downmix.
        return HardwareProfile(
            name="anker_powerconf_s330",
            prefer_capture_channels=2,
            mute_detection="none",
        )

    return HardwareProfile(name="default")
