#!/usr/bin/env python3
"""Automated init test using subprocess"""

import subprocess
import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env.dev
load_dotenv('.env.dev')

# Clean previous state
for path in ['platform/platform.yaml', Path.home() / '.ztp' / 'secrets', '.ztc/session.json']:
    try:
        Path(path).unlink()
    except FileNotFoundError:
        pass

# Prepare answers from environment
answers = [
    os.getenv('ORG_NAME', 'test-org'),
    os.getenv('APP_NAME', 'test-app'),
    os.getenv('HCLOUD_TOKEN'),
    os.getenv('HETZNER_DNS_TOKEN'),
    os.getenv('SERVER_IPS'),
    'y',  # rescue mode confirm
    os.getenv('GITHUB_APP_ID'),
    os.getenv('GITHUB_APP_INSTALLATION_ID'),
    os.getenv('GITHUB_APP_PRIVATE_KEY'),
    os.getenv('CONTROL_PLANE_REPO_URL'),
    os.getenv('DATA_PLANE_REPO_URL'),
    os.getenv('S3_ACCESS_KEY'),
    os.getenv('S3_SECRET_KEY'),
    os.getenv('S3_ENDPOINT'),
    os.getenv('S3_BUCKET_NAME'),
]

# Run init with piped input
input_text = '\n'.join(answers) + '\n'
result = subprocess.run(
    ['./ztc-new.py', 'init'],
    input=input_text,
    text=True,
    capture_output=True
)

print(result.stdout)
if result.stderr:
    print("STDERR:", result.stderr)

exit(result.returncode)
