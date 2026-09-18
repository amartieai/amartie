#!/usr/bin/env python3
"""
AMARTIE Simple Server
======================
Zero-dependency HTTP server for the backend API.
Uses only Python stdlib — no FastAPI/uvicorn needed.
"""

import os
import sys
import json
import threading
from http.server import HTTPServer, SimpleHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)

from amartie.backend import (
    EncryptedStore, APIProvider, VoiceEngine, MusicEngine,
    VideoEngine, ImageEngine, JarvisEngine
)

class AMARTIEHandler(SimpleHTTPRequestHandler):
    """Handle all AMARTIE API endpoints."""
    
    store = EncryptedStore()
    api = APIProvider(store)
    voice = VoiceEngine(store)
    music = MusicEngine(store)
    video = VideoEngine(store)
    image = ImageEngine(store)
    jarvis = JarvisEngine(store, api)
    
    def log_message(self, format, *args):
        """Silent logging to keep output clean."""
        pass
    
    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        
        # API endpoints
        if path == '/api/health':
            return self._json(200, {
                "status": "ok",
                "providers": len(self.store.list_keys()),
                "timestamp": self._now()
            })
        
        if path == '/api/providers':
            return self._json(200, {"providers": self.store.list_keys()})
        
        if path == '/api/jarvis/history':
            return self._json(200, {"history": []})
        
        # Static files — serve from visuals/
        if path == '/' or path == '':
            path = '/visuals/landing.html'
        if not path.startswith('/api'):
            if path.startswith('/visuals/'):
                filepath = os.path.join(BASE, path)
            else:
                filepath = os.path.join(BASE, 'visuals', path.lstrip('/'))
            if os.path.exists(filepath):
                return self._serve_file(filepath)
            return self._json(404, {"error": "not found"})
        
        return self._json(404, {"error": "unknown endpoint"})
    
    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path
        
        # Read body
        length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(length) if length else b'{}'
        try:
            data = json.loads(body)
        except:
            data = {}
        
        if path == '/api/chat':
            messages = data.get('messages', [])
            result = self.api.chat(messages)
            if result.get('ok'):
                return self._json(200, result)
            return self._json(400, result)
        
        if path == '/api/voice/speak':
            text = data.get('text', '')
            path_file = self.voice.speak(text, data.get('voice_id'))
            return self._json(200, {"ok": True, "path": path_file})
        
        if path == '/api/music/generate':
            result = self.music.generate(
                data.get('prompt', ''),
                data.get('genre', 'country'),
                data.get('mood', 'upbeat')
            )
            if result.get('ok'):
                return self._json(200, result)
            return self._json(400, result)
        
        if path == '/api/video/generate':
            provider = data.get('provider', 'luma')
            if provider == 'luma':
                result = self.video.generate_luma(data.get('prompt', ''), data.get('duration', '5s'))
            else:
                result = self.video.generate_runway(data.get('prompt', ''), data.get('duration', '5s'))
            if result.get('ok'):
                return self._json(200, result)
            return self._json(400, result)
        
        if path == '/api/image/generate':
            provider = data.get('provider', 'leonardo')
            if provider == 'leonardo':
                result = self.image.generate_leonardo(data.get('prompt', ''), data.get('style', 'photorealistic'))
            else:
                result = self.image.generate_luma(data.get('prompt', ''))
            if result.get('ok'):
                return self._json(200, result)
            return self._json(400, result)
        
        if path == '/api/jarvis':
            result = self.jarvis.execute(data.get('input', ''))
            return self._json(200, result)
        
        # Provider management
        if path.startswith('/api/providers/'):
            provider_id = path.split('/')[-1]
            if not provider_id:
                return self._json(400, {"error": "no provider id"})
            key = data.get('key', '')
            if key:
                self.store.set(provider_id, key)
                return self._json(200, {"ok": True})
            return self._json(400, {"error": "no key provided"})
        
        return self._json(404, {"error": "unknown endpoint"})
    
    def do_DELETE(self):
        parsed = urlparse(self.path)
        path = parsed.path
        if path.startswith('/api/providers/'):
            provider_id = path.split('/')[-1]
            self.store.delete(provider_id)
            return self._json(200, {"ok": True})
        return self._json(404, {"error": "unknown endpoint"})
    
    def _json(self, code, data):
        resp = json.dumps(data).encode()
        self.send_response(code)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(resp)))
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(resp)
    
    def _serve_file(self, path):
        ct = 'text/html'
        if path.endswith('.css'): ct = 'text/css'
        elif path.endswith('.js'): ct = 'application/javascript'
        elif path.endswith('.png'): ct = 'image/png'
        elif path.endswith('.svg'): ct = 'image/svg+xml'
        try:
            with open(path, 'rb') as f:
                content = f.read()
            self.send_response(200)
            self.send_header('Content-Type', ct)
            self.send_header('Content-Length', str(len(content)))
            self.end_headers()
            self.wfile.write(content)
        except Exception as e:
            self._json(500, {"error": str(e)})
    
    @staticmethod
    def _now():
        from datetime import datetime, timezone
        return datetime.now(timezone.utc).isoformat()


def run_server(port=8715):
    server = HTTPServer(('127.0.0.1', port), AMARTIEHandler)
    print(f"AMARTIE server running at http://127.0.0.1:{port}")
    print(f"Landing page: http://127.0.0.1:{port}/visuals/landing.html")
    print(f"Cockpit: http://127.0.0.1:{port}/visuals/cockpit.html")
    print(f"Health check: http://127.0.0.1:{port}/api/health")
    server.serve_forever()


if __name__ == '__main__':
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8715
    run_server(port)
