import json
with open('pyright_output.txt', 'r', encoding='utf-16le') as f:
    data = json.load(f)
for d in data.get('generalDiagnostics', []):
    print(f"{d['file']}:{d['range']['start']['line']+1} {d['message']}")
