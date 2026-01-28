import os, re, json, sys, requests
from pathlib import Path

comment_body = os.environ.get("COMMENT_BODY", "")
issue_body = os.environ.get("ISSUE_BODY", "")
issue_title = os.environ.get("ISSUE_TITLE", "")
issue_author = os.environ.get("ISSUE_AUTHOR", "")
repo = os.environ.get("GITHUB_REPOSITORY", "hl2sbpp/Workshop")

def convert_to_direct_link(url):
    if "drive.google.com" in url:
        file_id_match = re.search(r'/d/([a-zA-Z0-9_-]+)', url)
        if not file_id_match:
            file_id_match = re.search(r'id=([a-zA-Z0-9_-]+)', url)
        if file_id_match:
            file_id = file_id_match.group(1)
            return f"https://drive.google.com/uc?export=download&id={file_id}"
    
    elif "mediafire.com" in url and "/file/" in url:
        try:
            r = requests.get(url, timeout=15)
            direct_match = re.search(r'href="(https://download\d+\.mediafire\.com/[^"]+)"', r.text)
            if direct_match:
                return direct_match.group(1)
        except Exception:
            pass
    
    return url

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
    with open(ADDONS_FILE, "w", encoding="utf-8") as f:
        json.dump({"mods": []}, f, indent=2)

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
    k, v = line.split(':', 1)
    key = k.strip().lower()
    value = v.strip()
    addon[key] = value

download_url = None
if "download" in addon:
    download_url = addon["download"].strip().strip("\"'").rstrip(")>.,")
else:
    file_match = re.search(r"(https?://\S+\.(?:zip|vpk))", selected_text, re.IGNORECASE)
    if file_match:
        download_url = file_match.group(1).strip().strip("\"'").rstrip(")>.,")

if not download_url:
    print("Error: 'Download' URL is required. Must be a .zip or .vpk file.")
    print("Provide 'Download: <url>' or include a .zip/.vpk URL in the issue/comment.")
    sys.exit(1)

download_url = convert_to_direct_link(download_url)

if not (download_url.lower().endswith('.zip') or download_url.lower().endswith('.vpk')):
    print(f"Error: Download URL must be a .zip or .vpk file. Got: {download_url}")
    sys.exit(1)

addons_dir = Path("addons")
addons_dir.mkdir(exist_ok=True)

ext = ".zip" if download_url.lower().endswith('.zip') else ".vpk"
safe_name = re.sub(r"[^\w\-]", "_", addon.get("name", issue_title or "addon"))
local_addon_file = addons_dir / f"{safe_name}{ext}"

try:
    r = requests.get(download_url, timeout=60, allow_redirects=True)
    r.raise_for_status()
    
    with open(local_addon_file, "wb") as f:
        f.write(r.content)
    
    file_size_bytes = len(r.content)
    addon["size_mb"] = max(1, round(file_size_bytes / (1024 * 1024)))
    
    if file_size_bytes > 100 * 1024 * 1024:
        try:
            import subprocess
            subprocess.run(["git", "lfs", "install"], check=False, capture_output=True)
            subprocess.run(["git", "lfs", "track", str(local_addon_file)], check=True, capture_output=True)
            with open(".gitattributes", "a") as ga:
                ga.write(f"addons/*{ext} filter=lfs diff=lfs merge=lfs -text\n")
        except Exception as lfs_error:
            print(f"Warning: Could not set up Git LFS: {lfs_error}")
    
    download_url = f"https://raw.githubusercontent.com/{repo}/main/addons/{local_addon_file.name}"
except Exception as e:
    print(f"Error: Failed to download and re-host addon file: {e}")
    print("The addon file must be accessible for download.")
    sys.exit(1)

addon["download"] = download_url

addon["name"] = addon.get("name", issue_title or "Unnamed Addon")
addon["author"] = addon.get("author", issue_author or "Unknown")
addon["version"] = addon.get("version", "1.0")

desc_text = "\n".join(desc_lines).strip()
desc_text = re.sub(r"Download:\s*https?://\S+", "", desc_text, flags=re.IGNORECASE).strip()
desc_text = re.sub(r"^https?://\S+$", "", desc_text, flags=re.MULTILINE).strip()
addon["description"] = desc_text or "No Description"

preview_url = None
default_preview = f"https://raw.githubusercontent.com/{repo}/main/thumbs/unknown.png"
local_thumb_file = None

if "preview" in addon:
    preview_url = addon["preview"].strip().strip("\"'")

if not preview_url:
    img_match = re.search(r'<img[^>]+src=["\'](https?://[^"\']+)["\']', selected_text, re.IGNORECASE)
    if img_match:
        preview_url = img_match.group(1)

if not preview_url:
    img_match = re.search(r"!\[.*?\]\((https?://\S+\.(?:png|jpg|jpeg|gif|webp))\)", selected_text, re.IGNORECASE)
    if img_match:
        preview_url = img_match.group(1)

if not preview_url:
    img_match = re.search(r"(https?://\S+\.(?:png|jpg|jpeg|gif|webp))", selected_text, re.IGNORECASE)
    if img_match:
        potential_url = img_match.group(1).strip().strip("\"'").rstrip(")>.,")
        if potential_url != download_url:
            preview_url = potential_url

if preview_url:
    ext_match = re.search(r"\.(png|jpg|jpeg|gif|webp)(?:\?|$)", preview_url, re.IGNORECASE)
    ext = f".{ext_match.group(1).lower()}" if ext_match else ".png"
    
    safe_name = re.sub(r"[^\w\-]", "_", addon["name"])
    local_file = thumbs_dir / f"{safe_name}{ext}"
    
    try:
        r = requests.get(preview_url, timeout=15)
        r.raise_for_status()
        
        with open(local_file, "wb") as f:
            f.write(r.content)
        
        local_thumb_file = local_file
        addon["preview"] = f"https://raw.githubusercontent.com/{repo}/main/thumbs/{local_file.name}"
    except Exception as e:
        print(f"Warning: Failed to download thumbnail from {preview_url}: {e}")
        addon["preview"] = default_preview
else:
    addon["preview"] = default_preview

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

files_to_commit = [ADDONS_FILE, str(local_addon_file)]
if local_thumb_file:
    files_to_commit.append(str(local_thumb_file))
if file_size_bytes > 100 * 1024 * 1024:
    files_to_commit.append(".gitattributes")

with open("files_to_commit.txt", "w") as f:
    f.write("\n".join(files_to_commit))
