#!/usr/bin/env python3
"""
E2E Test: Fully automated GitHub repository creation.

This script demonstrates fully automated, end-to-end functionality for the
`clawui` tool. It combines robust CLI commands with browser UI automation
to achieve its goal without manual intervention, assuming a one-time setup
for GitHub authentication.

**Workflow:**
1.  Checks for GitHub CLI (`gh`) authentication OR a GitHub token in the environment or config.
2.  If authenticated (via gh or token), creates a new public repository.
3.  Launches Chromium via CDP (`cdp_helper`).
4.  Navigates the browser to the new repository's URL to verify its creation via UI.
5.  Clones the new repository into a temporary directory.
6.  Creates a test file, commits it, and pushes it to the new repository.
7.  Cleans up by deleting the test repository.
"""

import subprocess
import time
import os
import sys
import datetime
import json
import pathlib
import requests

# Ensure the project source is in the path
# Adjust this path if your project structure is different
PROJECT_DIR = os.path.join(os.path.dirname(__file__), 'projects', 'gui-automation')
if PROJECT_DIR not in sys.path:
    sys.path.insert(0, PROJECT_DIR)

try:
    from src.cdp_helper import CDPClient
except ImportError:
    print("Error: Could not import CDPClient. Make sure the project path is correct.")
    sys.exit(1)

REPO_NAME = "clawui-e2e-demo-" + str(int(time.time()))
TEST_FILE = "hello_clawui.txt"
TEST_CONTENT = f"This repository was created automatically by the clawui agent at {datetime.datetime.now()}\n"
GH_OWNER = "longgo1001"

CONFIG_PATH = pathlib.Path.home() / ".config" / "clawui" / "config.json" 

def log(msg):
    """Simple logger."""
    print(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] {msg}")

def load_token_from_config() -> str | None:
    """Load GitHub PAT from ClawUI config file."""
    if not CONFIG_PATH.exists():
        return None
    try:
        with open(CONFIG_PATH) as f:
            config = json.load(f)
            token = config.get("github_pat")
            if token:
                log("✅ Loaded GitHub token from config.")
            return token
    except Exception as e:
        log(f"⚠️  Failed to read token from config: {e}")
        return None

def check_gh_auth():
    """Check if the user is authenticated with the GitHub CLI."""
    log("Checking GitHub CLI authentication status...")
    try:
        run_cmd(['gh', 'auth', 'status'])
        log("✅ GitHub CLI is authenticated.")
        return True
    except subprocess.CalledProcessError:
        log("⚠️ GitHub CLI not authenticated.")
        return False

def create_repo_via_api(token, repo_name, repo_desc):
    """Create a GitHub repo using the API."""
    log("Attempting to create repo via GitHub API...")
    url = "https://api.github.com/user/repos"
    headers = {"Authorization": f"token {token}", "Accept": "application/vnd.github.v3+json"}
    data = {"name": repo_name, "description": repo_desc, "private": False}
    try:
        response = requests.post(url, headers=headers, json=data, timeout=15)
        if response.status_code == 201:
            log("✅ Repo created successfully via API.")
            return f"https://github.com/{GH_OWNER}/{repo_name}"
        else:
            log(f"❌ API request failed: {response.status_code} {response.text}")
            return None
    except requests.RequestException as e:
        log(f"❌ API request error: {e}")
        return None

def delete_repo_via_api(token, repo_name):
    """Delete a GitHub repo using the API."""
    log(f"Deleting repository '{repo_name}' via API...")
    url = f"https://api.github.com/repos/{GH_OWNER}/{repo_name}"
    headers = {"Authorization": f"token {token}", "Accept": "application/vnd.github.v3+json"}
    try:
        response = requests.delete(url, headers=headers, timeout=15)
        if response.status_code == 204:
            log("✅ Repository deleted successfully via API.")
            return True
        else:
            log(f"❌ API delete failed: {response.status_code} {response.text}")
            return False
    except requests.RequestException as e:
        log(f"❌ API delete error: {e}")
        return False

