# add_addon.py
import os
import re
import json
import sys
import requests

ADDONS_FILE = "mods.json"

with open(ADDONS_FILE, "r", encoding="utf-8") as f:
    data = json.load(f)

issue_body = os.environ.get("ISSUE_BODY", "")
issue_author = os.environ.get("ISSUE_AUTHOR", "Unknown")

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

if "name" not in addon or "download" not in addon:
    print("Error: 'Name' and 'Download' are required fields.")
    sys.exit(1)

addon["description"] = "\n".join(desc_lines).strip()

addon["author"] = issue_author
addon["version"] = addon.get("version", "1.0")

img_match = re.search(r"(https?://\S+\.(?:png|jpg|jpeg|gif))", issue_body, re.IGNORECASE)
addon["preview"] = img_match.group(1) if img_match else ""

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
