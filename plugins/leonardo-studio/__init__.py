"""
Leonardo Studio Plugin
======================
AI image and video generation via Leonardo.Ai API.
"""

import json
import os
import urllib.request
import time
from typing import Optional

PLUGIN_NAME = "Leonardo Studio"
PLUGIN_VERSION = "0.1.0"
PLUGIN_DESCRIPTION = "AI image & video generation via Leonardo.Ai"
STUDIO_TYPE = "image_generation"

LEONARDO_API_BASE = "https://cloud.leonardo.ai/api/rest/v1"
API_KEY = os.environ.get("LEONARDO_API_KEY", "")


def render(config: dict = None) -> dict:
    return {
        "name": PLUGIN_NAME,
        "version": PLUGIN_VERSION,
        "type": STUDIO_TYPE,
        "html": get_studio_html(),
        "scripts": get_studio_scripts(),
        "config": config or {}
    }


def handle(action: str, data: dict) -> dict:
    if action == "generate":
        return generate(data)
    elif action == "status":
        return check_status(data.get("generation_id", ""))
    else:
        return {"error": f"Unknown action: {action}"}


def generate(data: dict) -> dict:
    if not API_KEY:
        return {"error": "LEONARDO_API_KEY not set"}
    try:
        url = f"{LEONARDO_API_BASE}/generations"
        payload = json.dumps({
            "prompt": data.get("prompt", ""),
            "modelId": data.get("model", "6be09fc0-5fcc-4d01-8bce-1e5a8f7e0061"),
            "width": data.get("width", 1024),
            "height": data.get("height", 1024),
            "num_images": data.get("num_images", 1)
        }).encode()
        req = urllib.request.Request(url, data=payload, headers={
            "Authorization": f"Bearer {API_KEY}",
            "Content-Type": "application/json",
            "Accept": "application/json"
        }, method="POST")
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read())
            gen_id = result.get("sdGenerationJob", {}).get("generationId", "")
            return {"status": "submitted", "generation_id": gen_id}
    except Exception as e:
        return {"error": str(e)}


def check_status(generation_id: str) -> dict:
    if not API_KEY:
        return {"error": "LEONARDO_API_KEY not set"}
    try:
        url = f"{LEONARDO_API_BASE}/generations/{generation_id}"
        req = urllib.request.Request(url, headers={
            "Authorization": f"Bearer {API_KEY}",
            "Accept": "application/json"
        })
        with urllib.request.urlopen(req, timeout=15) as resp:
            result = json.loads(resp.read())
            images = result.get("generations_by_pk", {}).get("generated_images", [])
            urls = [img.get("url", "") for img in images]
            return {"status": "completed" if images else "processing", "images": urls}
    except Exception as e:
        return {"error": str(e)}


def get_studio_html() -> str:
    return """
<div class="studio-image">
  <h2>Leonardo Studio</h2>
  <p class="muted">AI image generation via Leonardo.Ai</p>
  <div class="row"><label>Prompt</label><textarea id="leo-prompt" rows="3"></textarea></div>
  <div class="row"><label>Model</label><select id="leo-model">
    <option value="6be09fc0-5fcc-4d01-8bce-1e5a8f7e0061">Leonardo Diffusion XL</option>
    <option value="e71a138f-efb3-4364-b1a4-58d4b05c6b09">Leonardo Vision XL</option>
    <option value="2067ae52-11d5-42d6-b16b-5e3a0a6e0000">Leonardo Kino XL</option>
  </select></div>
  <div class="row"><label>Width</label><input type="number" id="leo-width" value="1024"></div>
  <div class="row"><label>Height</label><input type="number" id="leo-height" value="1024"></div>
  <div class="row"><label>Number</label><input type="number" id="leo-num" value="1" min="1" max="4"></div>
  <button onclick="leoGenerate()">Generate</button>
  <div id="leo-status"></div>
  <div id="leo-result"></div>
</div>
"""


def get_studio_scripts() -> str:
    return """
async function leoGenerate() {
  const btn = document.querySelector('.studio-image button');
  btn.disabled = true;
  document.getElementById('leo-status').textContent = 'Submitting...';
  const res = await cockpit.pluginAction('leonardo-studio', 'generate', {
    prompt: document.getElementById('leo-prompt').value,
    model: document.getElementById('leo-model').value,
    width: parseInt(document.getElementById('leo-width').value),
    height: parseInt(document.getElementById('leo-height').value),
    num_images: parseInt(document.getElementById('leo-num').value)
  });
  if (res.error) { document.getElementById('leo-status').textContent = 'Error: ' + res.error; btn.disabled = false; return; }
  document.getElementById('leo-status').textContent = 'Processing...';
  let done = false;
  while (!done) {
    await new Promise(r => setTimeout(r, 3000));
    const poll = await cockpit.pluginAction('leonardo-studio', 'status', { generation_id: res.generation_id });
    if (poll.images && poll.images.length > 0) {
      document.getElementById('leo-status').textContent = 'Done!';
      document.getElementById('leo-result').innerHTML = poll.images.map(u => '<img src="' + u + '" />').join('');
      done = true;
    } else if (poll.error) {
      document.getElementById('leo-status').textContent = 'Error: ' + poll.error;
      done = true;
    }
  }
  btn.disabled = false;
}
"""
