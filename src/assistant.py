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
        
        settings = load_settings()
        
        # OpenAI API key: settings takes priority, then .env
        api_key = settings.get('openai_api_key') or os.getenv('OPENAI_API_KEY')
        self.openai_client = OpenAI(api_key=api_key) if api_key else None
        self.wake_word = (os.getenv('WAKE_WORD') or settings.get('wake_word') or 'jetson').strip().lower()

        self.whisper_mode = (os.getenv('WHISPER_MODE') or settings.get('whisper_mode') or 'local').strip().lower()
        self.whisper_model_size = (os.getenv('WHISPER_MODEL_SIZE') or settings.get('whisper_model_size') or 'small').strip()
        self.whisper_language = (os.getenv('WHISPER_LANGUAGE') or settings.get('whisper_language') or 'en').strip()

        self.audio_sample_rate = int(os.getenv('AUDIO_SAMPLE_RATE') or settings.get('audio_sample_rate') or 16000)
        self.audio_channels = int(os.getenv('AUDIO_CHANNELS') or settings.get('audio_channels') or 1)
        self.audio_record_seconds = float(os.getenv('AUDIO_RECORD_SECONDS') or settings.get('audio_record_seconds') or 4)
        
        # Audio device for arecord (ALSA hw device like "hw:2,0")
        self.audio_device = os.getenv('AUDIO_DEVICE') or settings.get('audio_device') or self._find_usb_alsa_device()

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
        
        # Greeting message
        self.speak("Hello! I'm your Jetson Voice Assistant. How can I help you today?")
    
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
        """Convert text to speech using gTTS (natural voice) with espeak fallback"""
        print(f"Assistant: {text}", flush=True)
        play_device = self.audio_device.replace('hw:', 'plughw:')
        
        # Try gTTS first (natural Google voice, requires internet)
        try:
            from gtts import gTTS
            with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as f:
                tts = gTTS(text=text, lang='en', slow=False)
                tts.save(f.name)
                # Convert mp3 to wav and play through Jabra
                # Use ffmpeg if available, otherwise mpg123
                try:
                    subprocess.run(
                        ['ffmpeg', '-i', f.name, '-f', 'wav', '-acodec', 'pcm_s16le', '-ar', '48000', '-'],
                        stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True
                    )
                    # ffmpeg available, use it
                    ffmpeg = subprocess.Popen(
                        ['ffmpeg', '-i', f.name, '-f', 'wav', '-acodec', 'pcm_s16le', '-ar', '48000', '-'],
                        stdout=subprocess.PIPE, stderr=subprocess.PIPE
                    )
                    aplay = subprocess.Popen(['aplay', '-D', play_device, '-q'], stdin=ffmpeg.stdout, stderr=subprocess.PIPE)
                    ffmpeg.stdout.close()
                    aplay.communicate()
                except FileNotFoundError:
                    # No ffmpeg, try mpg123 to play mp3 directly
                    subprocess.run(['mpg123', '-a', play_device, '-q', f.name], check=True)
                os.unlink(f.name)
                return
        except Exception as e:
            print(f"gTTS error (falling back to espeak): {e}", flush=True)
        
        # Fallback to espeak (robotic but reliable, no internet needed)
        try:
            espeak_cmd = ['espeak', '-s', '150', '-v', 'en', '--stdout', text]
            aplay_cmd = ['aplay', '-D', play_device, '-q']
            espeak_proc = subprocess.Popen(espeak_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            aplay_proc = subprocess.Popen(aplay_cmd, stdin=espeak_proc.stdout, stderr=subprocess.PIPE)
            espeak_proc.stdout.close()
            aplay_proc.communicate()
        except Exception as e:
            print(f"TTS error: {e}", flush=True)

    def _record_audio(self):
        """Record audio using arecord and return float32 mono samples."""
        duration = int(self.audio_record_seconds)
        samplerate = self.audio_sample_rate

        print(f"Listening... (recording {duration}s)", flush=True)
        
        # Use arecord for reliable USB audio capture
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as f:
            tmp_path = f.name
        
        try:
            cmd = [
                'arecord',
                '-D', self.audio_device,
                '-f', 'S16_LE',
                '-r', str(samplerate),
                '-c', '1',
                '-d', str(duration),
                '-q',  # quiet
                tmp_path
            ]
            subprocess.run(cmd, check=True, capture_output=True)
            
            # Read the recorded audio
            audio, sr = sf.read(tmp_path, dtype='float32')
            return audio
        except subprocess.CalledProcessError as e:
            print(f"Recording error: {e.stderr.decode() if e.stderr else e}", flush=True)
            return np.zeros(int(duration * samplerate), dtype='float32')
        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)

    def _transcribe_local(self, audio_samples: np.ndarray) -> str:
        # faster-whisper expects a file path or numpy audio; file path is simplest.
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=True) as f:
            sf.write(f.name, audio_samples, self.audio_sample_rate)
            segments, info = self._whisper_model.transcribe(
                f.name,
                language=self.whisper_language or None,
                vad_filter=True,
            )
            text = "".join(seg.text for seg in segments).strip()
            return text

    def _transcribe_api(self, audio_samples: np.ndarray) -> str:
        # Writes a temp wav and sends to OpenAI Whisper.
        # NOTE: requires OPENAI_API_KEY.
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=True) as f:
            sf.write(f.name, audio_samples, self.audio_sample_rate)
            with open(f.name, 'rb') as audio_file:
                # openai-python older versions use Audio.transcribe; newer use client.audio.transcriptions
                # Keep compatible with current dependency pinned in requirements.
                result = openai.Audio.transcribe(
                    model='whisper-1',
                    file=audio_file,
                    language=self.whisper_language or None,
                )
                if isinstance(result, dict):
                    return (result.get('text') or '').strip()
                return (getattr(result, 'text', '') or '').strip()
    
    def _transcribe(self, audio_samples):
        """Transcribe audio samples to text."""
        if self.whisper_mode == 'api':
            return self._transcribe_api(audio_samples)
        else:
            return self._transcribe_local(audio_samples)
    
    def listen_for_wake_word(self):
        """Listen for the wake word. Returns True if wake word detected."""
        try:
            audio_samples = self._record_audio()
            text = self._transcribe(audio_samples)
            
            if not text:
                return False
            
            text_lower = text.lower()
            print(f"Heard: {text_lower}", flush=True)
            
            # Check if wake word is in the transcription
            if self.wake_word in text_lower:
                print(f"Wake word '{self.wake_word}' detected!", flush=True)
                return True
            return False
        except Exception as e:
            print(f"Wake word detection error: {e}", flush=True)
            return False
    
    def listen_for_command(self):
        """Listen for a command after wake word detected."""
        try:
            self.speak("Yes?")
            audio_samples = self._record_audio()
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
            audio_samples = self._record_audio()
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
            # Use OpenAI for general conversation
            if self.openai_client:
                try:
                    response = self.openai_client.chat.completions.create(
                        model="gpt-3.5-turbo",
                        messages=[
                            {"role": "system", "content": "You are a helpful voice assistant. Keep responses brief and conversational."},
                            {"role": "user", "content": command}
                        ]
                    )
                    response_text = response.choices[0].message.content
                    self.speak(response_text)
                except Exception as e:
                    print(f"Error with OpenAI API: {e}", flush=True)
                    response_text = "I had trouble connecting to OpenAI."
                    self.speak("I had trouble connecting to OpenAI. Please try again.")
            else:
                response_text = "OpenAI API key not configured."
                self.speak("I don't have an OpenAI API key configured. Please add one in the admin portal.")
        
        # Record query to history
        duration_ms = int((time.time() - start_time) * 1000)
        record_query(command, response_text, duration_ms)
        
        return True

def main():
    assistant = VoiceAssistant()
    
    print(f"Waiting for wake word '{assistant.wake_word}'...", flush=True)
    
    # Main loop with wake word detection
    running = True
    while running:
        # Wait for wake word
        if assistant.listen_for_wake_word():
            # Wake word detected, listen for command
            command = assistant.listen_for_command()
            if command:
                running = assistant.process_command(command)
            print(f"Waiting for wake word '{assistant.wake_word}'...", flush=True)

if __name__ == "__main__":
    main()
