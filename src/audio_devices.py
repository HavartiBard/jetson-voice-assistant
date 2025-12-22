"""Audio device detection utilities."""
import subprocess
import re
import os
import json
import time
import struct
from typing import List, Dict, Optional, Tuple


def get_audio_input_devices() -> List[Dict[str, str]]:
    """Get list of available audio input (capture) devices."""
    devices = []
    try:
        result = subprocess.run(['arecord', '-l'], capture_output=True, text=True)
        for line in result.stdout.split('\n'):
            if 'card' in line and ':' in line:
                # Parse "card 2: USB [Jabra SPEAK 510 USB], device 0: USB Audio [USB Audio]"
                parts = line.split(':')
                if len(parts) >= 2:
                    card_part = parts[0].strip()
                    card_num = card_part.replace('card', '').strip()
                    
                    # Get device name
                    name_part = parts[1].strip()
                    if '[' in name_part:
                        name = name_part.split('[')[1].split(']')[0]
                    else:
                        name = name_part.split(',')[0].strip()
                    
                    device_id = f"hw:{card_num},0"
                    devices.append({
                        'id': device_id,
                        'name': f"{name} ({device_id})",
                        'card': card_num
                    })
    except Exception as e:
        print(f"Error detecting input devices: {e}")
    
    # Add default option
    if not devices:
        devices.append({'id': 'default', 'name': 'Default', 'card': '0'})
    
    return devices


def get_audio_output_devices() -> List[Dict[str, str]]:
    """Get list of available audio output (playback) devices."""
    devices = []
    try:
        result = subprocess.run(['aplay', '-l'], capture_output=True, text=True)
        for line in result.stdout.split('\n'):
            if 'card' in line and ':' in line:
                # Parse "card 2: USB [Jabra SPEAK 510 USB], device 0: USB Audio [USB Audio]"
                parts = line.split(':')
                if len(parts) >= 2:
                    card_part = parts[0].strip()
                    card_num = card_part.replace('card', '').strip()
                    
                    # Get device name
                    name_part = parts[1].strip()
                    if '[' in name_part:
                        name = name_part.split('[')[1].split(']')[0]
                    else:
                        name = name_part.split(',')[0].strip()
                    
                    # Use plughw for playback (handles format conversion)
                    device_id = f"plughw:{card_num},0"
                    devices.append({
                        'id': device_id,
                        'name': f"{name} ({device_id})",
                        'card': card_num
                    })
    except Exception as e:
        print(f"Error detecting output devices: {e}")
    
    # Add default option
    if not devices:
        devices.append({'id': 'default', 'name': 'Default', 'card': '0'})
    
    return devices


def get_card_number_from_device(device_id: str) -> Optional[str]:
    """Extract card number from device ID like 'hw:2,0' -> '2'."""
    if not device_id or device_id == 'default':
        return None
    match = re.match(r'(?:plug)?hw:(\d+)', device_id)
    return match.group(1) if match else None


def _find_input_mute_led_path(device_name_hint: Optional[str] = None) -> Optional[str]:
    """Find a sysfs LED path for a device mute indicator.

    This supports devices like the Jabra SPEAK 510, which expose mute state
    via an input LED (e.g., /sys/class/leds/input11::mute/brightness).

    Args:
        device_name_hint: Optional case-insensitive substring to match against the
            associated input device name (from /sys/class/input/inputX/device/name).

    Returns:
        Path to a LED directory (e.g., /sys/class/leds/input11::mute) or None.
    """
    leds_dir = '/sys/class/leds'
    if not os.path.isdir(leds_dir):
        return None

    candidates: List[str] = []
    try:
        for entry in os.listdir(leds_dir):
            if not entry.endswith('::mute'):
                continue
            led_path = os.path.join(leds_dir, entry)
            brightness_path = os.path.join(led_path, 'brightness')
            if os.path.isfile(brightness_path):
                candidates.append(led_path)
    except Exception:
        return None

    if not candidates:
        return None

    if not device_name_hint:
        return candidates[0]

    hint = device_name_hint.strip().lower()
    for led_path in candidates:
        # Try to map led -> input device name via sysfs
        # /sys/class/leds/input11::mute/device typically links to /sys/class/input/input11
        try:
            dev_link = os.path.join(led_path, 'device')
            real = os.path.realpath(dev_link)
            # real path might end with .../input/input11
            if '/sys/class/input/' in real:
                input_dir = real
            else:
                input_dir = None

            if input_dir:
                name_path = os.path.join(input_dir, 'device', 'name')
                if os.path.isfile(name_path):
                    with open(name_path, 'r') as f:
                        name = (f.read() or '').strip().lower()
                    if hint in name:
                        return led_path
        except Exception:
            continue

    return candidates[0]


