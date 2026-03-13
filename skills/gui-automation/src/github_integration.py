"""GitHub integration for ClawUI agent.

Provides a unified `create_github_repo` function that tries multiple authentication
methods in order of preference:
1. GITHUB_TOKEN (or config file) via GitHub API
2. gh CLI (if authenticated)
3. CDP browser automation (requires logged-in session)

All network operations use standard library (urllib) to avoid extra dependencies.
"""

import json
import os
import subprocess
import time
import urllib.request
import urllib.error
from pathlib import Path
from typing import Optional, Tuple, Dict, Any

from .cdp_helper import get_or_create_cdp_client, launch_chromium_with_cdp


def load_token_from_config() -> Optional[str]:
    """Load GitHub PAT from ClawUI config file (~/.config/clawui/config.json)."""
    config_path = Path.home() / ".config" / "clawui" / "config.json"
    if not config_path.exists():
        return None
    try:
        with open(config_path) as f:
            config = json.load(f)
            token = config.get("github_pat") or config.get("github_token")
            if token:
                return token
    except Exception:
        pass
    return None


def get_github_token() -> Optional[str]:
    """Get GitHub token from environment or config."""
    return os.getenv("GITHUB_TOKEN") or os.getenv("GITHUB_PAT") or load_token_from_config()


def get_github_username(token: str) -> Optional[str]:
    """Fetch authenticated username via GitHub API."""
    try:
        req = urllib.request.Request(
            "https://api.github.com/user",
            headers={"Authorization": f"token {token}"}
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.load(resp)
            return data.get("login")
    except Exception:
        return None


def is_gh_authenticated() -> bool:
    """Check if the user is authenticated with the gh CLI."""
    try:
        subprocess.run(
            ['gh', 'auth', 'status'],
            check=True,
            capture_output=True,
            text=True,
            timeout=5
        )
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


def create_repo_via_api(token: str, repo_name: str, repo_desc: str = "") -> Tuple[bool, Optional[str], Optional[str]]:
    """Create a GitHub repo using the API.

    Returns (success, error_message, html_url).
    """
    try:
        # Determine if repo_name includes an owner (e.g., "org/repo")
        if '/' in repo_name:
            # Might be creating under an org; use /orgs/:org/repos
            owner, repo = repo_name.split('/', 1)
            if owner.lower() == "users":  # not supported
                return False, "Invalid owner in repo_name", None
            url = f"https://api.github.com/orgs/{owner}/repos"
            data = {"name": repo, "description": repo_desc, "private": False}
        else:
            url = "https://api.github.com/user/repos"
            data = {"name": repo_name, "description": repo_desc, "private": False}

        headers = {
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github.v3+json"
        }
        req_data = json.dumps(data).encode('utf-8')
        req = urllib.request.Request(url, data=req_data, headers=headers, method='POST')
        with urllib.request.urlopen(req, timeout=15) as resp:
            if resp.status == 201:
                resp_data = json.load(resp)
                html_url = resp_data.get("html_url")
                return True, None, html_url
            else:
                body = resp.read().decode('utf-8', errors='ignore')
                return False, f"HTTP {resp.status}: {body[:200]}", None
    except urllib.error.HTTPError as e:
        body = e.read().decode('utf-8', errors='ignore') if e.fp else ""
        return False, f"HTTP {e.code}: {body[:200]}", None
    except urllib.error.URLError as e:
        return False, f"Network error: {e.reason}", None
    except Exception as e:
        return False, str(e), None


def create_repo_via_gh_cli(repo_name: str, repo_desc: str = "") -> Tuple[bool, Optional[str], Optional[str]]:
    """Create a GitHub repo using the gh CLI.

    Returns (success, error_message, repo_url).
    """
    try:
        # gh repo create accepts full name or just name
        cmd = ['gh', 'repo', 'create', repo_name, '--public']
        if repo_desc:
            cmd.append(f'--description={repo_desc}')
        # Use --json to get structured output (gh >= 2.0)
        cmd.append('--json')
        cmd.append('html_url')
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=20, check=False)
        if result.returncode == 0:
            try:
                data = json.loads(result.stdout)
                html_url = data.get("html_url")
                return True, None, html_url
            except json.JSONDecodeError:
                # Fallback: try to extract URL from stderr
                return True, None, f"https://github.com/{repo_name}"
        else:
            err = result.stderr.strip() or result.stdout.strip()
            return False, f"gh error: {err[:200]}", None
    except FileNotFoundError:
        return False, "gh command not found", None
    except subprocess.TimeoutExpired:
        return False, "gh command timed out", None
    except Exception as e:
        return False, str(e), None


