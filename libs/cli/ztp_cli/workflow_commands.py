"""Workflow CLI commands for MCP Workflow Engine"""

import typer
from pathlib import Path
from typing import Optional
import asyncio
import time

from ztp_cli.mcp_client import get_default_client
from ztp_cli.storage import FilesystemStore
from ztp_cli.display import QuestionRenderer

app = typer.Typer(name="workflow", help="Workflow management commands")
renderer = QuestionRenderer()


@app.command()
def start(
    workflow_id: str = typer.Argument(..., help="Workflow identifier"),
    workflow_path: str = typer.Argument(..., help="Path to workflow YAML file")
):
    """Start a new workflow session"""
    asyncio.run(_start_workflow(workflow_id, workflow_path))


async def _start_workflow(workflow_id: str, workflow_path: str):
    """Start workflow implementation"""
    try:
        client = get_default_client(workflow_base_path=Path("."))
        store = FilesystemStore()
        
        async with client.connect() as session:
            # List available tools for debugging
            tools = await client.list_tools(session)
            
            result = await client.call_tool(
                session,
                "start_workflow",
                {
                    "workflow_id": workflow_id,
                    "workflow_dsl_path": workflow_path
                }
            )
            
            if result.get("question"):
                renderer.render_question(result["question"])
                
                await store.save(result["session_id"], {
                    "session_id": result["session_id"],
                    "workflow_id": workflow_id,
                    "state_blob": result["state_blob"]
                })
                
                renderer.render_session_started(result["session_id"])
            else:
                renderer.render_completion()
            
    except ValueError as e:
        renderer.render_error(str(e))
        raise typer.Exit(1)
    except Exception as e:
        renderer.render_error(f"Unexpected error: {str(e)}")
        raise typer.Exit(1)


@app.command()
def answer(
    session_id: str = typer.Argument(..., help="Session identifier"),
    answer: str = typer.Argument(..., help="Answer value")
):
    """Submit answer to current question"""
    asyncio.run(_submit_answer(session_id, answer))


async def _submit_answer(session_id: str, answer: str):
    """Submit answer implementation"""
    try:
        store = FilesystemStore()
        session = await store.load(session_id)
        
        if not session:
            renderer.render_session_not_found(session_id)
            raise typer.Exit(1)
        
        client = get_default_client(workflow_base_path=Path("."))
        
        async with client.connect() as mcp_session:
            result = await client.call_tool(
                mcp_session,
                "submit_answer",
                {
                    "session_id": session_id,
                    "state_blob": session["state_blob"],
                    "answer_value": answer,
                    "answer_type": "string",
                    "timestamp": int(time.time() * 1000)
                }
            )
            
            session["state_blob"] = result["state_blob"]
            await store.save(session_id, session)
            
            if result.get("completed"):
                renderer.render_completion()
                await store.delete(session_id)
            elif result.get("question"):
                renderer.render_question(result["question"])
        
    except ValueError as e:
        renderer.render_error(str(e))
        raise typer.Exit(1)
    except Exception as e:
        renderer.render_error(f"Unexpected error: {str(e)}")
        raise typer.Exit(1)


@app.command()
def restore(
    session_id: str = typer.Argument(..., help="Session identifier")
):
    """Restore workflow session"""
    asyncio.run(_restore_session(session_id))


async def _restore_session(session_id: str):
    """Restore session implementation"""
    try:
        store = FilesystemStore()
        session = await store.load(session_id)
        
        if not session:
            renderer.render_session_not_found(session_id)
            raise typer.Exit(1)
        
        client = get_default_client(workflow_base_path=Path("."))
        
        async with client.connect() as mcp_session:
            result = await client.call_tool(
                mcp_session,
                "restore_session",
                {
                    "session_id": session_id,
                    "state_blob": session["state_blob"]
                }
            )
            
            if result.get("question"):
                renderer.render_question(result["question"])
                renderer.render_restore_hint(session_id)
            
    except ValueError as e:
        renderer.render_error(str(e))
        raise typer.Exit(1)
    except Exception as e:
        renderer.render_error(f"Unexpected error: {str(e)}")
        raise typer.Exit(1)


@app.command()
def restart(
    workflow_id: str = typer.Argument(..., help="Workflow identifier"),
    workflow_path: str = typer.Argument(..., help="Path to workflow YAML file")
):
    """Restart workflow from beginning"""
    asyncio.run(_start_workflow(workflow_id, workflow_path))
