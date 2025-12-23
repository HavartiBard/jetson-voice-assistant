import pyttsx3
import datetime
import webbrowser
import os
import random
import pyjokes
from dotenv import load_dotenv
from openai import OpenAI
import json
import tempfile
import subprocess
import re

import numpy as np
import soundfile as sf
from faster_whisper import WhisperModel

from settings_store import load_settings
from history_store import record_query
from ollama_client import OllamaClient
from hardware_profiles import get_hardware_profile
from audio_devices import (
    check_audio_has_speech,
    get_audio_amplitude,
    write_mute_state,
)
import time
import threading
from collections import deque

try:
    import openwakeword
    from openwakeword.model import Model as OwwModel
except Exception:
    openwakeword = None
    OwwModel = None


class PersistentAudioStream:
    """Keeps arecord running continuously to prevent Jabra mute reset on device open."""
    
    def __init__(self, device, sample_rate=16000, channels=1):
        self.device = device
        self.sample_rate = sample_rate
        self.channels = channels
        self.bytes_per_sample = 2  # S16_LE = 2 bytes
        self.bytes_per_second = sample_rate * channels * self.bytes_per_sample
        
        self._process = None
        self._buffer = deque()
        self._buffer_lock = threading.Lock()
        self._reader_thread = None
        self._running = False
        
        self._start()
    
    def _start(self):
        """Start the persistent arecord process and reader thread."""
        self._running = True
        
        cmd = [
            'arecord',
            '-D', self.device,
            '-f', 'S16_LE',
            '-r', str(self.sample_rate),
            '-c', str(self.channels),
            '-t', 'raw',
            '-q',
        ]
        self._process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            bufsize=self.bytes_per_second  # 1 second buffer
        )
        
        # Start background thread to continuously read from arecord
        self._reader_thread = threading.Thread(target=self._reader_loop, daemon=True)
        self._reader_thread.start()
        
        print(f"Started persistent audio stream on {self.device}", flush=True)
    
    def _reader_loop(self):
        """Background thread that continuously reads from arecord into buffer."""
        chunk_size = self.bytes_per_second // 10  # Read 100ms chunks
        
        while self._running and self._process and self._process.poll() is None:
            try:
                data = self._process.stdout.read(chunk_size)
                if data:
                    with self._buffer_lock:
                        self._buffer.append(data)
                        # Keep only last 10 seconds in buffer
                        max_chunks = 100  # 10 seconds at 100ms chunks
                        while len(self._buffer) > max_chunks:
                            self._buffer.popleft()
            except Exception as e:
                print(f"Audio reader error: {e}", flush=True)
                break
        
        # Process died, try to restart
        if self._running:
            print("Audio stream died, restarting...", flush=True)
            time.sleep(0.5)
            self._start()
    
    def read_seconds(self, duration):
        """Read specified duration of audio from buffer.
        
        Args:
            duration: Seconds of audio to read
            
        Returns:
            Raw PCM bytes
        """
        bytes_needed = int(duration * self.bytes_per_second)
        
        # Wait for enough data (with timeout)
        timeout = duration + 2  # Allow extra time
        start = time.time()
        
        while time.time() - start < timeout:
            with self._buffer_lock:
                total_buffered = sum(len(chunk) for chunk in self._buffer)
                if total_buffered >= bytes_needed:
                    # Collect bytes from buffer
                    result = b''
                    while len(result) < bytes_needed and self._buffer:
                        chunk = self._buffer.popleft()
                        result += chunk
                    
                    # If we got too much, put excess back
                    if len(result) > bytes_needed:
                        excess = result[bytes_needed:]
                        result = result[:bytes_needed]
                        self._buffer.appendleft(excess)
                    
                    return result
            
            time.sleep(0.05)  # Wait 50ms before checking again
        
        # Timeout - return what we have, padded with silence
        with self._buffer_lock:
            result = b''.join(self._buffer)
            self._buffer.clear()
        
        if len(result) < bytes_needed:
            result += b'\x00' * (bytes_needed - len(result))
        
        return result[:bytes_needed]

    def read_bytes(self, bytes_needed: int, timeout_seconds: float = 2.0) -> bytes:
        """Read an exact number of bytes from the buffer.

        Args:
            bytes_needed: Number of raw PCM bytes to return
            timeout_seconds: How long to wait for enough buffered data

        Returns:
            Raw PCM bytes of length bytes_needed (padded with zeros on timeout)
        """
        start = time.time()

        while time.time() - start < timeout_seconds:
            with self._buffer_lock:
                total_buffered = sum(len(chunk) for chunk in self._buffer)
                if total_buffered >= bytes_needed:
                    result = b''
                    while len(result) < bytes_needed and self._buffer:
                        chunk = self._buffer.popleft()
                        result += chunk

                    if len(result) > bytes_needed:
                        excess = result[bytes_needed:]
                        result = result[:bytes_needed]
                        self._buffer.appendleft(excess)

                    return result

            time.sleep(0.01)

        with self._buffer_lock:
            result = b''.join(self._buffer)
            self._buffer.clear()

        if len(result) < bytes_needed:
            result += b'\x00' * (bytes_needed - len(result))
        return result[:bytes_needed]
    
    def stop(self):
        """Stop the audio stream."""
        self._running = False
        if self._process:
            self._process.terminate()
            try:
                self._process.wait(timeout=2)
            except:
                self._process.kill()


