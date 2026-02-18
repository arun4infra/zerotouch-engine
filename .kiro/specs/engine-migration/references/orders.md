Here is the extracted structure from your diagram, organized by heading → subheading → defaults.

⸻

1️⃣ Infra

Bare Metal (On-Prem)

⸻

Public cloud (Default)

→ Hetzner (Default)
→ Bare metal (Default)
→ Hetzner adapter (Default)

⸻

2️⃣ GitOps Architecture

Git provider
	•	Github (Default)
	•	Gitlab

⸻

GitOps repository model? (Default)

Default Option:
	•	Control-plane + data-plane + per-service repos

Alternative Option:
	•	Control-plane repo + data-plane repo

⸻

Github Adapter (Default)

⸻

3️⃣ Secret Management

Secret management strategy
	•	Cloud Secret Manager
	•	SOPS (encrypted in Git) (Default)
→ KSOPS Adapter (Default)

⸻

4️⃣ OS
	•	talos (Default)
→ Talos Adapter (Default)

Here is the extracted structure from the second diagram, organized by heading → subheading → defaults.

⸻

5️⃣ Networking Model

API Gateway (Default)

→ Cilium Adapter (Default)

⸻

6️⃣ Cluster tenancy model
	•	Single-tenant (one team per cluster)
	•	Soft multi-tenancy (namespaces per team) (Default)
	•	Hard multi-tenancy
(isolated node pools / strong policy)
	•	Soft multi-tenancy (namespaces per team)
(appears duplicated in the diagram)

⸻

7️⃣ GitOps engine
	•	ArgoCD Adapter (Default)
	•	Flux

⸻

8️⃣ Infrastructure Provisioner
	•	Crossplane (Default)
