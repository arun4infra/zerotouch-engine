"""Environment variable input handler for non-interactive mode"""

import os
from typing import Optional


def get_env_value(field_name: str) -> Optional[str]:
    """Get value from environment variable
    
    Maps field names to environment variable names.
    Tries both uppercase and lowercase variants.
    """
    # Direct mapping for common fields
    env_map = {
        "org_name": ["ORG_NAME", "org_name"],
        "app_name": ["APP_NAME", "app_name"],
        "hcloud_api_token": ["HCLOUD_TOKEN", "HETZNER_API_TOKEN"],
        "hetzner_dns_token": ["HETZNER_DNS_TOKEN"],
        "server_ips": ["SERVER_IPS", "IP"],
        "rescue_mode_confirm": ["RESCUE_MODE_CONFIRM"],
        "github_app_id": ["GITHUB_APP_ID", "APP_ID"],
        "github_app_installation_id": ["GITHUB_APP_INSTALLATION_ID", "INSTALLATION_ID"],
        "github_app_private_key": ["GITHUB_APP_PRIVATE_KEY"],
        "control_plane_repo_url": ["CONTROL_PLANE_REPO_URL", "control_plane_url"],
        "data_plane_repo_url": ["DATA_PLANE_REPO_URL", "data_plane_url"],
        "s3_access_key": ["S3_ACCESS_KEY", "HETZNER_S3_ACCESS_KEY"],
        "s3_secret_key": ["S3_SECRET_KEY", "HETZNER_S3_SECRET_KEY"],
        "s3_endpoint": ["S3_ENDPOINT", "HETZNER_S3_ENDPOINT"],
        "s3_bucket_name": ["S3_BUCKET_NAME"],
        "s3_region": ["S3_REGION"],
        "cluster_name": ["CLUSTER_NAME", "cluster_name"],
        "cluster_endpoint": ["CLUSTER_ENDPOINT", "cluster_endpoint"],
    }
    
    # Try mapped env vars first
    if field_name in env_map:
        for env_var in env_map[field_name]:
            value = os.getenv(env_var)
            if value:
                return value
    
    # Fallback to uppercase field name
    return os.getenv(field_name.upper())


def is_non_interactive() -> bool:
    """Check if running in non-interactive mode"""
    return os.getenv("ZTC_NON_INTERACTIVE", "").lower() in ("1", "true", "yes")
