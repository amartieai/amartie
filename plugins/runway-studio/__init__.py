"""
Runway Studio Plugin
====================
AI video generation via RunwayML API.
"""

import json
import os
import urllib.request

PLUGIN_NAME = "Runway Studio"
PLUGIN_VERSION = "0.1.0"
PLUGIN_DESCRIPTION = "AI video generation via RunwayML"
STUDIO_TYPE = "video_generation"

RUNWAY_API_BASE = "https://api.runwayml.com/v1"
API_KEY = os.environ.get("RUNWAY_API_KEY", "")


def render(config=None):
    return {"name": PLUGIN_NAME, "version": PLUGIN_VERSION, "type": STUDIO_TYPE, "html": get_html(), "scripts": get_js()}


def handle(action, data):
    if action == "text_to_video":
        return gen_video(data)
    elif action == "image_to_video":
        return gen_image_video(data)
    elif action == "status":
        return check_status(data.get("task_id", ""))
    return {"error": "unknown action"}


def gen_video(data):
    if not API_KEY:
        return {"error": "RUNWAY_API_KEY not set"}
    try:
        url = f"{RUNWAY_API_BASE}/video"
        payload = json.dumps({"promptText": data.get("prompt", ""), "model": "gen4.5", "ratio": "1280:720", "duration": data.get("duration", 5)}).encode()
        req = urllib.request.Request(url, data=payload, headers={"Authorization": API_KEY, "Content-Type": "application/json", "Accept": "application/json"}, method="POST")
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read())
    except Exception as e:
        return {"error": str(e)}


def gen_image_video(data):
    if not API_KEY:
        return {"error": "RUNWAY_API_KEY not set"}
    try:
        url = f"{RUNWAY_API_BASE}/video"
        payload = json.dumps({"promptImage": data.get("image_url", ""), "promptText": data.get("prompt", ""), "model": "gen4.5", "ratio": "1280:720", "duration": data.get("duration", 5)}).encode()
        req = urllib.request.Request(url, data=payload, headers={"Authorization": API_KEY, "Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read())
    except Exception as e:
        return {"error": str(e)}


def check_status(task_id):
    if not API_KEY:
        return {"error": "RUNWAY_API_KEY not set"}
    try:
        url = f"{RUNWAY_API_BASE}/task/{task_id}"
        req = urllib.request.Request(url, headers={"Authorization": API_KEY, "Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read())
    except Exception as e:
        return {"error": str(e)}


def get_html():
    return """
<div class="studio-video">
  <h2>Runway Studio</h2>
  <p class="muted">AI video generation via RunwayML Gen-4.5</p>
  <div class="row"><label>Prompt</label><textarea id="rw-prompt" rows="3"></textarea></div>
  <div class="row"><label>Source</label><select id="rw-source"><option value="text">Text to Video</option><option value="image">Image to Video</option></select></div>
  <div class="row" id="rw-image-row" style="display:none"><label>Image URL</label><input type="text" id="rw-image" placeholder="https://..."></div>
  <div class="row"><label>Duration (s)</label><input type="number" id="rw-duration" value="5" min="1" max="12"></div>
  <button onclick="rwGenerate()">Generate</button>
  <div id="rw-status"></div>
  <div id="rw-result"></div>
</div>
"""


def get_js():
    return """
async function rwGenerate() {
  const source = document.getElementById('rw-source').value;
  const action = source === 'text' ? 'text_to_video' : 'image_to_video';
  const data = { prompt: document.getElementById('rw-prompt').value, duration: parseInt(document.getElementById('rw-duration').value) };
  if (source === 'image') data.image_url = document.getElementById('rw-image').value;
  const res = await cockpit.pluginAction('runway-studio', action, data);
  if (res.error) { document.getElementById('rw-status').textContent = 'Error: ' + res.error; return; }
  document.getElementById('rw-status').textContent = 'Processing...';
}
"""
