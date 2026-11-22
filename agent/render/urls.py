#!/usr/bin/env python3
"""Print the public URLs Instagram will download, for files already pushed.

Usage (inside the repo, after `git push`):
    python3 agent/render/urls.py FILE [FILE ...]

Images -> raw.githubusercontent.com (served as image/jpeg).
Videos -> cdn.jsdelivr.net (served as video/mp4); the raw URL is the fallback.
URLs are pinned to the current commit, so they never change afterwards.
The GitHub repo comes from "github_repo" in agent/config.json.
"""
import json
import pathlib
import subprocess
import sys

from common import REPO_ROOT, load_config


def git(*args) -> str:
    return subprocess.run(["git", *args], cwd=REPO_ROOT, capture_output=True,
                          text=True, check=True).stdout.strip()


def main():
    files = sys.argv[1:]
    if not files:
        sys.exit(__doc__)
    repo = load_config().get("github_repo")
    if not repo or "/" not in repo:
        sys.exit('Set "github_repo": "owner/name" in agent/config.json')
    sha = git("rev-parse", "HEAD")
    try:
        unpushed = git("log", "--oneline", "@{u}..HEAD")
    except subprocess.CalledProcessError:
        sys.exit("No upstream branch: push first with `git push -u origin <branch>`.")
    if unpushed:
        sys.exit("Push first: these commits are not on GitHub yet:\n" + unpushed)
    for f in files:
        rel = pathlib.Path(f).resolve().relative_to(REPO_ROOT).as_posix()
        if subprocess.run(["git", "ls-files", "--error-unmatch", rel], cwd=REPO_ROOT,
                          capture_output=True).returncode != 0:
            sys.exit(f"Not committed: {rel}")
        raw = f"https://raw.githubusercontent.com/{repo}/{sha}/{rel}"
        cdn = f"https://cdn.jsdelivr.net/gh/{repo}@{sha}/{rel}"
        is_video = rel.lower().endswith((".mp4", ".mov"))
        print(json.dumps({"file": rel, "url": cdn if is_video else raw,
                          "fallback_url": raw if is_video else cdn}))


if __name__ == "__main__":
    main()
