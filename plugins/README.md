# AMARTIE Plugins

## Installed Plugins

### Voice Studio (`voice-studio`)
Voice-first AI interaction engine.
- Local Whisper STT (CPU) + cloud TTS (ElevenLabs)
- Pipeline scheduling: cuts 6.8s → 3.0s latency
- Cross-platform: macOS, Linux, Windows
- Barge-in interruption support

### Jarvis Studio (`jarvis-studio`)
Multi-tool AI agent with gate-verified actions.
- Voice + Gmail + Calendar + Drive + custom tools
- 9-judge gate verification on every action
- Tool registry: add tools without rebuilding
- Model-agnostic: works with any LLM provider

### Free Providers (`free-providers`)
Free AI API integrations with automatic fallback.
- Inception Labs: 100M tokens, Mercury 2.5
- Atria AI: 100M tokens, Dawn Preview
- Cloudflare Workers AI: 10M tokens/day
- OpenCode Zen: 1M tokens/day, 56+ models
- Together AI: $25 free credits
- Groq: fast inference
- Google Gemini: 1.5M tokens/day

## Architecture

Every plugin has:
- `manifest.json` — plugin metadata and permissions
- `__init__.py` — plugin logic with `render()` and `handle()` entry points
- `templates/` — optional UI templates

## Adding a Plugin

1. Create a directory under `plugins/`
2. Add `manifest.json` with required fields
3. Add `__init__.py` with `render()` and `handle()` functions
4. Restart AMARTIE — plugin is auto-discovered

## Gate Integration

All plugins route outbound actions through the AMARTIE 9-judge gate.
No action leaves the system unverified.
