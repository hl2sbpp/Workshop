# add_addon.py
import os
import re
import json
import sys
import requests
from pathlib import Path

comment_body = os.environ.get("COMMENT_BODY", "")
issue_body = os.environ.get("ISSUE_BODY", "")
issue_author = os.environ.get("ISSUE_AUTHOR", "Unknown")
issue_title = os.environ.get("ISSUE_TITLE", "Unnamed Addon")

comment_body = comment_body or ""
selected_text = ""

if comment_body:
    cb = comment_body.strip()
    if not cb.startswith("/add-addon"):
        print("No /add-addon command found in comment, exiting.")
        sys.exit(0)

    after = cb[len("/add-addon"):].strip()
    selected_text = after if after else issue_body
else:
    selected_text = issue_body

if not selected_text or not selected_text.strip():
    print("Error: no content found in issue or comment to parse.")
    sys.exit(1)

thumbs_dir = Path("thumbs")
thumbs_dir.mkdir(exist_ok=True)

ADDONS_FILE = "mods.json"

if not Path(ADDONS_FILE).exists():
    base = {"mods": []}
    with open(ADDONS_FILE, "w", encoding="utf-8") as f:
        json.dump(base, f, indent=2)
with open(ADDONS_FILE, "r", encoding="utf-8") as f:
    data = json.load(f)

lines = selected_text.strip().splitlines()
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
    url_match = re.search(r"(https?://\S+)", selected_text, re.IGNORECASE)
    if url_match:
        addon["download"] = url_match.group(1).strip()

if "download" not in addon or not addon["download"].strip():
    print("Error: 'Download' URL is required.")
    sys.exit(1)

addon["name"] = issue_title
addon["author"] = issue_author
addon["version"] = addon.get("version", "1.0")
addon["description"] = "\n".join(desc_lines).strip() or "No Description"

img_match = re.search(r"(https?://\S+\.(?:png|jpg|jpeg|gif))", selected_text, re.IGNORECASE)
default_preview = "https://raw.githubusercontent.com/ThePixelMoon/Workshop/main/thumbs/unknown.png"
addon["preview"] = img_match.group(1) if img_match else default_preview

preview_url = addon["preview"]
if preview_url and "user-images.githubusercontent.com" in preview_url:
    safe_name = re.sub(r"[^\w\-]", "_", addon["name"])
    local_file = thumbs_dir / f"{safe_name}.png"
    try:
        r = requests.get(preview_url, timeout=15)
        r.raise_for_status()
        with open(local_file, "wb") as f:
            f.write(r.content)
        addon["preview"] = f"https://raw.githubusercontent.com/hl2sbpp/Workshop/main/thumbs/{local_file.name}?raw=true"
    except Exception as e:
        print(f"Warning: could not download preview image, using default. {e}")
        addon["preview"] = default_preview

download_url = addon["download"]
try:
    r = requests.head(download_url, allow_redirects=True, timeout=10)
    size_bytes = r.headers.get("Content-Length")
    if size_bytes is None or int(size_bytes) == 0:
        r = requests.get(download_url, stream=True, timeout=15)
        size_bytes = r.headers.get("Content-Length")
    size_bytes = int(size_bytes) if size_bytes else 0
    addon["size_mb"] = max(1, round(size_bytes / (1024 * 1024))) if size_bytes > 0 else 1
except Exception as e:
    print("Warning: could not detect size, defaulting to 1MB.", e)
    addon["size_mb"] = 1

current_ids = [m.get("id", 0) for m in data.get("mods", [])]
addon["id"] = max(current_ids, default=1023) + 1

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

data.setdefault("mods", []).append(addon_json)
data["mods"] = sorted(data["mods"], key=lambda x: x["id"])

with open(ADDONS_FILE, "w", encoding="utf-8") as f:
    json.dump(data, f, indent=2, ensure_ascii=False)
    f.write("\n")

print(f"Addon '{addon_json['name']}' added with ID {addon_json['id']}.")
