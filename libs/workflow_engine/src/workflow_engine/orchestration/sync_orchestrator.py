"""Sync orchestrator - syncs platform manifests to control plane repo"""

import asyncio
from pathlib import Path
from typing import Optional, Dict, Any
from dataclasses import dataclass
import subprocess
import yaml
import os

from workflow_engine.services.platform_config_service import PlatformConfigService
from workflow_engine.engine.script_executor import ScriptExecutor
from workflow_engine.adapters.base import ScriptReference
from workflow_engine.adapters.github.adapter import GitHubScripts
from workflow_engine.services.secrets_provider import SecretsProvider


@dataclass
class SyncResult:
    """Result from sync operation"""
    success: bool
    pr_url: Optional[str] = None
    message: Optional[str] = None
    error: Optional[str] = None


class SyncOrchestrator:
    """Orchestrates platform manifest sync to control plane repo"""
    
    def __init__(
        self,
        platform_yaml_path: Path = Path("platform/platform.yaml")
    ):
        self.platform_yaml_path = platform_yaml_path
    
    async def execute(self) -> SyncResult:
        """Execute sync operation"""
        try:
            config_service = PlatformConfigService()
            
            if not config_service.exists():
                return SyncResult(
                    success=False,
                    error="platform.yaml not found. Run 'ztc init' first."
                )
            
            config = config_service.load()
            
            if not Path("platform/generated").exists():
                return SyncResult(
                    success=False,
                    error="platform/generated not found. Run 'ztc render' first."
                )
            
            github_config = config.adapters.get('github')
            if not github_config:
                return SyncResult(
                    success=False,
                    error="GitHub adapter not configured"
                )
            
            control_plane_url = github_config.get('control_plane_repo_url')
            platform_repo_branch = github_config.get('platform_repo_branch', 'main')
            
            if not control_plane_url:
                return SyncResult(
                    success=False,
                    error="control_plane_repo_url not found"
                )
            
            import re
            match = re.match(r"^https://github\.com/([^/]+)/([^/]+?)(\.git)?/?$", control_plane_url.rstrip('/'))
            if not match:
                return SyncResult(
                    success=False,
                    error=f"Invalid repo URL: {control_plane_url}"
                )
            
            cp_org = match.group(1)
            cp_repo = match.group(2)
            
            # Get GitHub App credentials from config
            github_app_id = github_config.get('github_app_id', '')
            github_app_installation_id = github_config.get('github_app_installation_id', '')
            
            # Use feature branch for PR, not main
            if platform_repo_branch == 'main':
                platform_repo_branch = 'platform-manifests-update'
            
            # Use singleton secrets provider
            secrets_provider = SecretsProvider()
            secret_env_vars = secrets_provider.get_env_vars(self.platform_yaml_path)
            
            if not secret_env_vars.get('GIT_APP_PRIVATE_KEY'):
                print("⚠️  GitHub App credentials not available")
                print("   GitHub App credentials are required for repository sync")
                return SyncResult(
                    success=False,
                    error="GitHub App credentials not found. Ensure secrets are encrypted and Age key is available."
                )
            
            sync_script = ScriptReference(
                package="workflow_engine.adapters.github.scripts",
                resource=GitHubScripts.SYNC_PLATFORM_REPO,
                description="Sync platform manifests",
                timeout=300,
                context_data={
                    "control_plane_repo_url": control_plane_url,
                    "platform_repo_branch": platform_repo_branch,
                    "tenant_org_name": cp_org,
                    "control_plane_repo_name": cp_repo,
                    "github_app_id": github_app_id,
                    "github_app_installation_id": github_app_installation_id
                }
            )
            
            script_executor = ScriptExecutor()
            result = script_executor.execute(sync_script, secret_env_vars=secret_env_vars)
            
            if result.exit_code != 0:
                return SyncResult(
                    success=False,
                    error=result.stderr or result.stdout
                )
            
            output = result.stdout
            
            if "No changes to sync" in output:
                return SyncResult(
                    success=True,
                    message="No changes to sync"
                )
            
            pr_url = None
            for line in output.split('\n'):
                if 'PR URL:' in line or 'https://github.com' in line:
                    parts = line.split('https://github.com')
                    if len(parts) > 1:
                        pr_url = 'https://github.com' + parts[1].split()[0]
                        break
            
            return SyncResult(
                success=True,
                pr_url=pr_url,
                message="PR created successfully"
            )
        
        except Exception as e:
            return SyncResult(
                success=False,
                error=str(e)
            )
