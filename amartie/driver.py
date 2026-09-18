"""
AMARTIE AI Driver
==================
The autonomous agent that powers the cockpit.
Has voice, memory, and plugin autonomy.
"""

import os
import json
import time
from typing import Dict, List, Optional, Any


class Memory:
    """Persistent memory for the AMARTIE agent."""
    
    def __init__(self, memory_path: str = "~/.amartie/memory"):
        self.memory_path = os.path.expanduser(memory_path)
        os.makedirs(self.memory_path, exist_ok=True)
        self.short_term: List[dict] = []
        self.long_term: Dict[str, Any] = {}
        self.preferences: Dict[str, Any] = {}
        self.files_index: Dict[str, str] = {}
        self.conversation_history: List[dict] = []
    
    def remember(self, key: str, value: Any, permanent: bool = True):
        """Store a memory."""
        if permanent:
            self.long_term[key] = value
            self._save_long_term()
        else:
            self.short_term.append({"key": key, "value": value, "time": time.time()})
    
    def recall(self, key: str) -> Optional[Any]:
        """Retrieve a memory."""
        if key in self.long_term:
            return self.long_term[key]
        for item in reversed(self.short_term):
            if item["key"] == key:
                return item["value"]
        return None
    
    def index_file(self, file_path: str, description: str):
        """Index a file for later retrieval."""
        self.files_index[description] = file_path
        self._save_long_term()
    
    def find_file(self, query: str) -> Optional[str]:
        """Find a file by description."""
        for desc, path in self.files_index.items():
            if query.lower() in desc.lower():
                return path
        return None
    
    def set_preference(self, key: str, value: Any):
        """Set a user preference."""
        self.preferences[key] = value
        self._save_long_term()
    
    def get_preference(self, key: str, default: Any = None) -> Any:
        """Get a user preference."""
        return self.preferences.get(key, default)
    
    def add_conversation(self, role: str, content: str):
        """Add to conversation history."""
        self.conversation_history.append({
            "role": role,
            "content": content,
            "timestamp": time.time()
        })
        # Keep last 100 messages
        if len(self.conversation_history) > 100:
            self.conversation_history = self.conversation_history[-100:]
    
    def get_conversation(self, last_n: int = 10) -> List[dict]:
        """Get recent conversation."""
        return self.conversation_history[-last_n:]
    
    def _save_long_term(self):
        """Save long-term memory to disk."""
        data = {
            "long_term": self.long_term,
            "preferences": self.preferences,
            "files_index": self.files_index
        }
        path = os.path.join(self.memory_path, "memory.json")
        with open(path, "w") as f:
            json.dump(data, f, indent=2)
    
    def load(self):
        """Load memory from disk."""
        path = os.path.join(self.memory_path, "memory.json")
        if os.path.exists(path):
            with open(path) as f:
                data = json.load(f)
            self.long_term = data.get("long_term", {})
            self.preferences = data.get("preferences", {})
            self.files_index = data.get("files_index", {})


class Voice:
    """Voice synthesis via ElevenLabs."""
    
    def __init__(self):
        self.api_key = os.environ.get("ELEVENLABS_API_KEY", "")
        self.voice_id = os.environ.get("ELEVENLABS_VOICE_ID", "JBFqnCBsd6RMkjVDRZzb")
        self.enabled = bool(self.api_key)
    
    def speak(self, text: str) -> Optional[str]:
        """Convert text to speech. Returns path to audio file."""
        if not self.enabled:
            return None
        
        try:
            import urllib.request
            url = f"https://api.elevenlabs.io/v1/text-to-speech/{self.voice_id}"
            payload = json.dumps({
                "text": text,
                "model_id": "eleven_multilingual_v2"
            }).encode()
            
            req = urllib.request.Request(url, data=payload, headers={
                "xi-api-key": self.api_key,
                "Content-Type": "application/json"
            }, method="POST")
            
            with urllib.request.urlopen(req, timeout=30) as resp:
                audio = resp.read()
                output = f"/tmp/amartie_voice_{int(time.time())}.mp3"
                with open(output, "wb") as f:
                    f.write(audio)
                return output
        except Exception as e:
            print(f"Voice error: {e}")
            return None
    
    def list_voices(self) -> List[dict]:
        """List available voices."""
        if not self.enabled:
            return []
        try:
            import urllib.request
            url = "https://api.elevenlabs.io/v1/voices"
            req = urllib.request.Request(url, headers={"xi-api-key": self.api_key})
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read())
                return data.get("voices", [])
        except:
            return []


