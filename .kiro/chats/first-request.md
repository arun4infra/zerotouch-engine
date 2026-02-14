Context:We are migrating a legacy GitOps/Bash-based infrastructure repository (zerotouch-platform) into a Python-based CLI engine called ZTC (ZeroTouch Composition).We have successfully established a migration pattern using 5 core adapters: hetzner, talos, ksop,argocd, crosspane and cilium. We are now creating a new adapter for argocd.

The Goal: Analyze the provided "Reference Source Files" (from the legacy system) and ask clarifications about the implementation for a new ZTC Adapter - Phase 3 Runtime Foundations (The Middleware).

### **Phase 3: Runtime Foundations (The Middleware)**
*   **Adapters:** `nats`, `keda`, `cnpg`, `cert-manager`, `external-dns`
    *   **Source:** Corresponding files in `bootstrap/argocd/base/` and `overlays/`.
    *   **Role:** Provides messaging, autoscaling, database operators, and DNS/Cert management.
    *   **Design:** Each should be a distinct adapter to align with `platform/versions.yaml` versioning.
    *   **Dependencies:** `external-dns` and `cert-manager` require `cloud-infrastructure` credentials (Hetzner).

i want you to read and understand below first 

- zerotouch-engine/llm-context/adapter-design/ 
- zerotouch-engine/llm-context/lifecycle-commands.md
- zerotouch-platform/bootstrap/
- zerotouch-platform/scripts/
- zerotouch-engine/ztc/adapters/

Go through all the existing adapters before proposing - you have to align with existing pattern.
for reference- here is a genearted infra using ztc render cli command for existing adapter. - zerotouch-engine/platform/

here is reference specs that was created for argocd - .kiro/specs/crossplane-adapter/
we have to create similar spec for cross plane.
analyse and report back.

#just-report.md 