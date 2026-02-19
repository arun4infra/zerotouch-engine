
1. User runs: ./ztc-new.py init

2. Init workflow collects inputs:
   - Hetzner: hcloud_api_token, hetzner_dns_token → saved to ~/.ztp/secrets
   - GitHub: github_app_id, github_app_installation_id, github_app_private_key → saved to ~/.ztp/secrets
   - KSOPS: s3_access_key, s3_secret_key → saved to ~/.ztp/secrets

3. After KSOPS inputs collected, validation runs:
   - Engine calls: ksops_adapter.init()
   - Returns: ScriptReference to "setup-env-secrets.sh"
   - Engine executes: setup-env-secrets.sh

4. setup-env-secrets.sh orchestrates 5 steps:

   Step 1: Generate Age keypair
   - Calls: 08b-generate-age-keys.sh
   - Checks S3 for existing key, or generates new one
   - Exports: AGE_PUBLIC_KEY, AGE_PRIVATE_KEY

   Step 2: Backup Age key to S3
   - Calls: 08b-backup-age-to-s3.sh
   - Encrypts private key with recovery key
   - Uploads to S3 bucket

   Step 3: Convert secrets to .env format
   - Calls: secrets-to-env.sh
   - Reads: ~/.ztp/secrets (INI format)
   - Outputs: /tmp/ztc-secrets-$$.env

   Step 4: Generate encrypted secrets ← THIS IS WHERE YAML FILES ARE CREATED
   - Creates directory: platform/generated/argocd/overlays/main/core/secrets/
   - Generates .sops.yaml with AGE_PUBLIC_KEY
   - Calls: generate_core_secrets.py
     → Reads ~/.ztp/secrets
     → Generates YAML files (hcloud.secret.yaml, github-app-credentials.secret.yaml, etc.)
     → Returns list of generated files
   - Calls: generate_tenant_registry_secrets.py
     → Reads ~/.ztp/secrets
     → Generates tenant-specific YAML files
     → Returns list of generated files
   - Encrypts each YAML file with SOPS using .sops.yaml config

   Step 5: Export keys for subsequent use
   - Exports AGE_PUBLIC_KEY, AGE_PRIVATE_KEY for other scripts

5. Validation completes, init continues to next adapter


Key Points:
- Secrets are read from ~/.ztp/secrets (saved during input collection)
- Python scripts (generate_core_secrets.py,
generate_tenant_registry_secrets.py) convert secrets to Kubernetes Secret
YAML format
- SOPS encrypts the YAML files using Age public key
- All happens during KSOPS init validation phase