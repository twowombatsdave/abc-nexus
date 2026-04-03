#!/usr/bin/env python3
"""
GitHub Secrets Setup Script

This script sets up GitHub secrets from a secrets.json file using GitHub CLI.
Supports both string secrets and file-based secrets (JSON credentials).

Usage:
    python gh_secrets.py

Requirements:
    - GitHub CLI (gh) installed and authenticated
    - config/secrets.json file with 'strings' and 'files' keys
"""

import json
import subprocess
import sys
from pathlib import Path

def check_gh_cli():
    """Check if GitHub CLI is installed and authenticated."""
    try:
        # Check if gh is installed
        result = subprocess.run(['gh', '--version'], capture_output=True, text=True, check=True)
        print("✓ GitHub CLI is installed")

        # Check if authenticated
        result = subprocess.run(['gh', 'auth', 'status'], capture_output=True, text=True, check=True)
        print("✓ GitHub CLI is authenticated")
        return True

    except subprocess.CalledProcessError as e:
        print("Error: GitHub CLI not available or not authenticated.")
        print("Please install GitHub CLI and run 'gh auth login'")
        print(f"Error details: {e}")
        return False
    except FileNotFoundError:
        print("Error: GitHub CLI (gh) not found.")
        print("Please install GitHub CLI from: https://cli.github.com/")
        return False

def get_repo_info():
    """Get repository information from git config or gh CLI as fallback."""
    # 1) Try git remote first
    try:
        result = subprocess.run(
            ['git', 'remote', 'get-url', 'origin'],
            capture_output=True,
            text=True,
            check=True,
        )
        remote_url = result.stdout.strip()

        repo_path = None
        if 'github.com' in remote_url:
            if remote_url.startswith('git@github.com:'):
                repo_path = remote_url.replace('git@github.com:', '')
            elif remote_url.startswith('ssh://git@github.com/'):
                repo_path = remote_url.replace('ssh://git@github.com/', '')
            elif remote_url.startswith('https://github.com/'):
                repo_path = remote_url.replace('https://github.com/', '')
            elif 'github.com:' in remote_url:
                # e.g. github.com:owner/repo
                repo_path = remote_url.split('github.com:')[1]

        if repo_path:
            return repo_path.replace('.git', '')
    except subprocess.CalledProcessError:
        pass

    # 2) Fallback to gh CLI (works even outside a git repo if authed in the repo context)
    try:
        gh_view = subprocess.run(
            ['gh', 'repo', 'view', '--json', 'nameWithOwner', '-q', '.nameWithOwner'],
            capture_output=True,
            text=True,
            check=True,
        )
        repo_path = gh_view.stdout.strip()
        if repo_path:
            return repo_path
    except subprocess.CalledProcessError:
        pass

    print("Error: Could not detect GitHub repository (git or gh).")
    print("Tip: run this inside a cloned GitHub repo, or set the remote 'origin'.")
    sys.exit(1)

def read_secrets_config():
    """Read secrets configuration from config/secrets.json file."""
    secrets_path = Path("./config/secrets.json")

    if not secrets_path.exists():
        print(f"Error: Secrets file not found at {secrets_path}")
        print("Please create config/secrets.json with the following format:")
        print('''
{
  "strings": {
    "SECRET_NAME_1": "secret_value_1",
    "SECRET_NAME_2": "secret_value_2"
  },
  "files": {
    "SERVICE_ACCOUNT_SECRET": "service_account.json",
    "OTHER_CREDS_SECRET": "other_credentials.json"
  }
}
        ''')
        sys.exit(1)

    try:
        with open(secrets_path, 'r') as f:
            config = json.load(f)

        # Validate structure
        if 'strings' not in config and 'files' not in config:
            print("Error: secrets.json must contain 'strings' and/or 'files' keys")
            sys.exit(1)

        return config
    except json.JSONDecodeError:
        print("Error: Invalid JSON in secrets file.")
        sys.exit(1)
    except Exception as e:
        print(f"Error reading secrets file: {e}")
        sys.exit(1)

def set_github_secret(repo_path, secret_name, secret_value):
    """Set a single GitHub secret using GitHub CLI."""
    try:
        print(f"Setting secret '{secret_name}'...")
        result = subprocess.run([
            'gh', 'secret', 'set', secret_name,
            '--repo', repo_path,
            '--body', secret_value
        ], capture_output=True, text=True, check=True)

        print(f"✓ Secret '{secret_name}' set successfully!")
        return True

    except subprocess.CalledProcessError as e:
        print(f"Error setting secret '{secret_name}': {e}")
        print(f"Command output: {e.stdout}")
        print(f"Error output: {e.stderr}")
        return False
    except Exception as e:
        print(f"Unexpected error setting secret '{secret_name}': {e}")
        return False

def read_file_content(file_path):
    """Read the full content of a file."""
    try:
        with open(file_path, 'r') as f:
            return f.read()
    except Exception as e:
        print(f"Error reading file {file_path}: {e}")
        return None

def setup_github_secrets():
    """Main function to set up GitHub secrets from config/secrets.json."""
    print("GitHub Secrets Setup")
    print("=" * 30)

    # Check GitHub CLI
    if not check_gh_cli():
        sys.exit(1)

    # Get repository info
    repo_path = get_repo_info()
    print(f"Repository: {repo_path}")

    # Read secrets configuration
    print("Reading secrets configuration...")
    config = read_secrets_config()
    print("✓ Secrets configuration loaded successfully")

    # Process string secrets
    string_secrets = config.get('strings', {})
    file_secrets = config.get('files', {})

    total_secrets = len(string_secrets) + len(file_secrets)
    success_count = 0

    print(f"\nProcessing {len(string_secrets)} string secrets and {len(file_secrets)} file secrets...")

    # Set up string secrets
    if string_secrets:
        print("\nSetting up string secrets...")
        for secret_name, secret_value in string_secrets.items():
            if set_github_secret(repo_path, secret_name, secret_value):
                success_count += 1

    # Set up file-based secrets
    if file_secrets:
        print("\nSetting up file-based secrets...")
        for secret_name, file_path in file_secrets.items():
            full_path = Path("./config") / file_path
            if not full_path.exists():
                print(f"❌ File not found: {full_path}")
                continue

            file_content = read_file_content(full_path)
            if file_content is not None:
                if set_github_secret(repo_path, secret_name, file_content):
                    success_count += 1

    print(f"\n📊 Setup Summary:")
    print(f"Repository: {repo_path}")
    print(f"Secrets Set: ✅ {success_count}/{total_secrets}")

    if success_count == total_secrets:
        print("\n✅ Setup complete! All secrets have been uploaded to GitHub.")
    else:
        print(f"\n❌ Setup failed for {total_secrets - success_count} secrets. Please check the error messages above.")
        sys.exit(1)

if __name__ == "__main__":
    setup_github_secrets()
