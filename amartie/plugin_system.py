"""
AMARTIE Plugin System
=====================
Plugins transform the cockpit into specialized studios.
Each plugin is a self-contained module with a manifest.
The cockpit loads plugins dynamically.
"""

import json
import os
from typing import Dict, List, Optional, Any


class PluginManifest:
    """Every plugin has a manifest describing what it is and what it needs."""
    
    def __init__(self, manifest_path: str):
        with open(manifest_path) as f:
            self.data = json.load(f)
    
    @property
    def name(self) -> str:
        return self.data["name"]
    
    @property
    def version(self) -> str:
        return self.data["version"]
    
    @property
    def description(self) -> str:
        return self.data["description"]
    
    @property
    def entrypoint(self) -> str:
        return self.data["entrypoint"]
    
    @property
    def permissions(self) -> List[str]:
        return self.data.get("permissions", [])
    
    @property
    def api_endpoints(self) -> Dict[str, str]:
        return self.data.get("api_endpoints", {})
    
    @property
    def studio_type(self) -> str:
        return self.data.get("studio_type", "generic")
    
    def validate(self) -> bool:
        """Validate manifest has all required fields."""
        required = ["name", "version", "entrypoint", "permissions"]
        for field in required:
            if field not in self.data:
                return False
        return True


class Plugin:
    """A loaded plugin instance."""
    
    def __init__(self, manifest: PluginManifest, plugin_dir: str):
        self.manifest = manifest
        self.plugin_dir = plugin_dir
        self.loaded = False
        self.instance = None
    
    def load(self) -> bool:
        """Load the plugin module."""
        try:
            import importlib.util
            entrypoint_path = os.path.join(self.plugin_dir, self.manifest.entrypoint)
            spec = importlib.util.spec_from_file_location(
                self.manifest.name, entrypoint_path
            )
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            self.instance = module
            self.loaded = True
            return True
        except Exception as e:
            print(f"Failed to load plugin {self.manifest.name}: {e}")
            return False
    
    def render(self, **kwargs) -> str:
        """Render the plugin's UI (returns HTML or JSON)."""
        if not self.loaded:
            return ""
        if hasattr(self.instance, 'render'):
            return self.instance.render(**kwargs)
        return ""
    
    def handle(self, action: str, data: dict) -> dict:
        """Handle an action from the cockpit."""
        if not self.loaded:
            return {"error": "Plugin not loaded"}
        if hasattr(self.instance, 'handle'):
            return self.instance.handle(action, data)
        return {"error": "Plugin has no handler"}


class PluginManager:
    """
    Discovers, loads, and manages plugins.
    
    Plugin directory structure:
    plugins/
      design-studio/
        manifest.json
        __init__.py
        templates/
      video-studio/
        manifest.json
        __init__.py
      cad-studio/
        manifest.json
        __init__.py
    """
    
    def __init__(self, plugins_dir: str = "plugins"):
        self.plugins_dir = plugins_dir
        self.plugins: Dict[str, Plugin] = {}
        self.active_plugin: Optional[str] = None
    
    def discover(self) -> List[PluginManifest]:
        """Find all plugins in the plugins directory."""
        manifests = []
        if not os.path.exists(self.plugins_dir):
            return manifests
        
        for name in os.listdir(self.plugins_dir):
            plugin_dir = os.path.join(self.plugins_dir, name)
            if not os.path.isdir(plugin_dir):
                continue
            manifest_path = os.path.join(plugin_dir, "manifest.json")
            if os.path.exists(manifest_path):
                try:
                    manifest = PluginManifest(manifest_path)
                    if manifest.validate():
                        manifests.append(manifest)
                except Exception as e:
                    print(f"Invalid manifest for {name}: {e}")
        
        return manifests
    
    def load_plugin(self, name: str) -> bool:
        """Load a specific plugin."""
        plugin_dir = os.path.join(self.plugins_dir, name)
        manifest_path = os.path.join(plugin_dir, "manifest.json")
        
        if not os.path.exists(manifest_path):
            return False
        
        manifest = PluginManifest(manifest_path)
        plugin = Plugin(manifest, plugin_dir)
        
        if plugin.load():
            self.plugins[name] = plugin
            return True
        return False
    
    def load_all(self):
        """Load all discovered plugins."""
        manifests = self.discover()
        for manifest in manifests:
            self.load_plugin(manifest.name)
    
    def activate(self, name: str) -> bool:
        """Activate a plugin (shows its UI in the cockpit)."""
        if name in self.plugins:
            self.active_plugin = name
            return True
        return False
    
    def get_active(self) -> Optional[Plugin]:
        """Get the currently active plugin."""
        if self.active_plugin:
            return self.plugins.get(self.active_plugin)
        return None
    
    def list_plugins(self) -> List[dict]:
        """List all loaded plugins."""
        result = []
        for name, plugin in self.plugins.items():
            result.append({
                "name": plugin.manifest.name,
                "version": plugin.manifest.version,
                "description": plugin.manifest.description,
                "studio_type": plugin.manifest.studio_type,
                "active": name == self.active_plugin
            })
        return result


# Singleton plugin manager
plugin_manager = PluginManager()
