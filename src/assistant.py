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

import numpy as np
import soundfile as sf
from faster_whisper import WhisperModel

from settings_store import load_settings
from history_store import record_query
from ollama_client import OllamaClient
from audio_devices import check_audio_is_silent, write_mute_state
import time


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
        if self.whisper_mode == 'local':
            # device choices: 'cpu', 'cuda'
            # compute_type choices: 'int8', 'int8_float16', 'float16', 'float32'
            # On Jetson Nano, CPU+int8 is typically the most reliable out of the box.
            self._whisper_model = WhisperModel(
                self.whisper_model_size,
                device='cpu',
                compute_type='int8',
            )
        
        print(f"Using audio device: {self.audio_device}", flush=True)
        
        # Hardware mute state tracking with hysteresis
        self._last_mute_state = False
        self._mute_announced = False
        self._mute_counter = 0  # Counter for hysteresis
        
        # Greeting message
        self.speak("Hello! I'm your Jetson Voice Assistant. How can I help you today?")
    
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
                self._load_settings()
                if old_wake_word != self.wake_word:
                    self.speak(f"Wake word changed to {self.wake_word}")
            except Exception as e:
                print(f"Error reloading settings: {e}", flush=True)
    
    def check_and_update_mute_status(self, audio_data: bytes) -> bool:
        """Check if audio is silent (hardware muted) and update state.
        
        Uses hysteresis to prevent flapping - requires 3 consecutive
        readings in the same direction before changing state.
        
        Args:
            audio_data: Raw PCM audio bytes from recording
            
        Returns:
            bool: True if microphone is currently muted (silent audio)
        """
        is_silent = check_audio_is_silent(audio_data)
        
        # Hysteresis: require 3 consecutive readings to change state
        HYSTERESIS_COUNT = 3
        
        if is_silent and not self._last_mute_state:
            # Currently unmuted, seeing silent audio
            self._mute_counter += 1
            if self._mute_counter >= HYSTERESIS_COUNT:
                self._last_mute_state = True
                self._mute_counter = 0
                print("Hardware mute detected - audio is silent", flush=True)
        elif not is_silent and self._last_mute_state:
            # Currently muted, seeing active audio
            self._mute_counter += 1
            if self._mute_counter >= HYSTERESIS_COUNT:
                self._last_mute_state = False
                self._mute_counter = 0
                print("Hardware unmute detected - audio is active", flush=True)
        else:
            # State matches reading, reset counter
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
        """Record audio using arecord directly to memory (no disk writes).
        
        Returns:
            Tuple of (audio_samples, raw_bytes) - numpy array and raw PCM bytes
        """
        duration = int(self.audio_record_seconds)
        samplerate = self.audio_sample_rate

        print(f"Listening... (recording {duration}s)", flush=True)
        
        try:
            # Record directly to stdout as raw PCM (no disk write)
            cmd = [
                'arecord',
                '-D', self.audio_device,
                '-f', 'S16_LE',
                '-r', str(samplerate),
                '-c', '1',
                '-d', str(duration),
                '-t', 'raw',
                '-q',
            ]
            result = subprocess.run(cmd, capture_output=True, check=True)
            raw_bytes = result.stdout
            
            # Convert raw PCM bytes to float32 numpy array
            audio_int16 = np.frombuffer(raw_bytes, dtype=np.int16)
            audio = audio_int16.astype(np.float32) / 32768.0
            return audio, raw_bytes
        except Exception as e:
            print(f"Recording error: {e}", flush=True)
            return np.zeros(int(duration * samplerate), dtype='float32'), b''

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
            audio_samples, raw_bytes = self._record_audio()
            
            # Check for hardware mute (silent audio) and update state for portal
            is_muted = self.check_and_update_mute_status(raw_bytes)
            if is_muted:
                # Audio is silent - device is muted, skip transcription
                return False, None
            
            text = self._transcribe(audio_samples)
            
            if not text:
                return False, None
            
            text_lower = text.lower()
            print(f"Heard: {text_lower}", flush=True)
            
            # Check if wake word is in the transcription
            if self.wake_word in text_lower:
                print(f"Wake word '{self.wake_word}' detected!", flush=True)
                
                # Extract any command that follows the wake word
                wake_idx = text_lower.find(self.wake_word)
                trailing = text_lower[wake_idx + len(self.wake_word):].strip()
                # Remove common filler words/punctuation at the start
                trailing = trailing.lstrip('.,!? ')
                
                if trailing and len(trailing) > 2:
                    print(f"Trailing command: {trailing}", flush=True)
                    return True, trailing
                return True, None
            return False, None
        except Exception as e:
            print(f"Wake word detection error: {e}", flush=True)
            return False, None
    
    def listen_for_command(self):
        """Listen for a command after wake word detected."""
        try:
            self.speak("Yes?")
            audio_samples, raw_bytes = self._record_audio()
            
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
            
            if command:
                running = assistant.process_command(command)
            print(f"Waiting for wake word '{assistant.wake_word}'...", flush=True)

if __name__ == "__main__":
    main()