class AutonomousAgent:
    """
    The AMARTIE AI driver.
    Combines memory, voice, and plugin autonomy.
    """
    
    def __init__(self):
        self.memory = Memory()
        self.memory.load()
        self.voice = Voice()
        self.plugins: Dict[str, Any] = {}
        self.active_plugin: Optional[str] = None
        self.personality = {
            "name": "AMARTIE",
            "tone": "direct",
            "style": "terse",
            "language": "en"
        }
    
    def load_plugin(self, name: str, plugin_module):
        """Load a plugin module."""
        self.plugins[name] = plugin_module
    
    def process(self, user_input: str) -> dict:
        """
        Process user input and return a response.
        This is the main entry point for the AI driver.
        """
        self.memory.add_conversation("user", user_input)
        
        # Parse intent
        intent = self._parse_intent(user_input)
        
        # Execute based on intent
        result = self._execute_intent(intent, user_input)
        
        # Store response
        self.memory.add_conversation("assistant", result.get("response", ""))
        
        return result
    
    def _parse_intent(self, text: str) -> dict:
        """Parse user intent from text."""
        text_lower = text.lower()
        
        # File retrieval
        if any(w in text_lower for w in ["remember", "find", "show", "pull up", "open"]):
            return {"type": "file_retrieval", "query": text}
        
        # Music generation
        if any(w in text_lower for w in ["music", "song", "beat", "track", "sing", "rap"]):
            return {"type": "music_generation", "query": text}
        
        # Video generation
        if any(w in text_lower for w in ["video", "animate", "motion", "clip"]):
            return {"type": "video_generation", "query": text}
        
        # Image generation
        if any(w in text_lower for w in ["image", "picture", "photo", "draw", "art"]):
            return {"type": "image_generation", "query": text}
        
        # Voice
        if any(w in text_lower for w in ["speak", "say", "voice", "talk", "read"]):
            return {"type": "voice_synthesis", "query": text}
        
        # Memory storage
        if any(w in text_lower for w in ["remember", "save", "store", "note"]):
            return {"type": "memory_store", "query": text}
        
        # Plugin activation
        if any(w in text_lower for w in ["open", "launch", "start", "switch to"]):
            return {"type": "plugin_activation", "query": text}
        
        return {"type": "conversation", "query": text}
    
    def _execute_intent(self, intent: dict, original: str) -> dict:
        """Execute a parsed intent."""
        itype = intent["type"]
        
        if itype == "file_retrieval":
            file_path = self.memory.find_file(intent["query"])
            if file_path:
                return {"response": f"Found: {file_path}", "file": file_path}
            return {"response": "I couldn't find that file. Can you describe it differently?"}
        
        elif itype == "music_generation":
            return {
                "response": "Switching to Suno Studio. What kind of music?",
                "action": "activate_plugin",
                "plugin": "suno-studio"
            }
        
        elif itype == "video_generation":
            return {
                "response": "Switching to Luma Studio. What do you want to create?",
                "action": "activate_plugin",
                "plugin": "luma-studio"
            }
        
        elif itype == "image_generation":
            return {
                "response": "Switching to Leonardo Studio. Describe the image.",
                "action": "activate_plugin",
                "plugin": "leonardo-studio"
            }
        
        elif itype == "voice_synthesis":
            text = original
            audio_path = self.voice.speak(text)
            if audio_path:
                return {"response": "Done.", "audio": audio_path}
            return {"response": "Voice synthesis is not configured. Set ELEVENLABS_API_KEY."}
        
        elif itype == "memory_store":
            # Extract key/value from query
            self.memory.remember(f"note_{int(time.time())}", original)
            return {"response": "Saved to memory."}
        
        elif itype == "plugin_activation":
            # Try to find which plugin
            for name in self.plugins:
                if name.lower() in original.lower():
                    return {
                        "response": f"Activating {name}.",
                        "action": "activate_plugin",
                        "plugin": name
                    }
            return {"response": "Which studio? Available: Suno, Luma, Leonardo, Runway, ElevenLabs."}
        
        else:
            # General conversation
            return {"response": "I'm listening. What would you like to create?"}
    
    def speak(self, text: str) -> Optional[str]:
        """Speak a response."""
        return self.voice.speak(text)
    
    def remember(self, key: str, value: Any):
        """Store a memory."""
        self.memory.remember(key, value)
    
    def recall(self, key: str) -> Optional[Any]:
        """Recall a memory."""
        return self.memory.recall(key)


# Singleton agent
agent = AutonomousAgent()
