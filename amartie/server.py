#!/usr/bin/env python3
"""
AMARTIE Simple Server
======================
Zero-dependency HTTP server for the backend API.
Uses only Python stdlib — no FastAPI/uvicorn needed.
"""

import json
import os
import sys
from datetime import datetime, timezone
from http.server import HTTPServer, SimpleHTTPRequestHandler
from socketserver import ThreadingMixIn
from urllib import error as urllib_error
from urllib import parse as urllib_parse
from urllib import request as urllib_request
from urllib.parse import urlparse

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)

from amartie.backend import (
    APIProvider,
    EncryptedStore,
    ImageEngine,
    JarvisEngine,
    MusicEngine,
    VideoEngine,
    VoiceEngine,
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

    def _repo_target(self):
        owner = os.getenv("GITHUB_REPO_OWNER", "amartieai")
        repo = os.getenv("GITHUB_REPO_NAME", "amartie")
        return owner, repo

    def _github_headers(self):
        headers = {
            "Accept": "application/vnd.github+json",
            "User-Agent": "AMARTIE-local-dashboard",
        }
        token = os.getenv("GITHUB_TOKEN")
        if token:
            headers["Authorization"] = f"Bearer {token}"
        return headers

    def _github_get(self, path, params=None):
        owner, repo = self._repo_target()
        query = ""
        if params:
            query = "?" + urllib_parse.urlencode(params)
        url = f"https://api.github.com{path.format(owner=owner, repo=repo)}{query}"
        req = urllib_request.Request(url, headers=self._github_headers())
        try:
            with urllib_request.urlopen(req, timeout=15) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib_error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            try:
                payload = json.loads(body)
            except json.JSONDecodeError:
                payload = {"message": body or str(exc)}
            return {"error": True, "status": exc.code, "message": payload.get("message", str(exc))}
        except Exception as exc:
            return {"error": True, "message": str(exc)}

    def _github_metrics(self):
        owner, repo = self._repo_target()
        data = self._github_get("/repos/{owner}/{repo}")
        if data.get("error"):
            return {
                "ok": False,
                "owner": owner,
                "repo": repo,
                "message": data.get("message", "Unable to fetch repository metadata."),
            }
        return {
            "ok": True,
            "owner": owner,
            "repo": repo,
            "description": data.get("description"),
            "default_branch": data.get("default_branch"),
            "html_url": data.get("html_url"),
            "pushed_at": data.get("pushed_at"),
            "created_at": data.get("created_at"),
            "stargazers_count": data.get("stargazers_count", 0),
            "forks_count": data.get("forks_count", 0),
            "watchers_count": data.get("subscribers_count", 0),
            "open_issues_count": data.get("open_issues_count", 0),
            "visibility": data.get("visibility"),
            "archived": data.get("archived", False),
        }

    def _github_traffic(self):
        owner, repo = self._repo_target()
        views = self._github_get("/repos/{owner}/{repo}/traffic/views")
        clones = self._github_get("/repos/{owner}/{repo}/traffic/clones")
        return {
            "ok": not views.get("error") and not clones.get("error"),
            "owner": owner,
            "repo": repo,
            "views": {
                "count": views.get("count", 0),
                "uniques": views.get("uniques", 0),
                "items": views.get("views", []),
            },
            "clones": {
                "count": clones.get("count", 0),
                "uniques": clones.get("uniques", 0),
                "items": clones.get("clones", []),
            },
            "requires_token": bool(views.get("error") or clones.get("error")),
            "message": (
                "Traffic endpoints are rate-limited and may require a GitHub token. "
                "This dashboard remains localhost-only."
                if (views.get("error") or clones.get("error"))
                else "Traffic available."
            ),
        }

    def _github_events(self):
        owner, repo = self._repo_target()
        pulls = self._github_get("/repos/{owner}/{repo}/pulls", {"state": "all", "per_page": 5})
        commits = self._github_get("/repos/{owner}/{repo}/commits", {"per_page": 5})

        normalized = []
        for item in pulls if isinstance(pulls, list) else []:
            normalized.append({
                "type": "pull_request",
                "title": item.get("title", "Untitled pull request"),
                "state": item.get("state", "unknown"),
                "updated_at": item.get("updated_at"),
                "html_url": item.get("html_url"),
            })

        for item in commits if isinstance(commits, list) else []:
            normalized.append({
                "type": "commit",
                "title": item.get("commit", {}).get("message", "Untitled commit").split("\n", 1)[0],
                "updated_at": item.get("commit", {}).get("committer", {}).get("date"),
                "html_url": item.get("html_url"),
            })

        normalized.sort(key=lambda x: x.get("updated_at") or "", reverse=True)
        return {
            "ok": True,
            "owner": owner,
            "repo": repo,
            "items": normalized[:10],
        }

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path

        if path == "/api/health":
            return self._json(200, {
                "status": "ok",
                "providers": len(self.store.list_keys()),
                "timestamp": self._now(),
            })

        if path == "/api/providers":
            return self._json(200, {"providers": self.store.list_keys()})

        if path == "/api/jarvis/history":
            return self._json(200, {"history": []})

        if path == "/api/github/metrics":
            return self._json(200, self._github_metrics())

        if path == "/api/github/traffic":
            return self._json(200, self._github_traffic())

        if path == "/api/github/events":
            return self._json(200, self._github_events())

        # Static files — serve from visuals/
        if path == "/" or path == "":
            filepath = os.path.join(BASE, "visuals", "landing.html")
        elif path.startswith("/visuals/"):
            filepath = os.path.join(BASE, "visuals", path[len("/visuals/") :])
        else:
            filepath = os.path.join(BASE, "visuals", path.lstrip("/"))

        if os.path.exists(filepath):
            return self._serve_file(filepath)
        return self._json(404, {"error": "not found"})

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path

        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length) if length else b"{}"
        try:
            data = json.loads(body)
        except Exception:
            data = {}

        if path == "/api/chat":
            messages = data.get("messages", [])
            result = self.api.chat(messages)
            if result.get("ok"):
                return self._json(200, result)
            return self._json(400, result)

        if path == "/api/voice/speak":
            text = data.get("text", "")
            path_file = self.voice.speak(text, data.get("voice_id"))
            return self._json(200, {"ok": True, "path": path_file})

        if path == "/api/music/generate":
            result = self.music.generate(
                data.get("prompt", ""),
                data.get("genre", "country"),
                data.get("mood", "upbeat"),
            )
            if result.get("ok"):
                return self._json(200, result)
            return self._json(400, result)

        if path == "/api/video/generate":
            provider = data.get("provider", "luma")
            if provider == "luma":
                result = self.video.generate_luma(data.get("prompt", ""), data.get("duration", "5s"))
            else:
                result = self.video.generate_runway(data.get("prompt", ""), data.get("duration", "5s"))
            if result.get("ok"):
                return self._json(200, result)
            return self._json(400, result)

        if path == "/api/image/generate":
            provider = data.get("provider", "leonardo")
            if provider == "leonardo":
                result = self.image.generate_leonardo(data.get("prompt", ""), data.get("style", "photorealistic"))
            else:
                result = self.image.generate_luma(data.get("prompt", ""))
            if result.get("ok"):
                return self._json(200, result)
            return self._json(400, result)

        if path == "/api/jarvis":
            result = self.jarvis.execute(data.get("input", ""))
            return self._json(200, result)

        if path.startswith("/api/providers/"):
            provider_id = path.split("/")[-1]
            if not provider_id:
                return self._json(400, {"error": "no provider id"})
            key = data.get("key", "")
            if key:
                self.store.set(provider_id, key)
                return self._json(200, {"ok": True})
            return self._json(400, {"error": "no key provided"})

        return self._json(404, {"error": "unknown endpoint"})

    def do_DELETE(self):
        parsed = urlparse(self.path)
        path = parsed.path
        if path.startswith("/api/providers/"):
            provider_id = path.split("/")[-1]
            self.store.delete(provider_id)
            return self._json(200, {"ok": True})
        return self._json(404, {"error": "unknown endpoint"})

    def _json(self, code, data):
        resp = json.dumps(data).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(resp)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(resp)

    def _serve_file(self, path):
        ct = "text/html"
        if path.endswith(".css"):
            ct = "text/css"
        elif path.endswith(".js"):
            ct = "application/javascript"
        elif path.endswith(".mjs"):
            ct = "application/javascript"
        elif path.endswith(".json"):
            ct = "application/json"
        elif path.endswith(".png"):
            ct = "image/png"
        elif path.endswith(".svg"):
            ct = "image/svg+xml"
        elif path.endswith(".ico"):
            ct = "image/x-icon"
        elif path.endswith(".woff2"):
            ct = "font/woff2"
        elif path.endswith(".woff"):
            ct = "font/woff"
        try:
            with open(path, "rb") as f:
                content = f.read()
            self.send_response(200)
            self.send_header("Content-Type", ct)
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content)
        except Exception as exc:
            self._json(500, {"error": str(exc)})

    @staticmethod
    def _now():
        return datetime.now(timezone.utc).isoformat()


class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    daemon_threads = True
    allow_reuse_address = True


def run_server(port=8715):
    server = ThreadedHTTPServer(("127.0.0.1", port), AMARTIEHandler)
    print(f"AMARTIE threaded server running at http://127.0.0.1:{port}")
    print(f"Landing page: http://127.0.0.1:{port}/visuals/landing.html")
    print(f"Cockpit: http://127.0.0.1:{port}/visuals/cockpit.html")
    server.serve_forever()


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8715
    run_server(port)
