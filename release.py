"""Publish a new version: bump the version, build the exe, publish it as a GitHub Release.

Run release.bat (or: python release.py 1.0.1). Uses your saved git login for GitHub.
Installed apps see the new release next time they open and offer "Update now".
"""
import json
import re
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

from updater import ASSET_NAME, RELEASES_REPO, parse_version

HERE = Path(__file__).parent
VERSION_FILE = HERE / "version.py"
ZIP = HERE / ASSET_NAME


def run(*cmd):
    print(">", " ".join(cmd))
    subprocess.run(cmd, cwd=HERE, check=True)


def github_token():
    out = subprocess.run(["git", "credential", "fill"], input="protocol=https\nhost=github.com\n\n",
                         capture_output=True, text=True, timeout=60).stdout
    token = dict(l.split("=", 1) for l in out.splitlines() if "=" in l).get("password")
    if not token:
        sys.exit("No saved GitHub login. Push to GitHub once with git, then try again.")
    return token


def api(method, url, token, data=None, content_type="application/json"):
    body = json.dumps(data).encode() if isinstance(data, dict) else data
    req = urllib.request.Request(url, data=body, method=method, headers={
        "Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json",
        "Content-Type": content_type, "User-Agent": "ClientIntake-release"})
    with urllib.request.urlopen(req, timeout=300) as resp:
        return json.load(resp)


def current_version():
    return re.search(r'"([\d.]+)"', VERSION_FILE.read_text()).group(1)


def main():
    current = current_version()
    new = sys.argv[1] if len(sys.argv) > 1 else input(f"Current version is {current}. New version: ").strip()
    if not re.fullmatch(r"\d+\.\d+\.\d+", new):
        sys.exit("Use a version like 1.0.1")
    if parse_version(new) < parse_version(current):
        sys.exit(f"{new} is older than {current}.")
    notes = input("What changed (one line, optional): ").strip() if len(sys.argv) < 3 else sys.argv[2]

    token = github_token()
    tag = f"v{new}"
    try:
        api("GET", f"https://api.github.com/repos/{RELEASES_REPO}/releases/tags/{tag}", token)
        sys.exit(f"{tag} is already published. Pick a higher version.")
    except urllib.error.HTTPError as e:
        if e.code != 404:
            raise

    if new != current:
        VERSION_FILE.write_text(f'__version__ = "{new}"\n')
        run("git", "add", "version.py")
        run("git", "commit", "-m", f"Release {tag}")
    run("cmd", "/c", str(HERE / "build.bat"))
    run("git", "tag", "-f", tag)
    run("git", "push")
    run("git", "push", "-f", "origin", tag)

    release = api("POST", f"https://api.github.com/repos/{RELEASES_REPO}/releases", token, {
        "tag_name": tag, "name": f"Client Intake {new}",
        "body": notes or f"Client Intake {new}"})
    print("Uploading", ZIP.name, f"({ZIP.stat().st_size // 1_000_000} MB)...")
    upload = release["upload_url"].split("{")[0] + f"?name={ASSET_NAME}"
    api("POST", upload, token, ZIP.read_bytes(), content_type="application/zip")
    print(f"\nPublished {tag}: {release['html_url']}")
    print("Open apps will offer the update next time they start.")


if __name__ == "__main__":
    main()
