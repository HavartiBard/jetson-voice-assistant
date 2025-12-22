import pyttsx3
import datetime
import webbrowser
import os
import random
import pyjokes
from dotenv import load_dotenv
import openai
import json
import tempfile

import numpy as np
import sounddevice as sd
import soundfile as sf
from faster_whisper import WhisperModel

from settings_store import load_settings

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
        openai.api_key = settings.get('openai_api_key') or os.getenv('OPENAI_API_KEY')
        self.wake_word = (os.getenv('WAKE_WORD') or settings.get('wake_word') or 'jetson').strip().lower()

        self.whisper_mode = (os.getenv('WHISPER_MODE') or settings.get('whisper_mode') or 'local').strip().lower()
        self.whisper_model_size = (os.getenv('WHISPER_MODEL_SIZE') or settings.get('whisper_model_size') or 'small').strip()
        self.whisper_language = (os.getenv('WHISPER_LANGUAGE') or settings.get('whisper_language') or 'en').strip()

        self.audio_sample_rate = int(os.getenv('AUDIO_SAMPLE_RATE') or settings.get('audio_sample_rate') or 16000)
        self.audio_channels = int(os.getenv('AUDIO_CHANNELS') or settings.get('audio_channels') or 1)
        self.audio_record_seconds = float(os.getenv('AUDIO_RECORD_SECONDS') or settings.get('audio_record_seconds') or 4)

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
        
        # Greeting message
        self.speak("Hello! I'm your Jetson Voice Assistant. How can I help you today?")
    
    def speak(self, text):
        """Convert text to speech"""
        print(f"Assistant: {text}")
        self.engine.say(text)
        self.engine.runAndWait()

    def _record_audio(self):
        """Record audio from the default microphone and return float32 mono samples."""
        duration = self.audio_record_seconds
        samplerate = self.audio_sample_rate
        channels = self.audio_channels

        print(f"Listening... (recording {duration:.1f}s)")
        audio = sd.rec(
            int(duration * samplerate),
            samplerate=samplerate,
            channels=channels,
            dtype='float32',
        )
        sd.wait()

        if channels > 1:
            audio = np.mean(audio, axis=1)
        else:
            audio = audio.reshape(-1)

        return audio

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
    
    def listen(self):
        """Listen for audio input and convert it to text using Whisper."""
        try:
            audio_samples = self._record_audio()
            if self.whisper_mode == 'api':
                text = self._transcribe_api(audio_samples)
            else:
                text = self._transcribe_local(audio_samples)

            if not text:
                self.speak("Sorry, I didn't catch that. Could you please repeat?")
                return ""

            print(f"You said: {text}")
            return text.lower()
        except Exception as e:
            print(f"Transcription error: {e}")
            self.speak("Sorry, I had trouble understanding audio just now.")
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
            return
            
        if "hello" in command or "hi" in command:
            self.speak("Hello! How can I assist you today?")
            
        elif "time" in command:
            self.get_time()
            
        elif "date" in command:
            self.get_date()
            
        elif "joke" in command:
            self.tell_joke()
            
        elif "search" in command:
            query = command.replace("search", "").strip()
            if query:
                self.search_web(query)
            else:
                self.speak("What would you like me to search for?")
                query = self.listen()
                if query:
                    self.search_web(query)
        
        elif "thank" in command or "thanks" in command:
            responses = ["You're welcome!", "Happy to help!", "Anytime!", "My pleasure!"]
            self.speak(random.choice(responses))
            
        elif "goodbye" in command or "bye" in command or "exit" in command:
            self.speak("Goodbye! Have a great day!")
            return False
            
        else:
            # Use OpenAI for general conversation
            try:
                response = openai.ChatCompletion.create(
                    model="gpt-3.5-turbo",
                    messages=[
                        {"role": "system", "content": "You are a helpful assistant."},
                        {"role": "user", "content": command}
                    ]
                )
                reply = response.choices[0].message['content']
                self.speak(reply)
            except Exception as e:
                print(f"Error with OpenAI API: {e}")
                self.speak("I'm not sure how to respond to that. Could you try something else?")
        
        return True

def main():
    assistant = VoiceAssistant()
    
    # Main loop
    running = True
    while running:
        command = assistant.listen()
        if command:
            running = assistant.process_command(command)

if __name__ == "__main__":
    main()
