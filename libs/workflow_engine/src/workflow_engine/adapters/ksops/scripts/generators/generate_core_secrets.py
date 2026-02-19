#!/usr/bin/env python3
"""
Generate core Kubernetes secrets from ~/.ztp/secrets
Renders Jinja2 templates and outputs unencrypted YAML files
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


def generate_core_secrets(secrets: Dict, templates_dir: Path, output_dir: Path, github_config: Dict = None) -> List[str]:
    """Generate core platform secrets
    
    Args:
        secrets: Secrets loaded from ~/.ztp/secrets
        templates_dir: Path to Jinja2 templates
        output_dir: Output directory for generated secrets
        github_config: GitHub config from platform.yaml (contains repo URLs)
    """
    if github_config is None:
        github_config = {}
    
    env = Environment(loader=FileSystemLoader(templates_dir))
    template = env.get_template('universal-secret.yaml.j2')
    
    generated_files = []
    
    # Extract GitHub secrets from ~/.ztp/secrets
    github_secrets = secrets.get('github', {})
    git_app_private_key = github_secrets.get('github_app_private_key', '')
    
    # Get other GitHub fields from platform.yaml
    git_app_id = github_config.get('github_app_id', '')
    git_app_installation_id = github_config.get('github_app_installation_id', '')
    data_plane_repo_url = github_config.get('data_plane_repo_url', '')
    
    # Extract org and repo from data plane URL
    org_name, tenants_repo_name = extract_org_and_repo(data_plane_repo_url)
    
    # Generate ORG_NAME secret
    if org_name:
        content = template.render(
            secret_name='org-name',
            namespace='kube-system',
            annotations='argocd.argoproj.io/sync-wave: "0"',
            secret_type='Opaque',
            secret_key='value',
            secret_value=org_name
        )
        output_file = output_dir / 'org-name.secret.yaml'
        output_file.write_text(content)
        generated_files.append('org-name.secret.yaml')
    
    # Generate TENANTS_REPO_NAME secret
    if tenants_repo_name:
        content = template.render(
            secret_name='tenants-repo-name',
            namespace='kube-system',
            annotations='argocd.argoproj.io/sync-wave: "0"',
            secret_type='Opaque',
            secret_key='value',
            secret_value=tenants_repo_name
        )
        output_file = output_dir / 'tenants-repo-name.secret.yaml'
        output_file.write_text(content)
        generated_files.append('tenants-repo-name.secret.yaml')
    
    # Generate GitHub App credentials secret (multi-key secret with private key)
    if git_app_id and git_app_installation_id and git_app_private_key:
        secret_yaml = f"""apiVersion: v1
kind: Secret
metadata:
  name: github-app-credentials
  namespace: kube-system
  annotations:
    argocd.argoproj.io/sync-wave: "0"
type: Opaque
stringData:
  git-app-id: "{git_app_id}"
  git-app-installation-id: "{git_app_installation_id}"
  git-app-private-key: |
"""
        # Indent private key lines
        for line in git_app_private_key.splitlines():
            secret_yaml += f"    {line}\n"
        
        output_file = output_dir / 'github-app-credentials.secret.yaml'
        output_file.write_text(secret_yaml)
        generated_files.append('github-app-credentials.secret.yaml')
    
    # Generate Hetzner secrets
    hetzner_secrets = secrets.get('hetzner', {})
    hcloud_token = hetzner_secrets.get('hcloud_api_token', '')
    hetzner_dns_token = hetzner_secrets.get('hetzner_dns_token', '')
    
    if hcloud_token:
        content = template.render(
            secret_name='hcloud',
            namespace='kube-system',
            annotations='argocd.argoproj.io/sync-wave: "0"',
            secret_type='Opaque',
            secret_key='token',
            secret_value=hcloud_token
        )
        output_file = output_dir / 'hcloud.secret.yaml'
        output_file.write_text(content)
        generated_files.append('hcloud.secret.yaml')
    
    if hetzner_dns_token:
        # External DNS secret
        content = template.render(
            secret_name='external-dns-hetzner',
            namespace='kube-system',
            annotations='argocd.argoproj.io/sync-wave: "0"',
            secret_type='Opaque',
            secret_key='HETZNER_DNS_TOKEN',
            secret_value=hetzner_dns_token
        )
        output_file = output_dir / 'external-dns-hetzner.secret.yaml'
        output_file.write_text(content)
        generated_files.append('external-dns-hetzner.secret.yaml')
        
        # Cert-manager secret
        content = template.render(
            secret_name='hetzner-dns',
            namespace='cert-manager',
            annotations='argocd.argoproj.io/sync-wave: "4"',
            secret_type='Opaque',
            secret_key='api-key',
            secret_value=hetzner_dns_token
        )
        output_file = output_dir / 'hetzner-dns.secret.yaml'
        output_file.write_text(content)
        generated_files.append('hetzner-dns.secret.yaml')
    
    return generated_files


def main():
    """Main entry point"""
    if len(sys.argv) != 2:
        print("Usage: generate_core_secrets.py <output_dir>", file=sys.stderr)
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
        generated_files = generate_core_secrets(secrets, templates_path, output_dir, github_config)
    
    # Output list of generated files as JSON
    print(json.dumps(generated_files))


if __name__ == '__main__':
    main()
