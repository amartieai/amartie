"""
AMARTIE Free AI Providers
===========================
Free API provider integrations with token tracking.
All providers use OpenAI-compatible endpoints.
Providers: Inception Labs, Atria, Cloudflare, OpenCode, and more.
"""

import json
import os
import urllib.request
import urllib.error
from typing import Dict, List, Optional
from datetime import datetime, timezone

PLUGIN_NAME = "Free AI Providers"
PLUGIN_VERSION = "0.2.0"
PLUGIN_DESCRIPTION = "Free AI API integrations with usage tracking"

# Free provider catalog
FREE_PROVIDERS = {
    "inception_labs": {
        "name": "Inception Labs",
        "base_url": "https://api.inceptionlabs.ai/v1",
        "models": ["mercury-2.5", "mercury-2"],
        "free_tokens": 100_000_000,
        "token_reset": "never",
        "notes": "100M free tokens, no credit card, Mercury 2.5 reasoning model",
        "signup_url": "https://platform.inceptionlabs.ai/"
    },
    "atria": {
        "name": "Atria AI",
        "base_url": "https://api.atria.ai/v1",
        "models": ["atria-dawn-preview"],
        "free_tokens": 100_000_000,
        "token_reset": "never",
        "notes": "100M free tokens, Dawn Preview reasoning model (GLM-5.2 based)",
        "signup_url": "https://atria.ai/"
    },
    "cloudflare": {
        "name": "Cloudflare Workers AI",
        "base_url": "https://api.cloudflare.com/client/v4/accounts/{account_id}/ai/v1",
        "models": ["@cf/meta/llama-3.1-8b-instruct", "@cf/mistral/mistral-7b-instruct-v0.2"],
        "free_tokens": 10_000_000,
        "token_reset": "daily",
        "notes": "10M tokens/day, multiple open-source models, requires Cloudflare account",
        "signup_url": "https://dash.cloudflare.com/"
    },
    "opencode": {
        "name": "OpenCode Zen",
        "base_url": "https://api.opencode.ai/v1",
        "models": ["union-alpha", "deepseek-v4-flash", "glm-5-3", "muse-spark", "solar-pro", "luna-s2.1"],
        "free_tokens": 1_000_000,
        "token_reset": "daily",
        "notes": "1M tokens/day, 56+ models available, OpenAI-compatible",
        "signup_url": "https://opencode.ai/zen"
    },
    "together_ai": {
        "name": "Together AI",
        "base_url": "https://api.together.xyz/v1",
        "models": ["meta-llama/Llama-3.3-70B-Instruct-Turbo", "mistralai/Mixtral-8x7B-Instruct-v0.1"],
        "free_tokens": 25_000_000,
        "token_reset": "never",
        "notes": "$25 free credits, open-source models",
        "signup_url": "https://together.ai/"
    },
    "groq": {
        "name": "Groq",
        "base_url": "https://api.groq.com/openai/v1",
        "models": ["llama-3.3-70b-versatile", "mixtral-8x7b-32768"],
        "free_tokens": 15_000_000,
        "token_reset": "never",
        "notes": "Free tier with rate limits, fast inference",
        "signup_url": "https://groq.com/"
    },
    "gemini": {
        "name": "Google Gemini",
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai",
        "models": ["gemini-1.5-flash", "gemini-1.5-pro"],
        "free_tokens": 1_500_000,
        "token_reset": "daily",
        "notes": "1.5M tokens/day, requires Google API key",
        "signup_url": "https://aistudio.google.com/"
    }
}


class ProviderClient:
    """OpenAI-compatible client for any provider."""
    
    def __init__(self, provider_id: str, api_key: str):
        self.provider = FREE_PROVIDERS.get(provider_id)
        if not self.provider:
            raise ValueError(f"Unknown provider: {provider_id}")
        self.api_key = api_key
        self.base_url = self.provider["base_url"]
        self.usage: Dict[str, int] = {"prompt_tokens": 0, "completion_tokens": 0}
        
    def list_models(self) -> List[str]:
        """List available models."""
        return self.provider["models"]
        
    def chat(self, messages: List[dict], model: str = None, **kwargs) -> dict:
        """
        Send a chat completion request.
        
        Args:
            messages: List of {role, content} messages
            model: Model to use (defaults to first available)
            **kwargs: Additional parameters (temperature, max_tokens, etc.)
        """
        if not model:
            model = self.provider["models"][0]
            
        url = f"{self.base_url}/chat/completions"
        data = json.dumps({
            "model": model,
            "messages": messages,
            **kwargs
        }).encode()
        
        req = urllib.request.Request(url, data=data, headers={
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        })
        
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                result = json.loads(resp.read().decode())
                # Track usage
                usage = result.get("usage", {})
                self.usage["prompt_tokens"] += usage.get("prompt_tokens", 0)
                self.usage["completion_tokens"] += usage.get("completion_tokens", 0)
                return {"status": "success", "data": result}
        except urllib.error.HTTPError as e:
            body = e.read().decode() if e.fp else ""
            return {"status": "error", "code": e.code, "message": body}
        except Exception as e:
            return {"status": "error", "message": str(e)}
            
    def get_usage(self) -> dict:
        """Get current usage stats."""
        return {
            "provider": self.provider["name"],
            "usage": self.usage,
            "free_tokens": self.provider["free_tokens"],
            "remaining": max(0, self.provider["free_tokens"] - self.usage["prompt_tokens"] - self.usage["completion_tokens"])
        }


