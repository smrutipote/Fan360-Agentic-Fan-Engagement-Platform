import requests, json

MCP = "http://localhost:5000/mcp"
H = {"Content-Type": "application/json", "Accept": "application/json, text/event-stream"}

# Step 1: Initialize
init_payload = {
    "jsonrpc": "2.0", "id": 1, "method": "initialize",
    "params": {
        "protocolVersion": "2025-03-26",
        "capabilities": {},
        "clientInfo": {"name": "test", "version": "1.0"}
    }
}
r = requests.post(MCP, headers=H, json=init_payload, stream=True, timeout=15)
print("Init status:", r.status_code)
sid = r.headers.get("Mcp-Session-Id")
print("Session ID:", sid)
for line in r.iter_lines():
    if line:
        print("INIT LINE:", line.decode("utf-8"))

# Step 2: Call with session
H2 = {**H, "Mcp-Session-Id": sid}
call_payload = {
    "jsonrpc": "2.0", "id": 2, "method": "tools/call",
    "params": {
        "name": "read_records",
        "arguments": {"entity": "gold_dim_fan", "first": 1}
    }
}
r2 = requests.post(MCP, headers=H2, json=call_payload, stream=True, timeout=15)
print("\nCall status:", r2.status_code)
for line in r2.iter_lines():
    if line:
        decoded = line.decode("utf-8")
        print("CALL LINE:", decoded)
        if decoded.startswith("data:"):
            data = json.loads(decoded[5:].strip())
            print("PARSED:", json.dumps(data, indent=2)[:500])
