Based on **Section 2.1 (Command Structure)** and **Section 5 (Bootstrap Execution)** of the design document, the ZTC CLI currently supports the following commands:

### Core Workflow Commands

1.  **`ztc init`**
    *   **Purpose:** Initializes the `platform.yaml` configuration via an interactive wizard (Typer + Rich). It guides the user through selecting the Cloud Provider, Network, and OS.
    *   **Options:**
        *   `--resume`: Resumes the wizard from an existing `platform.yaml` file, skipping already configured adapters.

2.  **`ztc render`**
    *   **Purpose:** Generates the actual machine configurations, manifests, and the pipeline YAML based on the `platform.yaml` input. It creates the atomic `platform/generated/` directory and the `lock.json` file.
    *   **Options:**
        *   `--debug`: Preserves the temporary workspace if the render fails (useful for troubleshooting Jinja2 errors).
        *   `--partial [adapter_name]`: Renders only specific adapters (e.g., just "cilium") instead of the whole chain.

3.  **`ztc bootstrap`**
    *   **Purpose:** Executes the generated pipeline (`production.yaml`) using the `stage-executor.sh` pattern. It extracts embedded scripts to a secure temporary directory and runs them.
    *   **Options:**
        *   `--env [name]`: Specifies the target environment (default: "production").
        *   `--skip-cache`: Forces all stages to run, ignoring the `bootstrap-stage-cache.json`.

### Utility & Debugging Commands

4.  **`ztc validate`**
    *   **Purpose:** Validates the integrity of generated artifacts against the `lock.json` file to ensure no configuration drift has occurred since the last render.
    *   **Options:** None explicitly listed in the snippet, implies a check against current filesystem state.

5.  **`ztc eject`**
    *   **Purpose:** The "Break-Glass" mode. It extracts all embedded scripts, context files, and the pipeline YAML to a specified directory for manual inspection or execution.
    *   **Options:**
        *   `--env [name]`: Target environment to eject.
        *   `--output [path]`: Directory to dump the artifacts (default: "debug").

6.  **`ztc version`**
    *   **Purpose:** Displays the CLI version and the versions of all embedded adapters (Talos, Cilium, Hetzner).
    *   **Options:** None.