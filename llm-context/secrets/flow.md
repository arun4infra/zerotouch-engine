Here is the ASCII sequence diagram illustrating the workflow engine initialization lifecycle, highlighting the interaction between the User, CLI, Engine, standard Adapters, and the specific KSOPS encryption flow.

```text
+------+    +-----+    +--------+    +----------+    +---------+    +-------+    +----+
| User |    | CLI |    | Engine |    | Adapters |    | LocalFS |    | KSOPS |    | S3 |
+--+---+    +--+--+    +---+----+    +-----+----+    +----+----+    +---+---+    +--+-+
   |           |           |               |              |             |           |
   | start init|           |               |              |             |           |
   |---------->|           |               |              |             |           |
   |           | initiate  |               |              |             |           |
   |           |---------->|               |              |             |           |
   |           |           |               |              |             |           |
   |           |           |               |              |             |           |
   ================= PHASE 1: INPUT COLLECTION LOOP ===============================
   |           |           |               |              |             |           |
   |           |           | [Loop: For each Adapter (Hetzner, Git, etc)]           |
   |           |           |               |              |             |           |
   |           |           | get fields    |              |             |           |
   |           |           |-------------->|              |             |           |
   |           |           | return schema |              |             |           |
   |           |           |<--------------|              |             |           |
   |           |           |               |              |             |           |
   |           |           | [Loop: For each Field/Question]            |           |
   |           |  display  |               |              |             |           |
   |           |<----------|               |              |             |           |
   | prompt    |           |               |              |             |           |
   |<----------|           |               |              |             |           |
   | input     |           |               |              |             |           |
   |---------->|  submit   |               |              |             |           |
   |           |---------->|               |              |             |           |
   |           |           | write raw     |              |             |           |
   |           |           | secret        |              |             |           |
   |           |           |----------------------------->|             |           |
   |           |           |               | (~/.ztp/secrets)           |           |
   |           |           |               |              |             |           |
   |           |           | run init script              |             |           |
   |           |           |----------------------------->|             |           |
   |           |           |               |              |             |           |
   |           |           |      <Next Field>            |             |           |
   |           |           |                              |             |           |
   |           |      <Next Adapter>                      |             |           |
   |           |           |               |              |             |           |
   |           |           |               |              |             |           |
   ================= PHASE 2: KSOPS & ENCRYPTION ==================================
   |           |           |               |              |             |           |
   |           |           | trigger ksops init           |             |           |
   |           |           |------------------------------------------->|           |
   |           |           |               |              |             |           |
   |           |           |               |              | create bucket           |
   |           |           |               |              |------------------------>|
   |           |           |               |              |             |           |
   |           |           |               |              | gen AGE keys|           |
   |           |           |               |              |------------>|           |
   |           |           |               |              |             |           |
   |           |           |               |              | store keys  |           |
   |           |           |               |              |------------------------>|
   |           |           |               |              |             |           |
   |           |           |               | write .sops.yaml           |           |
   |           |           |               |<---------------------------|           |
   |           |           |               |              |             |           |
   |           |           |               | read secrets |             |           |
   |           |           |               | (~/.ztp/secrets)           |           |
   |           |           |               |<---------------------------|           |
   |           |           |               |              |             |           |
   |           |           |               |              | encrypt data|           |
   |           |           |               |              | (using AGE) |           |
   |           |           |               |              |------------>|           |
   |           |           |               |              |             |           |
   |           |           |               | write encrypted            |           |
   |           |           |               | to platform.yaml           |           |
   |           |           |               |<---------------------------|           |
   |           |           |               |              |             |           |
   |           |           | success       |              |             |           |
   |           |<----------|               |              |             |           |
   | complete  |           |               |              |             |           |
   |<----------|           |               |              |             |           |
   |           |           |               |              |             |           |
+--+---+    +--+--+    +---+----+    +-----+----+    +----+----+    +---+---+    +--+-+
| User |    | CLI |    | Engine |    | Adapters |    | LocalFS |    | KSOPS |    | S3 |
+------+    +-----+    +--------+    +----------+    +---------+    +-------+    +----+
```

### Key Stages Explained

1.  **Phase 1: Input Collection Loop**
    *   The **Engine** acts as the orchestrator.
    *   It queries generic **Adapters** for their required fields (questions).
    *   The **CLI** is strictly a display/input pass-through.
    *   Crucially, inputs (like API tokens) are saved immediately to **LocalFS** at `~/.ztp/secrets` in plain text (temporarily) or internal memory storage, alongside executing any specific init scripts for that adapter.

2.  **Phase 2: KSOPS & Encryption**
    *   This triggers after inputs are collected.
    *   **KSOPS** first interacts with **S3** to prepare the storage bucket.
    *   **KSOPS** generates the cryptography keys (AGE) and backs them up to **S3**.
    *   **KSOPS** configures the local directory by writing `.sops.yaml` (LocalFS).
    *   Finally, **KSOPS** reads the plain text secrets from `~/.ztp/secrets`, encrypts them using the public key defined in `.sops.yaml`, and writes the *encrypted* result into `platform.yaml`.
    *   **Result:** `platform.yaml` allows GitOps workflows without exposing secrets.