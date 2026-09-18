"""
Luma Studio Plugin
==================
AI image and video generation via Luma Dream Machine API.
Activates as a cockpit plugin.
"""

import json
import os
import urllib.request
import urllib.parse
import time
from typing import Optional

# Plugin metadata (read by cockpit)
PLUGIN_NAME = "Luma Studio"
PLUGIN_VERSION = "0.1.0"
PLUGIN_DESCRIPTION = "AI image and video generation via Luma Dream Machine"
STUDIO_TYPE = "video_generation"

# API Configuration
LUMA_API_BASE = "https://api.lumalabs.ai/dream-machine/v1"
API_KEY = os.environ.get("LUMA_API_KEY", "")


def render(config: dict = None) -> dict:
    """
    Render the plugin UI for the cockpit.
    Returns HTML/JSON that the cockpit displays.
    """
    return {
        "name": PLUGIN_NAME,
        "version": PLUGIN_VERSION,
        "type": STUDIO_TYPE,
        "html": get_studio_html(),
        "scripts": get_studio_scripts(),
        "config": config or {}
    }


def handle(action: str, data: dict) -> dict:
    """Handle actions from the cockpit UI."""
    if action == "generate_image":
        return generate_image(
            prompt=data.get("prompt", ""),
            model=data.get("model", "ray-2"),
            resolution=data.get("resolution", "1024x1024")
        )
    elif action == "generate_video":
        return generate_video(
            prompt=data.get("prompt", ""),
            model=data.get("model", "ray-2"),
            resolution=data.get("resolution", "720p"),
            duration=data.get("duration", 5)
        )
    elif action == "check_status":
        return check_generation_status(data.get("generation_id", ""))
    elif action == "config":
        return {"api_key_set": bool(API_KEY)}
    else:
        return {"error": f"Unknown action: {action}"}


def generate_image(prompt: str, model: str = "ray-2", resolution: str = "1024x1024") -> dict:
    """Generate an image via Luma API."""
    if not API_KEY:
        return {"error": "LUMA_API_KEY not set. Set environment variable."}
    
    try:
        url = f"{LUMA_API_BASE}/generations/image"
        payload = json.dumps({
            "prompt": prompt,
            "model": model,
            "resolution": resolution
        }).encode()
        
        req = urllib.request.Request(
            url,
            data=payload,
            headers={
                "Authorization": f"Bearer {API_KEY}",
                "Content-Type": "application/json",
                "Accept": "application/json"
            },
            method="POST"
        )
        
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read())
            return {
                "status": "submitted",
                "generation_id": result.get("id"),
                "estimated_time": result.get("estimated_time", "unknown")
            }
    except Exception as e:
        return {"error": str(e)}


def generate_video(prompt: str, model: str = "ray-2", resolution: str = "720p", duration: int = 5) -> dict:
    """Generate a video via Luma API."""
    if not API_KEY:
        return {"error": "LUMA_API_KEY not set. Set environment variable."}
    
    try:
        url = f"{LUMA_API_BASE}/generations/video"
        payload = json.dumps({
            "prompt": prompt,
            "model": model,
            "resolution": resolution,
            "duration": duration
        }).encode()
        
        req = urllib.request.Request(
            url,
            data=payload,
            headers={
                "Authorization": f"Bearer {API_KEY}",
                "Content-Type": "application/json",
                "Accept": "application/json"
            },
            method="POST"
        )
        
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read())
            return {
                "status": "submitted",
                "generation_id": result.get("id"),
                "estimated_time": result.get("estimated_time", "unknown")
            }
    except Exception as e:
        return {"error": str(e)}


def check_generation_status(generation_id: str) -> dict:
    """Check the status of a generation."""
    if not API_KEY:
        return {"error": "LUMA_API_KEY not set."}
    
    try:
        url = f"{LUMA_API_BASE}/generations/{generation_id}"
        req = urllib.request.Request(
            url,
            headers={
                "Authorization": f"Bearer {API_KEY}",
                "Accept": "application/json"
            }
        )
        
        with urllib.request.urlopen(req, timeout=15) as resp:
            result = json.loads(resp.read())
            return {
                "status": result.get("state", "unknown"),
                "progress": result.get("progress", 0),
                "result_url": result.get("assets", {}).get("video", "") if result.get("state") == "completed" else None
            }
    except Exception as e:
        return {"error": str(e)}


def poll_until_complete(generation_id: str, max_wait: int = 120) -> dict:
    """Poll a generation until it completes or fails."""
    start = time.time()
    while time.time() - start < max_wait:
        status = check_generation_status(generation_id)
        if status.get("status") == "completed":
            return status
        if status.get("status") == "failed":
            return status
        time.sleep(5)
    return {"error": "Timeout waiting for generation"}


def get_studio_html() -> str:
    """Get the studio UI HTML."""
    return """
<div class="studio-video">
  <h2>Luma Studio</h2>
  <p class="muted">AI image &amp; video generation via Dream Machine</p>
  <div class="row">
    <label>Prompt</label>
    <textarea id="luma-prompt" rows="3" placeholder="Describe what you want to create..."></textarea>
  </div>
  <div class="row">
    <label>Type</label>
    <select id="luma-type">
      <option value="image">Image</option>
      <option value="video">Video</option>
    </select>
  </div>
  <div class="row">
    <label>Model</label>
    <select id="luma-model">
      <option value="ray-2">Ray 2</option>
      <option value="ray-3">Ray 3</option>
    </select>
  </div>
  <div class="row video-only">
    <label>Duration (seconds)</label>
    <input type="range" id="luma-duration" min="1" max="10" value="5">
    <span id="luma-duration-val">5s</span>
  </div>
  <button id="luma-generate" onclick="lumaGenerate()">Generate</button>
  <div id="luma-status"></div>
  <div id="luma-result"></div>
</div>
"""


def get_studio_scripts() -> str:
    """Get the studio UI JavaScript."""
    return """
async function lumaGenerate() {
  const prompt = document.getElementById('luma-prompt').value;
  const type = document.getElementById('luma-type').value;
  const model = document.getElementById('luma-model').value;
  const duration = document.getElementById('luma-duration').value;
  const status = document.getElementById('luma-status');
  const result = document.getElementById('luma-result');
  
  status.textContent = 'Submitting...';
  result.innerHTML = '';
  
  const action = type === 'video' ? 'generate_video' : 'generate_image';
  const payload = { prompt, model };
  if (type === 'video') payload.duration = parseInt(duration);
  
  const res = await cockpit.pluginAction('luma-studio', action, payload);
  
  if (res.error) {
    status.textContent = 'Error: ' + res.error;
    return;
  }
  
  status.textContent = 'Generation submitted: ' + res.generation_id;
  
  // Poll for completion
  let done = false;
  while (!done) {
    await new Promise(r => setTimeout(r, 3000));
    const poll = await cockpit.pluginAction('luma-studio', 'check_status', { generation_id: res.generation_id });
    if (poll.status === 'completed') {
      status.textContent = 'Complete!';
      if (poll.result_url) {
        if (type === 'video') {
          result.innerHTML = '<video controls src="' + poll.result_url + '"></video>';
        } else {
          result.innerHTML = '<img src="' + poll.result_url + '" />';
        }
      }
      done = true;
    } else if (poll.status === 'failed') {
      status.textContent = 'Failed: ' + (poll.error || 'Unknown error');
      done = true;
    } else {
      status.textContent = 'Status: ' + poll.status;
    }
  }
}
"""
