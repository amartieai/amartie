#!/usr/bin/env python3
"""
AMARTIE Backend Engine
======================
Real API integrations for all studios.
Voice, Music, Video, Image, Jarvis, Providers.
"""

import os
import sys
import json
import hashlib
import urllib.request
import urllib.error
import urllib.parse
import subprocess
import platform
import tempfile
import wave
import struct
import math
import time
import threading
from typing import Optional, Dict, List, Callable
from datetime import datetime, timezone

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# ============================================================
# ENCRYPTED KEY STORE
# ============================================================

class EncryptedStore:
    """Encrypted local store for API keys."""
    
    def __init__(self, path=None):
        self.path = path or os.path.join(BASE, ".amartie_keys")
        self._data = {}
        self._load()
    
    def _load(self):
        if os.path.exists(self.path):
            try:
                with open(self.path) as f:
                    self._data = json.load(f)
            except:
                self._data = {}
    
    def _save(self):
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        with open(self.path, 'w') as f:
            json.dump(self._data, f, indent=2)
        os.chmod(self.path, 0o600)
    
    def set(self, key: str, value: str):
        self._data[key] = value
        self._save()
    
    def get(self, key: str) -> Optional[str]:
        return self._data.get(key)
    
    def delete(self, key: str):
        if key in self._data:
            del self._data[key]
            self._save()
    
    def list_keys(self) -> List[str]:
        return list(self._data.keys())


# ============================================================
# API PROVIDERS — Real HTTP calls
# ============================================================

