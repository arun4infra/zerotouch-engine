#!/bin/bash
# Age Key Helper Functions
# Shared functions for Age key operations across KSOPS scripts
#
# Usage: source this file in scripts that need Age key operations
#   source "$SCRIPT_DIR/../helpers/age-helpers.sh"

# Generate new Age keypair
# Returns: 0 if successful, 1 if error
# Exports: AGE_PUBLIC_KEY and AGE_PRIVATE_KEY to environment
generate_age_keypair() {
    # Check if age-keygen is installed
    if ! command -v age-keygen &> /dev/null; then
        echo "Error: age-keygen not found" >&2
        echo "Install age: https://github.com/FiloSottile/age" >&2
        return 1
    fi
    
    # Generate keypair and capture output
    local keygen_output
    if ! keygen_output=$(age-keygen 2>&1); then
        echo "Error: Failed to generate Age keypair" >&2
        return 1
    fi
    
    # Extract public key (format: # public key: age1...)
    AGE_PUBLIC_KEY=$(echo "$keygen_output" | grep "# public key:" | sed 's/# public key: //')
    
    # Extract private key (format: AGE-SECRET-KEY-1...)
    AGE_PRIVATE_KEY=$(echo "$keygen_output" | grep "^AGE-SECRET-KEY-1" | head -n 1)
    
    # Validate keys were generated
    if [ -z "$AGE_PUBLIC_KEY" ]; then
        echo "Error: Failed to extract public key" >&2
        return 1
    fi
    
    if [ -z "$AGE_PRIVATE_KEY" ]; then
        echo "Error: Failed to extract private key" >&2
        return 1
    fi
    
    # Export to environment
    export AGE_PUBLIC_KEY
    export AGE_PRIVATE_KEY
    
    return 0
}

# Derive public key from private key
# Args: $1 = AGE_PRIVATE_KEY
# Returns: 0 if successful, 1 if error
# Outputs: Public key to stdout
derive_age_public_key() {
    local age_private_key="$1"
    
    if [ -z "$age_private_key" ]; then
        echo "Error: Private key parameter required" >&2
        return 1
    fi
    
    # Check if age-keygen is installed
    if ! command -v age-keygen &> /dev/null; then
        echo "Error: age-keygen not found" >&2
        return 1
    fi
    
    # Derive public key
    local age_public_key
    if ! age_public_key=$(echo "$age_private_key" | age-keygen -y 2>/dev/null); then
        echo "Error: Failed to derive public key from private key" >&2
        return 1
    fi
    
    if [ -z "$age_public_key" ]; then
        echo "Error: Derived public key is empty" >&2
        return 1
    fi
    
    echo "$age_public_key"
    return 0
}

# Generate recovery keypair for Age key encryption
# Returns: 0 if successful, 1 if error
# Exports: RECOVERY_PUBLIC, RECOVERY_PRIVATE to environment
generate_recovery_keypair() {
    # Check if age-keygen is installed
    if ! command -v age-keygen &> /dev/null; then
        echo "Error: age-keygen not found" >&2
        return 1
    fi
    
    # Generate recovery keypair
    local recovery_key
    if ! recovery_key=$(age-keygen 2>/dev/null); then
        echo "Error: Failed to generate recovery keypair" >&2
        return 1
    fi
    
    # Extract public and private keys
    RECOVERY_PUBLIC=$(echo "$recovery_key" | grep "public key:" | cut -d: -f2 | xargs)
    RECOVERY_PRIVATE=$(echo "$recovery_key" | grep "AGE-SECRET-KEY-" | xargs)
    
    # Validate keys
    if [ -z "$RECOVERY_PUBLIC" ]; then
        echo "Error: Failed to extract recovery public key" >&2
        return 1
    fi
    
    if [ -z "$RECOVERY_PRIVATE" ]; then
        echo "Error: Failed to extract recovery private key" >&2
        return 1
    fi
    
    # Export to environment
    export RECOVERY_PUBLIC
    export RECOVERY_PRIVATE
    
    return 0
}

# Validate Age private key format
# Args: $1 = AGE_PRIVATE_KEY
# Returns: 0 if valid, 1 if invalid
validate_age_private_key() {
    local age_private_key="$1"
    
    if [ -z "$age_private_key" ]; then
        echo "Error: Private key parameter required" >&2
        return 1
    fi
    
    # Trim whitespace and extract key
    age_private_key=$(echo "$age_private_key" | tr -d '[:space:]' | grep -o 'AGE-SECRET-KEY-1[A-Z0-9]*')
    
    if [[ ! "$age_private_key" =~ ^AGE-SECRET-KEY-1 ]]; then
        echo "Error: Invalid Age private key format" >&2
        return 1
    fi
    
    echo "$age_private_key"
    return 0
}

# Encrypt Age private key with recovery public key
# Args: $1 = AGE_PRIVATE_KEY, $2 = RECOVERY_PUBLIC_KEY
# Returns: 0 if successful, 1 if error
# Outputs: Encrypted content to stdout
encrypt_age_key() {
    local age_private_key="$1"
    local recovery_public_key="$2"
    
    if [ -z "$age_private_key" ] || [ -z "$recovery_public_key" ]; then
        echo "Error: Missing required parameters" >&2
        return 1
    fi
    
    # Check if age is installed
    if ! command -v age &> /dev/null; then
        echo "Error: age not found" >&2
        return 1
    fi
    
    # Encrypt Age key
    local encrypted_content
    if ! encrypted_content=$(echo "$age_private_key" | age -r "$recovery_public_key" -a 2>&1); then
        echo "Error: Failed to encrypt Age key" >&2
        return 1
    fi
    
    echo "$encrypted_content"
    return 0
}

# Decrypt Age private key with recovery private key
# Args: $1 = encrypted_file_path, $2 = recovery_private_key_path
# Returns: 0 if successful, 1 if error
# Outputs: Decrypted Age private key to stdout
decrypt_age_key() {
    local encrypted_file="$1"
    local recovery_key_file="$2"
    
    if [ -z "$encrypted_file" ] || [ -z "$recovery_key_file" ]; then
        echo "Error: Missing required parameters" >&2
        return 1
    fi
    
    if [ ! -f "$encrypted_file" ]; then
        echo "Error: Encrypted file not found: $encrypted_file" >&2
        return 1
    fi
    
    if [ ! -f "$recovery_key_file" ]; then
        echo "Error: Recovery key file not found: $recovery_key_file" >&2
        return 1
    fi
    
    # Check if age is installed
    if ! command -v age &> /dev/null; then
        echo "Error: age not found" >&2
        return 1
    fi
    
    # Decrypt Age key
    local decrypted_key
    if ! decrypted_key=$(age -d -i "$recovery_key_file" "$encrypted_file" 2>/dev/null); then
        echo "Error: Failed to decrypt Age key" >&2
        return 1
    fi
    
    echo "$decrypted_key"
    return 0
}
