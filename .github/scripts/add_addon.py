# add_addon.py
import os
import re
import json
import sys
import requests
from pathlib import Path

comment_body = os.environ.get("COMMENT_BODY", "")
if comment_body and not comment_body.strip().startswith("/add-addon"):
    print("No /add-addon command found, exiting.")
    exit(0)

thumbs_dir = Path("thumbs")
thumbs_dir.mkdir(exist_ok=True)

ADDONS_FILE = "mods.json"

with open(ADDONS_FILE, "r", encoding="utf-8") as f:
    data = json.load(f)

issue_body = os.environ.get("ISSUE_BODY", "")
issue_author = os.environ.get("ISSUE_AUTHOR", "Unknown")
issue_title = os.environ.get("ISSUE_TITLE", "Unnamed Addon")

lines = issue_body.strip().splitlines()
kv_lines = []
desc_lines = []
found_blank = False

for line in lines:
    if not line.strip() and not found_blank:
        found_blank = True
        continue
    if not found_blank:
        kv_lines.append(line.strip())
    else:
        desc_lines.append(line)

addon = {}
for line in kv_lines:
    if ':' not in line:
        continue
    key, val = line.split(':', 1)
    addon[key.strip().lower()] = val.strip()

if "download" not in addon:
    print("Error: 'Download' URL is required.")
    sys.exit(1)

addon["description"] = "\n".join(desc_lines).strip() or "No Description"
addon["name"] = issue_title

addon["author"] = issue_author
addon["version"] = addon.get("version", "1.0")

img_match = re.search(r"(https?://\S+\.(?:png|jpg|jpeg|gif))", issue_body, re.IGNORECASE)
addon["preview"] = img_match.group(1) if img_match else ""

default_preview = "https://raw.githubusercontent.com/ThePixelMoon/Workshop/main/thumbs/unknown.png"

img_match = re.search(r"(https?://\S+\.(?:png|jpg|jpeg|gif))", issue_body, re.IGNORECASE)
addon["preview"] = img_match.group(1) if img_match else default_preview

preview_url = addon["preview"]
if preview_url and "user-images.githubusercontent.com" in preview_url:
    safe_name = re.sub(r"[^\w\-]", "_", addon["name"])
    local_file = thumbs_dir / f"{safe_name}.png"

    r = requests.get(preview_url)
    r.raise_for_status()
    with open(local_file, "wb") as f:
        f.write(r.content)

    addon["preview"] = f"https://raw.githubusercontent.com/hl2sbpp/Workshop/main/thumbs/{local_file.name}?raw=true"

try:
    r = requests.head(addon["download"], allow_redirects=True, timeout=10)
    size_bytes = int(r.headers.get("Content-Length", 0))
    addon["size_mb"] = max(1, round(size_bytes / (1024 * 1024)))
except Exception as e:
    print("Warning: could not detect size, defaulting to 1MB.", e)
    addon["size_mb"] = 1

addon["id"] = max([m.get("id", 1023) for m in data["mods"]], default=1023) + 1

addon_json = {
    "name": addon["name"],
    "author": addon["author"],
    "version": addon["version"],
    "description": addon["description"],
    "download_url": addon["download"],
    "preview": addon["preview"],
    "size_mb": addon["size_mb"],
    "id": addon["id"]
}

data["mods"].append(addon_json)
data["mods"] = sorted(data["mods"], key=lambda x: x["id"])

with open(ADDONS_FILE, "w", encoding="utf-8") as f:
    json.dump(data, f, indent=2, ensure_ascii=False)
    f.write("\n")

print(f"Addon '{addon_json['name']}' added with ID {addon_json['id']}.")
