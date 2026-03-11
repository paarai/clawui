# tools/github_pat_manager.py

import os
import json
from pathlib import Path

CONFIG_DIR = Path.home() / ".config" / "clawui"
CONFIG_FILE = CONFIG_DIR / "config.json"

def save_token(token: str):
    """
    Saves the GitHub PAT to the local config file.
    Creates the config directory if it doesn't exist.
    """
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    
    config = {}
    if CONFIG_FILE.exists():
        with open(CONFIG_FILE, 'r') as f:
            try:
                config = json.load(f)
            except json.JSONDecodeError:
                pass # Overwrite if corrupt

    config['github_pat'] = token
    
    with open(CONFIG_FILE, 'w') as f:
        json.dump(config, f, indent=2)
    
    print(f"GitHub token saved to {CONFIG_FILE}")

def load_token() -> str | None:
    """
    Loads the GitHub PAT from the local config file.
    Returns the token string or None if not found.
    """
    if not CONFIG_FILE.exists():
        return None
        
    with open(CONFIG_FILE, 'r') as f:
        try:
            config = json.load(f)
            return config.get('github_pat')
        except (json.JSONDecodeError, KeyError):
            return None

def main():
    """
    A simple CLI for managing the PAT.
    """
    import argparse
    parser = argparse.ArgumentParser(description="Manage GitHub Personal Access Token for ClawUI.")
    parser.add_argument("--save", type=str, help="Save a new token.")
    parser.add_argument("--load", action="store_true", help="Load and print the token.")
    
    args = parser.parse_args()
    
    if args.save:
        save_token(args.save)
    elif args.load:
        token = load_token()
        if token:
            print(f"Loaded token: ...{token[-4:]}") # Obfuscate for safety
        else:
            print("No token found.")
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
