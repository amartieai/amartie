"""
ElevenLabs Studio Plugin
========================
Voice synthesis, text-to-speech, and voice cloning.
"""

import json
import os
import urllib.request

PLUGIN_NAME = "ElevenLabs Studio"
PLUGIN_VERSION = "0.1.0"
PLUGIN_DESCRIPTION = "Voice synthesis and text-to-speech"
STUDIO_TYPE = "voice_synthesis"

ELEVENLABS_API_BASE = "https://api.elevenlabs.io/v1"
API_KEY = os.environ.get("ELEVENLABS_API_KEY", "")


def render(config=None):
    return {"name": PLUGIN_NAME, "version": PLUGIN_VERSION, "type": STUDIO_TYPE, "html": get_html(), "scripts": get_js()}


def handle(action, data):
    if action == "speak":
        return speak(data)
    elif action == "voices":
        return list_voices()
    return {"error": "unknown action"}


def speak(data):
    if not API_KEY:
        return {"error": "ELEVENLABS_API_KEY not set"}
    try:
        voice_id = data.get("voice_id", "JBFqnCBsd6RMkjVDRZzb")
        url = f"{ELEVENLABS_API_BASE}/text-to-speech/{voice_id}"
        payload = json.dumps({
            "text": data.get("text", ""),
            "model_id": data.get("model", "eleven_multilingual_v2")
        }).encode()
        req = urllib.request.Request(url, data=payload, headers={
            "xi-api-key": API_KEY,
            "Content-Type": "application/json"
        }, method="POST")
        with urllib.request.urlopen(req, timeout=30) as resp:
            audio = resp.read()
            # Save audio file
            output = f"/tmp/amartie_speech_{voice_id[:8]}.mp3"
            with open(output, "wb") as f:
                f.write(audio)
            return {"status": "done", "file": output}
    except Exception as e:
        return {"error": str(e)}


def list_voices():
    if not API_KEY:
        return {"error": "ELEVENLABS_API_KEY not set"}
    try:
        url = f"{ELEVENLABS_API_BASE}/voices"
        req = urllib.request.Request(url, headers={"xi-api-key": API_KEY})
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read())
    except Exception as e:
        return {"error": str(e)}


def get_html():
    return """
<div class="studio-voice">
  <h2>ElevenLabs Studio</h2>
  <p class="muted">Text-to-speech and voice synthesis</p>
  <div class="row"><label>Text</label><textarea id="el-text" rows="4" placeholder="Enter text to speak..."></textarea></div>
  <div class="row"><label>Voice</label><select id="el-voice">
    <option value="JBFqnCBsd6RMkjVDRZzb">Default</option>
    <option value="21m00Tcm4TlvDq8ikWAM">Rachel</option>
    <option value="AZnzlk1XvdvUeBnXmlld">Domi</option>
    <option value="EXAVITQu4vr4xnSDxMaL">Bella</option>
  </select></div>
  <button onclick="elSpeak()">Speak</button>
  <div id="el-status"></div>
  <div id="el-result"></div>
</div>
"""


def get_js():
    return """
async function elSpeak() {
  const btn = document.querySelector('.studio-voice button');
  btn.disabled = true;
  document.getElementById('el-status').textContent = 'Synthesizing...';
  const res = await cockpit.pluginAction('elevenlabs-studio', 'speak', {
    text: document.getElementById('el-text').value,
    voice_id: document.getElementById('el-voice').value
  });
  if (res.error) { document.getElementById('el-status').textContent = 'Error: ' + res.error; btn.disabled = false; return; }
  document.getElementById('el-status').textContent = 'Done!';
  if (res.file) document.getElementById('el-result').innerHTML = '<audio controls src="/files/' + res.file.split('/').pop() + '"></audio>';
  btn.disabled = false;
}
"""