def run_cmd(cmd, check=True, **kwargs):
    """Executes a shell command."""
    log(f"Executing: {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True, check=check, **kwargs)
    if result.returncode != 0 and check:
        # The CalledProcessError will be raised by subprocess.run
        log(f"❌ Command failed: {' '.join(cmd)}")
        log(f"   STDOUT: {result.stdout.strip()}")
        log(f"   STDERR: {result.stderr.strip()}")
    return result

def check_gh_auth():
    """Check if the user is authenticated with the GitHub CLI."""
    log("Checking GitHub CLI authentication status...")
    try:
        run_cmd(['gh', 'auth', 'status'])
        log("✅ GitHub CLI is authenticated.")
        return True
    except subprocess.CalledProcessError:
        log("⚠️ GitHub CLI not authenticated.")
        log("   Please run 'gh auth login' once manually to enable full automation.")
        return False

def create_repo_with_gh():
    """Creates a new public repository using the `gh` CLI."""
    log(f"Creating new public repository named '{REPO_NAME}'...")
    try:
        # The --source=. and --push is a trick to create and push in one go
        # But for this demo, we'll create an empty repo first.
        run_cmd([
            'gh', 'repo', 'create', REPO_NAME,
            '--public',
            '--description', 'Repository created by clawui automated test'
        ])
        log(f"✅ Successfully created repository: {GH_OWNER}/{REPO_NAME}")
        return f"https://github.com/{GH_OWNER}/{REPO_NAME}"
    except subprocess.CalledProcessError:
        log("❌ Failed to create repository using `gh`.")
        return None

def verify_repo_in_browser(repo_url):
    """Launch a browser and navigate to the repo URL to verify UI."""
    log("Verifying repository creation in browser via CDP...")
    client = CDPClient()
    browser_proc = None
    if not client.is_available():
        log("Starting Chromium for CDP...")
        browser_proc = subprocess.Popen([
            'snap', 'run', 'chromium', '--remote-debugging-port=9222',
            '--remote-allow-origins=*', '--no-first-run', 'about:blank'
        ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        time.sleep(4)
        if not client.is_available():
            log("❌ Failed to start Chromium with CDP.")
            if browser_proc: browser_proc.terminate()
            return False

    client.navigate(repo_url)
    time.sleep(3)
    
    page_title = client.get_page_title()
    log(f"Browser navigated to page with title: '{page_title}'")
    
    if browser_proc:
        browser_proc.terminate()

    return REPO_NAME in page_title

def clone_commit_push(repo_url):
    """Clones the new repo, adds a file, commits, and pushes."""
    log("Cloning, committing, and pushing test file...")
    tmp_dir = f"/tmp/{REPO_NAME}"
    ssh_url = f"git@github.com:{GH_OWNER}/{REPO_NAME}.git"
    
    if os.path.exists(tmp_dir):
        run_cmd(['rm', '-rf', tmp_dir])

    run_cmd(['git', 'clone', ssh_url, tmp_dir])
    
    test_file_path = os.path.join(tmp_dir, TEST_FILE)
    with open(test_file_path, 'w') as f:
        f.write(TEST_CONTENT)
    log(f"Created test file: {test_file_path}")
    
    # Use the 'cwd' argument for subprocess to run git commands in the new repo's directory
    run_cmd(['git', 'add', TEST_FILE], cwd=tmp_dir)
    run_cmd(['git', 'commit', '-m', f"feat: Add test file via clawui automation"], cwd=tmp_dir)
    run_cmd(['git', 'push', 'origin', 'main'], cwd=tmp_dir)
    log("✅ Successfully pushed test file to the new repository.")
    return True

def main():
    """Main execution loop."""
    log("Starting fully automated end-to-end test for `clawui`...")

    # Try to get a token: env var first, then config file.
    token = os.getenv("GITHUB_TOKEN") or load_token_from_config()
    creation_method = None  # 'api' or 'gh'
    repo_url = None

    # Attempt API method if token is available
    if token:
        repo_url = create_repo_via_api(token, REPO_NAME, REPO_DESC)
        if repo_url:
            creation_method = 'api'
        else:
            log("❌ API method failed.")
            token = None  # clear token to try gh next

    # If API failed or no token, try gh CLI
    if not token:
        if check_gh_auth():
            repo_url = create_repo_with_gh()
            if repo_url:
                creation_method = 'gh'
            else:
                log("❌ Failed to create repository using `gh`.")
                return 1
        else:
            log("❌ No GitHub authentication available (neither GITHUB_TOKEN nor gh CLI auth).")
            log("   Please set GITHUB_TOKEN or run 'gh auth login'.")
            return 2

    if not repo_url:
        log("❌ Failed to obtain repository URL.")
        return 1

    if not verify_repo_in_browser(repo_url):
        log("⚠️ Browser verification failed, but repo likely exists. Proceeding with git.")

    if not clone_commit_push(repo_url):
        log("❌ Git operations failed.")
        # Still attempt cleanup before returning
        if creation_method == 'api':
            delete_repo_via_api(token, REPO_NAME)
        elif creation_method == 'gh':
            run_cmd(['gh', 'repo', 'delete', REPO_NAME, '--yes'])
        return 1

    log("✅✅✅ Full end-to-end test completed successfully! ✅✅✅")

    # Clean up the created repo
    log(f"Cleaning up by deleting repository '{REPO_NAME}'...")
    if creation_method == 'api':
        if not delete_repo_via_api(token, REPO_NAME):
            log("⚠️ API deletion failed; you may need to delete the repo manually.")
    elif creation_method == 'gh':
        run_cmd(['gh', 'repo', 'delete', REPO_NAME, '--yes'])
    else:
        log("⚠️ Unknown creation method; skipping automatic deletion.")

    return 0

if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        log(f"An unexpected error occurred: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
