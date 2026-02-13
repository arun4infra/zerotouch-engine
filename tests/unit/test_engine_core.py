"""Unit tests for engine core functionality"""

import pytest
from pathlib import Path
from unittest.mock import Mock, MagicMock
from pydantic import BaseModel

from ztc.engine.context import (
    ContextSnapshot,
    PlatformContext,
    CapabilityNotFoundError,
    AdapterNotExecutedError,
    CapabilityConflictError
)
from ztc.engine.resolver import (
    DependencyResolver,
    MissingCapabilityError,
    CircularDependencyError
)
from ztc.interfaces.capabilities import (
    Capability,
    CNIArtifacts,
    KubernetesAPICapability,
    CloudInfrastructureCapability
)
from ztc.adapters.base import AdapterOutput, PlatformAdapter


class TestContextSnapshot:
    """Test ContextSnapshot immutability and capability access"""
    
    def test_get_capability_data_success(self):
        """Test successful capability data retrieval"""
        cni_data = CNIArtifacts(manifests="test-manifests", ready=True)
        capabilities = {Capability.CNI: cni_data}
        snapshot = ContextSnapshot(capabilities, {})
        
        result = snapshot.get_capability_data(Capability.CNI)
        assert result == cni_data
        assert result.manifests == "test-manifests"
        assert result.ready is True
    
    def test_get_capability_data_not_found(self):
        """Test capability not found error"""
        snapshot = ContextSnapshot({}, {})
        
        with pytest.raises(CapabilityNotFoundError) as exc_info:
            snapshot.get_capability_data(Capability.CNI)
        
        assert "No adapter provides capability 'cni'" in str(exc_info.value)
    
    def test_get_capability_data_type_mismatch(self):
        """Test type mismatch detection"""
        # Wrong type for CNI capability
        wrong_data = KubernetesAPICapability(
            cluster_endpoint="1.2.3.4:6443",
            kubeconfig_path="/path",
            version=">=1.28"
        )
        capabilities = {Capability.CNI: wrong_data}
        snapshot = ContextSnapshot(capabilities, {})
        
        with pytest.raises(TypeError) as exc_info:
            snapshot.get_capability_data(Capability.CNI)
        
        assert "expected type CNIArtifacts" in str(exc_info.value)
    
    def test_has_capability(self):
        """Test capability existence check"""
        cni_data = CNIArtifacts(manifests="test", ready=False)
        capabilities = {Capability.CNI: cni_data}
        snapshot = ContextSnapshot(capabilities, {})
        
        assert snapshot.has_capability(Capability.CNI) is True
        assert snapshot.has_capability(Capability.KUBERNETES_API) is False
    
    def test_get_output_success(self):
        """Test adapter output retrieval"""
        output = AdapterOutput(
            manifests={"test.yaml": "content"},
            stages=[],
            env_vars={},
            capabilities={},
            data={}
        )
        outputs = {"test-adapter": output}
        snapshot = ContextSnapshot({}, outputs)
        
        result = snapshot.get_output("test-adapter")
        assert result == output
    
    def test_get_output_not_executed(self):
        """Test error when adapter not executed"""
        snapshot = ContextSnapshot({}, {})
        
        with pytest.raises(AdapterNotExecutedError) as exc_info:
            snapshot.get_output("missing-adapter")
        
        assert "has not been executed yet" in str(exc_info.value)


class TestPlatformContext:
    """Test PlatformContext mutable state management"""
    
    def test_register_output_success(self):
        """Test successful output registration"""
        context = PlatformContext()
        cni_data = CNIArtifacts(manifests="test", ready=True)
        output = AdapterOutput(
            manifests={},
            stages=[],
            env_vars={},
            capabilities={"cni": cni_data},
            data={}
        )
        
        context.register_output("cilium", output)
        
        assert context.has_capability(Capability.CNI) is True
        assert context.get_output("cilium") == output
    
    def test_register_output_unknown_capability(self):
        """Test error on unknown capability"""
        context = PlatformContext()
        output = AdapterOutput(
            manifests={},
            stages=[],
            env_vars={},
            capabilities={"unknown-cap": Mock()},
            data={}
        )
        
        with pytest.raises(ValueError) as exc_info:
            context.register_output("test", output)
        
        assert "unknown capability 'unknown-cap'" in str(exc_info.value)
    
    def test_register_output_not_pydantic_model(self):
        """Test error when capability data is not Pydantic model"""
        context = PlatformContext()
        output = AdapterOutput(
            manifests={},
            stages=[],
            env_vars={},
            capabilities={"cni": {"not": "a model"}},
            data={}
        )
        
        with pytest.raises(TypeError) as exc_info:
            context.register_output("test", output)
        
        assert "must be a Pydantic model" in str(exc_info.value)
    
    def test_register_output_wrong_type(self):
        """Test error when capability data has wrong type"""
        context = PlatformContext()
        # Using KubernetesAPICapability for CNI capability (wrong type)
        wrong_data = KubernetesAPICapability(
            cluster_endpoint="1.2.3.4:6443",
            kubeconfig_path="/path",
            version=">=1.28"
        )
        output = AdapterOutput(
            manifests={},
            stages=[],
            env_vars={},
            capabilities={"cni": wrong_data},
            data={}
        )
        
        with pytest.raises(TypeError) as exc_info:
            context.register_output("test", output)
        
        assert "must be CNIArtifacts" in str(exc_info.value)
    
    def test_register_output_capability_conflict(self):
        """Test error when capability already provided"""
        context = PlatformContext()
        cni_data1 = CNIArtifacts(manifests="test1", ready=True)
        cni_data2 = CNIArtifacts(manifests="test2", ready=True)
        
        output1 = AdapterOutput(
            manifests={},
            stages=[],
            env_vars={},
            capabilities={"cni": cni_data1},
            data={}
        )
        output2 = AdapterOutput(
            manifests={},
            stages=[],
            env_vars={},
            capabilities={"cni": cni_data2},
            data={}
        )
        
        context.register_output("cilium", output1)
        
        with pytest.raises(CapabilityConflictError) as exc_info:
            context.register_output("calico", output2)
        
        assert "already provided by another adapter" in str(exc_info.value)
    
    def test_snapshot_immutability(self):
        """Test that snapshot is immutable copy"""
        context = PlatformContext()
        cni_data = CNIArtifacts(manifests="test", ready=True)
        output = AdapterOutput(
            manifests={},
            stages=[],
            env_vars={},
            capabilities={"cni": cni_data},
            data={}
        )
        
        context.register_output("cilium", output)
        snapshot = context.snapshot()
        
        # Verify snapshot has data
        assert snapshot.has_capability(Capability.CNI) is True
        
        # Modify context
        k8s_data = KubernetesAPICapability(
            cluster_endpoint="1.2.3.4:6443",
            kubeconfig_path="/path",
            version=">=1.28"
        )
        output2 = AdapterOutput(
            manifests={},
            stages=[],
            env_vars={},
            capabilities={"kubernetes-api": k8s_data},
            data={}
        )
        context.register_output("talos", output2)
        
        # Snapshot should not have new data
        assert snapshot.has_capability(Capability.KUBERNETES_API) is False
        assert context.has_capability(Capability.KUBERNETES_API) is True


