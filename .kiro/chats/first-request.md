Context:We are migrating a legacy GitOps/Bash-based infrastructure repository (zerotouch-platform) into a Python-based CLI engine called ZTC (ZeroTouch Composition).We have successfully established a migration pattern using few core adapters. We are now supporting and creating new adapters.

The Goal: Analyze the provided "Reference Source Files" (from the legacy system) and ask clarifications about the implementation for a new ZTC Adapter - Phase 3 Runtime Foundations (The Middleware).

### **Phase 3: Agent Sandbox and Agent Gateway (The Middleware)**
*   **Adapters:** `agent-sandbox`, `agent-gateway`
    *   **Source:** Corresponding files in `bootstrap/argocd/base/agent-sandbox-wrapper`, `zerotouch-platform/bootstrap/argocd/base/04-agent-sandbox.yaml`, `zerotouch-platform/bootstrap/argocd/base/06-agentgateway.yaml`.
    * `overlays/` - zerotouch-platform/bootstrap/argocd/overlays/main/core/agentgateway-httproute, zerotouch-platform/bootstrap/argocd/overlays/main/core/gateway , zerotouch-platform/bootstrap/argocd/overlays/main/core/00-gateway-api-crds.yaml, zerotouch-platform/bootstrap/argocd/overlays/main/core/06-agentgateway-httproute.yaml, zerotouch-platform/bootstrap/argocd/overlays/main/core/04-gateway-config.yaml, zerotouch-platform/bootstrap/argocd/overlays/main/dev/gateway-config, zerotouch-platform/bootstrap/argocd/overlays/main/dev/04-gateway-config.yaml, 
    *   **Role:** Provides messaging, autoscaling, database operators, and DNS/Cert management.
    *   **Design:** Each should be a distinct adapter to align with `platform/versions.yaml` versioning.
    *   **Dependencies:** ??

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