"""Init workflow handler for MCP tools"""

import json
from pathlib import Path
from workflow_engine.registry import AdapterRegistry


class InitWorkflowHandler:
    def __init__(self, mcp, allow_write: bool = False):
        self.mcp = mcp
        self.allow_write = allow_write
        self.registry = AdapterRegistry()
        self._register_tools()
    
    def _register_tools(self):
        @self.mcp.tool()
        async def init_start() -> str:
            """Start platform init workflow"""
            try:
                # Build selection groups from adapter registry
                selection_groups = self._build_selection_groups()
                
                if not selection_groups:
                    return json.dumps({"error": "No adapters available"})
                
                # Initialize workflow state
                workflow_state = {
                    "current_step": "org_name",
                    "answers": {},
                    "selection_groups": selection_groups,
                    "current_group_index": -1
                }
                
                # First question: organization name
                question = {
                    "id": "org_name",
                    "type": "string",
                    "prompt": "Organization name",
                    "help_text": "Used for consistent naming across all resources",
                    "required": True
                }
                
                return json.dumps({
                    "question": question,
                    "workflow_state": json.dumps(workflow_state),
                    "completed": False
                })
            except Exception as e:
                return json.dumps({"error": str(e)})
        
        @self.mcp.tool()
        async def init_answer(workflow_state: str, answer_value: str) -> str:
            """Submit answer and get next question"""
            try:
                state = json.loads(workflow_state)
                current_step = state["current_step"]
                
                # Store answer
                state["answers"][current_step] = answer_value
                
                # Determine next question
                if current_step == "org_name":
                    state["current_step"] = "app_name"
                    question = {
                        "id": "app_name",
                        "type": "string",
                        "prompt": "Application name (lowercase, hyphens only)",
                        "help_text": f"Must start with organization name: {answer_value}-",
                        "required": True
                    }
                    return json.dumps({
                        "question": question,
                        "workflow_state": json.dumps(state),
                        "completed": False
                    })
                
                elif current_step == "app_name":
                    # Move to first selection group
                    state["current_group_index"] = 0
                    return self._get_selection_group_question(state)
                
                elif current_step.endswith("_selection"):
                    # Adapter selected, get its inputs
                    group_name = current_step.replace("_selection", "")
                    return self._get_adapter_inputs_question(state, group_name, answer_value)
                
                elif current_step.endswith("_validation_failed"):
                    # User responded to validation failure
                    if answer_value.lower() in ["true", "yes", "y"]:
                        # Retry: reset input collection for same adapter
                        input_state = state["current_adapter_inputs"]
                        input_state["current_index"] = 0
                        input_state["collected"] = {}
                        del state["validation_error"]
                        return self._get_adapter_inputs_question(state, input_state["group_name"], input_state["adapter_name"])
                    else:
                        # User declined retry, abort
                        return json.dumps({"error": "Validation failed and user declined retry"})
                
                elif "_input_" in current_step:
                    # Collecting adapter input
                    input_state = state["current_adapter_inputs"]
                    inputs = input_state["inputs"]
                    current_index = input_state["current_index"]
                    
                    # Store answer
                    inp = inputs[current_index]
                    input_state["collected"][inp["name"]] = answer_value
                    
                    print(f"DEBUG: Stored answer for {inp['name']}, current_index={current_index}, total_inputs={len(inputs)}")
                    
                    # Move to next input
                    input_state["current_index"] += 1
                    
                    print(f"DEBUG: Incremented index to {input_state['current_index']}")
                    
                    return self._get_adapter_inputs_question(state, input_state["group_name"], input_state["adapter_name"])
                
                elif current_step.endswith("_config"):
                    # Config collected, move to next group
                    state["current_group_index"] += 1
                    return self._get_selection_group_question(state)
                
                else:
                    return json.dumps({"error": f"Unknown step: {current_step}"})
                    
            except Exception as e:
                return json.dumps({"error": str(e)})
    
    def _build_selection_groups(self):
        """Build selection groups from adapter registry"""
        groups = {}
        
        for adapter_name in self.registry.list_adapters():
            metadata = self.registry.get_metadata(adapter_name)
            selection_group = metadata.get("selection_group")
            group_order = metadata.get("group_order")
            
            # Skip adapters without group_order (not ready for init workflow)
            if not selection_group or group_order is None:
                continue
                
            if selection_group not in groups:
                groups[selection_group] = {
                    "name": selection_group,
                    "adapters": [],
                    "order": group_order
                }
            
            groups[selection_group]["adapters"].append({
                "name": adapter_name,
                "display_name": metadata.get("display_name", adapter_name),
                "version": metadata.get("version", "unknown"),
                "is_default": metadata.get("is_default", False)
            })
        
        return sorted(groups.values(), key=lambda g: g["order"])
    
    def _get_selection_group_question(self, state):
        """Get question for current selection group"""
        groups = state["selection_groups"]
        index = state["current_group_index"]
        
        if index >= len(groups):
            # All groups done, generate platform.yaml
            return self._generate_platform_yaml(state)
        
        group = groups[index]
        group_name = group["name"]
        
        # Auto-select if only one adapter
        if len(group["adapters"]) == 1:
            adapter = group["adapters"][0]
            state["answers"][f"{group_name}_selection"] = adapter["name"]
            state["current_step"] = f"{group_name}_selection"
            return self._get_adapter_inputs_question(state, group_name, adapter["name"])
        
        # Build choices
        choices = []
        default = None
        for adapter in group["adapters"]:
            choice_text = f"{adapter['display_name']} (v{adapter['version']})"
            if adapter["is_default"]:
                choice_text += " [default]"
                default = adapter["name"]
            choices.append({
                "value": adapter["name"],
                "label": choice_text
            })
        
        state["current_step"] = f"{group_name}_selection"
        question = {
            "id": f"{group_name}_selection",
            "type": "choice",
            "prompt": f"Select {group_name.replace('_', ' ')}",
            "choices": choices,
            "default": default,
            "required": True
        }
        
        return json.dumps({
            "question": question,
            "workflow_state": json.dumps(state),
            "completed": False
        })
    
    def _get_adapter_inputs_question(self, state, group_name, adapter_name):
        """Get adapter configuration inputs one by one"""
        try:
            print(f"DEBUG: _get_adapter_inputs_question called for {adapter_name}")
            
            # Get or initialize input collection state
            if "current_adapter_inputs" not in state:
                adapter = self.registry.get_adapter(adapter_name, {})
                inputs = adapter.get_required_inputs() if hasattr(adapter, 'get_required_inputs') else []
                
                if not inputs:
                    # No inputs needed, move to next group
                    state["current_group_index"] += 1
                    return self._get_selection_group_question(state)
                
                state["current_adapter_inputs"] = {
                    "adapter_name": adapter_name,
                    "group_name": group_name,
                    "inputs": [{"name": inp.name, "type": inp.type, "prompt": inp.prompt, "help_text": getattr(inp, 'help_text', None), "default": getattr(inp, 'default', None), "choices": getattr(inp, 'choices', None), "validation": getattr(inp, 'validation', None)} for inp in inputs],
                    "current_index": 0,
                    "collected": {}
                }
            
            input_state = state["current_adapter_inputs"]
            inputs = input_state["inputs"]
            current_index = input_state["current_index"]
            
            print(f"DEBUG: current_index={current_index}, len(inputs)={len(inputs)}")
            
            if current_index >= len(inputs):
                # All inputs collected, validate with init scripts
                adapter_name = input_state["adapter_name"]
                collected_config = input_state["collected"]
                
                import sys
                print(f"DEBUG: All inputs collected for {adapter_name}, calling init scripts...", file=sys.stderr)
                
                # Execute adapter init scripts for validation
                validation_result = self._execute_adapter_init_scripts(adapter_name, collected_config, state)
                
                print(f"DEBUG: Validation result: {validation_result}", file=sys.stderr)
                
                if validation_result.get("failed"):
                    # Validation failed, ask user to retry
                    state["current_step"] = f"{input_state['group_name']}_validation_failed"
                    state["validation_error"] = validation_result
                    
                    question = {
                        "id": state["current_step"],
                        "type": "boolean",
                        "prompt": f"Validation failed: {validation_result['error']}\n\nFix the issue and retry configuration for {adapter_name}?",
                        "default": True,
                        "required": True
                    }
                    
                    return json.dumps({
                        "question": question,
                        "workflow_state": json.dumps(state),
                        "completed": False
                    })
                
                # Validation succeeded, store config and move to next group
                state["answers"][f"{input_state['group_name']}_config"] = collected_config
                del state["current_adapter_inputs"]
                if "validation_error" in state:
                    del state["validation_error"]
                state["current_group_index"] += 1
                
                # Return next question with validation script results
                next_result = self._get_selection_group_question(state)
                result_data = json.loads(next_result)
                result_data["validation_scripts"] = validation_result.get("scripts", [])
                return json.dumps(result_data)
            
            # Get current input
            inp = inputs[current_index]
            field_name = inp["name"]
            
            # Build full platform config for cross-adapter access
            all_adapters_config = {}
            for key, value in state["answers"].items():
                if key.endswith("_config"):
                    adapter_name_from_key = state["answers"].get(key.replace("_config", "_selection"))
                    if adapter_name_from_key:
                        all_adapters_config[adapter_name_from_key] = value
            
            # Check if adapter can derive this field's value
            adapter = self.registry.get_adapter(adapter_name, input_state["collected"])
            adapter._all_adapters_config = all_adapters_config  # Provide cross-adapter access
            derived_value = adapter.derive_field_value(field_name, input_state["collected"]) if hasattr(adapter, 'derive_field_value') else None
            
            if derived_value is not None:
                # Auto-derive, store value, and continue to next input
                input_state["collected"][field_name] = derived_value
                input_state["current_index"] += 1
                
                # Store the derived value info to display later
                if "auto_derived_fields" not in state:
                    state["auto_derived_fields"] = []
                state["auto_derived_fields"].append({
                    "prompt": inp["prompt"],
                    "value": derived_value
                })
                
                # Recursively get next question (might be another auto-derived field)
                return self._get_adapter_inputs_question(state, group_name, adapter_name)
            
            state["current_step"] = f"{group_name}_input_{field_name}"
            
            question = {
                "id": state["current_step"],
                "type": inp["type"],
                "prompt": inp["prompt"],
                "help_text": inp.get("help_text"),
                "default": inp.get("default"),
                "choices": inp.get("choices"),
                "validation": inp.get("validation"),
                "name": inp["name"],
                "required": True
            }
            
            # Let adapter provide additional context for the question
            if hasattr(adapter, 'get_input_context'):
                context = adapter.get_input_context(field_name, input_state["collected"])
                if context:
                    question.update(context)
            
            result = {
                "question": question,
                "workflow_state": json.dumps(state),
                "completed": False
            }
            
            # Include auto-derived fields for display (only if present)
            if "auto_derived_fields" in state and state["auto_derived_fields"]:
                result["auto_derived_fields"] = state["auto_derived_fields"]
                # Clear immediately in state so they don't appear again
                del state["auto_derived_fields"]
                # Update workflow_state with cleared fields
                result["workflow_state"] = json.dumps(state)
            
            return json.dumps(result)
        except Exception as e:
            return json.dumps({"error": str(e)})
    
    def _execute_adapter_init_scripts(self, adapter_name: str, config: dict, state: dict) -> dict:
        """Execute adapter init scripts for validation
        
        Returns:
            dict with 'failed' (bool), 'error' (str), 'scripts' (list of script results)
        """
        try:
            from workflow_engine.engine.script_executor import ScriptExecutor
            
            # Get adapter with collected config
            adapter = self.registry.get_adapter(adapter_name, config)
            
            # Get init scripts
            init_scripts = adapter.init() if hasattr(adapter, 'init') else []
            
            if not init_scripts:
                return {"failed": False, "scripts": []}
            
            # Execute scripts
            executor = ScriptExecutor()
            script_results = []
            
            for script_ref in init_scripts:
                result = executor.execute(script_ref)
                
                script_results.append({
                    "description": script_ref.description,
                    "success": result.exit_code == 0,
                    "exit_code": result.exit_code,
                    "stdout": result.stdout,
                    "stderr": result.stderr
                })
                
                if result.exit_code != 0:
                    return {
                        "failed": True,
                        "error": f"{script_ref.description} failed",
                        "stderr": result.stderr,
                        "stdout": result.stdout,
                        "script": script_ref.description,
                        "scripts": script_results
                    }
            
            return {"failed": False, "scripts": script_results}
            
        except Exception as e:
            return {
                "failed": True,
                "error": f"Script execution error: {str(e)}",
                "stderr": str(e),
                "stdout": ""
            }
    
    def _generate_platform_yaml(self, state):
        """Generate final platform.yaml from collected answers"""
        if not self.allow_write:
            return json.dumps({"error": "Write operations not allowed"})
        
        try:
            import yaml
            
            # Build platform config
            platform_data = {
                "version": "1.0",
                "platform": {
                    "organization": state["answers"].get("org_name"),
                    "app_name": state["answers"].get("app_name")
                },
                "adapters": {}
            }
            
            # Add selected adapters
            for key, value in state["answers"].items():
                if key.endswith("_selection"):
                    adapter_name = value
                    group_name = key.replace("_selection", "")
                    config_key = f"{group_name}_config"
                    config = state["answers"].get(config_key, {})
                    
                    # Parse JSON config if string
                    if isinstance(config, str) and config:
                        try:
                            config = json.loads(config)
                        except:
                            config = {}
                    
                    # Get adapter to filter secrets and parse types
                    adapter = self.registry.get_adapter(adapter_name, {})
                    cleaned_config = self._clean_adapter_config(adapter, config)
                    
                    platform_data["adapters"][adapter_name] = cleaned_config
            
            yaml_content = yaml.dump(platform_data, sort_keys=False, default_flow_style=False)
            
            return json.dumps({
                "completed": True,
                "platform_yaml": yaml_content,
                "workflow_state": json.dumps(state)
            })
        except Exception as e:
            return json.dumps({"error": str(e)})
    
    def _clean_adapter_config(self, adapter, config: dict) -> dict:
        """Remove secrets and parse types properly"""
        from pydantic import SecretStr
        import json
        
        cleaned = {}
        config_model = adapter.config_model
        
        for field_name, field_value in config.items():
            # Skip if field doesn't exist in model
            if field_name not in config_model.model_fields:
                continue
            
            field_info = config_model.model_fields[field_name]
            field_type = field_info.annotation
            
            # Skip SecretStr fields
            if field_type == SecretStr or (hasattr(field_type, '__origin__') and field_type.__origin__ == SecretStr):
                continue
            
            # Parse string values back to proper types
            if isinstance(field_value, str):
                # Try to parse as JSON first (for lists/dicts)
                if field_value.startswith('[') or field_value.startswith('{'):
                    try:
                        field_value = json.loads(field_value)
                    except:
                        pass
                # Parse booleans
                elif field_value in ['True', 'False']:
                    field_value = field_value == 'True'
                # Parse integers
                elif field_value.isdigit():
                    field_value = int(field_value)
            
            cleaned[field_name] = field_value
        
        return cleaned
