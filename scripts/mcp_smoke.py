"""Run three prompts through headless Claude Code and save the MCP evidence.

Claude Code loads ./.mcp.json, calls each tool, and this script copies the
exact tool name and tool result from its event stream into output/mcp_smoke.json.
Needs a logged-in Claude Code CLI. Run:  python3 scripts/mcp_smoke.py
"""
import glob
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

PROMPTS = [
    "How many size S Classic Bulldog Tees (SKU CC-TEE-WHITE) do we have in stock? Use the campus-customs MCP tool.",
    "When is rent due on lease 1 and how many days away is that? Use the campus-customs MCP tool.",
    "What is the unit cost, list price and margin for the hoodie SKU CC-HOOD-NAVY? Use the campus-customs MCP tool.",
]
TOOLS = ",".join(f"mcp__campus-customs__{t}" for t in ("check_stock", "get_lease", "get_pricing"))


def find_claude() -> str:
    pattern = os.path.expanduser(
        "~/Library/Application Support/Claude/claude-code/*/*/claude.app/Contents/MacOS/claude"
    )
    found = sorted(glob.glob(pattern))
    return found[-1] if found else "claude"


def run(prompt: str) -> dict:
    out = subprocess.run(
        [find_claude(), "-p", prompt, "--mcp-config", ".mcp.json", "--strict-mcp-config",
         "--allowedTools", TOOLS, "--output-format", "stream-json", "--verbose"],
        cwd=ROOT, capture_output=True, text=True,
    ).stdout
    calls, results = {}, {}
    for line in out.splitlines():
        ev = json.loads(line)
        if ev.get("type") == "result" and ev.get("is_error"):
            raise SystemExit(f"Claude Code error: {ev.get('result')}")
        for block in (ev.get("message") or {}).get("content") or []:
            if not isinstance(block, dict):
                continue
            if block.get("type") == "tool_use" and block["name"].startswith("mcp__campus-customs__"):
                calls[block["id"]] = block["name"].removeprefix("mcp__campus-customs__")
            if block.get("type") == "tool_result" and block["tool_use_id"] in calls:
                content = block["content"]
                text = content if isinstance(content, str) else "".join(c.get("text", "") for c in content)
                results[block["tool_use_id"]] = json.loads(text)
    if not results:
        raise SystemExit(f"No MCP tool call found for prompt: {prompt}")
    tid = next(iter(results))
    return {"prompt": prompt, "tool_name": calls[tid], "tool_output": results[tid]}


if __name__ == "__main__":
    subprocess.run([sys.executable, str(ROOT / "scripts" / "reset_db.py")], check=True)
    entries = [run(p) for p in PROMPTS]
    (ROOT / "output" / "mcp_smoke.json").write_text(json.dumps(entries, indent=2) + "\n")
    for e in entries:
        print(e["tool_name"], "->", json.dumps(e["tool_output"]))