def _ensure_cdp_client(timeout: int = 15):
    """Get or launch a CDP client."""
    client = get_or_create_cdp_client()
    if client and client.is_available():
        return client
    # Try to launch Chromium
    proc = launch_chromium_with_cdp()
    if not proc:
        return None
    # Wait for CDP to be ready
    for _ in range(timeout):
        time.sleep(1)
        if client and client.is_available():
            return client
    return None


def create_repo_via_cdp(client, repo_name: str, repo_desc: str = "") -> Tuple[bool, Optional[str], Optional[str]]:
    """Create a GitHub repo using CDP browser automation.

    Assumes the logged-in user is already authenticated on github.com.

    Returns (success, error_message, final_url).
    """
    try:
        # Navigate to new repo page
        client.navigate("https://github.com/new")
        time.sleep(3)  # wait for page load

        # Check login status: presence of "Sign in" link/button
        title = client.get_page_title() or ""
        if "sign in" in title.lower() or "log in" in title.lower():
            return False, "Not logged in to GitHub in browser session", None

        # Fill repository name
        fill_js = f'''
        (function() {{
            const nameInput = document.querySelector('input[name="repository[name]"], input[id="repository_name"]');
            if (!nameInput) return "no-name-field";
            nameInput.value = "{repo_name}";
            nameInput.dispatchEvent(new Event('input', {{bubbles:true}}));
            const descInput = document.querySelector('input[name="repository[description]"], textarea[name="repository[description]"]');
            if (descInput) {{ descInput.value = "{repo_desc}"; descInput.dispatchEvent(new Event('input', {{bubbles:true}})); }}
            return "filled";
        }})()
        '''
        fill_result = client.evaluate(fill_js)
        if not fill_result or fill_result.get('result', {}).get('value') == "no-name-field":
            return False, "Could not find repository name field", None
        time.sleep(1)

        # Click "Create repository" button
        click_js = '''
        (function() {
            const btns = Array.from(document.querySelectorAll('button'));
            const createBtn = btns.find(b => b.textContent.trim().includes('Create repository'));
            if (createBtn) {
                createBtn.click();
                return "clicked";
            }
            return "not-found";
        })()
        '''
        click_result = client.evaluate(click_js)
        time.sleep(3)

        # Verify success: URL should contain /<username>/<repo_name>
        final_url = client.get_page_url() or ""
        if repo_name in final_url and "github.com" in final_url:
            return True, None, final_url
        else:
            return False, f"Unexpected page after creation: {final_url}", final_url
    except Exception as e:
        return False, str(e), None


def create_github_repo(repo_name: str, repo_desc: str = "") -> Dict[str, Any]:
    """Create a GitHub repository using the best available method.

    Order of attempts:
    1. GITHUB_TOKEN (or config) via API
    2. gh CLI (if authenticated)
    3. CDP browser automation (requires logged-in session)

    Args:
        repo_name: Repository name (e.g., 'my-repo' or 'org/my-repo')
        repo_desc: Optional description

    Returns:
        dict with keys: success (bool), method (str or None), error (str or None), repo_url (str or None)
    """
    # Method 1: API token
    token = get_github_token()
    if token:
        success, error, html_url = create_repo_via_api(token, repo_name, repo_desc)
        if success:
            return {"success": True, "method": "api", "error": None, "repo_url": html_url or f"https://github.com/{repo_name}"}
        # If API fails due to auth, continue to next method

    # Method 2: gh CLI
    if is_gh_authenticated():
        success, error, html_url = create_repo_via_gh_cli(repo_name, repo_desc)
        if success:
            return {"success": True, "method": "gh", "error": None, "repo_url": html_url or f"https://github.com/{repo_name}"}

    # Method 3: CDP browser automation
    try:
        client = _ensure_cdp_client()
        if not client:
            return {"success": False, "method": None, "error": "Failed to start CDP browser", "repo_url": None}
        success, error, final_url = create_repo_via_cdp(client, repo_name, repo_desc)
        if success:
            return {"success": True, "method": "cdp", "error": None, "repo_url": final_url}
        return {"success": False, "method": "cdp", "error": error, "repo_url": None}
    except Exception as e:
        return {"success": False, "method": None, "error": str(e), "repo_url": None}


# Expose for direct usage
__all__ = ["create_github_repo"]
