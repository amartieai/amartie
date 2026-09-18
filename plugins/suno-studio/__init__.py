"""
Suno Studio Plugin
==================
AI music generation via Suno API.
"""

import json
import os
import urllib.request
import time

PLUGIN_NAME = "Suno Studio"
PLUGIN_VERSION = "0.1.0"
PLUGIN_DESCRIPTION = "AI music generation via Suno"
STUDIO_TYPE = "music_generation"

SUNO_API_BASE = "https://api.aimusicapi.ai/v1/suno"
API_KEY = os.environ.get("SUNO_API_KEY", "")


def render(config=None):
    return {"name": PLUGIN_NAME, "version": PLUGIN_VERSION, "type": STUDIO_TYPE, "html": get_html(), "scripts": get_js()}


def handle(action, data):
    if action == "generate":
        return generate(data)
    elif action == "status":
        return check_status(data.get("job_id", ""))
    elif action == "lyrics":
        return generate_lyrics(data.get("prompt", ""))
    return {"error": "unknown action"}


def generate(data):
    if not API_KEY:
        return {"error": "SUNO_API_KEY not set"}
    try:
        url = f"{SUNO_API_BASE}/create"
        payload = json.dumps({
            "prompt": data.get("prompt", ""),
            "tags": data.get("tags", ""),
            "title": data.get("title", "Untitled"),
            "model": data.get("model", "suno-v5"),
            "wait_audio": False
        }).encode()
        req = urllib.request.Request(url, data=payload, headers={
            "Authorization": f"Bearer {API_KEY}",
            "Content-Type": "application/json"
        }, method="POST")
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read())
    except Exception as e:
        return {"error": str(e)}


def check_status(job_id):
    if not API_KEY:
        return {"error": "SUNO_API_KEY not set"}
    try:
        url = f"{SUNO_API_BASE}/jobs/{job_id}"
        req = urllib.request.Request(url, headers={"Authorization": f"Bearer {API_KEY}"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read())
    except Exception as e:
        return {"error": str(e)}


def generate_lyrics(prompt):
    if not API_KEY:
        return {"error": "SUNO_API_KEY not set"}
    try:
        url = f"{SUNO_API_BASE}/lyrics"
        payload = json.dumps({"prompt": prompt}).encode()
        req = urllib.request.Request(url, data=payload, headers={
            "Authorization": f"Bearer {API_KEY}",
            "Content-Type": "application/json"
        }, method="POST")
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read())
    except Exception as e:
        return {"error": str(e)}


def get_html():
    return """
<div class="studio-music">
  <h2>Suno Studio</h2>
  <p class="muted">AI music generation — vocals, instrumentals, full songs</p>
  <div class="row"><label>Prompt</label><textarea id="suno-prompt" rows="3" placeholder="Describe the song you want..."></textarea></div>
  <div class="row"><label>Tags (comma separated)</label><input type="text" id="suno-tags" placeholder="rock, blues, reggae, classical"></div>
  <div class="row"><label>Title</label><input type="text" id="suno-title" placeholder="My Song"></div>
  <div class="row"><label>Model</label><select id="suno-model">
    <option value="suno-v5">Suno V5</option>
    <option value="suno-v6">Suno V6</option>
    <option value="suno-v6-mini">Suno V6 Mini (fast)</option>
  </select></div>
  <button onclick="sunoGenerate()">Generate</button>
  <div id="suno-status"></div>
  <div id="suno-result"></div>
</div>
"""


def get_js():
    return """
async function sunoGenerate() {
  const btn = document.querySelector('.studio-music button');
  btn.disabled = true;
  document.getElementById('suno-status').textContent = 'Generating...';
  const res = await cockpit.pluginAction('suno-studio', 'generate', {
    prompt: document.getElementById('suno-prompt').value,
    tags: document.getElementById('suno-tags').value,
    title: document.getElementById('suno-title').value,
    model: document.getElementById('suno-model').value
  });
  if (res.error) { document.getElementById('suno-status').textContent = 'Error: ' + res.error; btn.disabled = false; return; }
  document.getElementById('suno-status').textContent = 'Processing...';
  let done = false;
  while (!done) {
    await new Promise(r => setTimeout(r, 3000));
    const poll = await cockpit.pluginAction('suno-studio', 'status', { job_id: res.jobId });
    if (poll.status === 'COMPLETED') {
      document.getElementById('suno-status').textContent = 'Done!';
      const aud = poll.result || [];
      document.getElementById('suno-result').innerHTML = aud.map(a => '<audio controls src="' + a.audioUrl + '"></audio>').join('');
      done = true;
    } else if (poll.status === 'FAILED') {
      document.getElementById('suno-status').textContent = 'Failed: ' + (poll.error || 'Unknown');
      done = true;
    }
  }
  btn.disabled = false;
}
"""
