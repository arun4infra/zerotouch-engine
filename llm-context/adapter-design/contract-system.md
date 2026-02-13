# ZTC Adapter Contract System

This document defines the two-layer contract system that governs adapter implementation in the ZeroTouch Composition Engine.

## Overview

ZTC uses a dual-contract architecture to balance universal requirements with adapter-specific extensibility:

1. **Platform Lifecycle Contract** - Mandatory, runtime-enforced via ABC
2. **CLI Extension Contract** - Optional, dev-time enforced via Protocol

---

## Layer 1: Platform Lifecycle Contract

### Interface Definition

```python
# ztc/adapters/base.py
from abc import ABC, abstractmethod

class PlatformAdapter(ABC):
    """Universal adapter lifecycle contract"""
    
    @property
    @abstractmethod
    def config_model(self) -> Type[BaseModel]:
        """Return Pydantic model for config validation"""
        pass
    
    @abstractmethod
    def get_required_inputs(self) -> List[InputPrompt]:
        """Return interactive prompts for user input"""
        pass
    
    @abstractmethod
    def pre_work_scripts(self) -> List[ScriptReference]:
        """Return pre-work scripts (e.g., rescue mode)"""
        pass
    
    @abstractmethod
    def bootstrap_scripts(self) -> List[ScriptReference]:
        """Return core adapter responsibility scripts"""
        pass
    
    @abstractmethod
    def post_work_scripts(self) -> List[ScriptReference]:
        """Return post-work scripts (e.g., additional config)"""
        pass
    
    @abstractmethod
    def validation_scripts(self) -> List[ScriptReference]:
        """Return verification scripts"""
        pass
    
    @abstractmethod
    async def render(self, ctx: 'ContextSnapshot') -> AdapterOutput:
        """Generate manifests, configs, and stage definitions"""
        pass
```

### Enforcement Mechanism

**Type**: Abstract Base Class (ABC)
**Enforcement Point**: Runtime - Python raises `TypeError` if abstract methods not implemented
**Failure Mode**: Build fails during adapter instantiation

```python
# This will fail at runtime
class MyAdapter(PlatformAdapter):
    # Missing render() implementation
    pass

adapter = MyAdapter(config={})  # TypeError: Can't instantiate abstract class
```

### Scope

**Universal**: ALL adapters must implement these methods
**Purpose**: Ensures consistent lifecycle across infrastructure, networking, secrets, storage adapters
**Non-Negotiable**: Cannot be skipped or made optional

---

## Layer 2: CLI Extension Contract

### Interface Definition

```python
# ztc/adapters/base.py
from typing import Protocol, runtime_checkable
import typer

@runtime_checkable
class CLIExtension(Protocol):
    """Optional protocol for adapters providing CLI commands"""
    
    @staticmethod
    def get_cli_category() -> str:
        """Return CLI category name (e.g., 'secret', 'network')
        
        Static method allows CLI registration without adapter instantiation.
        """
        ...
    
    def get_cli_app(self) -> typer.Typer:
        """Return Typer app with registered commands
        
        Commands appear under 'ztc {category}' namespace.
        """
        ...
```

### Enforcement Mechanism

**Type**: Protocol (structural subtyping)
**Enforcement Point**: Dev-time - Type checkers (mypy/pyright) validate signatures
**Failure Mode**: Type check warnings, not runtime errors

```python
# Type checker validates this
class MyAdapter(PlatformAdapter):
    @staticmethod
    def get_cli_category() -> str:
        return "secret"
    
    def get_cli_app(self) -> typer.Typer:
        app = typer.Typer()
        # Register commands
        return app

# Runtime check
if isinstance(MyAdapter, CLIExtension):
    # Adapter provides CLI commands
    pass
```

### Scope

**Optional**: Only adapters providing user-facing CLI tools implement this
**Purpose**: Enables interactive operations (secret rotation, network diagnostics, etc.)
**Category-Specific**: Each category (secret, network, storage) defines its own command contract

---

## Category Command Contracts

Adapters in the same category must implement compatible CLI commands to maintain consistent UX.

### Example: Secrets Category

All secrets adapters (KSOPS, Sealed Secrets, External Secrets) must implement:

**Required Commands**:
- `init-secrets <env>` - Initialize environment secrets
- `encrypt-secret <file>` - Encrypt secret file
- `rotate-keys` - Rotate encryption keys

