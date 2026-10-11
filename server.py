import hashlib, json, os
from flask import Flask, request, Response

EMAIL = os.environ.get("EXAM_EMAIL", "23f3000514@ds.study.iitm.ac.in").strip().lower()
PROTOCOL_VERSIONS = ["2025-06-18", "2025-03-26", "2024-11-05"]

app = Flask(__name__)

TOOL = {
    "name": "solve_challenge",
    "description": "Returns the exam answer for the per-call X-Exam-Challenge header.",
    "inputSchema": {"type": "object", "properties": {}},
}

def answer(challenge: str) -> str:
    return hashlib.sha256(f"{challenge}:{EMAIL}".encode()).hexdigest()[:16]

def reply(obj, status=200):
    r = Response(json.dumps(obj), status=status, mimetype="application/json")
    r.headers["Access-Control-Allow-Origin"] = "*"
    r.headers["Access-Control-Allow-Headers"] = "*"
    r.headers["Access-Control-Expose-Headers"] = "Mcp-Session-Id"
    return r

def handle(msg):
    method, mid, params = msg.get("method"), msg.get("id"), msg.get("params") or {}
    if mid is None:                      # notification -> no response
        return None
    if method == "initialize":
        want = params.get("protocolVersion")
        ver = want if want in PROTOCOL_VERSIONS else PROTOCOL_VERSIONS[0]
        result = {"protocolVersion": ver,
                  "capabilities": {"tools": {"listChanged": False}},
                  "serverInfo": {"name": "exam-mcp", "version": "1.0.0"}}
    elif method == "ping":
        result = {}
    elif method == "tools/list":
        result = {"tools": [TOOL]}
    elif method == "tools/call":
        if params.get("name") != "solve_challenge":
            return {"jsonrpc": "2.0", "id": mid,
                    "error": {"code": -32602, "message": "Unknown tool"}}
        ch = (request.headers.get("X-Exam-Challenge") or "").strip()
        if not ch:
            result = {"content": [{"type": "text", "text": "missing X-Exam-Challenge header"}],
                      "isError": True}
        else:
            result = {"content": [{"type": "text", "text": answer(ch)}]}
    else:
        return {"jsonrpc": "2.0", "id": mid,
                "error": {"code": -32601, "message": f"Method not found: {method}"}}
    return {"jsonrpc": "2.0", "id": mid, "result": result}

@app.route("/", methods=["GET", "POST", "OPTIONS", "DELETE"])
@app.route("/mcp", methods=["GET", "POST", "OPTIONS", "DELETE"])
def mcp():
    if request.method == "OPTIONS":
        return reply({}, 204)
    if request.method != "POST":
        return reply({"error": "use POST"}, 405)
    try:
        body = request.get_json(force=True)
    except Exception:
        return reply({"jsonrpc": "2.0", "id": None,
                      "error": {"code": -32700, "message": "Parse error"}}, 400)
    if isinstance(body, list):
        outs = [o for o in (handle(m) for m in body) if o is not None]
        return reply(outs) if outs else reply({}, 202)
    out = handle(body)
    return reply(out) if out is not None else Response(status=202, headers={"Access-Control-Allow-Origin": "*"})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))
