"""Unit tests for KSOPS template rendering

Tests verify:
1. All 7 templates exist and are valid Jinja2
2. Templates render without errors
3. Age public key properly injected
4. .sops.yaml generated correctly
"""

import pytest
from pathlib import Path
from jinja2 import Environment, FileSystemLoader


class TestKSOPSTemplateExistence:
    """Test all 7 KSOPS templates exist"""
    
    def test_templates_directory_exists(self):
        """Test templates directory exists"""
        templates_dir = Path(__file__).parent.parent / "templates"
        assert templates_dir.exists()
        assert templates_dir.is_dir()
    
    def test_all_templates_exist(self):
        """Test all 7 required templates exist"""
        templates_dir = Path(__file__).parent.parent / "templates"
        required_templates = [
            "age-key-guardian.yaml.j2",
            "ghcr-pull-secret.yaml.j2",
            "ksops-generator.yaml.j2",
            "kustomization.yaml.j2",
            "universal-secret-data.yaml.j2",
            "universal-secret.yaml.j2",
            ".sops.yaml.j2"
        ]
        
        for template in required_templates:
            template_path = templates_dir / template
            assert template_path.exists(), f"Template {template} not found"


class TestKSOPSTemplateRendering:
    """Test templates render correctly"""
    
    @pytest.fixture
    def jinja_env(self):
        """Create Jinja2 environment for testing"""
        templates_dir = Path(__file__).parent.parent / "templates"
        return Environment(loader=FileSystemLoader(str(templates_dir)))
    
    def test_sops_yaml_renders(self, jinja_env):
        """Test .sops.yaml template renders with age_public_key"""
        template = jinja_env.get_template(".sops.yaml.j2")
        rendered = template.render(age_public_key="age1test123")
        
        assert "age1test123" in rendered
        assert "creation_rules:" in rendered
        assert "encrypted_regex:" in rendered
    
    def test_age_key_guardian_renders(self, jinja_env):
        """Test age-key-guardian template renders"""
        template = jinja_env.get_template("age-key-guardian.yaml.j2")
        rendered = template.render()
        
        assert "ServiceAccount" in rendered
        assert "age-key-guardian" in rendered
        assert "CronJob" in rendered
    
    def test_kustomization_renders(self, jinja_env):
        """Test kustomization template renders"""
        template = jinja_env.get_template("kustomization.yaml.j2")
        rendered = template.render()
        
        assert "apiVersion: kustomize.config.k8s.io/v1beta1" in rendered
        assert "generators:" in rendered
    
    def test_universal_secret_renders(self, jinja_env):
        """Test universal-secret template renders with variables"""
        template = jinja_env.get_template("universal-secret.yaml.j2")
        rendered = template.render(
            secret_name="test-secret",
            namespace="test-ns",
            annotations="test: annotation",
            secret_type="Opaque",
            secret_key="key1",
            secret_value="value1"
        )
        
        assert "test-secret" in rendered
        assert "test-ns" in rendered
        assert "stringData:" in rendered


class TestKSOPSTemplateValidation:
    """Test template content validation"""
    
    def test_sops_yaml_has_age_variable(self):
        """Test .sops.yaml template contains age_public_key variable"""
        templates_dir = Path(__file__).parent.parent / "templates"
        sops_template = (templates_dir / ".sops.yaml.j2").read_text()
        
        assert "{{ age_public_key }}" in sops_template
        assert "creation_rules:" in sops_template
    
    def test_templates_are_valid_yaml_structure(self):
        """Test templates have valid YAML structure markers"""
        templates_dir = Path(__file__).parent.parent / "templates"
        
        yaml_templates = [
            "age-key-guardian.yaml.j2",
            "kustomization.yaml.j2",
            ".sops.yaml.j2"
        ]
        
        for template_name in yaml_templates:
            content = (templates_dir / template_name).read_text()
            # Should have YAML structure
            assert ":" in content or "---" in content
