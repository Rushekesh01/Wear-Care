import subprocess
out = subprocess.run(['pyright', 'app.py', 'fix.py'], capture_output=True, text=True, encoding='utf-8').stdout
for line in out.splitlines():
    if 'error' in line.lower() or 'app.py' in line or 'fix.py' in line:
        print(line)
