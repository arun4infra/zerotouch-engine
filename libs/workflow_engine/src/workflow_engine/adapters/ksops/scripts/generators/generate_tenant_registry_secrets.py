#!/usr/bin/env python3
"""
Generate tenant registry secrets from ~/.ztp/secrets
Creates ArgoCD repo credentials and GHCR pull secrets
"""

import sys
import base64
import configparser
import json
from pathlib import Path
from typing import Dict, List, Optional
from jinja2 import Environment, FileSystemLoader
import re


def load_secrets(secrets_file: Path) -> Dict[str, Dict[str, str]]:
    """Load secrets from ~/.ztp/secrets INI file"""
    if not secrets_file.exists():
        raise FileNotFoundError(f"Secrets file not found: {secrets_file}")
    
    print(f"Loading secrets from: {secrets_file}", file=sys.stderr)
    
    config = configparser.ConfigParser()
    config.read(secrets_file)
    
    print(f"Found sections: {config.sections()}", file=sys.stderr)
    
    secrets = {}
    for section in config.sections():
        print(f"Processing section: {section}", file=sys.stderr)
        secrets[section] = {}
        for key, value in config.items(section):
            print(f"  Loading {section}.{key} (length: {len(value)})", file=sys.stderr)
            # Decode base64-encoded values (multi-line secrets like private keys)
            if value.startswith("base64:"):
                print(f"  Decoding base64 value for {section}.{key}", file=sys.stderr)
                try:
                    decoded = base64.b64decode(value[7:]).decode()
                    secrets[section][key] = decoded
                    print(f"  ✓ Decoded {section}.{key}", file=sys.stderr)
                except Exception as e:
                    print(f"Warning: Failed to decode base64 value for {section}.{key}: {e}", file=sys.stderr)
                    secrets[section][key] = value
            else:
                secrets[section][key] = value
    
    print(f"Successfully loaded {len(secrets)} sections", file=sys.stderr)
    return secrets


def extract_org_and_repo(tenant_repo_url: str) -> tuple[Optional[str], Optional[str]]:
    """Extract org and repo name from GitHub URL"""
    match = re.match(r'https://github\.com/([^/]+)/([^/]+)', tenant_repo_url)
    if match:
        return match.group(1), match.group(2)
    return None, None


def generate_jwt(app_id: str, private_key: str) -> str:
    """Generate JWT for GitHub App authentication"""
    import time
    import jwt
    
    now = int(time.time())
    payload = {
        'iat': now - 60,
        'exp': now + 600,
        'iss': app_id
    }
    
    return jwt.encode(payload, private_key, algorithm='RS256')


def get_github_app_token(app_id: str, installation_id: str, private_key: str) -> Optional[str]:
    """Get GitHub App installation access token"""
    import requests
    
    try:
        jwt_token = generate_jwt(app_id, private_key)
        
        response = requests.post(
            f'https://api.github.com/app/installations/{installation_id}/access_tokens',
            headers={
                'Authorization': f'Bearer {jwt_token}',
                'Accept': 'application/vnd.github+json'
            },
            timeout=10
        )
        
        if response.status_code == 201:
            return response.json().get('token')
        else:
            print(f"Warning: Failed to get GitHub token: {response.status_code}", file=sys.stderr)
            return None
    except Exception as e:
        print(f"Warning: Error getting GitHub token: {e}", file=sys.stderr)
        return None


