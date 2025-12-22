"""Audio device detection utilities."""
import subprocess
import re
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


def check_hardware_mute(device_id: str) -> Tuple[bool, bool]:
    """Check if the microphone has a hardware mute button and its current state.
    
    Args:
        device_id: ALSA device ID like 'hw:2,0'
        
    Returns:
        Tuple of (has_mute_button, is_muted)
        - has_mute_button: True if the device has a hardware mute control
        - is_muted: True if currently muted (only valid if has_mute_button is True)
    """
    card_num = get_card_number_from_device(device_id)
    if card_num is None:
        return False, False
    
    try:
        # Query amixer for capture controls on this card
        result = subprocess.run(
            ['amixer', '-c', card_num, 'contents'],
            capture_output=True, text=True, timeout=5
        )
        
        if result.returncode != 0:
            return False, False
        
        # Look for capture switch controls
        # Common patterns:
        # - "Capture Switch" - generic capture mute
        # - "Mic Capture Switch" - microphone specific
        # - "Input Source Capture Switch" - input mute
        output = result.stdout
        
        # Parse amixer contents output
        # Format is like:
        # numid=X,iface=MIXER,name='Capture Switch'
        #   ; type=BOOLEAN,access=rw------,values=1
        #   : values=on
        
        current_control = None
        has_capture_switch = False
        is_muted = False
        
        for line in output.split('\n'):
            if 'name=' in line and 'Capture Switch' in line:
                current_control = 'capture_switch'
                has_capture_switch = True
            elif current_control == 'capture_switch' and ': values=' in line:
                # Check if value is 'off' (muted) or 'on' (unmuted)
                values_part = line.split(': values=')[1].strip()
                # Could be "off" or "on" or "off,off" for stereo
                is_muted = 'off' in values_part.lower()
                break
        
        if has_capture_switch:
            return True, is_muted
        
        # Alternative: Check for "Auto Mute Mode" or device-specific mute controls
        # Some USB devices use different control names
        for line in output.split('\n'):
            # Jabra devices often have 'Mic Playback Switch' or similar
            if 'name=' in line and ('Mute' in line or 'Mic' in line) and 'Switch' in line:
                current_control = 'alt_mute'
                has_capture_switch = True
            elif current_control == 'alt_mute' and ': values=' in line:
                values_part = line.split(': values=')[1].strip()
                is_muted = 'off' in values_part.lower()
                break
        
        return has_capture_switch, is_muted
        
    except subprocess.TimeoutExpired:
        print("Timeout checking hardware mute status")
        return False, False
    except Exception as e:
        print(f"Error checking hardware mute: {e}")
        return False, False


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
