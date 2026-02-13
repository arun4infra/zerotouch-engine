"""Test project setup and structure"""

import importlib
from pathlib import Path


def test_package_imports():
    """Verify all core dependencies are importable"""
    importlib.import_module("typer")
    importlib.import_module("rich")
    importlib.import_module("pydantic")
    importlib.import_module("jinja2")
    importlib.import_module("yaml")


def test_directory_structure():
    """Verify project directory structure matches design spec"""
    base_dir = Path(__file__).parent.parent
    
    assert (base_dir / "ztc").is_dir()
    assert (base_dir / "ztc" / "__init__.py").is_file()
    assert (base_dir / "ztc" / "adapters").is_dir()
    assert (base_dir / "ztc" / "cli.py").is_file()
    assert (base_dir / "tests").is_dir()
    assert (base_dir / "tests" / "unit").is_dir()
    assert (base_dir / "tests" / "integration").is_dir()
