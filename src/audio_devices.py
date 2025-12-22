"""Audio device detection utilities."""
import subprocess
from typing import List, Dict


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
