"""
Jarvis Voice Module for AMARTIE
=================================
Voice-controlled browser agent — same stack as Prompt Engineer 48's demo:
  Faster-Whisper → JEV → Playwright

All voice processing LOCAL (no cloud APIs needed for STT).
Uses JEV for intent routing (not full LLM) — 193x faster, 244x cheaper.

Usage:
  python3 -m amartie.jarvis_voice
"""

import os
import sys
import json
import time
import queue
import threading
import subprocess
from typing import Optional, List, Dict, Any

# Try Whisper (STT)
try:
    import whisper
    HAS_WHISPER = True
except ImportError:
    HAS_WHISPER = False

# Try PyAudio
try:
    import pyaudio
    import wave
    HAS_AUDIO = True
except ImportError:
    HAS_AUDIO = False

# Try Playwright for browser automation
try:
    from playwright.sync_api import sync_playwright, Page, Browser
    HAS_PLAYWRIGHT = True
except ImportError:
    HAS_PLAYWRIGHT = False

# Import JEV/Layer from gate
try:
    from amartie.gate import JudgeGate, JudgeVerdict
    HAS_GATE = True
except ImportError:
    HAS_GATE = False


class WhisperSTT:
    """Local speech-to-text using Faster-Whisper."""
    
    def __init__(self, model_size: str = "base"):
        """
        Initialize Whisper STT.
        
        Args:
            model_size: Whisper model size (tiny, base, small, medium, large)
        """
        if not HAS_WHISPER:
            raise ImportError("Install whisper: pip install faster-whisper")
        print(f"Loading Whisper model: {model_size}...")
        self.model = whisper.load_model(model_size)
        print("Whisper model loaded.")
    
    def transcribe(self, audio_path: str) -> str:
        """Transcribe audio file to text."""
        result = self.model.transcribe(audio_path, language="en")
        return result["text"].strip()
    
    def listen_and_transcribe(self, duration: int = 5, 
                               output_path: str = "/tmp/jarvis_audio.wav") -> str:
        """
        Record audio from microphone and transcribe.
        
        Args:
            duration: Recording duration in seconds
            output_path: Path to save audio file
            
        Returns:
            Transcribed text
        """
        if not HAS_AUDIO:
            raise ImportError("Install pyaudio: pip install pyaudio")
        
        # Record audio
        CHUNK = 1024
        FORMAT = pyaudio.paInt16
        CHANNELS = 1
        RATE = 16000
        
        p = pyaudio.PyAudio()
        stream = p.open(format=FORMAT, channels=CHANNELS, rate=RATE,
                        input=True, frames_per_buffer=CHUNK)
        
        print(f"🎤 Listening for {duration}s...")
        frames = []
        
        for _ in range(0, int(RATE / CHUNK * duration)):
            data = stream.read(CHUNK)
            frames.append(data)
        
        print("🔇 Done listening.")
        stream.stop_stream()
        stream.close()
        p.terminate()
        
        # Save audio
        with wave.open(output_path, 'wb') as wf:
            wf.setnchannels(CHANNELS)
            wf.setsampwidth(p.get_sample_size(FORMAT))
            wf.setframerate(RATE)
            wf.writeframes(b''.join(frames))
        
        # Transcribe
        return self.transcribe(output_path)


class JEVIntentRouter:
    """
    Route voice commands to actions using JEV.
    
    Uses the AMARTIE 9-judge gate to determine:
    - Which action to perform (Choice)
    - How confident we are (Score)
    - Whether it's safe (Noul)
    """
    
    def __init__(self, mock_mode: bool = True):
        """
        Initialize the intent router.
        
        Args:
            mock_mode: If True, use mock judges (no API key needed)
        """
        if not HAS_GATE:
            raise ImportError("AMARTIE gate module not available")
        
        self.gate = JudgeGate(mock_mode=mock_mode)
        self.commands = {
            "open_url": "Navigate to a URL",
            "click_element": "Click on a page element",
            "scroll": "Scroll up or down",
            "type_text": "Type text into a field",
            "go_back": "Go back in browser history",
            "take_screenshot": "Take a screenshot",
            "close": "Close the browser",
        }
    
    def parse_command(self, text: str) -> Dict[str, Any]:
        """
        Parse a voice command into an action.
        
        Args:
            text: Transcribed voice command
            
        Returns:
            Dict with action_type and parameters
        """
        text_lower = text.lower().strip()
        
        # Simple command parsing
        if "open" in text_lower or "go to" in text_lower or "navigate" in text_lower:
            # Extract URL
            url = self._extract_url(text)
            return {"action_type": "open_url", "url": url, "raw": text}
        
        if "click" in text_lower or "press" in text_lower:
            return {"action_type": "click_element", "raw": text}
        
        if "scroll" in text_lower:
            direction = "down" if "down" in text_lower else "up"
            return {"action_type": "scroll", "direction": direction, "raw": text}
        
        if "type" in text_lower or "enter" in text_lower:
            return {"action_type": "type_text", "raw": text}
        
        if "back" in text_lower:
            return {"action_type": "go_back", "raw": text}
        
        if "screenshot" in text_lower:
            return {"action_type": "take_screenshot", "raw": text}
        
        if "close" in text_lower or "quit" in text_lower or "exit" in text_lower:
            return {"action_type": "close", "raw": text}
        
        return {"action_type": "unknown", "raw": text}
    
    def _extract_url(self, text: str) -> str:
        """Extract URL from text."""
        words = text.split()
        for word in words:
            if word.startswith("http"):
                return word
            if "." in word and " " not in word:
                return f"https://{word}"
        return "https://www.google.com"
    
    def evaluate_command(self, action: Dict[str, Any]) -> tuple:
        """
        Evaluate a command through the JEV gate.
        
        Returns:
            (passed, receipt): Whether the action passed and receipt
        """
        action_type = action.get("action_type", "unknown")
        passed, receipt = self.gate.verify_action(
            action_type=action_type,
            payload=action,
            judge_responses=None  # Will use JEV
        )
        return passed, receipt