class TestDependencyResolver:
    """Test dependency resolution with topological sort"""
    
    def create_mock_adapter(self, name: str, phase: str, provides: list, requires: list):
        """Create mock adapter with metadata"""
        adapter = Mock(spec=PlatformAdapter)
        adapter.name = name
        adapter.phase = phase
        adapter.load_metadata.return_value = {
            "name": name,
            "phase": phase,
            "provides": provides,
            "requires": requires
        }
        return adapter
    
    def test_resolve_simple_dependency(self):
        """Test simple dependency resolution"""
        # Hetzner provides cloud-infrastructure
        hetzner = self.create_mock_adapter(
            "hetzner",
            "foundation",
            [{"capability": "cloud-infrastructure"}],
            []
        )
        
        # Talos requires cloud-infrastructure
        talos = self.create_mock_adapter(
            "talos",
            "foundation",
            [{"capability": "kubernetes-api"}],
            [{"capability": "cloud-infrastructure"}]
        )
        
        resolver = DependencyResolver()
        result = resolver.resolve([talos, hetzner])
        
        # Hetzner should come before Talos
        assert result.index(hetzner) < result.index(talos)
    
    def test_resolve_chain_dependency(self):
        """Test chain of dependencies"""
        hetzner = self.create_mock_adapter(
            "hetzner",
            "foundation",
            ["cloud-infrastructure"],
            []
        )
        
        talos = self.create_mock_adapter(
            "talos",
            "foundation",
            ["kubernetes-api"],
            ["cloud-infrastructure"]
        )
        
        cilium = self.create_mock_adapter(
            "cilium",
            "networking",
            ["cni"],
            ["kubernetes-api"]
        )
        
        resolver = DependencyResolver()
        result = resolver.resolve([cilium, talos, hetzner])
        
        # Verify order: Hetzner → Talos → Cilium
        assert result.index(hetzner) < result.index(talos)
        assert result.index(talos) < result.index(cilium)
    
    def test_resolve_missing_capability(self):
        """Test error when required capability not provided"""
        talos = self.create_mock_adapter(
            "talos",
            "foundation",
            ["kubernetes-api"],
            ["cloud-infrastructure"]
        )
        
        resolver = DependencyResolver()
        
        with pytest.raises(MissingCapabilityError) as exc_info:
            resolver.resolve([talos])
        
        assert "requires capability 'cloud-infrastructure'" in str(exc_info.value)
        assert "no adapter provides it" in str(exc_info.value)
    
    def test_resolve_circular_dependency(self):
        """Test error on circular dependency"""
        adapter_a = self.create_mock_adapter(
            "adapter-a",
            "foundation",
            ["cap-a"],
            ["cap-b"]
        )
        
        adapter_b = self.create_mock_adapter(
            "adapter-b",
            "foundation",
            ["cap-b"],
            ["cap-a"]
        )
        
        resolver = DependencyResolver()
        
        with pytest.raises(CircularDependencyError) as exc_info:
            resolver.resolve([adapter_a, adapter_b])
        
        assert "Circular dependency detected" in str(exc_info.value)
    
    def test_resolve_no_dependencies(self):
        """Test resolution with no dependencies"""
        adapter1 = self.create_mock_adapter(
            "adapter1",
            "foundation",
            ["cap1"],
            []
        )
        
        adapter2 = self.create_mock_adapter(
            "adapter2",
            "foundation",
            ["cap2"],
            []
        )
        
        resolver = DependencyResolver()
        result = resolver.resolve([adapter1, adapter2])
        
        # Both should be in result
        assert len(result) == 2
        assert adapter1 in result
        assert adapter2 in result
