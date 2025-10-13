#!/usr/bin/env python3
"""
Compare the local workspace with the remote GitHub repository tree (Link-Checker:main).
Generates a simple report 'compare_report.txt' in the workspace root listing:
 - files present in remote but missing locally
 - files present locally but not in remote
 - files present in both but size differs (likely modified)

This script uses the GitHub tree API. To increase rate limits, set GITHUB_TOKEN in environment.
"""
import os
import json
import urllib.request
import urllib.error

REPO = 'sahookirank/Link-Checker'
BRANCH = 'main'
API_URL = f'https://api.github.com/repos/{REPO}/git/trees/{BRANCH}?recursive=1'

# Determine repo root (assume this script lives in <repo>/scripts)
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, '..'))
REPORT_PATH = os.path.join(REPO_ROOT, 'compare_report.txt')

headers = {'Accept': 'application/vnd.github.v3+json'}
GITHUB_TOKEN = os.getenv('GITHUB_TOKEN')
if GITHUB_TOKEN:
    headers['Authorization'] = f'token {GITHUB_TOKEN}'

print(f"Fetching remote tree from {API_URL} ...")
req = urllib.request.Request(API_URL, headers=headers)
try:
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.load(resp)
except urllib.error.HTTPError as e:
    print(f"HTTP error fetching remote tree: {e.code} {e.reason}")
    raise
except Exception as e:
    print(f"Error fetching remote tree: {e}")
    raise

remote_tree = data.get('tree', [])
remote_blobs = {entry['path']: entry.get('size', 0) for entry in remote_tree if entry.get('type') == 'blob'}

# Gather local files
local_files = {}
for root, dirs, files in os.walk(REPO_ROOT):
    # Skip .git folder
    if '.git' in root.split(os.sep):
        continue
    for fname in files:
        relpath = os.path.relpath(os.path.join(root, fname), REPO_ROOT)
        try:
            size = os.path.getsize(os.path.join(root, fname))
        except OSError:
            size = None
        local_files[relpath] = size

remote_paths = set(remote_blobs.keys())
local_paths = set(local_files.keys())

missing_in_local = sorted(remote_paths - local_paths)
extra_in_local = sorted(local_paths - remote_paths)

# Files present in both, check sizes
diff_size = []
for path in sorted(remote_paths & local_paths):
    remote_size = remote_blobs.get(path, None)
    local_size = local_files.get(path, None)
    # If sizes are both not None and differ, mark
    if remote_size is not None and local_size is not None and remote_size != local_size:
        diff_size.append((path, remote_size, local_size))

# Write report
with open(REPORT_PATH, 'w', encoding='utf-8') as out:
    out.write(f"Repository comparison report\n")
    out.write(f"Remote repo: {REPO} branch: {BRANCH}\n")
    out.write(f"Local path: {REPO_ROOT}\n\n")

    out.write(f"Summary:\n")
    out.write(f"  Remote files total: {len(remote_paths)}\n")
    out.write(f"  Local files total:  {len(local_paths)}\n")
    out.write(f"  Missing in local:   {len(missing_in_local)}\n")
    out.write(f"  Extra in local:     {len(extra_in_local)}\n")
    out.write(f"  Size mismatches:    {len(diff_size)}\n\n")

    if missing_in_local:
        out.write("Files present in remote but missing locally:\n")
        for p in missing_in_local:
            out.write(f"  {p} (remote size: {remote_blobs.get(p)})\n")
        out.write('\n')

    if extra_in_local:
        out.write("Files present locally but not in remote:\n")
        for p in extra_in_local:
            out.write(f"  {p} (local size: {local_files.get(p)})\n")
        out.write('\n')

    if diff_size:
        out.write("Files present in both but with size differences (remote_size, local_size):\n")
        for p, rsize, lsize in diff_size:
            out.write(f"  {p}: {rsize} != {lsize}\n")
        out.write('\n')

print(f"Comparison complete. Report written to: {REPORT_PATH}")
print('Missing_in_local:', len(missing_in_local))
print('Extra_in_local:', len(extra_in_local))
print('Size mismatches:', len(diff_size))
