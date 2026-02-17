"""Transport security configuration for MCP server"""
from enum import Enum
from typing import Optional


class TransportSecurityMode(str, Enum):
    """Security modes for MCP transport"""
    DEVELOPMENT = "development"  # HTTP on localhost only
    PRODUCTION = "production"    # HTTPS/TLS mandatory


class SecurityError(Exception):
    """Raised when security constraints are violated"""
    pass


def validate_transport_security(
    transport_type: str,
    security_mode: TransportSecurityMode,
    host: str,
    tls_enabled: bool = False
) -> None:
    """Enforce security mode constraints
    
    Args:
        transport_type: Type of transport (stdio, streamable-http)
        security_mode: Security mode (development, production)
        host: Host binding address
        tls_enabled: Whether TLS is enabled
        
    Raises:
        SecurityError: If security constraints are violated
    """
    if security_mode == TransportSecurityMode.PRODUCTION:
        if transport_type == "streamable-http":
            # In production, require TLS
            if not tls_enabled:
                raise SecurityError(
                    "Production mode requires TLS for HTTP transport"
                )
            
            # Reject localhost-only bindings in production
            if host in ("127.0.0.1", "localhost", "::1"):
                raise SecurityError(
                    "Production mode requires network-accessible binding, "
                    f"not localhost ({host})"
                )
    
    elif security_mode == TransportSecurityMode.DEVELOPMENT:
        if transport_type == "streamable-http":
            # In development, only allow localhost
            if host not in ("127.0.0.1", "localhost", "::1"):
                raise SecurityError(
                    f"Development mode only allows localhost binding, "
                    f"not {host}"
                )


def get_transport_config(
    security_mode: TransportSecurityMode,
    host: Optional[str] = None,
    port: int = 8000,
    tls_cert_path: Optional[str] = None,
    tls_key_path: Optional[str] = None
) -> dict:
    """Get transport configuration based on security mode
    
    Args:
        security_mode: Security mode (development, production)
        host: Host to bind to (defaults based on mode)
        port: Port to bind to
        tls_cert_path: Path to TLS certificate (production only)
        tls_key_path: Path to TLS private key (production only)
        
    Returns:
        Dictionary with transport configuration
        
    Raises:
        SecurityError: If configuration is invalid for security mode
    """
    if security_mode == TransportSecurityMode.DEVELOPMENT:
        # Development: localhost only, no TLS
        final_host = host or "127.0.0.1"
        
        # Validate host is localhost
        if final_host not in ("127.0.0.1", "localhost", "::1"):
            raise SecurityError(
                f"Development mode only allows localhost binding, not {final_host}"
            )
        
        return {
            "transport": "streamable-http",
            "host": final_host,
            "port": port,
            "tls_enabled": False
        }
    
    elif security_mode == TransportSecurityMode.PRODUCTION:
        # Production: network binding, TLS required
        if not tls_cert_path or not tls_key_path:
            raise SecurityError(
                "Production mode requires TLS certificate and key paths"
            )
        
        final_host = host or "0.0.0.0"
        
        # Reject localhost-only bindings in production
        if final_host in ("127.0.0.1", "localhost", "::1"):
            raise SecurityError(
                f"Production mode requires network-accessible binding, not localhost ({final_host})"
            )
        
        return {
            "transport": "streamable-http",
            "host": final_host,
            "port": port,
            "tls_enabled": True,
            "tls_cert": tls_cert_path,
            "tls_key": tls_key_path
        }
    
    raise ValueError(f"Unknown security mode: {security_mode}")
