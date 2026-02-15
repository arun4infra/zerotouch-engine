# GitHub Adapter

## Overview

The GitHub adapter provides Git provider capabilities for platform repository management. It validates GitHub App credentials, creates tenant repositories if needed, injects repository access secrets into the cluster, and enables ArgoCD to sync from private repositories.

## Selection Group

`git_provider` - Executes after cloud_provider, before secrets_management in the init workflow.

## Configuration

```yaml
github:
  github_app_id: "123456"
  github_app_installation_id: "789012"
  github_app_private_key: "-----BEGIN RSA PRIVATE KEY-----\n...\n-----END RSA PRIVATE KEY-----"
  tenant_org_name: "my-org"
  tenant_repo_name: "platform-repo"
```

## Capabilities

**Provides:**
- `git-credentials`: Repository access credentials for GitOps workflows

**Requires:**
- None (standalone adapter)

## Lifecycle Scripts

### Init Phase
- `validate-github-access.sh`: Validates GitHub App credentials by generating JWT, exchanging for installation token, and testing repository access. Creates repository if it doesn't exist (requires GitHub App to have "Contents: Read & Write" and "Administration: Read & Write" permissions).

### Bootstrap Phase
- `00-inject-identities.sh`: Creates Kubernetes secret with GitHub App credentials in argocd namespace
- `apply-env-substitution.sh`: Performs environment variable substitution in ArgoCD configuration files

### Validation Phase
- `validate-github-credentials.sh`: Verifies GitHub credentials secret exists in cluster

## Render Output

The GitHub adapter generates no Kubernetes manifests. It only provides capability data for consumption by other adapters (e.g., ArgoCD uses git-credentials to configure repository access).

## Migration from KSOPS

Previously, GitHub credentials were managed by the KSOPS adapter. This created tight coupling between secrets management and Git provider concerns. The refactoring:

1. Moved GitHub fields from KSOPSConfig to GitHubConfig
2. Moved GitHub bootstrap scripts from KSOPS to GitHub adapter
3. Introduced init phase for pre-cluster credential validation and repository creation
4. Maintained backward compatibility for existing deployments

## Script Organization

```
ztc/adapters/github/
├── scripts/
│   ├── init/
│   │   └── validate-github-access.sh
│   ├── bootstrap/
│   │   ├── 00-inject-identities.sh
│   │   └── apply-env-substitution.sh
│   └── validation/
│       └── validate-github-credentials.sh
```

All scripts use `$ZTC_CONTEXT_FILE` for configuration data and environment variables for secrets (private key).
