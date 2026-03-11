#!/usr/bin/env python3
"""
End-to-end GitHub repository creation using CDP browser automation.
Assumptions:
- Chromium is running with default profile and already logged into GitHub.
- The session is valid (no 2FA prompt).
"""

import sys, os, time, json, re

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

from cdp_helper import CDPClient

def main():
    c = CDPClient()
    if not c.is_available():
        print("ERROR: CDP not available. Start Chromium with --remote-debugging-port=9222")
        return

    print("=== GitHub Repo Creation E2E Demo ===\n")

    # 1. Navigate to new repo page
    url = "https://github.com/new"
    print(f"1. Navigate to {url}")
    c.navigate(url)
    time.sleep(3)

    # 2. Check if we're logged in: look for "Sign in" link or avatar
    login_btn = c.evaluate('document.querySelector(\'a[href*="login"]\') !== null')
    if login_btn.get('result', {}).get('value'):
        print("   ERROR: Not logged in to GitHub. Sign in first in the default browser profile.")
        print("   Aborting demo. (You can log in manually then re-run.)")
        return
    else:
        print("   Logged in (no sign-in button detected).")

    # 3. Generate a unique repo name
    repo_name = f"clawui-demo-repo-{int(time.time())}"
    print(f"2. Repository name: {repo_name}")

    # 4. Fill repository name
    print("3. Filling repository name field...")
    # Use selector for the repo name input; GitHub uses input with id="repository_name"
    c.type_text('input[id="repository_name"]', repo_name)
    time.sleep(0.5)

    # 5. Optionally fill description
    c.type_text('input[id="repository_description"]', "Created by ClawUI CDP automation demo")
    time.sleep(0.5)

    # 6. Select Public (if not default)
    # The radio for Public has id="repository_visibility_public"
    public_radio = c.evaluate('document.querySelector(\'input[id="repository_visibility_public"]\')')
    if public_radio and 'false' in str(public_radio):
        c.click_element('input[id="repository_visibility_public"]')
        time.sleep(0.3)

    # 7. Uncheck "Initialize this repository with a README" if present (so creation is instant)
    try:
        c.click_element('input[ id="repository_auto_init"]')
        time.sleep(0.2)
    except:
        pass

    # 8. Click "Create repository" button
    # The button text may be "Create repository"
    print("4. Creating repository...")
    # The button has data-disable-with and contains "Create repository"
    c.evaluate('''
        (function() {
            const btns = Array.from(document.querySelectorAll('button'));
            const createBtn = btns.find(b => b.textContent.trim() === 'Create repository');
            if (createBtn) { createBtn.click(); return 'clicked'; }
            return 'not-found';
        })()
    ''')
    time.sleep(2)

    # 9. Verify success: URL should contain /<username>/<repo_name>
    current_url = c.get_page_url()
    print(f"5. Current URL: {current_url}")

    if re.search(r"github\.com/[^/]+/" + re.escape(repo_name), current_url):
        print(f"\n✅ SUCCESS: Repository '{repo_name}' created!")
    else:
        print("\n⚠️  WARNING: Could not confirm creation. Check page manually.")

    # 10. Take a screenshot
    ss = c.take_screenshot()
    print(f"Screenshot: {len(ss) if ss else 0} chars base64")

    print("\n=== E2E Demo finished ===")

if __name__ == "__main__":
    main()
