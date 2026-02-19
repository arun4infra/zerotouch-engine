sequenceDiagram
    actor User
    participant CLI
    participant Engine
    participant Adapters
    participant LocalFS as Local FS<br/>(~/.ztp & Root)
    participant KSOPS as KSOPS Script
    participant S3 as S3 Bucket

    User->>CLI: Start Init
    CLI->>Engine: Begin Initialization

    %% Phase 1: Input Collection
    rect rgb(240, 248, 255)
    note right of User: <b>Phase 1: Input Collection</b>
    loop For Each Adapter (Hetzner, Git, etc.)
        Engine->>Adapters: Request Input Schema
        Adapters-->>Engine: Return Fields/Questions

        loop For Each Field
            Engine->>CLI: Send Question
            CLI->>User: Display Prompt
            User->>CLI: Provide Input (e.g., Secrets)
            CLI->>Engine: Submit Input
            
            %% Store raw secret locally
            Engine->>LocalFS: Store Raw Secret (~/.ztp/secrets)
            
            %% Run specific adapter script
            Engine->>Adapters: Execute Adapter Init Script
        end
    end
    end

    %% Phase 2: Encryption
    rect rgb(255, 250, 240)
    note right of User: <b>Phase 2: KSOPS & Encryption</b>
    Engine->>KSOPS: Trigger KSOPS Init
    
    %% S3 and Key Generation
    KSOPS->>S3: Create Bucket for App
    KSOPS->>KSOPS: Generate AGE Keys (Public/Private)
    KSOPS->>S3: Store AGE Keys
    
    %% Config Creation
    KSOPS->>LocalFS: Create .sops.yaml (at Root)
    
    %% Encryption Process
    KSOPS->>LocalFS: Read Plaintext Secrets (~/.ztp/secrets)
    LocalFS-->>KSOPS: Return Secrets
    KSOPS->>KSOPS: Encrypt Secrets (using .sops.yaml key)
    
    %% Final Write
    note right of KSOPS: Secrets stored encrypted<br/>in platform.yaml
    KSOPS->>LocalFS: Update platform.yaml
    
    KSOPS-->>Engine: KSOPS Init Success
    end

    Engine-->>CLI: Workflow Complete
    CLI-->>User: Display Success