"""KSOPS adapter output data model."""

from pydantic import BaseModel, SecretStr, field_validator, ConfigDict
from typing import Any


class KSOPSOutputData(BaseModel):
    """KSOPS adapter output metadata (non-sensitive only).
    
    Prevents accidental secret leakage in adapter output.
    """

    model_config = ConfigDict(extra="forbid")

    s3_bucket: str
    tenant_org: str
    tenant_repo: str

    @field_validator("*")
    @classmethod
    def no_secret_str(cls, v: Any) -> Any:
        """Reject SecretStr types in output."""
        if isinstance(v, SecretStr):
            raise ValueError(
                "SecretStr not allowed in adapter output. "
                "Use secret_env_vars in ScriptReference instead."
            )
        return v
