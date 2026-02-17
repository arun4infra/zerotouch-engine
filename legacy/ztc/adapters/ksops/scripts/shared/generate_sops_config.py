#!/usr/bin/env python3
"""
Generate .sops.yaml configuration file using Jinja2 template
Usage: generate_sops_config.py <age_public_key> <output_path>
"""

import sys
from pathlib import Path
from jinja2 import Environment, FileSystemLoader


def main():
    if len(sys.argv) != 3:
        print("Usage: generate_sops_config.py <age_public_key> <output_path>", file=sys.stderr)
        sys.exit(1)
    
    age_public_key = sys.argv[1]
    output_path = Path(sys.argv[2])
    
    # Validate Age public key format
    if not age_public_key.startswith('age1') or len(age_public_key) != 62:
        print(f"Error: Invalid Age public key format: {age_public_key}", file=sys.stderr)
        sys.exit(1)
    
    # Load templates from installed package using context manager
    import importlib.resources
    templates_pkg = importlib.resources.files('ztc.adapters.ksops.templates')
    
    # Use as_file context manager to get actual filesystem path
    with importlib.resources.as_file(templates_pkg) as templates_path:
        env = Environment(loader=FileSystemLoader(str(templates_path)))
        template = env.get_template('.sops.yaml.j2')
        content = template.render(age_public_key=age_public_key)
        
        # Write output
        output_path.write_text(content)
        print(f"✓ Generated .sops.yaml at: {output_path}")


if __name__ == '__main__':
    main()