**Optional Commands**:
- `display-key` - Display public key
- `recover` - Disaster recovery

### Enforcement

**Type**: Convention + Documentation
**Validation**: Manual review during adapter development
**Future**: Could be enforced via category-specific Protocol subclasses

---

## Contract Comparison

| Aspect | Platform Lifecycle | CLI Extension |
|--------|-------------------|---------------|
| **Enforcement** | Runtime (ABC) | Dev-time (Protocol) |
| **Scope** | Universal (all adapters) | Optional (CLI-enabled adapters) |
| **Failure Mode** | Build fails | Type warnings |
| **Purpose** | Consistent lifecycle | Interactive tools |
| **Flexibility** | None - mandatory | High - adapter-specific |
| **Contract Owner** | ZTC Engine | Adapter category |

---

## Design Rationale

### Why Two Layers?

**Platform Lifecycle (ABC)**:
- Ensures all adapters integrate with ZTC engine
- Provides predictable render → bootstrap → validate flow
- Enables capability-based composition

**CLI Extension (Protocol)**:
- Allows adapters to provide domain-specific tools
- Avoids forcing CLI on adapters that don't need it (e.g., CNI adapters)
- Maintains adapter autonomy for command design

### Why Protocol Instead of ABC for CLI?

**Flexibility**: Not all adapters need CLI commands (e.g., Cilium CNI)
**Duck Typing**: Adapters can implement CLI without explicit inheritance
**Type Safety**: Still get compile-time validation via type checkers
**Lazy Loading**: Static methods enable CLI registration without instantiation

---

## Implementation Guidelines

### For Adapter Developers

1. **Always implement Platform Lifecycle** - Non-negotiable, build will fail otherwise
2. **Implement CLI Extension if needed** - Only if adapter provides user-facing tools
3. **Follow category conventions** - If implementing CLI, match category command contract
4. **Use type hints** - Enable type checker validation for Protocol compliance

### For Engine Developers

1. **Enforce Platform Lifecycle at runtime** - Use ABC to catch missing methods early
2. **Validate CLI Extension at dev-time** - Use type checkers, not runtime checks
3. **Document category contracts** - Maintain command compatibility within categories
4. **Support lazy loading** - CLI registration should not instantiate adapters

---

## Examples

### Minimal Adapter (No CLI)

```python
class CiliumAdapter(PlatformAdapter):
    """CNI adapter - no CLI commands needed"""
    
    @property
    def config_model(self) -> Type[BaseModel]:
        return CiliumConfig
    
    def get_required_inputs(self) -> List[InputPrompt]:
        return [...]
    
    def bootstrap_scripts(self) -> List[ScriptReference]:
        return [...]
    
    async def render(self, ctx: ContextSnapshot) -> AdapterOutput:
        return AdapterOutput(...)
    
    # No CLI methods - adapter doesn't implement CLIExtension
```

### Full Adapter (With CLI)

```python
class KSOPSAdapter(PlatformAdapter):
    """Secrets adapter with CLI tools"""
    
    # Platform Lifecycle methods (mandatory)
    @property
    def config_model(self) -> Type[BaseModel]:
        return KSOPSConfig
    
    async def render(self, ctx: ContextSnapshot) -> AdapterOutput:
        return AdapterOutput(...)
    
    # CLI Extension methods (optional)
    @staticmethod
    def get_cli_category() -> str:
        return "secret"
    
    def get_cli_app(self) -> typer.Typer:
        app = typer.Typer()
        app.command(name="init-secrets")(self.init_secrets_command)
        app.command(name="rotate-keys")(self.rotate_keys_command)
        return app
    
    def init_secrets_command(self, env: str):
        """Initialize secrets for environment"""
        pass
```

---

## Future Enhancements

### Category Protocol Enforcement

Define category-specific protocols to enforce command contracts:

```python
class SecretsCLIProvider(Protocol):
    """Protocol for secrets category CLI commands"""
    
    def init_secrets_command(self, env: str) -> None: ...
    def rotate_keys_command(self) -> None: ...
    def encrypt_secret_command(self, file: str) -> None: ...
```

### Automated Contract Validation

Add CI checks to validate:
- All adapters implement Platform Lifecycle
- CLI-enabled adapters match category contracts
- Command signatures are compatible within categories
