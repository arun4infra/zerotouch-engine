Context:We are migrating a legacy GitOps/Bash-based infrastructure repository (zerotouch-platform) into a Python-based CLI engine called ZTC (ZeroTouch Composition).We have successfully established a migration pattern using 4 core adapters: hetzner, talos, ksop, and cilium. We are now creating a new adapter for argocd.

The Goal: Analyze the provided "Reference Source Files" (from the legacy system) and ask clarifications about the implementation for a new ZTC Adapter.

i want you to read and understand below first 

- zerotouch-engine/llm-context/adapter-design/ 
- zerotouch-engine/llm-context/lifecycle-commands.md
- zerotouch-platform/bootstrap/
- zerotouch-platform/scripts/
- zerotouch-engine/ztc/adapters/

Go through all the existing adapters before proposing - you have to align with existing pattern.
for reference- here is a genearted infra using ztc render cli command for existing adapter. - zerotouch-engine/platform/

#just-report.md 