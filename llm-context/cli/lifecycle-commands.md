### Core Lifecycle Commands

| Command | Description | Key Options |
| :--- | :--- | :--- |
| **`ztc init`** | Initializes platform configuration via interactive prompts. Collects adapter configs, executes init scripts for validation, and generates platform.yaml. Supports resuming existing configurations. | `--resume`: Resume from an existing `platform.yaml`. |
| **`ztc render`** | Generates platform artifacts (manifests, pipeline config) from `platform.yaml`. It resolves dependencies, creates context snapshots, and writes to `platform/generated`. | `--debug`: Preserves the workspace on failure.<br>`--partial <name>`: Renders only specific adapters. |
| **`ztc validate`** | Validates generated artifacts against the `platform/lock.json` file to ensure no drift has occurred between configuration and generation. | N/A |
| **`ztc bootstrap`** | Executes the bootstrap pipeline. It extracts scripts to a secure temporary directory and runs the stage executor. | `--env`: Target environment (default: production).<br>`--skip-cache`: Ignore stage completion cache. |

### Debugging & Maintenance Commands

| Command | Description | Key Options |
| :--- | :--- | :--- |
| **`ztc eject`** | **"Break-glass" mode.** Extracts all embedded scripts, context files, and the pipeline to a debug directory for manual inspection and execution. | `--output`: Directory to extract to (default: `debug`).<br>`--env`: Target environment. |
| **`ztc vacuum`** | Cleans up stale temporary directories (`ztc-secure-*`) from crashed runs. This runs automatically on startup but can be invoked manually. | N/A |

### Informational Commands

| Command | Description | Key Options |
| :--- | :--- | :--- |
| **`ztc version`** | Displays the CLI version and a table of embedded adapter versions, including their phases and the capabilities they provide. | N/A |

### Global Options
All commands support the standard Typer/Click global options:
*   `--help`: Show help message and exit.

### Implementation Note
According to `docs/CLI_REFERENCE.md` and `llm-context/adapter-design/sub-commands.md`, the architecture supports **category-based subcommands** (e.g., `ztc secret init`, `ztc network status`). However, in the provided `ztc/cli.py` source code, the dynamic registration logic for these subcommands is not currently implemented in the main application entry point. Only the commands listed above are explicitly defined in the Python code.