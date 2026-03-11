#!/usr/bin/env python3
"""
Check GitHub issues for ClawUI.
Set GITHUB_TOKEN environment variable (no scopes required for public repo).
"""

import os
import json
import subprocess
import sys
from datetime import datetime, timedelta

REPO = "longgo1001/clawui"
TOKEN = os.getenv("GITHUB_TOKEN", "")

def fetch_issues():
    """Fetch open issues via GitHub API."""
    url = f"https://api.github.com/repos/{REPO}/issues"
    headers = ["Accept: application/vnd.github.v3+json"]
    if TOKEN:
        headers.append(f"Authorization: token {TOKEN}")
    cmd = ["curl", "-s"] + [f"-H{h}" for h in headers] + [url + "?state=open&per_page=100"]
    try:
        out = subprocess.check_output(cmd, stderr=subprocess.DEVNULL)
        return json.loads(out)
    except subprocess.CalledProcessError as e:
        print(f"Error fetching issues: {e}")
        return []
    except json.JSONDecodeError:
        return []

def main():
    issues = fetch_issues()
    # Filter issues created in last 7 days (or all if none)
    week_ago = datetime.now() - timedelta(days=7)
    recent = [i for i in issues if datetime.strptime(i['created_at'], "%Y-%m-%dT%H:%M:%SZ") > week_ago]

    print(f"ClawUI Open Issues: {len(issues)} total, {len(recent)} created in last 7 days")
    if not issues:
        return

    print("\nRecent Issues (last 7 days):")
    for i in recent[:10]:
        print(f"#{i['number']}: {i['title'][:60]}")
        print(f"   URL: {i['html_url']}")
        print(f"   Labels: {', '.join([l['name'] for l in i.get('labels', [])])}")
        print()

    if len(recent) > 10:
        print(f"... and {len(recent)-10} more recent issues.")

    # Optionally, could auto-assign, comment, or close based on criteria (skipped for safety)

if __name__ == "__main__":
    main()
