"""Narrow, value-redacting secret-pattern scan of nonignored workspace files.

This is not an entropy scan, history scan, or replacement for a secret scanner.
Only candidate file paths and pattern names are printed, never matching values.
"""
from pathlib import Path
import re
import subprocess

root = Path(__file__).resolve().parents[1]
paths = subprocess.check_output(['git', 'ls-files', '--cached', '--others', '--exclude-standard', '-z'], cwd=root).split(b'\0')
patterns = {
    'aws_access_key': re.compile(r'\b(?:AKIA|ASIA)[A-Z0-9]{16}\b'),
    'private_key_header': re.compile(r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----'),
    'github_token': re.compile(r'\bgh[pousr]_[A-Za-z0-9]{30,}\b'),
}
count = 0
for raw in sorted(set(paths)):
    if not raw:
        continue
    path = root / raw.decode('utf-8', errors='replace')
    if not path.is_file() or path.stat().st_size > 2_000_000:
        continue
    data = path.read_bytes()
    if b'\0' in data:
        continue
    count += 1
    value = data.decode('utf-8', errors='replace')
    for name, pattern in patterns.items():
        if pattern.search(value):
            print(f'{name}: {path.relative_to(root)}')
print(f'Scanned {count} nonignored text files; candidate paths only.')