class ProviderManager:
    """Manage multiple free providers with automatic fallback."""
    
    def __init__(self):
        self.clients: Dict[str, ProviderClient] = {}
        self.preferred_order = ["inception_labs", "atria", "opencode", "cloudflare", "groq", "gemini"]
        
    def add_provider(self, provider_id: str, api_key: str):
        """Add a provider with API key."""
        try:
            self.clients[provider_id] = ProviderClient(provider_id, api_key)
            return True
        except Exception as e:
            print(f"Failed to add {provider_id}: {e}")
            return False
            
    def remove_provider(self, provider_id: str):
        """Remove a provider."""
        if provider_id in self.clients:
            del self.clients[provider_id]
            
    def chat(self, messages: List[dict], model: str = None, 
             preferred: str = None, **kwargs) -> dict:
        """
        Send chat request with automatic fallback.
        
        Tries providers in order: preferred -> preferred_order.
        If a provider fails, falls back to next.
        """
        order = []
        if preferred and preferred in self.clients:
            order.append(preferred)
        for p in self.preferred_order:
            if p in self.clients and p not in order:
                order.append(p)
                
        for provider_id in order:
            client = self.clients[provider_id]
            result = client.chat(messages, model, **kwargs)
            if result["status"] == "success":
                result["provider"] = provider_id
                return result
            # If failed, try next provider
            continue
            
        return {"status": "error", "message": "All providers failed"}
        
    def get_all_usage(self) -> Dict[str, dict]:
        """Get usage for all providers."""
        return {pid: client.get_usage() for pid, client in self.clients.items()}
        
    def get_total_free_tokens(self) -> int:
        """Get total free tokens available across all providers."""
        total = 0
        for pid in self.clients:
            total += FREE_PROVIDERS[pid]["free_tokens"]
        return total


# Plugin interface
def render(config=None):
    return {
        "name": PLUGIN_NAME,
        "version": PLUGIN_VERSION,
        "type": "providers",
        "html": get_studio_html(),
        "scripts": get_studio_scripts(),
        "config": config or {}
    }


def handle(action, data):
    if action == "list":
        return list_providers()
    elif action == "add":
        return add_provider(data)
    elif action == "chat":
        return chat_request(data)
    elif action == "usage":
        return get_usage_status(data)
    elif action == "signup":
        return get_signup_links()
    return {"error": "unknown action"}


def list_providers():
    """List all available free providers."""
    return {"providers": {pid: {"name": p["name"], "free_tokens": p["free_tokens"], "models": p["models"], "signup_url": p["signup_url"]} for pid, p in FREE_PROVIDERS.items()}}


def add_provider(data):
    """Add a provider with API key."""
    provider_id = data.get("provider_id", "")
    api_key = data.get("api_key", "")
    if not provider_id or not api_key:
        return {"error": "provider_id and api_key required"}
    # In production: store securely and initialize client
    return {"status": "provider_added", "provider": provider_id}


def chat_request(data):
    """Send a chat request."""
    messages = data.get("messages", [])
    model = data.get("model")
    preferred = data.get("preferred_provider")
    # In production: use ProviderManager
    return {"status": "sent", "message_count": len(messages)}


def get_usage_status(data):
    """Get usage status for all providers."""
    return {"usage": {}}


def get_signup_links():
    """Get signup links for all providers."""
    return {pid: {"name": p["name"], "url": p["signup_url"], "free_tokens": p["free_tokens"]} for pid, p in FREE_PROVIDERS.items()}


def get_studio_html():
    return """
<div class="studio-providers">
  <h2>Free AI Providers</h2>
  <p class="muted">Multiple free AI APIs with automatic fallback</p>
  <div class="provider-grid" id="provider-grid">
    <div class="provider-card">
      <h4>Inception Labs</h4>
      <div class="tokens">100M free tokens</div>
      <div class="models">Mercury 2.5</div>
      <a href="https://platform.inceptionlabs.ai/" target="_blank">Sign up</a>
    </div>
    <div class="provider-card">
      <h4>Atria AI</h4>
      <div class="tokens">100M free tokens</div>
      <div class="models">Dawn Preview</div>
      <a href="https://atria.ai/" target="_blank">Sign up</a>
    </div>
    <div class="provider-card">
      <h4>Cloudflare</h4>
      <div class="tokens">10M tokens/day</div>
      <div class="models">Llama, Mistral</div>
      <a href="https://dash.cloudflare.com/" target="_blank">Sign up</a>
    </div>
    <div class="provider-card">
      <h4>OpenCode Zen</h4>
      <div class="tokens">1M tokens/day</div>
      <div class="models">56+ models</div>
      <a href="https://opencode.ai/zen" target="_blank">Sign up</a>
    </div>
  </div>
  <hr>
  <h3>Add Provider</h3>
  <div class="row">
    <select id="provider-select">
      <option value="inception_labs">Inception Labs</option>
      <option value="atria">Atria AI</option>
      <option value="cloudflare">Cloudflare</option>
      <option value="opencode">OpenCode</option>
      <option value="groq">Groq</option>
      <option value="gemini">Google Gemini</option>
    </select>
  </div>
  <div class="row">
    <input type="password" id="provider-key" placeholder="API Key">
    </div>
  <button onclick="providerAdd()">Add Provider</button>
  <hr>
  <h3>Usage</h3>
  <button onclick="providerUsage()">Check Usage</button>
  <div id="provider-usage"></div>
</div>"""


def get_studio_scripts():
    return """
async function providerAdd() {
  const pid = document.getElementById('provider-select').value;
  const key = document.getElementById('provider-key').value;
  const res = await cockpit.pluginAction('free-providers', 'add', {provider_id: pid, api_key: key});
  alert(res.status || res.error);
}
async function providerUsage() {
  const res = await cockpit.pluginAction('free-providers', 'usage', {});
  document.getElementById('provider-usage').textContent = JSON.stringify(res.usage, null, 2);
}"""
