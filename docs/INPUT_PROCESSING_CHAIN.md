# Input Processing Chain Refactoring

## Pattern: Chain of Responsibility

Replaced nested if/else conditions with a clean, extensible handler chain.

## Architecture

```
Input → SkipFieldHandler → DefaultValueHandler → DerivedValueHandler → PromptUserHandler
         ↓ skip              ↓ auto-select         ↓ auto-derive         ↓ prompt user
```

## Components

### 1. `InputProcessingHandler` (Abstract Base)
- Base class for all handlers
- Implements chain linking: `set_next()`
- Delegates to `_process()` for specific logic

### 2. Concrete Handlers

**SkipFieldHandler**
- Checks `adapter.should_skip_field()`
- Returns `ProcessingResult(handled=True, skip_to_next=True)`
- Example: Skip BGP ASN when BGP disabled

**DefaultValueHandler**
- Checks `input_def.get("default")`
- Auto-selects without prompting
- Returns value with "(auto-selected)" message

**DerivedValueHandler**
- Calls `adapter.derive_field_value()`
- Auto-derives from other fields
- Returns value with "(auto-derived)" message

**PromptUserHandler**
- Final handler - always handles
- Returns `ProcessingResult(handled=True, value=None)`
- Signals that user prompt is needed

### 3. `InputProcessingChain`
- Orchestrates the handler chain
- Builds and links handlers in constructor
- Single entry point: `process()`

## Benefits

### Before (Nested Conditions)
```python
if should_skip_field():
    skip
elif has_default():
    auto-select
elif derive_field_value():
    auto-derive
else:
    prompt user
```

### After (Chain of Responsibility)
```python
result = self.processing_chain.process(field_name, inp, adapter, collected_config)

if result.skip_to_next:
    # Handle skip
elif result.value is not None:
    # Handle auto-value
else:
    # Prompt user
```

### Advantages
1. **Extensible**: Add new handlers without modifying existing code
2. **Testable**: Each handler is independently testable
3. **Maintainable**: Single responsibility per handler
4. **Clear**: No nested if/else chains
5. **Reusable**: Chain can be used in other workflows

## Usage

```python
from workflow_engine.engine.input_processing_chain import InputProcessingChain

# Initialize once
chain = InputProcessingChain()

# Process each input
result = chain.process(field_name, input_def, adapter, collected_config)

if result.skip_to_next:
    # Move to next field
    pass
elif result.value is not None:
    # Use auto-selected/derived value
    collected[field_name] = result.value
else:
    # Prompt user for input
    pass
```

## Adding New Handlers

To add a new processing rule:

1. Create handler class:
```python
class CustomHandler(InputProcessingHandler):
    def _process(self, field_name, input_def, adapter, collected_config):
        if your_condition:
            return ProcessingResult(handled=True, value=your_value)
        return ProcessingResult(handled=False)
```

2. Add to chain in `InputProcessingChain.__init__()`:
```python
self.custom_handler = CustomHandler()
self.skip_handler.set_next(self.custom_handler) \
                 .set_next(self.default_handler) \
                 ...
```

## Testing

```bash
# Unit test the chain
python3 -c "
import sys; sys.path.insert(0, 'libs')
from workflow_engine.engine.input_processing_chain import InputProcessingChain
# ... test code
"

# Integration test with init workflow
./ztc-new.py init
```

## Files Modified

- `libs/workflow_engine/engine/input_processing_chain.py` (NEW)
- `libs/workflow_engine/engine/init_workflow.py` (refactored)
- `libs/workflow_engine/engine/__init__.py` (exports)

## Migration Notes

- No breaking changes to adapter interface
- Existing adapters work without modification
- CLI behavior unchanged
- All tests pass
