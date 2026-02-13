"""Eject workflow for manual debugging and intervention"""

from pathlib import Path
from typing import List
from rich.console import Console
from rich.progress import Progress
from rich.table import Table
import json
from datetime import datetime


class EjectWorkflow:
    """Eject workflow for manual debugging and intervention
    
    Extracts all embedded scripts, context files, and pipeline to a debug directory.
    Operators can then inspect, modify, and manually execute bootstrap logic.
    
    Use cases:
    - Debugging failed bootstrap stages
    - Manual intervention during cluster setup
    - Understanding script execution flow
    - Customizing scripts for edge cases
    """
    
    def __init__(self, console: Console, output_dir: Path, env: str):
        """Initialize eject workflow
        
        Args:
            console: Rich console for output
            output_dir: Directory to extract artifacts to
            env: Environment name (e.g., "production")
        """
        self.console = console
        self.output_dir = Path(output_dir)
        self.env = env
        self.engine = None
    
    def run(self):
        """Execute eject workflow"""
        self.console.print(f"[bold blue]Ejecting bootstrap artifacts to {self.output_dir}[/bold blue]")
        
        # 1. Validate prerequisites
        self.validate_prerequisites()
        
        # 2. Load platform.yaml and initialize engine
        from ztc.engine.engine import PlatformEngine
        platform_yaml = Path("platform.yaml")
        self.engine = PlatformEngine(platform_yaml)
        
        # 3. Resolve adapters
        adapters = self.engine.resolve_adapters()
        
        # 4. Create output directory structure
        self.create_directory_structure()
        
        # 5. Extract scripts with context files
        with Progress() as progress:
            task = progress.add_task("[cyan]Extracting scripts...", total=len(adapters))
            
            for adapter in adapters:
                self.extract_adapter_scripts(adapter)
                progress.update(task, advance=1)
        
        # 6. Copy pipeline.yaml
        self.copy_pipeline_yaml()
        
        # 7. Generate execution guide
        self.generate_execution_guide(adapters)
        
        # 8. Display summary
        self.display_summary()
    
    def validate_prerequisites(self):
        """Validate that platform.yaml and generated artifacts exist"""
        if not Path("platform.yaml").exists():
            raise FileNotFoundError(
                "platform.yaml not found. Run 'ztc init' first."
            )
        
        if not Path("platform/generated").exists():
            raise FileNotFoundError(
                "Generated artifacts not found. Run 'ztc render' first."
            )
    
    def create_directory_structure(self):
        """Create output directory structure"""
        self.output_dir.mkdir(parents=True, exist_ok=True)
        (self.output_dir / "scripts").mkdir(exist_ok=True)
        (self.output_dir / "context").mkdir(exist_ok=True)
        (self.output_dir / "pipeline").mkdir(exist_ok=True)
    
    def extract_adapter_scripts(self, adapter: 'PlatformAdapter'):
        """Extract all scripts for an adapter with context files
        
        Args:
            adapter: PlatformAdapter instance to extract scripts from
        """
        adapter_scripts_dir = self.output_dir / "scripts" / adapter.name
        adapter_context_dir = self.output_dir / "context" / adapter.name
        
        adapter_scripts_dir.mkdir(parents=True, exist_ok=True)
        adapter_context_dir.mkdir(parents=True, exist_ok=True)
        
        # Get all script references from adapter lifecycle hooks
        all_scripts = (
            adapter.pre_work_scripts() +
            adapter.bootstrap_scripts() +
            adapter.post_work_scripts() +
            adapter.validation_scripts()
        )
        
        for script_ref in all_scripts:
            # Extract script content
            script_content = adapter.get_embedded_script(script_ref.resource.value)
            script_path = adapter_scripts_dir / script_ref.resource.value
            
            # Create parent directories if script is in subdirectory
            script_path.parent.mkdir(parents=True, exist_ok=True)
            
            script_path.write_text(script_content)
            script_path.chmod(0o755)
            
            # Write context file if present
            if script_ref.context_data:
                context_file = adapter_context_dir / f"{script_ref.resource.value}.context.json"
                
                # Create parent directories if context file is in subdirectory
                context_file.parent.mkdir(parents=True, exist_ok=True)
                
                context_file.write_text(json.dumps(script_ref.context_data, indent=2))
    
    def copy_pipeline_yaml(self):
        """Copy pipeline.yaml to output directory"""
        pipeline_src = Path(f"bootstrap/pipeline/{self.env}.yaml")
        
        if not pipeline_src.exists():
            self.console.print(
                f"[yellow]⚠[/yellow] Pipeline file not found: {pipeline_src}"
            )
            return
        
        pipeline_dst = self.output_dir / "pipeline" / f"{self.env}.yaml"
        pipeline_dst.write_text(pipeline_src.read_text())
    
    def generate_execution_guide(self, adapters: List['PlatformAdapter']):
        """Generate README with execution instructions
        
        Args:
            adapters: List of resolved adapters
        """
        guide_content = f"""# Ejected Bootstrap Artifacts

**Environment:** {self.env}
**Ejected:** {datetime.now().isoformat()}

## Directory Structure

```
{self.output_dir}/
├── scripts/              # Extracted scripts by adapter
│   ├── hetzner/
│   ├── cilium/
│   └── talos/
├── context/              # Context files for scripts
│   ├── hetzner/
│   ├── cilium/
│   └── talos/
├── pipeline/             # Pipeline YAML
│   └── {self.env}.yaml
└── README.md             # This file
```

## Adapters

"""
        
        for adapter in adapters:
            guide_content += f"\n### {adapter.name}\n\n"
            guide_content += f"**Phase:** {adapter.phase}\n\n"
            guide_content += "**Scripts:**\n\n"
            
            all_scripts = (
                adapter.pre_work_scripts() +
                adapter.bootstrap_scripts() +
                adapter.post_work_scripts() +
                adapter.validation_scripts()
            )
            
            for script_ref in all_scripts:
                guide_content += f"- `{script_ref.resource.value}` - {script_ref.description}\n"
                
                if script_ref.context_data:
                    guide_content += f"  - Context: `context/{adapter.name}/{script_ref.resource.value}.context.json`\n"
            
            guide_content += "\n"
        
        guide_content += f"""
## Manual Execution

### Using Context Files

Scripts that have context files read data via the `$ZTC_CONTEXT_FILE` environment variable:

```bash
export ZTC_CONTEXT_FILE="context/talos/03-install-talos.sh.context.json"
bash scripts/talos/03-install-talos.sh
```

### Reading Context in Scripts

Example bash script reading context.json:

```bash
#!/usr/bin/env bash
set -euo pipefail

# Read context file
if [[ -z "${{ZTC_CONTEXT_FILE:-}}" ]]; then
    echo "ERROR: ZTC_CONTEXT_FILE not set" >&2
    exit 1
fi

# Parse JSON with jq
SERVER_IP=$(jq -r '.server_ip' "$ZTC_CONTEXT_FILE")
CLUSTER_NAME=$(jq -r '.cluster_name' "$ZTC_CONTEXT_FILE")

echo "Installing Talos on $SERVER_IP for cluster $CLUSTER_NAME"
```

### Using stage-executor.sh

You can use the existing stage-executor.sh with ejected artifacts:

```bash
# Copy stage-executor.sh to output directory
cp /path/to/stage-executor.sh {self.output_dir}/

# Execute pipeline
cd {self.output_dir}
./stage-executor.sh pipeline/{self.env}.yaml
```

### Manual Stage Execution

Execute stages individually for debugging:

```bash
# Stage 1: Enable rescue mode
export HCLOUD_TOKEN="your-token"
bash scripts/hetzner/enable-rescue-mode.sh

# Stage 2: Install Talos
export ZTC_CONTEXT_FILE="context/talos/03-install-talos.sh.context.json"
bash scripts/talos/03-install-talos.sh
```

## Modifying Scripts

You can modify ejected scripts for debugging or edge cases:

1. Edit script in `scripts/<adapter>/<script-name>.sh`
2. Update context file in `context/<adapter>/<script-name>.sh.context.json` if needed
3. Execute manually or via stage-executor.sh

## Re-integrating Changes

If you fix issues in ejected scripts:

1. Update the adapter's embedded script in the ZTC source code
2. Rebuild the ZTC binary
3. Run `ztc render` to regenerate artifacts
4. Run `ztc bootstrap` to execute with fixed scripts

## Warning

Ejected artifacts are for debugging only. Production bootstraps should use `ztc bootstrap`.
"""
        
        readme_path = self.output_dir / "README.md"
        readme_path.write_text(guide_content)
    
    def display_summary(self):
        """Display eject summary"""
        table = Table(title="Eject Summary")
        table.add_column("Component", style="cyan")
        table.add_column("Location", style="yellow")
        table.add_column("Status", style="green")
        
        table.add_row("Scripts", str(self.output_dir / "scripts"), "✓ Extracted")
        table.add_row("Context Files", str(self.output_dir / "context"), "✓ Generated")
        table.add_row("Pipeline", str(self.output_dir / "pipeline"), "✓ Copied")
        table.add_row("README", str(self.output_dir / "README.md"), "✓ Generated")
        
        self.console.print(table)
        self.console.print(f"\n[green]✓[/green] Eject complete. Artifacts available at: {self.output_dir}")
