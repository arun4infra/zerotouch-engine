"""Init workflow orchestration"""

import json
from typing import Dict, Any
from pydantic import SecretStr

from workflow_engine.registry.adapter_registry import AdapterRegistry
from workflow_engine.engine.script_executor import ScriptExecutor
from workflow_engine.engine.input_processing_chain import InputProcessingChain


class InitWorkflow:
    """Handles init workflow orchestration and state management"""
    
    def __init__(self, registry: AdapterRegistry):
        self.registry = registry
        self.processing_chain = InputProcessingChain()
    
    def start(self) -> Dict[str, Any]:
        """Start init workflow"""
        selection_groups = self._build_selection_groups()
        
        if not selection_groups:
            return {"error": "No adapters available"}
        
        workflow_state = {
            "current_step": "org_name",
            "answers": {},
            "selection_groups": selection_groups,
            "current_group_index": -1
        }
        
        question = {
            "id": "org_name",
            "type": "string",
            "prompt": "Organization name",
            "help_text": "Used for consistent naming across all resources",
            "required": True
        }
        
        return {
            "question": question,
            "workflow_state": workflow_state,
            "completed": False
        }
    
    def answer(self, state: Dict[str, Any], answer_value: str) -> Dict[str, Any]:
        """Process answer and return next question"""
        import json
        
        # Parse answer_value only if it's a JSON array or object (not plain strings/numbers)
        if isinstance(answer_value, str) and (answer_value.startswith('[') or answer_value.startswith('{')):
            try:
                parsed_value = json.loads(answer_value)
                answer_value = parsed_value
            except (json.JSONDecodeError, TypeError):
                # Not valid JSON, use as-is
                pass
        
        current_step = state["current_step"]
        state["answers"][current_step] = answer_value
        
        if current_step == "org_name":
            return self._next_question_app_name(state, answer_value)
        elif current_step == "app_name":
            return self._next_question_selection(state)
        elif current_step.endswith("_selection"):
            return self._next_question_adapter_inputs(state, current_step, answer_value)
        elif current_step.endswith("_validation_failed"):
            return self._handle_validation_retry(state, answer_value)
        elif "_input_" in current_step:
            return self._next_question_collect_input(state)
        elif current_step.endswith("_config"):
            return self._next_question_next_group(state)
        else:
            return {"error": f"Unknown step: {current_step}"}
    
    def _next_question_app_name(self, state: Dict[str, Any], org_name: str) -> Dict[str, Any]:
        """Return app_name question"""
        state["current_step"] = "app_name"
        question = {
            "id": "app_name",
            "type": "string",
            "prompt": "Application name (lowercase, hyphens only)",
            "help_text": f"Must start with organization name: {org_name}-",
            "required": True
        }
        return {"question": question, "workflow_state": state, "completed": False}
    
    def _next_question_selection(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Move to first selection group"""
        state["current_group_index"] = 0
        return self._get_selection_group_question(state)
    
    def _next_question_adapter_inputs(self, state: Dict[str, Any], current_step: str, adapter_name: str) -> Dict[str, Any]:
        """Get adapter configuration inputs"""
        group_name = current_step.replace("_selection", "")
        return self._get_adapter_inputs_question(state, group_name, adapter_name)
    
    def _next_question_collect_input(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Continue collecting adapter inputs"""
        input_state = state["current_adapter_inputs"]
        inputs = input_state["inputs"]
        current_index = input_state["current_index"]
        
        # Store the answer in collected config
        inp = inputs[current_index]
        current_step = state["current_step"]
        answer_value = state["answers"][current_step]
        input_state["collected"][inp["name"]] = answer_value
        
        input_state["current_index"] += 1
        
        return self._get_adapter_inputs_question(state, input_state["group_name"], input_state["adapter_name"])
    
    def _next_question_next_group(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Move to next selection group"""
        state["current_group_index"] += 1
        return self._get_selection_group_question(state)
    
    def _handle_validation_retry(self, state: Dict[str, Any], answer_value: str) -> Dict[str, Any]:
        """Handle validation failure retry"""
        # Handle both boolean and string responses
        if isinstance(answer_value, bool):
            retry = answer_value
        else:
            retry = str(answer_value).lower() in ["true", "yes", "y"]
        
        if retry:
            input_state = state["current_adapter_inputs"]
            input_state["current_index"] = 0
            input_state["collected"] = {}
            del state["validation_error"]
            return self._get_adapter_inputs_question(state, input_state["group_name"], input_state["adapter_name"])
        else:
            return {"error": "Validation failed and user declined retry"}
    
    def _build_selection_groups(self) -> list:
        """Build selection groups from adapter registry"""
        groups = {}
        
        for adapter_name in self.registry.list_adapters():
            metadata = self.registry.get_metadata(adapter_name)
            selection_group = metadata.get("selection_group")
            group_order = metadata.get("group_order")
            
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
    
    def _get_selection_group_question(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Get question for current selection group"""
        groups = state["selection_groups"]
        index = state["current_group_index"]
        
        if index >= len(groups):
            return self.generate_platform_yaml(state)
        
        group = groups[index]
        group_name = group["name"]
        
        if len(group["adapters"]) == 1:
            adapter = group["adapters"][0]
            state["answers"][f"{group_name}_selection"] = adapter["name"]
            state["current_step"] = f"{group_name}_selection"
            return self._get_adapter_inputs_question(state, group_name, adapter["name"])
        
        choices = []
        default = None
        for adapter in group["adapters"]:
            choice_text = f"{adapter['display_name']} (v{adapter['version']})"
            if adapter["is_default"]:
                choice_text += " [default]"
                default = adapter["name"]
            choices.append({"value": adapter["name"], "label": choice_text})
        
        state["current_step"] = f"{group_name}_selection"
        question = {
            "id": f"{group_name}_selection",
            "type": "choice",
            "prompt": f"Select {group_name.replace('_', ' ')}",
            "choices": choices,
            "default": default,
            "required": True
        }
        
        return {"question": question, "workflow_state": state, "completed": False}
    
    def _get_adapter_inputs_question(self, state: Dict[str, Any], group_name: str, adapter_name: str) -> Dict[str, Any]:
        """Get adapter configuration inputs one by one, auto-filling defaults"""
        if "current_adapter_inputs" not in state:
            adapter = self.registry.get_adapter(adapter_name, {})
            inputs = adapter.get_required_inputs() if hasattr(adapter, 'get_required_inputs') else []
            
            if not inputs:
                state["current_group_index"] += 1
                return self._get_selection_group_question(state)
            
            state["current_adapter_inputs"] = {
                "adapter_name": adapter_name,
                "group_name": group_name,
                "inputs": [self._serialize_input(inp) for inp in inputs],
                "current_index": 0,
                "collected": {}
            }
        
        input_state = state["current_adapter_inputs"]
        
        # Auto-process fields until we need user input
        while True:
            inputs = input_state["inputs"]
            current_index = input_state["current_index"]
            
            if current_index >= len(inputs):
                return self._validate_and_continue(state, input_state)
            
            inp = inputs[current_index]
            field_name = inp["name"]
            
            all_adapters_config = self._build_cross_adapter_config(state)
            adapter = self.registry.get_adapter(adapter_name, {})
            adapter._all_adapters_config = all_adapters_config
            
            # Process input through the handler chain
            result = self.processing_chain.process(field_name, inp, adapter, input_state["collected"])
            
            # Handle skip
            if result.skip_to_next:
                input_state["current_index"] += 1
                continue  # Auto-process next field
            
            # Handle auto-selected or auto-derived values (check for None explicitly, not falsy)
            if result.value is not None and result.display_message is not None:
                input_state["collected"][field_name] = result.value
                input_state["current_index"] += 1
                continue  # Auto-process next field
            
            # Needs user input - stop and return question
            break
        
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
        
        if hasattr(adapter, 'get_input_context'):
            context = adapter.get_input_context(field_name, input_state["collected"])
            if context:
                question.update(context)
        
        return {"question": question, "workflow_state": state, "completed": False}
    
    def _validate_and_continue(self, state: Dict[str, Any], input_state: Dict[str, Any]) -> Dict[str, Any]:
        """Validate collected config with init scripts"""
        adapter_name = input_state["adapter_name"]
        collected_config = input_state["collected"]
        
        validation_result = self._execute_adapter_init_scripts(adapter_name, collected_config)
        
        if validation_result.get("failed"):
            state["current_step"] = f"{input_state['group_name']}_validation_failed"
            state["validation_error"] = validation_result
            
            question = {
                "id": state["current_step"],
                "type": "boolean",
                "prompt": f"Validation failed: {validation_result['error']}\n\nFix the issue and retry configuration for {adapter_name}?",
                "default": True,
                "required": True
            }
            
            return {"question": question, "workflow_state": state, "completed": False}
        
        # Clean config before storing (remove secrets, parse types)
        adapter = self.registry.get_adapter(adapter_name, {})
        cleaned_config = self._clean_adapter_config(adapter, collected_config)
        
        state["answers"][f"{input_state['group_name']}_config"] = cleaned_config
        del state["current_adapter_inputs"]
        if "validation_error" in state:
            del state["validation_error"]
        state["current_group_index"] += 1
        
        next_result = self._get_selection_group_question(state)
        # Always include validation_scripts (even if empty) so CLI knows validation completed
        next_result["validation_scripts"] = validation_result.get("scripts", [])
        return next_result
    
    def _execute_adapter_init_scripts(self, adapter_name: str, config: dict) -> Dict[str, Any]:
        """Execute adapter init scripts for validation"""
        try:
            adapter = self.registry.get_adapter(adapter_name, config)
            init_scripts = adapter.init() if hasattr(adapter, 'init') else []
            
            if not init_scripts:
                return {"failed": False, "scripts": []}
            
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
            return {"failed": True, "error": f"Script execution error: {str(e)}", "stderr": str(e), "stdout": ""}
    
    def generate_platform_yaml(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Generate final platform.yaml from collected answers"""
        import yaml
        
        platform_data = {
            "version": "1.0",
            "platform": {
                "organization": state["answers"].get("org_name"),
                "app_name": state["answers"].get("app_name")
            },
            "adapters": {}
        }
        
        for key, value in state["answers"].items():
            if key.endswith("_selection"):
                adapter_name = value
                group_name = key.replace("_selection", "")
                config_key = f"{group_name}_config"
                config = state["answers"].get(config_key, {})
                
                if isinstance(config, str) and config:
                    try:
                        config = json.loads(config)
                    except:
                        config = {}
                
                adapter = self.registry.get_adapter(adapter_name, {})
                cleaned_config = self._clean_adapter_config(adapter, config)
                
                platform_data["adapters"][adapter_name] = cleaned_config
        
        yaml_content = yaml.dump(platform_data, sort_keys=False, default_flow_style=False)
        
        return {"completed": True, "platform_yaml": yaml_content, "workflow_state": state}
    
    def _clean_adapter_config(self, adapter, config: dict) -> dict:
        """Remove secrets and parse types properly"""
        cleaned = {}
        config_model = adapter.config_model
        
        for field_name, field_value in config.items():
            if field_name not in config_model.model_fields:
                continue
            
            field_info = config_model.model_fields[field_name]
            field_type = field_info.annotation
            
            if field_type == SecretStr or (hasattr(field_type, '__origin__') and field_type.__origin__ == SecretStr):
                continue
            
            # Handle List types
            if hasattr(field_type, '__origin__') and field_type.__origin__ == list:
                if isinstance(field_value, str):
                    # Convert comma-separated string to list
                    if ',' in field_value:
                        field_value = [v.strip() for v in field_value.split(',')]
                    else:
                        field_value = [field_value]
            elif isinstance(field_value, str):
                if field_value.startswith('[') or field_value.startswith('{'):
                    try:
                        field_value = json.loads(field_value)
                    except:
                        pass
                elif field_value in ['True', 'False']:
                    field_value = field_value == 'True'
                elif field_value.isdigit():
                    field_value = int(field_value)
            
            cleaned[field_name] = field_value
        
        return cleaned
    
    def _serialize_input(self, inp) -> dict:
        """Serialize InputPrompt to dict"""
        return {
            "name": inp.name,
            "type": inp.type,
            "prompt": inp.prompt,
            "help_text": getattr(inp, 'help_text', None),
            "default": getattr(inp, 'default', None),
            "choices": getattr(inp, 'choices', None),
            "validation": getattr(inp, 'validation', None)
        }
    
    def _build_cross_adapter_config(self, state: Dict[str, Any]) -> dict:
        """Get cross-adapter config from CLI-provided platform config"""
        return state.get("platform_adapters_config", {})