def read_hardware_mute_led(device_name_hint: Optional[str] = None) -> Tuple[bool, bool]:
    """Read hardware mute state from an input LED (if available).

    Args:
        device_name_hint: Optional case-insensitive substring to match against
            input device name (e.g., "jabra").

    Returns:
        Tuple of (has_led_mute, is_muted)
    """
    led_path = _find_input_mute_led_path(device_name_hint=device_name_hint)
    if not led_path:
        return False, False

    try:
        with open(os.path.join(led_path, 'brightness'), 'r') as f:
            brightness = int((f.read() or '0').strip())
        return True, brightness > 0
    except Exception:
        return False, False


# Mute state file path - written by assistant, read by portal
MUTE_STATE_FILE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    'config', '.mute_state'
)


def get_audio_amplitude(audio_bytes: bytes) -> int:
    """Get the maximum amplitude from audio data.
    
    Args:
        audio_bytes: Raw PCM audio data (S16_LE format)
        
    Returns:
        Maximum amplitude value (0-32767)
    """
    if len(audio_bytes) < 100:
        return 0
    
    num_samples = len(audio_bytes) // 2
    max_amplitude = 0
    
    # Check sampled values to speed up detection
    for i in range(0, min(num_samples, 1000), 10):
        try:
            sample = struct.unpack('<h', audio_bytes[i*2:(i*2)+2])[0]
            max_amplitude = max(max_amplitude, abs(sample))
        except struct.error:
            break
    
    return max_amplitude


def check_audio_is_silent(audio_bytes: bytes, threshold: int = 200) -> bool:
    """Check if audio data is essentially silent (hardware muted).
    
    Args:
        audio_bytes: Raw PCM audio data (S16_LE format)
        threshold: Max amplitude below which audio is considered silent
        
    Returns:
        True if audio is silent/muted
    """
    return get_audio_amplitude(audio_bytes) < threshold


def check_audio_has_speech(audio_bytes: bytes, threshold: int = 300) -> bool:
    """Check if audio likely contains speech worth transcribing.
    
    Uses a higher threshold than mute detection to filter out
    background noise and save CPU by skipping transcription.
    
    Args:
        audio_bytes: Raw PCM audio data (S16_LE format)
        threshold: Min amplitude to consider as potential speech
        
    Returns:
        True if audio likely contains speech
    """
    return get_audio_amplitude(audio_bytes) >= threshold


def write_mute_state(is_muted: bool):
    """Write mute state to file for portal to read."""
    try:
        os.makedirs(os.path.dirname(MUTE_STATE_FILE), exist_ok=True)
        with open(MUTE_STATE_FILE, 'w') as f:
            json.dump({'is_muted': is_muted, 'timestamp': time.time()}, f)
    except Exception as e:
        print(f"Error writing mute state: {e}")


def read_mute_state() -> Tuple[bool, bool]:
    """Read mute state from file written by assistant.
    
    Returns:
        Tuple of (has_state, is_muted)
    """
    try:
        if os.path.exists(MUTE_STATE_FILE):
            with open(MUTE_STATE_FILE, 'r') as f:
                data = json.load(f)
                # Check if state is recent (within last 10 seconds)
                if time.time() - data.get('timestamp', 0) < 10:
                    return True, data.get('is_muted', False)
        return False, False
    except Exception:
        return False, False


def check_hardware_mute(device_id: str) -> Tuple[bool, bool]:
    """Check mute status by reading state file written by assistant.
    
    The assistant detects mute by monitoring audio levels during recording
    and writes the state to a file. This avoids conflicts with the assistant's
    audio recording.
    
    Args:
        device_id: ALSA device ID (not used, kept for API compatibility)
        
    Returns:
        Tuple of (has_mute_detection, is_muted)
    """
    return read_mute_state()


def get_mute_status(device_id: str) -> Dict:
    """Get comprehensive mute status for a device.
    
    Returns:
        Dict with keys:
        - has_hardware_mute: bool - device has hardware mute button
        - is_muted: bool - current mute state
        - device_id: str - the device checked
    """
    has_mute, is_muted = check_hardware_mute(device_id)
    return {
        'has_hardware_mute': has_mute,
        'is_muted': is_muted,
        'device_id': device_id
    }