class BrowserAutomator:
    """Browser automation using Playwright."""
    
    def __init__(self, headless: bool = False):
        """
        Initialize browser automator.
        
        Args:
            headless: If True, run browser in headless mode
        """
        if not HAS_PLAYWRIGHT:
            raise ImportError("Install playwright: pip install playwright")
        
        self.headless = headless
        self.browser: Optional[Browser] = None
        self.page: Optional[Page] = None
        self._playwright = None
    
    def start(self):
        """Start the browser."""
        self._playwright = sync_playwright().start()
        self.browser = self._playwright.chromium.launch(headless=self.headless)
        self.page = self.browser.new_page()
        print("🌐 Browser started.")
    
    def execute(self, action: Dict[str, Any]):
        """
        Execute an action in the browser.
        
        Args:
            action: Action dict with action_type and parameters
        """
        if not self.page:
            self.start()
        
        action_type = action.get("action_type")
        
        try:
            if action_type == "open_url":
                url = action.get("url", "https://www.google.com")
                print(f"Opening: {url}")
                self.page.goto(url)
            
            elif action_type == "click_element":
                # For voice, we'll use a simple selector
                selector = action.get("selector", "a")
                print(f"Clicking: {selector}")
                self.page.click(selector)
            
            elif action_type == "scroll":
                direction = action.get("direction", "down")
                print(f"Scrolling: {direction}")
                if direction == "down":
                    self.page.evaluate("window.scrollBy(0, window.innerHeight)")
                else:
                    self.page.evaluate("window.scrollBy(0, -window.innerHeight)")
            
            elif action_type == "type_text":
                text = action.get("text", "")
                print(f"Typing: {text}")
                self.page.keyboard.type(text)
            
            elif action_type == "go_back":
                print("Going back")
                self.page.go_back()
            
            elif action_type == "take_screenshot":
                path = "/tmp/jarvis_screenshot.png"
                print(f"Screenshot: {path}")
                self.page.screenshot(path=path)
            
            elif action_type == "close":
                print("Closing browser")
                self.stop()
            
            else:
                print(f"Unknown action: {action_type}")
        
        except Exception as e:
            print(f"❌ Error executing action: {e}")
    
    def stop(self):
        """Close the browser."""
        if self.browser:
            self.browser.close()
        if self._playwright:
            self._playwright.stop()
        print("🛑 Browser stopped.")


class JarvisVoice:
    """
    Main Jarvis voice controller.
    
    Pipeline: Mic → Whisper → JEV → Browser
    """
    
    def __init__(self, whisper_model: str = "base", mock_mode: bool = True):
        """
        Initialize Jarvis voice module.
        
        Args:
            whisper_model: Whisper model size (tiny, base, small)
            mock_mode: Use mock JEV if True
        """
        self.stt = WhisperSTT(model_size=whisper_model)
        self.router = JEVIntentRouter(mock_mode=mock_mode)
        self.browser = BrowserAutomator(headless=False)
        self.running = False
    
    def start(self):
        """Start Jarvis voice loop."""
        self.running = True
        print("\n🎤 Jarvis Voice Active")
        print("Say a command (e.g., 'open google.com', 'scroll down', 'close')")
        print("Say 'quit' to exit.\n")
        
        while self.running:
            try:
                # Listen
                text = self.stt.listen_and_transcribe(duration=3)
                if not text:
                    continue
                
                print(f"\n📝 Heard: '{text}'")
                
                # Parse
                action = self.router.parse_command(text)
                print(f"🎯 Action: {action['action_type']}")
                
                # Evaluate
                passed, receipt = self.router.evaluate_command(action)
                
                if passed:
                    print("✅ Gate: PASS")
                    self.browser.execute(action)
                else:
                    print("❌ Gate: DISSENT — command blocked")
                    for v in receipt.verdicts:
                        if v.verdict != "PASS":
                            print(f"   {v.judge_id}: {v.verdict}")
                
                # Check quit
                if action["action_type"] == "close":
                    self.running = False
                    
            except KeyboardInterrupt:
                print("\n👋 Stopping Jarvis.")
                self.running = False
            except Exception as e:
                print(f"❌ Error: {e}")
        
        self.browser.stop()
        print("Jarvis stopped.")


# Entry point
if __name__ == "__main__":
    jarvis = JarvisVoice(whisper_model="base", mock_mode=True)
    jarvis.start()
