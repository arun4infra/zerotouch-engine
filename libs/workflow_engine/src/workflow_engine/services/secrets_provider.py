"""Secrets provider - singleton for cached secret access"""

from pathlib import Path
from typing import Dict, Optional
import subprocess
import yaml
import os

from workflow_engine.services.age_key_provider import AgeKeyProvider


class SecretsProvider:
    """Singleton provider for decrypted secrets with caching
    
    Decrypts secrets once and caches in memory.
    Prevents multiple S3 calls to fetch Age key.
    """
    
    _instance: Optional['SecretsProvider'] = None
    _secrets_cache: Optional[Dict[str, Dict[str, str]]] = None
    _age_key_cache: Optional[str] = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        """Initialize provider (only once due to singleton)"""
        pass
    
    def get_age_key(self, platform_yaml_path: Path = Path('platform/platform.yaml')) -> Optional[str]:
        """Get Age private key (cached)
        
        Args:
            platform_yaml_path: Path to platform.yaml
            
        Returns:
            Age private key or None if not available
        """
        if self._age_key_cache is None:
            age_key_provider = AgeKeyProvider(platform_yaml_path)
            self._age_key_cache = age_key_provider.get_age_key()
        
        return self._age_key_cache
    
    def get_secrets(self, platform_yaml_path: Path = Path('platform/platform.yaml')) -> Dict[str, Dict[str, str]]:
        """Get all decrypted secrets (cached)
        
        Args:
            platform_yaml_path: Path to platform.yaml
            
        Returns:
            Dictionary of {secret_name: {key: value}}
        """
        if self._secrets_cache is None:
            self._secrets_cache = self._decrypt_secrets(platform_yaml_path)
        
        return self._secrets_cache
    
    def _decrypt_secrets(self, platform_yaml_path: Path) -> Dict[str, Dict[str, str]]:
        """Decrypt all secrets from platform/generated/secrets/
        
        Args:
            platform_yaml_path: Path to platform.yaml
            
        Returns:
            Dictionary of {secret_name: {key: value}}
        """
        secrets = {}
        secrets_dir = Path('platform/generated/secrets')
        
        if not secrets_dir.exists():
            print(f"ℹ️  Secrets directory not found: {secrets_dir}")
            return secrets
        
        # Get Age key (cached)
        age_key = self.get_age_key(platform_yaml_path)
        
        if not age_key:
            print("⚠️  Age private key not found. Secrets will not be available.")
            return secrets
        
        # Decrypt each secret file
        secret_files = list(secrets_dir.glob('*.secret.yaml'))
        if not secret_files:
            print(f"ℹ️  No secret files found in {secrets_dir}")
            return secrets
        
        print(f"🔓 Decrypting {len(secret_files)} secret(s)...")
        for secret_file in secret_files:
            try:
                # Set Age key in environment for SOPS
                env = os.environ.copy()
                env['SOPS_AGE_KEY'] = age_key
                
                result = subprocess.run(
                    ['sops', '-d', str(secret_file)],
                    capture_output=True,
                    text=True,
                    timeout=30,
                    env=env
                )
                
                if result.returncode == 0:
                    secret_data = yaml.safe_load(result.stdout)
                    secret_name = secret_data['metadata']['name']
                    secrets[secret_name] = secret_data.get('stringData', {})
                    print(f"   ✓ Decrypted: {secret_name}")
                else:
                    print(f"   ✗ Failed to decrypt {secret_file.name}: {result.stderr}")
            except subprocess.TimeoutExpired:
                print(f"   ✗ Timeout decrypting {secret_file.name}")
            except Exception as e:
                print(f"   ✗ Error decrypting {secret_file.name}: {e}")
        
        if secrets:
            print(f"✓ Successfully decrypted {len(secrets)} secret(s)")
        
        return secrets
    
    def get_env_vars(self, platform_yaml_path: Path = Path('platform/platform.yaml')) -> Dict[str, str]:
        """Get all secrets as environment variables (cached)
        
        Maps secret keys to environment variable names.
        
        Args:
            platform_yaml_path: Path to platform.yaml
            
        Returns:
            Dictionary of environment variables
        """
        env = {}
        secrets = self.get_secrets(platform_yaml_path)
        
        if not secrets:
            print("⚠️  No secrets available - some bootstrap stages may fail")
            return env
        
        # Age private key (for KSOPS injection into cluster)
        age_key = self.get_age_key(platform_yaml_path)
        if age_key:
            env['AGE_PRIVATE_KEY'] = age_key
        else:
            print("⚠️  Age private key not available - KSOPS stages will fail")
        
        # Hetzner API token
        if 'hcloud' in secrets:
            env['HETZNER_API_TOKEN'] = secrets['hcloud'].get('token', '')
            if env['HETZNER_API_TOKEN']:
                print("✓ Loaded Hetzner API token")
        
        # GitHub App credentials
        if 'github-app-credentials' in secrets:
            creds = secrets['github-app-credentials']
            git_key = creds.get('git-app-private-key', '')
            if git_key:
                env['GIT_APP_PRIVATE_KEY'] = git_key
                env['GIT_APP_ID'] = creds.get('git-app-id', '')
                env['GIT_APP_INSTALLATION_ID'] = creds.get('git-app-installation-id', '')
                print(f"✓ Loaded GitHub App credentials ({len(git_key)} bytes)")
            else:
                print("⚠️  GitHub App private key is empty - git operations will fail")
        else:
            print("⚠️  GitHub App credentials not found - git operations will fail")
        
        # GHCR pull secret
        if 'ghcr-pull-secret' in secrets:
            env['GHCR_USERNAME'] = secrets['ghcr-pull-secret'].get('username', '')
            env['GHCR_TOKEN'] = secrets['ghcr-pull-secret'].get('password', '')
            if env.get('GHCR_USERNAME'):
                print("✓ Loaded GHCR pull secret")
        
        # Hetzner DNS token
        if 'hetzner-dns' in secrets:
            env['HETZNER_DNS_TOKEN'] = secrets['hetzner-dns'].get('token', '')
            if env['HETZNER_DNS_TOKEN']:
                print("✓ Loaded Hetzner DNS token")
        
        # External DNS Hetzner token
        if 'external-dns-hetzner' in secrets:
            env['EXTERNAL_DNS_HETZNER_TOKEN'] = secrets['external-dns-hetzner'].get('token', '')
            if env['EXTERNAL_DNS_HETZNER_TOKEN']:
                print("✓ Loaded External DNS token")
        
        # Tenant org/repo names
        if 'org-name' in secrets:
            env['ORG_NAME'] = secrets['org-name'].get('value', '')
            if env['ORG_NAME']:
                print(f"✓ Loaded org name: {env['ORG_NAME']}")
        
        if 'tenants-repo-name' in secrets:
            env['TENANTS_REPO_NAME'] = secrets['tenants-repo-name'].get('value', '')
            if env['TENANTS_REPO_NAME']:
                print(f"✓ Loaded tenants repo name: {env['TENANTS_REPO_NAME']}")
        
        return env
    
    def clear_cache(self):
        """Clear cached secrets (for testing or security)"""
        if self._secrets_cache:
            # Zero out secrets before clearing
            for secret_name in self._secrets_cache:
                for key in self._secrets_cache[secret_name]:
                    self._secrets_cache[secret_name][key] = '\x00' * len(self._secrets_cache[secret_name][key])
        
        self._secrets_cache = None
        self._age_key_cache = None
    
    def __del__(self):
        """Zero secrets from memory on cleanup"""
        self.clear_cache()