class VoiceAssistant:
    def __init__(self):
        # Initialize text-to-speech engine
        self.engine = pyttsx3.init()
        
        # Set properties for voice
        voices = self.engine.getProperty('voices')
        self.engine.setProperty('voice', voices[0].id)  # 0 for male, 1 for female
        self.engine.setProperty('rate', 150)  # Speed of speech
        
        # Load environment variables
        load_dotenv()
        
        # Reload signal file path
        self._reload_signal_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            'config', '.reload_signal'
        )
        
        # Load settings
        self._load_settings()

        self._whisper_model = None
        self._init_whisper_model()
        
        print(f"Using audio device: {self.audio_device}", flush=True)

        # Apply device-specific quirks/capabilities
        self._hardware_profile = get_hardware_profile(self.audio_device)
        print(f"Audio hardware profile: {self._hardware_profile.name}", flush=True)

        self._capture_device = self._hardware_profile.preferred_capture_device or self.audio_device
        if self._capture_device != self.audio_device:
            print(f"Audio capture device override: {self.audio_device} -> {self._capture_device}", flush=True)

        # Capture at the same rate Whisper expects to avoid resampling artifacts.
        # Playback is handled by temporarily stopping capture during TTS.
        self._capture_sample_rate = self.audio_sample_rate

        # Some USB speakerphones expose capture only as stereo (channels=2).
        # Probe the device to pick a supported channel count.
        preferred_channels = self._hardware_profile.prefer_capture_channels or self.audio_channels
        self._audio_stream_channels = self._probe_capture_channels(
            self._capture_device,
            self._capture_sample_rate,
            preferred=preferred_channels,
        )
        
        # Initialize persistent audio stream (keeps device open to prevent Jabra mute reset)
        self._audio_stream = PersistentAudioStream(
            self._capture_device,
            sample_rate=self._capture_sample_rate,
            channels=self._audio_stream_channels
        )
        self._audio_stream_device = self._capture_device
        
        # Hardware mute state tracking with hysteresis
        self._last_mute_state = False
        self._mute_announced = False
        self._mute_counter = 0  # Counter for hysteresis
        self._last_noise_log_ts = 0.0
        
        # Initialize openWakeWord for fast wake word detection
        self._oww_model = None
        self._oww_frame_size = 1280  # 80ms at 16kHz (openWakeWord default)
        self._init_openwakeword()
        
        # Greeting message
        self.speak("Hello! I'm your Jetson Voice Assistant. How can I help you today?")

    def _probe_capture_channels(self, device: str, sample_rate: int, preferred: int = 1) -> int:
        """Pick a capture channel count supported by the ALSA device.

        Many USB conference speakerphones reject mono on the raw hw interface.
        We test a short arecord to choose 1 or 2 channels.
        """
        candidates = []
        if preferred in (1, 2):
            candidates.append(preferred)
        for c in (1, 2):
            if c not in candidates:
                candidates.append(c)

        for channels in candidates:
            try:
                result = subprocess.run(
                    [
                        'arecord',
                        '-D', device,
                        '-f', 'S16_LE',
                        '-c', str(channels),
                        '-r', str(sample_rate),
                        '-d', '1',
                        '-t', 'raw',
                        '-q',
                    ],
                    capture_output=True,
                    text=True,
                    timeout=3,
                )

                stderr = (result.stderr or '')
                if result.returncode == 0 and 'Channels count non available' not in stderr:
                    if channels != preferred:
                        print(f"Audio capture channel fallback: {preferred} -> {channels}", flush=True)
                    return channels
            except Exception:
                continue

        print(f"Audio capture channel probe failed; defaulting to {preferred}", flush=True)
        return preferred

    def _init_openwakeword(self):
        """Initialize openWakeWord for fast wake word detection."""
        if OwwModel is None:
            print("openWakeWord not available; using Whisper-based wake word detection.", flush=True)
            return
        
        try:
            # Download models if not present
            openwakeword.utils.download_models()
            
            # Map wake word to available openWakeWord models
            # Available: alexa, hey_jarvis, hey_mycroft, hey_rhasspy, etc.
            kw = (self.wake_word or 'hey jarvis').strip().lower()
            model_map = {
                'alexa': 'alexa',
                'jarvis': 'hey_jarvis',
                'hey jarvis': 'hey_jarvis',
                'mycroft': 'hey_mycroft',
                'hey mycroft': 'hey_mycroft',
                'computer': 'hey_mycroft',  # Fallback
            }
            model_name = model_map.get(kw, 'hey_jarvis')
            
            self._oww_model = OwwModel(
                wakeword_models=[model_name],
                inference_framework='onnx',
            )
            print(f"openWakeWord enabled (model='{model_name}')", flush=True)
        except Exception as e:
            self._oww_model = None
            print(f"openWakeWord init error; using Whisper fallback: {e}", flush=True)

    def _stop_audio_stream_for_playback(self):
        """Stop capture stream to avoid blocking playback on some USB devices."""
        try:
            if getattr(self, '_audio_stream', None):
                self._audio_stream.stop()
                self._audio_stream = None
        except Exception as e:
            print(f"Error stopping audio stream: {e}", flush=True)

    def _restart_audio_stream_after_playback(self):
        """Restart capture stream after playback."""
        try:
            if getattr(self, '_audio_stream', None):
                return
            self._audio_stream = PersistentAudioStream(
                self._audio_stream_device,
                sample_rate=self._capture_sample_rate,
                channels=self._audio_stream_channels,
            )
        except Exception as e:
            print(f"Error restarting audio stream: {e}", flush=True)
    
    def _load_settings(self):
        """Load or reload settings from config file. Settings.json takes priority over .env."""
        settings = load_settings()
        
        # Settings.json takes priority over .env for portal-configurable settings
        api_key = settings.get('openai_api_key') or os.getenv('OPENAI_API_KEY')
        self.openai_client = OpenAI(api_key=api_key) if api_key else None
        
        # Wake word from settings (portal) takes priority
        self.wake_word = (settings.get('wake_word') or os.getenv('WAKE_WORD') or 'jetson').strip().lower()

        self.whisper_mode = (settings.get('whisper_mode') or os.getenv('WHISPER_MODE') or 'local').strip().lower()
        self.whisper_model_size = (settings.get('whisper_model_size') or os.getenv('WHISPER_MODEL_SIZE') or 'small').strip()
        self.whisper_language = (settings.get('whisper_language') or os.getenv('WHISPER_LANGUAGE') or 'en').strip()

        self.audio_sample_rate = int(settings.get('audio_sample_rate') or os.getenv('AUDIO_SAMPLE_RATE') or 16000)
        self.audio_channels = int(settings.get('audio_channels') or os.getenv('AUDIO_CHANNELS') or 1)
        self.audio_record_seconds = float(settings.get('audio_record_seconds') or os.getenv('AUDIO_RECORD_SECONDS') or 4)
        
        # Audio devices (input/output)
        self.audio_input_device = settings.get('audio_input_device') or self._find_usb_alsa_device()
        self.audio_output_device = settings.get('audio_output_device') or self.audio_input_device.replace('hw:', 'plughw:') if self.audio_input_device else 'default'
        
        # For backward compatibility
        self.audio_device = self.audio_input_device
        
        # LLM settings
        self.llm_provider = settings.get('llm_provider', 'openai')
        self.llm_model = settings.get('llm_model', 'gpt-4o-mini')
        self.ollama_host = settings.get('ollama_host', 'http://localhost:11434')
        self.ollama_client = OllamaClient(self.ollama_host) if self.llm_provider == 'ollama' else None
        
        # TTS settings
        self.tts_provider = settings.get('tts_provider', 'gtts')
        self.tts_language = settings.get('tts_language', 'en')
        self.tts_speed = int(settings.get('tts_speed', 150))
        
        print(f"Settings loaded: wake_word='{self.wake_word}', llm={self.llm_provider}/{self.llm_model}, tts={self.tts_provider}", flush=True)
    
    def check_reload(self):
        """Check if settings reload was requested and reload if needed."""
        if os.path.exists(self._reload_signal_path):
            try:
                os.unlink(self._reload_signal_path)
                print("Reload signal detected, reloading settings...", flush=True)
                old_wake_word = self.wake_word
                old_whisper_mode = getattr(self, 'whisper_mode', None)
                old_whisper_model_size = getattr(self, 'whisper_model_size', None)
                self._load_settings()

                if old_whisper_mode != self.whisper_mode or old_whisper_model_size != self.whisper_model_size:
                    print(
                        f"Reloading Whisper model: mode={self.whisper_mode}, size={self.whisper_model_size}",
                        flush=True,
                    )
                    self._init_whisper_model()
                if old_wake_word != self.wake_word:
                    self.speak(f"Wake word changed to {self.wake_word}")
            except Exception as e:
                print(f"Error reloading settings: {e}", flush=True)

    def _init_whisper_model(self):
        if self.whisper_mode == 'local':
            print(f"Initializing Whisper model (local): size={self.whisper_model_size}", flush=True)
            self._whisper_model = WhisperModel(
                self.whisper_model_size,
                device='cpu',
                compute_type='int8',
            )
        else:
            print("Initializing Whisper model (api): local model disabled", flush=True)
            self._whisper_model = None
    
    def check_and_update_mute_status(self, audio_data: bytes) -> bool:
        """Check if microphone is hardware muted and update state.

        For devices that support it (e.g., Jabra SPEAK), hardware mute produces
        literal zero audio samples. We only apply that rule when the active
        hardware profile requests it.

        Uses a small hysteresis: 2 consecutive zero-amplitude windows to mute,
        and 1 non-zero window to unmute.

        Args:
            audio_data: Raw PCM audio bytes from recording
            
        Returns:
            bool: True if microphone is currently muted
        """
        # Default: do not infer "hardware mute" from audio for unknown devices.
        if getattr(self, '_hardware_profile', None) is None or getattr(self._hardware_profile, 'mute_detection', 'none') != 'amplitude_zero':
            write_mute_state(False)
            self._last_mute_state = False
            self._mute_counter = 0
            return False

        # Detect hardware mute by checking if max sample amplitude is exactly zero.
        amp = get_audio_amplitude(audio_data)
        # Use a small hysteresis:
        # - Mute: 2 consecutive zero-amplitude windows
        # - Unmute: 1 non-zero window
        if amp == 0:
            if not self._last_mute_state:
                self._mute_counter += 1
                if self._mute_counter >= 2:
                    self._last_mute_state = True
                    self._mute_counter = 0
                    print("Hardware mute detected - amplitude is 0", flush=True)
            else:
                # already muted
                self._mute_counter = 0
        else:
            # Any non-zero audio immediately clears mute
            if self._last_mute_state:
                self._last_mute_state = False
                print("Hardware unmute detected - amplitude > 0", flush=True)
            self._mute_counter = 0
        
        # Write state for portal to read
        write_mute_state(self._last_mute_state)
        
        return self._last_mute_state
    
    def _find_usb_alsa_device(self):
        """Auto-detect USB audio ALSA device (returns hw:X,0 string)"""
        try:
            result = subprocess.run(['arecord', '-l'], capture_output=True, text=True)
            for line in result.stdout.split('\n'):
                if 'USB' in line and 'card' in line:
                    # Parse "card 2: USB [Jabra...]" -> "hw:2,0"
                    parts = line.split(':')
                    if parts:
                        card_part = parts[0].strip()
                        card_num = card_part.replace('card', '').strip()
                        device = f"hw:{card_num},0"
                        print(f"Auto-detected USB audio device: {line.strip()} -> {device}", flush=True)
                        return device
        except Exception as e:
            print(f"Error detecting audio device: {e}", flush=True)
        return "default"
    
    def speak(self, text):
        """Convert text to speech using configured TTS provider."""
        print(f"Assistant: {text}", flush=True)
        play_device = self.audio_output_device if hasattr(self, 'audio_output_device') else 'default'
        tts_provider = getattr(self, 'tts_provider', 'gtts')
        tts_lang = getattr(self, 'tts_language', 'en')
        tts_speed = getattr(self, 'tts_speed', 150)

        # Some USB devices (including Jabra) can refuse playback if capture is held open.
        # Temporarily release capture during playback.
        needs_duplex_release = play_device != 'default'
        if needs_duplex_release:
            self._stop_audio_stream_for_playback()

        try:
            # pyttsx3 does not reliably allow selecting an ALSA output device.
            # If a specific ALSA device is configured, use the espeak->aplay path.
            if tts_provider == 'pyttsx3' and play_device != 'default':
                self._speak_espeak(text, play_device, tts_lang, tts_speed)
                return
        
            # Try the configured provider first
            if tts_provider == 'gtts':
                if self._speak_gtts(text, play_device, tts_lang):
                    return
                print("gTTS failed, falling back to espeak", flush=True)
                self._speak_espeak(text, play_device, tts_lang, tts_speed)
            elif tts_provider == 'espeak':
                self._speak_espeak(text, play_device, tts_lang, tts_speed)
            elif tts_provider == 'pyttsx3':
                if not self._speak_pyttsx3(text, tts_speed):
                    print("pyttsx3 failed, falling back to espeak", flush=True)
                    self._speak_espeak(text, play_device, tts_lang, tts_speed)
            else:
                # Unknown provider, default to espeak
                self._speak_espeak(text, play_device, tts_lang, tts_speed)
        finally:
            if needs_duplex_release:
                self._restart_audio_stream_after_playback()
    
    def _speak_gtts(self, text, play_device, lang='en'):
        """Speak using Google TTS (requires internet)."""
        try:
            from gtts import gTTS
            import io
            
            mp3_buffer = io.BytesIO()
            tts = gTTS(text=text, lang=lang, slow=False)
            tts.write_to_fp(mp3_buffer)
            mp3_buffer.seek(0)
            
            ffmpeg = subprocess.Popen(
                ['ffmpeg', '-i', 'pipe:0', '-f', 'wav', '-acodec', 'pcm_s16le', '-ar', '48000', 'pipe:1'],
                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE
            )
            aplay = subprocess.Popen(['aplay', '-D', play_device, '-q'], stdin=ffmpeg.stdout, stderr=subprocess.PIPE)
            ffmpeg.stdout.close()
            ffmpeg.stdin.write(mp3_buffer.read())
            ffmpeg.stdin.close()
            aplay.communicate()
            return True
        except Exception as e:
            print(f"gTTS error: {e}", flush=True)
            return False
    
    def _speak_espeak(self, text, play_device, lang='en', speed=150):
        """Speak using espeak (offline, robotic voice)."""
        try:
            espeak_cmd = ['espeak', '-s', str(speed), '-v', lang, '--stdout', text]
            aplay_cmd = ['aplay', '-D', play_device, '-q']
            espeak_proc = subprocess.Popen(espeak_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            aplay_proc = subprocess.Popen(aplay_cmd, stdin=espeak_proc.stdout, stderr=subprocess.PIPE)
            espeak_proc.stdout.close()
            aplay_proc.communicate()
            return True
        except Exception as e:
            print(f"espeak error: {e}", flush=True)
            return False
    
    def _speak_pyttsx3(self, text, speed=150):
        """Speak using pyttsx3 (offline, system voices)."""
        try:
            self.engine.setProperty('rate', speed)
            self.engine.say(text)
            self.engine.runAndWait()
            return True
        except Exception as e:
            print(f"pyttsx3 error: {e}", flush=True)
            return False

    def _record_audio(self):
        """Record audio from persistent stream (keeps device open to prevent Jabra mute reset).
        
        Returns:
            Tuple of (audio_samples, raw_bytes) - numpy array and raw PCM bytes
        """
        duration = self.audio_record_seconds
        target_rate = self.audio_sample_rate
        capture_rate = getattr(self, '_capture_sample_rate', target_rate)

        print(f"Listening... (recording {int(duration)}s)", flush=True)
        
        try:
            # Read from persistent audio stream (device stays open)
            raw_bytes = self._audio_stream.read_seconds(duration)
            
            # Convert raw PCM bytes to float32 numpy array
            audio_int16 = np.frombuffer(raw_bytes, dtype=np.int16)
            if self._audio_stream_channels and self._audio_stream_channels > 1:
                frames = len(audio_int16) // self._audio_stream_channels
                if frames > 0:
                    audio_int16 = audio_int16[: frames * self._audio_stream_channels]
                    audio_int16 = audio_int16.reshape(frames, self._audio_stream_channels).mean(axis=1).astype(np.int16)
            audio = audio_int16.astype(np.float32) / 32768.0

            # Resample if capture stream rate differs from whisper/sample rate.
            if capture_rate != target_rate and len(audio) > 0:
                # Prefer exact integer-ratio decimation when possible.
                if capture_rate % target_rate == 0:
                    step = int(capture_rate // target_rate)
                    if step > 0:
                        audio = audio[::step].astype(np.float32)
                else:
                    x_old = np.linspace(0.0, 1.0, num=len(audio), endpoint=False)
                    new_len = int(len(audio) * (target_rate / float(capture_rate)))
                    if new_len > 0:
                        x_new = np.linspace(0.0, 1.0, num=new_len, endpoint=False)
                        audio = np.interp(x_new, x_old, audio).astype(np.float32)

            # Software auto-gain for very quiet microphones (keeps wake word usable)
            if len(audio) > 0:
                peak = float(np.max(np.abs(audio)))
                if 0.0 < peak < 0.06:
                    target_peak = 0.20
                    gain = min(40.0, target_peak / peak)
                    audio = np.clip(audio * gain, -1.0, 1.0).astype(np.float32)
                    print(f"Applied software gain x{gain:.1f} (peak {peak:.4f} -> {float(np.max(np.abs(audio))):.4f})", flush=True)
            return audio, raw_bytes
        except Exception as e:
            print(f"Recording error: {e}", flush=True)
            return np.zeros(int(duration * target_rate), dtype='float32'), b''

    def _transcribe_local(self, audio_samples: np.ndarray) -> str:
        # faster-whisper accepts numpy arrays directly (no disk write needed)
        segments, info = self._whisper_model.transcribe(
            audio_samples,
            language=self.whisper_language or None,
            vad_filter=True,
        )
        text = "".join(seg.text for seg in segments).strip()
        return text

    def _transcribe_api(self, audio_samples: np.ndarray) -> str:
        # Use BytesIO to avoid disk writes
        import io
        buffer = io.BytesIO()
        sf.write(buffer, audio_samples, self.audio_sample_rate, format='WAV')
        buffer.seek(0)
        buffer.name = 'audio.wav'  # OpenAI API needs a filename
        
        result = self.openai_client.audio.transcriptions.create(
            model='whisper-1',
            file=buffer,
            language=self.whisper_language or None,
        )
        return (result.text or '').strip()
    
    def _transcribe(self, audio_samples):
        """Transcribe audio samples to text."""
        if self.whisper_mode == 'api':
            return self._transcribe_api(audio_samples)
        else:
            return self._transcribe_local(audio_samples)
    
    def listen_for_wake_word(self):
        """Listen for the wake word. Returns (detected, trailing_command) tuple.
        
        If user says "apple what time is it", returns (True, "what time is it")
        If user just says "apple", returns (True, None)
        If no wake word, returns (False, None)
        If muted (silent audio), returns (False, None) and updates mute state
        """
        try:
            # Preferred: openWakeWord for fast, low-latency detection
            if self._oww_model is not None:
                # Account for stereo: read enough bytes for channels, then downmix to mono
                bytes_per_frame = self._oww_frame_size * 2 * self._audio_stream_channels
                frame_bytes = self._audio_stream.read_bytes(bytes_per_frame, timeout_seconds=2.0)
                
                now = time.time()
                if now - self._last_noise_log_ts >= 2.0:
                    amp = get_audio_amplitude(frame_bytes)
                    print(f"Audio amplitude max={amp}", flush=True)
                    self._last_noise_log_ts = now
                
                # Check mute status
                if self.check_and_update_mute_status(frame_bytes):
                    return False, None
                
                # Convert to int16 numpy array
                pcm = np.frombuffer(frame_bytes, dtype=np.int16)
                
                # Downmix stereo to mono if needed (openWakeWord expects mono 16kHz)
                if self._audio_stream_channels == 2:
                    pcm = pcm.reshape(-1, 2).mean(axis=1).astype(np.int16)
                
                # openWakeWord expects chunks of 1280 samples (80ms at 16kHz)
                prediction = self._oww_model.predict(pcm)
                
                # Check if any wake word exceeded threshold
                for model_name, score in prediction.items():
                    if score > 0.5:  # Threshold
                        print(f"Wake word detected (openWakeWord: {model_name}, score={score:.3f})", flush=True)
                        # Reset model state to prevent repeated detections
                        self._oww_model.reset()
                        
                        # Record full audio to capture any trailing command
                        audio_samples, raw_bytes = self._record_audio()
                        text = self._transcribe(audio_samples)
                        if text:
                            trailing = text.lower().strip()
                            print(f"Trailing command: {trailing}", flush=True)
                            return True, trailing
                        return True, None
                
                return False, None
            
            # Fallback: Whisper-based wake word detection
            audio_samples, raw_bytes = self._record_audio()

            now = time.time()
            if now - self._last_noise_log_ts >= 2.0:
                amp = get_audio_amplitude(raw_bytes)
                print(f"Audio amplitude max={amp}", flush=True)
                self._last_noise_log_ts = now
            
            # Check for hardware mute (silent audio) and update state for portal
            is_muted = self.check_and_update_mute_status(raw_bytes)
            if is_muted:
                # Audio is silent - device is muted, skip transcription
                return False, None

            # Don't aggressively gate wake-word detection. Only skip if the signal
            # is extremely low (but non-zero) to avoid wasting CPU on near-silence.
            amp = get_audio_amplitude(raw_bytes)
            if amp < 30:
                return False, None
            
            text = self._transcribe(audio_samples)
            
            if not text:
                return False, None
            
            text_lower = text.lower()
            print(f"Heard: {text_lower}", flush=True)

            # Normalize transcription/wake word to handle variations like "jet son" vs "jetson"
            normalized_text = re.sub(r'[^a-z0-9]+', '', text_lower)
            normalized_wake = re.sub(r'[^a-z0-9]+', '', self.wake_word.lower())

            # Common Whisper mis-transcriptions for wake words.
            # Keep this tiny and conservative to avoid false positives.
            wake_aliases = []
            if normalized_wake:
                wake_aliases.append(normalized_wake)
            if normalized_wake == 'computer':
                wake_aliases += ['comehere', 'compute', 'commuter']
            elif normalized_wake == 'assistant':
                wake_aliases += ['aassistant']
            elif normalized_wake == 'jetson':
                wake_aliases += ['jetson', 'jetsonn', 'jetsonnn', 'jetson testing', 'jetson']

            wake_aliases = [re.sub(r'[^a-z0-9]+', '', a.lower()) for a in wake_aliases if a]
            wake_aliases = list(dict.fromkeys([a for a in wake_aliases if a]))
            
            # Check if wake word is in the transcription
            if self.wake_word in text_lower or any(a in normalized_text for a in wake_aliases):
                # Found wake word - extract trailing command if present
                parts = text_lower.split(self.wake_word, 1)
                trailing = parts[1].strip() if len(parts) > 1 else None
                if trailing:
                    return True, trailing
                return True, None
            return False, None
        except Exception as e:
            print(f"Wake word detection error: {e}", flush=True)
            return False, None
    
    def listen_for_command(self):
        """Listen for a command after wake word. Prompts with 'Yes?'."""
        try:
            self.speak("Yes?")
            
            audio_samples, raw_bytes = self._record_audio()
            
            # Reset openWakeWord state to clear any audio from the prompt
            if self._oww_model is not None:
                self._oww_model.reset()
            
            # Update mute state for portal
            self.check_and_update_mute_status(raw_bytes)
            
            text = self._transcribe(audio_samples)

            if not text:
                self.speak("Sorry, I didn't catch that.")
                return ""

            print(f"You said: {text}", flush=True)
            return text.lower()
        except Exception as e:
            print(f"Transcription error: {e}", flush=True)
            self.speak("Sorry, I had trouble understanding.")
            return ""
    
    def listen_for_followup(self, timeout_seconds=5.0):
        """Listen for follow-up commands without prompting. Returns command or empty string."""
        print("Listening for follow-up...", flush=True)
        start_time = time.time()
        
        while time.time() - start_time < timeout_seconds:
            try:
                audio_samples, raw_bytes = self._record_audio()
                
                # Reset openWakeWord state
                if self._oww_model is not None:
                    self._oww_model.reset()
                
                # Check mute status
                if self.check_and_update_mute_status(raw_bytes):
                    continue
                
                # Transcribe - let Whisper decide if there's speech
                text = self._transcribe(audio_samples)
                if text:
                    print(f"Follow-up: {text}", flush=True)
                    return text.lower()
            except Exception as e:
                print(f"Follow-up listen error: {e}", flush=True)
        
        return ""
    
    def listen(self):
        """Legacy listen method - records and transcribes."""
        try:
            audio_samples, raw_bytes = self._record_audio()
            
            # Update mute state for portal
            self.check_and_update_mute_status(raw_bytes)
            
            text = self._transcribe(audio_samples)
            if text:
                print(f"You said: {text}", flush=True)
            return text.lower() if text else ""
        except Exception as e:
            print(f"Transcription error: {e}", flush=True)
            return ""
    
    def get_time(self):
        """Get current time"""
        current_time = datetime.datetime.now().strftime("%I:%M %p")
        self.speak(f"The current time is {current_time}")
    
    def get_date(self):
        """Get current date"""
        current_date = datetime.datetime.now().strftime("%A, %B %d, %Y")
        self.speak(f"Today is {current_date}")
    
    def tell_joke(self):
        """Tell a random joke"""
        joke = pyjokes.get_joke()
        self.speak(joke)
    
    def search_web(self, query):
        """Search the web"""
        url = f"https://www.google.com/search?q={query.replace(' ', '+')}"
        webbrowser.open(url)
        self.speak(f"Here's what I found for {query}")
    
    def process_command(self, command):
        """Process user commands"""
        if not command:
            return True
        
        start_time = time.time()
        response_text = ""
            
        if "hello" in command or "hi" in command:
            response_text = "Hello! How can I assist you today?"
            self.speak(response_text)
            
        elif "time" in command:
            current_time = datetime.datetime.now().strftime("%I:%M %p")
            response_text = f"The current time is {current_time}"
            self.speak(response_text)
            
        elif "date" in command:
            current_date = datetime.datetime.now().strftime("%A, %B %d, %Y")
            response_text = f"Today is {current_date}"
            self.speak(response_text)
            
        elif "joke" in command:
            response_text = pyjokes.get_joke()
            self.speak(response_text)
            
        elif "search" in command:
            query = command.replace("search", "").strip()
            if query:
                self.search_web(query)
                response_text = f"Searching for: {query}"
            else:
                self.speak("What would you like me to search for?")
                query = self.listen()
                if query:
                    self.search_web(query)
                    response_text = f"Searching for: {query}"
        
        elif "thank" in command or "thanks" in command:
            responses = ["You're welcome!", "Happy to help!", "Anytime!", "My pleasure!"]
            response_text = random.choice(responses)
            self.speak(response_text)
            
        elif "goodbye" in command or "bye" in command or "exit" in command:
            response_text = "Goodbye! Have a great day!"
            self.speak(response_text)
            duration_ms = int((time.time() - start_time) * 1000)
            record_query(command, response_text, duration_ms)
            return False
            
        else:
            # Use configured LLM provider for general conversation
            prompt_tokens = 0
            completion_tokens = 0
            total_tokens = 0
            model_used = ""
            
            if self.llm_provider == "ollama" and self.ollama_client:
                # Use Ollama for local LLM
                try:
                    result = self.ollama_client.chat(
                        model=self.llm_model,
                        messages=[
                            {"role": "system", "content": "You are a helpful voice assistant. Keep responses brief and conversational."},
                            {"role": "user", "content": command}
                        ]
                    )
                    if "error" in result:
                        print(f"Ollama error: {result['error']}", flush=True)
                        response_text = "I had trouble with the local model."
                        self.speak("I had trouble connecting to the local model. Please check Ollama is running.")
                    else:
                        response_text = result.get("content", "")
                        prompt_tokens = result.get("prompt_tokens", 0)
                        completion_tokens = result.get("completion_tokens", 0)
                        total_tokens = result.get("total_tokens", 0)
                        model_used = result.get("model", self.llm_model)
                        self.speak(response_text)
                except Exception as e:
                    print(f"Error with Ollama: {e}", flush=True)
                    response_text = "I had trouble with the local model."
                    self.speak("I had trouble with the local model. Please try again.")
            elif self.openai_client:
                # Use OpenAI API
                try:
                    response = self.openai_client.chat.completions.create(
                        model=self.llm_model,
                        messages=[
                            {"role": "system", "content": "You are a helpful voice assistant. Keep responses brief and conversational."},
                            {"role": "user", "content": command}
                        ]
                    )
                    response_text = response.choices[0].message.content
                    # Capture token usage
                    if response.usage:
                        prompt_tokens = response.usage.prompt_tokens
                        completion_tokens = response.usage.completion_tokens
                        total_tokens = response.usage.total_tokens
                        model_used = response.model
                    self.speak(response_text)
                except Exception as e:
                    print(f"Error with OpenAI API: {e}", flush=True)
                    response_text = "I had trouble connecting to OpenAI."
                    self.speak("I had trouble connecting to OpenAI. Please try again.")
            else:
                response_text = "No LLM configured."
                self.speak("I don't have an LLM configured. Please set one up in the admin portal.")
        
        # Record query to history with token usage if available
        duration_ms = int((time.time() - start_time) * 1000)
        _locals = locals()
        record_query(
            command,
            response_text,
            duration_ms,
            prompt_tokens=_locals.get('prompt_tokens', 0),
            completion_tokens=_locals.get('completion_tokens', 0),
            total_tokens=_locals.get('total_tokens', 0),
            model=_locals.get('model_used', ""),
        )
        
        return True

def main():
    assistant = VoiceAssistant()
    
    print(f"Waiting for wake word '{assistant.wake_word}'...", flush=True)
    
    # Main loop with wake word detection
    running = True
    while running:
        # Check for settings reload signal
        assistant.check_reload()
        
        # Wait for wake word (may include trailing command)
        # Mute detection happens inside listen_for_wake_word via audio level check
        detected, trailing_command = assistant.listen_for_wake_word()
        if detected:
            # Use trailing command if present, otherwise listen for new command
            if trailing_command:
                command = trailing_command
            else:
                command = assistant.listen_for_command()
            
            # Process command if we got one
            if command:
                running = assistant.process_command(command)
                
                # After responding, listen for follow-ups (5 second window, no prompt)
                while running:
                    followup = assistant.listen_for_followup(timeout_seconds=5.0)
                    if not followup:
                        break  # No follow-up, go back to wake word
                    running = assistant.process_command(followup)
            
            print(f"Waiting for wake word '{assistant.wake_word}'...", flush=True)

if __name__ == "__main__":
    main()
