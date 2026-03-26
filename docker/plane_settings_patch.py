"""Patch Plane's Django settings to include plane_lazy_bird.

This script runs at Docker image build time. It appends configuration to
Plane's production settings file so that our app is loaded and its URLs
are registered.

It locates Plane's settings by importing the module path and appending
to the file. If the settings structure changes in a future Plane version,
this script should be updated accordingly.
"""

import os
import glob

PATCH = '''
# --- plane_lazy_bird integration patch ---
INSTALLED_APPS += ["plane_lazy_bird"]

LAZY_BIRD_API_URL = os.environ.get("LAZY_BIRD_API_URL", "http://localhost:8000")
LAZY_BIRD_API_KEY = os.environ.get("LAZY_BIRD_API_KEY", "")
LAZY_BIRD_WEBHOOK_SECRET = os.environ.get("LAZY_BIRD_WEBHOOK_SECRET", "")
# --- end plane_lazy_bird patch ---
'''

# Find Plane's settings files — try common locations
candidates = [
    "/app/plane/settings/production.py",
    "/app/plane/settings/common.py",
]

# Also search for settings in site-packages if installed as package
for sp in glob.glob("/usr/local/lib/python*/site-packages/plane/settings/production.py"):
    candidates.append(sp)
for sp in glob.glob("/usr/local/lib/python*/site-packages/plane/settings/common.py"):
    candidates.append(sp)

patched = False
for settings_path in candidates:
    if os.path.exists(settings_path):
        with open(settings_path, "r") as f:
            content = f.read()
        if "plane_lazy_bird" not in content:
            with open(settings_path, "a") as f:
                f.write(PATCH)
            print(f"Patched: {settings_path}")
            patched = True
            break
        else:
            print(f"Already patched: {settings_path}")
            patched = True
            break

if not patched:
    print("WARNING: Could not find Plane settings to patch.")
    print(f"Searched: {candidates}")
    print("You may need to manually add plane_lazy_bird to INSTALLED_APPS.")
