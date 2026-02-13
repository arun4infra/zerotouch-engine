## Engine Execution Flow

```
1. Init Workflow (ztc init)
   ├─ User selects adapters (Hetzner, Talos, Cilium)
   ├─ Collect adapter-specific inputs
   ├─ Validate configuration
   └─ Write platform.yaml

2. Render Pipeline (ztc render)
   ├─ Load platform.yaml
   ├─ Resolve adapter dependencies (topological sort)
   ├─ Execute adapters in order:
   │  ├─ Hetzner.render() → CloudInfrastructureCapability
   │  ├─ Cilium.render() → CNIArtifactsCapability
   │  └─ Talos.render() → KubernetesAPICapability
   ├─ Generate pipeline.yaml from adapter stages
   ├─ Write manifests to platform/generated/
   └─ Create lock.json with artifact hashes

3. Bootstrap Execution (ztc bootstrap)
   ├─ Validate lock file
   ├─ Extract scripts to secure temp directory
   ├─ Write context files for each script
   ├─ Execute stage-executor.sh with pipeline.yaml
   │  ├─ Pre-work: enable-rescue-mode.sh
   │  ├─ Bootstrap: install-talos.sh, bootstrap-talos.sh, wait-cilium.sh
   │  ├─ Post-work: (additional configurations if any)
   │  └─ Validation: validate-cluster.sh, validate-cni.sh
   └─ Cleanup temp directory

4. Validation (ztc validate)
   ├─ Check lock file integrity
   ├─ Validate artifact hashes
   └─ Detect configuration drift
```