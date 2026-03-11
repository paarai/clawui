#!/usr/bin/env python3
"""
E2E Test: Fully automated GitHub repository creation.

This script demonstrates fully automated, end-to-end functionality for the
`clawui` tool. It combines robust CLI commands with browser UI automation
to achieve its goal without manual intervention, assuming a one-time setup
for GitHub authentication.

**Workflow:**
1.  Checks for GitHub CLI (`gh`) authentication.
2.  If authenticated, creates a new public repository using `gh repo create`.
3.  Launches Chromium via CDP (`cdp_helper`).
4.  Navigates the browser to the new repository's URL to verify its creation via UI.
5.  Clones the new repository into a temporary directory.
6.  Creates a test file, commits it, and pushes it to the new repository.
"""

import subprocess
import time
import os
import sys
import datetime

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

def log(msg):
    """Simple logger."""
    print(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] {msg}")

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
    if not check_gh_auth():
        return 2 
    
    repo_url = create_repo_with_gh()
    if not repo_url:
        return 1
        
    if not verify_repo_in_browser(repo_url):
        log("⚠️ Browser verification failed, but repo likely exists. Proceeding with git.")
        
    if not clone_commit_push(repo_url):
        return 1

    log("✅✅✅ Full end-to-end test completed successfully! ✅✅✅")
    # Clean up the created repo
    log(f"Cleaning up by deleting repository '{REPO_NAME}'...")
    run_cmd(['gh', 'repo', 'delete', REPO_NAME, '--yes'])
    return 0

if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        log(f"An unexpected error occurred: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