def generate_tenant_secrets(secrets: Dict, templates_dir: Path, output_dir: Path, github_config: Dict = None) -> List[str]:
    """Generate tenant registry secrets (ArgoCD repo creds, GHCR pull secret)
    
    Args:
        secrets: Secrets loaded from ~/.ztp/secrets
        templates_dir: Path to Jinja2 templates
        output_dir: Output directory for generated secrets
        github_config: GitHub config from platform.yaml (contains repo URLs)
    """
    if github_config is None:
        github_config = {}
    
    env = Environment(loader=FileSystemLoader(templates_dir))
    generated_files = []
    
    # Extract GitHub private key from ~/.ztp/secrets
    github_secrets = secrets.get('github', {})
    git_app_private_key = github_secrets.get('github_app_private_key', '')
    
    # Get other GitHub fields from platform.yaml
    git_app_id = github_config.get('github_app_id', '')
    git_app_installation_id = github_config.get('github_app_installation_id', '')
    data_plane_repo_url = github_config.get('data_plane_repo_url', '')
    
    org_name, tenants_repo_name = extract_org_and_repo(data_plane_repo_url)
    
    # Generate ArgoCD repo credentials
    if org_name and tenants_repo_name and git_app_id and git_app_installation_id and git_app_private_key:
        repo_url = f"https://github.com/{org_name}/{tenants_repo_name}.git"
        
        secret_yaml = f"""apiVersion: v1
kind: Secret
metadata:
  name: repo-zerotouch-tenants
  namespace: argocd
  labels:
    argocd.argoproj.io/secret-type: repo-creds
  annotations:
    argocd.argoproj.io/sync-wave: "2"
type: Opaque
stringData:
  type: git
  url: {repo_url}
  project: default
  githubAppID: "{git_app_id}"
  githubAppInstallationID: "{git_app_installation_id}"
  githubAppPrivateKey: |
"""
        # Indent private key lines
        for line in git_app_private_key.splitlines():
            secret_yaml += f"    {line}\n"
        
        output_file = output_dir / 'repo-zerotouch-tenants.secret.yaml'
        output_file.write_text(secret_yaml)
        generated_files.append('repo-zerotouch-tenants.secret.yaml')
    
    # Generate GHCR pull secret
    if git_app_id and git_app_installation_id and git_app_private_key:
        github_token = get_github_app_token(git_app_id, git_app_installation_id, git_app_private_key)
        
        if github_token:
            # Create dockerconfigjson
            auth_string = base64.b64encode(f"x-access-token:{github_token}".encode()).decode()
            docker_config = {
                "auths": {
                    "ghcr.io": {
                        "auth": auth_string
                    }
                }
            }
            dockerconfigjson_base64 = base64.b64encode(json.dumps(docker_config).encode()).decode()
            
            template = env.get_template('ghcr-pull-secret.yaml.j2')
            content = template.render(
                secret_name='ghcr-pull-secret',
                namespace='argocd',
                annotations='argocd.argoproj.io/sync-wave: "0"',
                dockerconfigjson_base64=dockerconfigjson_base64
            )
            
            output_file = output_dir / 'ghcr-pull-secret.secret.yaml'
            output_file.write_text(content)
            generated_files.append('ghcr-pull-secret.secret.yaml')
    
    return generated_files


def main():
    """Main entry point"""
    if len(sys.argv) != 2:
        print("Usage: generate_tenant_registry_secrets.py <output_dir>", file=sys.stderr)
        sys.exit(1)
    
    output_dir = Path(sys.argv[1])
    print(f"Output directory: {output_dir}", file=sys.stderr)
    
    # Load secrets from ~/.ztp/secrets
    secrets_file = Path.home() / '.ztp' / 'secrets'
    print(f"Secrets file path: {secrets_file}", file=sys.stderr)
    
    try:
        secrets = load_secrets(secrets_file)
        print(f"Loaded secrets for adapters: {list(secrets.keys())}", file=sys.stderr)
    except Exception as e:
        print(f"Error loading secrets: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc(file=sys.stderr)
        sys.exit(1)
    
    # Load platform.yaml for repo URLs
    platform_yaml_path = Path("platform/platform.yaml")
    github_config = {}
    if platform_yaml_path.exists():
        print(f"Loading platform.yaml from: {platform_yaml_path}", file=sys.stderr)
        import yaml
        with open(platform_yaml_path) as f:
            platform_data = yaml.safe_load(f)
            github_config = platform_data.get('adapters', {}).get('github', {})
            print(f"GitHub config from platform.yaml: {list(github_config.keys())}", file=sys.stderr)
    
    # Create output directory
    output_dir.mkdir(parents=True, exist_ok=True)
    print(f"Created output directory: {output_dir}", file=sys.stderr)
    
    # Load templates from installed package using context manager
    import importlib.resources
    templates_pkg = importlib.resources.files('workflow_engine.adapters.ksops.templates')
    
    with importlib.resources.as_file(templates_pkg) as templates_path:
        generated_files = generate_tenant_secrets(secrets, templates_path, output_dir, github_config)
    
    # Output list of generated files as JSON
    print(json.dumps(generated_files))


if __name__ == '__main__':
    main()