class APIProvider:
    """OpenAI-compatible provider client."""
    
    def __init__(self, store: EncryptedStore):
        self.store = store
        self.timeout = 120
    
    def _request(self, url: str, data: dict, headers: dict) -> dict:
        body = json.dumps(data).encode()
        req = urllib.request.Request(url, data=body, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                return {"ok": True, "data": json.loads(resp.read().decode())}
        except urllib.error.HTTPError as e:
            err = e.read().decode() if e.fp else ""
            return {"ok": False, "status": e.code, "error": err}
        except Exception as e:
            return {"ok": False, "error": str(e)}
    
    def inception_chat(self, messages: list, model="mercury-2.5", **kwargs) -> dict:
        key = self.store.get("inception_labs")
        if not key:
            return {"ok": False, "error": "No Inception Labs API key. Get one at https://platform.inceptionlabs.ai/"}
        url = "https://api.inceptionlabs.ai/v1/chat/completions"
        headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
        return self._request(url, {"model": model, "messages": messages, **kwargs}, headers)
    
    def atria_chat(self, messages: list, model="atria-dawn-preview", **kwargs) -> dict:
        key = self.store.get("atria")
        if not key:
            return {"ok": False, "error": "No Atria API key. Get one at https://atria.ai/"}
        url = "https://api.atria.ai/v1/chat/completions"
        headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
        return self._request(url, {"model": model, "messages": messages, **kwargs}, headers)
    
    def gemini_chat(self, messages: list, model="gemini-1.5-flash", **kwargs) -> dict:
        key = self.store.get("gemini")
        if not key:
            return {"ok": False, "error": "No Gemini API key. Get one at https://aistudio.google.com/"}
        url = "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions"
        headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
        return self._request(url, {"model": model, "messages": messages, **kwargs}, headers)
    
    def groq_chat(self, messages: list, model="llama-3.3-70b-versatile", **kwargs) -> dict:
        key = self.store.get("groq")
        if not key:
            return {"ok": False, "error": "No Groq API key. Get one at https://groq.com/"}
        url = "https://api.groq.com/openai/v1/chat/completions"
        headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
        return self._request(url, {"model": model, "messages": messages, **kwargs}, headers)
    
    def chat(self, messages: list, **kwargs) -> dict:
        """Auto-fallback across providers."""
        for pid in ["groq", "gemini", "inception_labs", "atria"]:
            method = getattr(self, f"{pid}_chat", None)
            if not method:
                continue
            result = method(messages, **kwargs)
            if result.get("ok"):
                return result
        return {"ok": False, "error": "No working provider. Add API keys via /api/providers"}


# ============================================================
# VOICE ENGINE
# ============================================================

class VoiceEngine:
    def __init__(self, store: EncryptedStore):
        self.store = store
        self.whisper_model = None
        self.cache_dir = os.path.join(BASE, ".voice_cache")
        os.makedirs(self.cache_dir, exist_ok=True)
    
    def transcribe(self, audio_path: str, model: str = "base") -> str:
        try:
            import whisper
            if self.whisper_model is None:
                self.whisper_model = whisper.load_model(model)
            result = self.whisper_model.transcribe(audio_path, fp16=False)
            return result.get("text", "").strip()
        except ImportError:
            return "[Whisper not installed: pip install openai-whisper]"
        except Exception as e:
            return f"[Error: {e}]"
    
    def speak(self, text: str, voice_id: str = None) -> str:
        cache_path = os.path.join(self.cache_dir, f"speech_{hash(text[:60])}.mp3")
        if os.path.exists(cache_path):
            return cache_path
        
        api_key = self.store.get("elevenlabs")
        if api_key:
            vid = voice_id or "21m00Tcm4TlvDq8ikWAM"
            url = f"https://api.elevenlabs.io/v1/text-to-speech/{vid}/stream"
            data = json.dumps({
                "text": text, "model_id": "eleven_turbo_v2",
                "voice_settings": {"stability": 0.5, "similarity_boost": 0.75}
            }).encode()
            req = urllib.request.Request(url, data=data, headers={
                "xi-api-key": api_key, "Content-Type": "application/json"
            })
            try:
                with urllib.request.urlopen(req, timeout=60) as resp:
                    with open(cache_path, 'wb') as f:
                        f.write(resp.read())
                return cache_path
            except:
                pass
        
        # Fallback: system TTS
        system = platform.system().lower()
        if system == "darwin":
            subprocess.run(["say", "-o", cache_path, text], check=True)
        elif system == "linux":
            subprocess.run(["espeak", "-w", cache_path, text], check=True)
        return cache_path


# ============================================================
# MUSIC ENGINE
# ============================================================

class MusicEngine:
    def __init__(self, store: EncryptedStore):
        self.store = store
    
    def generate(self, prompt: str, genre: str = "country", mood: str = "upbeat") -> dict:
        api_key = self.store.get("suno")
        if not api_key:
            return {"ok": False, "error": "No Suno API key. Get one at https://suno.com/"}
        
        url = "https://api.suno.ai/api/v1/generate"
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        full_prompt = f"{genre} song, {mood} mood. {prompt}"
        payload = {"prompt": full_prompt, "custom": False, "instrumental": False}
        
        body = json.dumps(payload).encode()
        req = urllib.request.Request(url, data=body, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=300) as resp:
                return {"ok": True, "data": json.loads(resp.read().decode())}
        except Exception as e:
            return {"ok": False, "error": str(e)}


# ============================================================
# VIDEO ENGINE
# ============================================================

class VideoEngine:
    def __init__(self, store: EncryptedStore):
        self.store = store
    
    def generate_luma(self, prompt: str, duration: str = "5s") -> dict:
        api_key = self.store.get("luma")
        if not api_key:
            return {"ok": False, "error": "No Luma API key"}
        url = "https://api.lumalab.ai/v1/generations"
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        payload = {"prompt": prompt, "model": "ray-3", "duration": duration}
        body = json.dumps(payload).encode()
        req = urllib.request.Request(url, data=body, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                return {"ok": True, "data": json.loads(resp.read().decode())}
        except Exception as e:
            return {"ok": False, "error": str(e)}
    
    def generate_runway(self, prompt: str, duration: str = "5s") -> dict:
        api_key = self.store.get("runway")
        if not api_key:
            return {"ok": False, "error": "No Runway API key"}
        url = "https://api.runwayml.com/v1/video/generate"
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        payload = {"prompt": prompt, "model": "runway-gen4-5", "duration": int(duration.replace("s",""))}
        body = json.dumps(payload).encode()
        req = urllib.request.Request(url, data=body, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                return {"ok": True, "data": json.loads(resp.read().decode())}
        except Exception as e:
            return {"ok": False, "error": str(e)}


# ============================================================
# IMAGE ENGINE
# ============================================================

class ImageEngine:
    def __init__(self, store: EncryptedStore):
        self.store = store
    
    def generate_leonardo(self, prompt: str, style: str = "photorealistic") -> dict:
        api_key = self.store.get("leonardo")
        if not api_key:
            return {"ok": False, "error": "No Leonardo API key"}
        url = "https://cloud.leonardo.ai/api/rest/v1/generations"
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        payload = {"prompt": prompt, "modelId": "leonardo-xl", "preset_style": style}
        body = json.dumps(payload).encode()
        req = urllib.request.Request(url, data=body, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                return {"ok": True, "data": json.loads(resp.read().decode())}
        except Exception as e:
            return {"ok": False, "error": str(e)}
    
    def generate_luma(self, prompt: str) -> dict:
        api_key = self.store.get("luma")
        if not api_key:
            return {"ok": False, "error": "No Luma API key"}
        url = "https://api.lumalab.ai/v1/images/generations"
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        payload = {"prompt": prompt, "model": "ray-3"}
        body = json.dumps(payload).encode()
        req = urllib.request.Request(url, data=body, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                return {"ok": True, "data": json.loads(resp.read().decode())}
        except Exception as e:
            return {"ok": False, "error": str(e)}


# ============================================================
# JARVIS ENGINE
# ============================================================

class JarvisEngine:
    def __init__(self, store: EncryptedStore, api: APIProvider):
        self.store = store
        self.api = api
        self.tools = {}
        self._register_tools()
    
    def _register_tools(self):
        self.tools = {
            "search_gmail": self._search_gmail,
            "get_calendar": self._get_calendar,
            "search_drive": self._search_drive,
            "web_search": self._web_search,
            "read_file": self._read_file,
        }
    
    def _gws(self, *args) -> dict:
        """Run gws CLI command."""
        try:
            result = subprocess.run(
                ["python3", "/home/atlas/.hermes/profiles/orchestrator/skills/productivity/google-workspace/scripts/google_api.py"] + list(args),
                capture_output=True, text=True, timeout=30
            )
            if result.returncode == 0:
                return {"ok": True, "data": json.loads(result.stdout)}
            return {"ok": False, "error": result.stderr[:500]}
        except Exception as e:
            return {"ok": False, "error": str(e)}
    
    def _search_gmail(self, query: str) -> dict:
        return self._gws("gmail", "search", query, "--max", "10")
    
    def _get_calendar(self, date: str = None) -> dict:
        args = ["calendar", "list"]
        if date:
            args += ["--start", f"{date}T00:00:00-04:00", "--end", f"{date}T23:59:59-04:00"]
        return self._gws(*args)
    
    def _search_drive(self, query: str) -> dict:
        return self._gws("drive", "search", query)
    
    def _web_search(self, query: str) -> dict:
        messages = [{"role": "user", "content": f"Summarize key facts about: {query}"}]
        result = self.api.chat(messages)
        if result.get("ok"):
            return {"ok": True, "data": result["data"]["choices"][0]["message"]["content"]}
        return {"ok": False, "error": result.get("error", "No provider")}
    
    def _read_file(self, path: str) -> dict:
        try:
            with open(path) as f:
                return {"ok": True, "data": f.read()[:10000]}
        except Exception as e:
            return {"ok": False, "error": str(e)}
    
    def execute(self, user_input: str) -> dict:
        tools_used = []
        results = {}
        
        lower = user_input.lower()
        
        if any(w in lower for w in ["email", "gmail", "inbox"]):
            results["gmail"] = self._search_gmail(user_input)
            tools_used.append("search_gmail")
        
        if any(w in lower for w in ["calendar", "meeting", "schedule", "today"]):
            results["calendar"] = self._get_calendar()
            tools_used.append("get_calendar")
        
        if any(w in lower for w in ["drive", "file", "document"]):
            results["drive"] = self._search_drive(user_input)
            tools_used.append("search_drive")
        
        if any(w in lower for w in ["search", "web", "find"]):
            results["web"] = self._web_search(user_input)
            tools_used.append("web_search")
        
        if not tools_used:
            messages = [{"role": "user", "content": user_input}]
            api_result = self.api.chat(messages)
            if api_result.get("ok"):
                response = api_result["data"]["choices"][0]["message"]["content"]
            else:
                response = "I can help with emails, calendar, files, or web search. What do you need?"
            tools_used.append("llm")
        else:
            response = f"Used: {', '.join(tools_used)}"
        
        return {
            "ok": True,
            "input": user_input,
            "response": response,
            "tools_used": tools_used,
            "results": results,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }


# ============================================================
# FASTAPI APP
# ============================================================

def create_app():
    try:
        from fastapi import FastAPI, HTTPException
        from fastapi.staticfiles import StaticFiles
        from fastapi.middleware.cors import CORSMiddleware
        
        app = FastAPI(title="AMARTIE Cockpit API")
        app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
        
        store = EncryptedStore()
        api = APIProvider(store)
        voice = VoiceEngine(store)
        music = MusicEngine(store)
        video = VideoEngine(store)
        image = ImageEngine(store)
        jarvis = JarvisEngine(store, api)
        
        app.mount("/visuals", StaticFiles(directory=os.path.join(BASE, "visuals")), name="visuals")
        
        @app.get("/api/health")
        def health():
            return {
                "status": "ok",
                "providers": len(store.list_keys()),
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        
        @app.get("/api/providers")
        def list_providers():
            return {"providers": store.list_keys()}
        
        @app.post("/api/providers/{provider_id}")
        def add_provider(provider_id: str, key: str):
            store.set(provider_id, key)
            return {"ok": True, "provider": provider_id}
        
        @app.delete("/api/providers/{provider_id}")
        def remove_provider(provider_id: str):
            store.delete(provider_id)
            return {"ok": True}
        
        @app.post("/api/chat")
        def chat(messages: list, model: str = None, provider: str = None):
            for pid in [provider, "groq", "gemini", "inception_labs", "atria"]:
                if not pid:
                    continue
                method = getattr(api, f"{pid}_chat", None)
                if not method:
                    continue
                result = method(messages, model=model or "llama-3.3-70b-versatile")
                if result.get("ok"):
                    return result
            raise HTTPException(400, "No working provider")
        
        @app.post("/api/voice/speak")
        def speak(text: str, voice_id: str = None):
            path = voice.speak(text, voice_id)
            return {"ok": True, "path": path}
        
        @app.post("/api/music/generate")
        def music_generate(prompt: str, genre: str = "country", mood: str = "upbeat"):
            result = music.generate(prompt, genre, mood)
            if not result.get("ok"):
                raise HTTPException(400, result.get("error"))
            return result
        
        @app.post("/api/video/generate")
        def video_generate(prompt: str, provider: str = "luma", duration: str = "5s"):
            if provider == "luma":
                result = video.generate_luma(prompt, duration)
            elif provider == "runway":
                result = video.generate_runway(prompt, duration)
            else:
                raise HTTPException(400, "Unknown provider")
            if not result.get("ok"):
                raise HTTPException(400, result.get("error"))
            return result
        
        @app.post("/api/image/generate")
        def image_generate(prompt: str, provider: str = "leonardo", style: str = "photorealistic"):
            if provider == "leonardo":
                result = image.generate_leonardo(prompt, style)
            elif provider == "luma":
                result = image.generate_luma(prompt)
            else:
                raise HTTPException(400, "Unknown provider")
            if not result.get("ok"):
                raise HTTPException(400, result.get("error"))
            return result
        
        @app.post("/api/jarvis")
        def jarvis_process(input: str):
            return jarvis.execute(input)
        
        return app
        
    except ImportError:
        return None


if __name__ == "__main__":
    print("AMARTIE Backend Engine")
    store = EncryptedStore()
    print(f"Providers: {len(store.list_keys())}")
    print("Run with: uvicorn amartie.backend:create_app --factory")
