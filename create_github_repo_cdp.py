#!/usr/bin/env python3
"""
GitHub repo creation automation using one of three methods, in order of preference:
1. GITHUB_TOKEN: Uses the GitHub API directly.
2. gh CLI: Uses `gh repo create` if the user is authenticated.
3. CDP Fallback: Uses browser automation, requiring a logged-in session.
"""

import sys, os, subprocess, time, json, requests

sys.path.insert(0, '/home/hung/.openclaw/workspace/skills/gui-automation')
from src.cdp_helper import CDPClient

# Config
REPO_NAME = "clawui-test-repo-" + str(int(time.time()))
REPO_DESC = "Test repository created via automation"
GITHUB_USER = "longgo1001"

def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}")

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
            return True
        else:
            log(f"❌ API request failed: {response.status_code} {response.text}")
            return False
    except requests.RequestException as e:
        log(f"❌ API request error: {e}")
        return False

def is_gh_authenticated():
    """Check if the user is authenticated with the gh CLI."""
    log("Checking gh auth status...")
    try:
        subprocess.run(['gh', 'auth', 'status'], check=True, capture_output=True, text=True, timeout=5)
        log("✅ gh CLI is authenticated.")
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        log("gh CLI not authenticated or not installed.")
        return False

def create_repo_via_gh_cli(repo_name, repo_desc):
    """Create a GitHub repo using the gh CLI."""
    log("Attempting to create repo via gh CLI...")
    repo_full_name = f"{GITHUB_USER}/{repo_name}"
    try:
        command = ['gh', 'repo', 'create', repo_full_name, '--public', f'--description={repo_desc}']
        subprocess.run(command, check=True, capture_output=True, text=True, timeout=20)
        log(f"✅ Repo {repo_full_name} created successfully via gh CLI.")
        return True
    except subprocess.CalledProcessError as e:
        log(f"❌ gh repo create failed: {e.stderr.strip()}")
        return False
    except FileNotFoundError:
        log("❌ gh command not found.")
        return False

def ensure_chromium():
    """Start Chromium with CDP if not running."""
    client = CDPClient()
    if client.is_available(): return client
    log("Launching Chromium...")
    subprocess.Popen(['snap', 'run', 'chromium', '--remote-debugging-port=9222', '--remote-allow-origins=*', '--no-first-run', 'about:blank'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for _ in range(10):
        if client.is_available():
            log("Chromium ready")
            return client
        time.sleep(1)
    raise RuntimeError("Chromium failed to start")

def create_repo_via_cdp(client: CDPClient):
    """Navigate to new repo page and create."""
    log("Navigating to new repo page...")
    client.navigate("https://github.com/new")
    time.sleep(3)
    js = f'''
    (function() {{
        const nameInput = document.querySelector('input[name="repository[name]"]');
        if (!nameInput) return "no-name-field";
        nameInput.value = "{REPO_NAME}";
        nameInput.dispatchEvent(new Event('input', {{bubbles:true}}));
        const descInput = document.querySelector('input[name="repository[description]"], textarea[name="repository[description]"]');
        if (descInput) {{ descInput.value = "{REPO_DESC}"; descInput.dispatchEvent(new Event('input', {{bubbles:true}})); }}
        return "filled";
    }})()
    '''
    client.evaluate(js)
    time.sleep(1)
    click_js = "Array.from(document.querySelectorAll('button')).find(b => b.textContent.trim().includes('Create repository'))?.click()"
    client.evaluate(click_js)
    time.sleep(3)
    return REPO_NAME in client.get_page_url()

def verify_via_git():
    """Verify repo exists via git ls-remote."""
    repo_url = f"https://github.com/{GITHUB_USER}/{REPO_NAME}.git"
    log(f"Verifying via git: {repo_url}")
    result = subprocess.run(['git', 'ls-remote', repo_url], capture_output=True, text=True, timeout=10)
    return result.returncode == 0

def main():
    log(f"=== GitHub Repo Creation ===")
    log(f"Target repository: {REPO_NAME}")

    github_token = os.getenv("GITHUB_TOKEN")

    # Method 1: API Token
    if github_token:
        if create_repo_via_api(github_token, REPO_NAME, REPO_DESC) and verify_via_git():
            log("✅ End-to-End SUCCESS (API)")
            return 0
        log("❌ API method failed.")
        return 1

    # Method 2: gh CLI
    if is_gh_authenticated():
        if create_repo_via_gh_cli(REPO_NAME, REPO_DESC) and verify_via_git():
            log("✅ End-to-End SUCCESS (gh CLI)")
            return 0
        log("❌ gh CLI method failed.")
        return 1

    # Method 3: CDP Fallback
    log("No token or gh auth found. Falling back to CDP browser automation.")
    try:
        client = ensure_chromium()
        client.navigate("https://github.com")
        time.sleep(2)
        if "sign in" in client.get_page_title().lower():
            log("⚠️  Not logged in to GitHub. Please log in or set GITHUB_TOKEN/gh auth.")
            return 2
        if create_repo_via_cdp(client) and verify_via_git():
            log("✅ End-to-End SUCCESS (CDP)")
            return 0
        log("❌ CDP method failed.")
        return 1
    except Exception as e:
        log(f"❌ CDP Error: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())
