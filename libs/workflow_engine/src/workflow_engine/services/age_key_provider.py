"""Age Key Provider - Retrieves SOPS Age keys from multiple sources"""

import os
import subprocess
from pathlib import Path
from typing import Optional
import yaml


class AgeKeyProvider:
    """Provides Age private key from multiple sources with fallback chain"""
    
    def __init__(self, platform_yaml_path: Path):
        """Initialize provider with platform config
        
        Args:
            platform_yaml_path: Path to platform.yaml
        """
        self.platform_yaml_path = platform_yaml_path
        self._platform_data = None
    
    def get_age_key(self) -> Optional[str]:
        """Get Age private key from available sources
        
        Priority:
        1. Local file: ~/.ztp_cli/secrets
        2. Environment variable: SOPS_AGE_KEY
        3. S3 bucket (if configured)
        
        Returns:
            Age private key string, or None if not available
        """
        # Try local file
        key = self._get_from_local_file()
        if key:
            return key
        
        # Try environment variable
        key = self._get_from_env()
        if key:
            return key
        
        # Try S3
        key = self._get_from_s3()
        if key:
            return key
        
        return None
    
    def _get_from_local_file(self) -> Optional[str]:
        """Get Age key from ~/.ztp/secrets"""
        age_key_file = Path.home() / '.ztp' / 'secrets'
        if age_key_file.exists():
            content = age_key_file.read_text().strip()
            # Check if it's an Age key directly (starts with AGE-SECRET-KEY-)
            if content.startswith('AGE-SECRET-KEY-'):
                return content
        return None
    
    def _get_from_env(self) -> Optional[str]:
        """Get Age key from SOPS_AGE_KEY environment variable"""
        return os.environ.get('SOPS_AGE_KEY')
    
    def _get_from_s3(self) -> Optional[str]:
        """Get Age key from S3 bucket
        
        Requires:
        - S3 credentials in ~/.ztp/secrets (s3_access_key, s3_secret_key)
        - S3 config in platform.yaml (s3_endpoint, s3_bucket_name)
        
        Returns:
            Decrypted Age private key, or None if not available
        """
        try:
            # Load S3 credentials
            s3_creds = self._load_s3_credentials()
            if not s3_creds:
                return None
            
            # Load S3 config from platform.yaml
            s3_config = self._load_s3_config()
            if not s3_config:
                return None
            
            # Download encrypted Age key from S3
            encrypted_key = self._download_from_s3(
                s3_config, s3_creds,
                'age-keys/ACTIVE-age-key-encrypted.txt'
            )
            if not encrypted_key:
                return None
            
            # Download recovery key from S3
            recovery_key = self._download_from_s3(
                s3_config, s3_creds,
                'age-keys/ACTIVE-recovery-key.txt'
            )
            if not recovery_key:
                return None
            
            # Decrypt Age key using recovery key
            decrypted_key = self._decrypt_age_key(encrypted_key, recovery_key)
            return decrypted_key
            
        except Exception:
            return None
    
    def _load_s3_credentials(self) -> Optional[dict]:
        """Load S3 credentials from ~/.ztp/secrets
        
        Returns:
            Dict with access_key and secret_key, or None
        """
        secrets_path = Path.home() / '.ztp' / 'secrets'
        if not secrets_path.exists():
            return None
        
        try:
            content = secrets_path.read_text()
            creds = {}
            
            # Parse INI-style format
            in_ksops_section = False
            for line in content.split('\n'):
                line = line.strip()
                
                if line == '[ksops]':
                    in_ksops_section = True
                    continue
                elif line.startswith('['):
                    in_ksops_section = False
                    continue
                
                if in_ksops_section and '=' in line:
                    key, value = line.split('=', 1)
                    key = key.strip()
                    value = value.strip()
                    
                    if key == 's3_access_key':
                        creds['access_key'] = value
                    elif key == 's3_secret_key':
                        creds['secret_key'] = value
            
            if 'access_key' in creds and 'secret_key' in creds:
                return creds
            
        except Exception:
            pass
        
        return None
    
    def _load_s3_config(self) -> Optional[dict]:
        """Load S3 config from platform.yaml
        
        Returns:
            Dict with endpoint, bucket, region, or None
        """
        if not self.platform_yaml_path.exists():
            return None
        
        try:
            if not self._platform_data:
                with open(self.platform_yaml_path) as f:
                    self._platform_data = yaml.safe_load(f)
            
            adapters = self._platform_data.get('adapters', {})
            ksops_config = adapters.get('ksops', {})
            
            endpoint = ksops_config.get('s3_endpoint')
            bucket = ksops_config.get('s3_bucket_name')
            region = ksops_config.get('s3_region', 'us-east-1')
            
            if endpoint and bucket:
                return {
                    'endpoint': endpoint,
                    'bucket': bucket,
                    'region': region
                }
            
            return None
        except Exception:
            return None
    
    def _download_from_s3(self, s3_config: dict, s3_creds: dict, s3_key: str) -> Optional[str]:
        """Download file from S3
        
        Args:
            s3_config: S3 configuration (endpoint, bucket, region)
            s3_creds: S3 credentials (access_key, secret_key)
            s3_key: S3 object key (path in bucket)
        
        Returns:
            File content, or None
        """
        try:
            temp_file = Path(f'/tmp/{s3_key.replace("/", "_")}')
            
            # Set AWS credentials in environment
            env = os.environ.copy()
            env['AWS_ACCESS_KEY_ID'] = s3_creds['access_key']
            env['AWS_SECRET_ACCESS_KEY'] = s3_creds['secret_key']
            env['AWS_DEFAULT_REGION'] = s3_config['region']
            
            # Download from S3
            result = subprocess.run(
                [
                    'aws', 's3', 'cp',
                    f"s3://{s3_config['bucket']}/{s3_key}",
                    str(temp_file),
                    '--endpoint-url', s3_config['endpoint'],
                    '--quiet'
                ],
                env=env,
                capture_output=True,
                timeout=10
            )
            
            if result.returncode != 0:
                return None
            
            # Read and cleanup
            content = temp_file.read_text().strip()
            temp_file.unlink()
            
            return content
            
        except Exception:
            return None
    
    def _decrypt_age_key(self, encrypted_key: str, recovery_key: str) -> Optional[str]:
        """Decrypt Age key using recovery key
        
        Args:
            encrypted_key: Encrypted Age private key content
            recovery_key: Recovery private key
        
        Returns:
            Decrypted Age private key, or None
        """
        try:
            # Write keys to temp files
            encrypted_file = Path('/tmp/age-key-encrypted.txt')
            recovery_file = Path('/tmp/recovery-key.txt')
            
            encrypted_file.write_text(encrypted_key)
            recovery_file.write_text(recovery_key)
            
            # Decrypt using age
            result = subprocess.run(
                ['age', '--decrypt', '-i', str(recovery_file), str(encrypted_file)],
                capture_output=True,
                text=True,
                timeout=5
            )
            
            # Cleanup
            encrypted_file.unlink()
            recovery_file.unlink()
            
            if result.returncode == 0:
                return result.stdout.strip()
            
            return None
            
        except Exception:
            return None
