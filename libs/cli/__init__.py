"""CLI presentation layer for workflow engine"""

__all__ = ["workflow_app", "core_app", "FilesystemStore"]

# Lazy imports to avoid circular dependencies
def __getattr__(name):
    if name == "workflow_app":
        from libs.cli.workflow_commands import app
        return app
    elif name == "core_app":
        from libs.cli.core_commands import app
        return app
    elif name == "FilesystemStore":
        from libs.cli.storage import FilesystemStore
        return FilesystemStore
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")
