from __future__ import annotations

import json
import os
import sys
from typing import Any


def response(request_id: Any, result: dict[str, Any]) -> None:
    sys.stdout.write(json.dumps({"jsonrpc": "2.0", "id": request_id, "result": result}) + "\n")
    sys.stdout.flush()


def main() -> int:
    canary = os.environ.get("OT_MCP_CANARY", "")
    for line in sys.stdin:
        try:
            message = json.loads(line)
        except json.JSONDecodeError:
            continue
        method = message.get("method")
        request_id = message.get("id")
        if request_id is None:
            continue
        if method == "initialize":
            requested_version = message.get("params", {}).get(
                "protocolVersion", "2025-06-18"
            )
            response(
                request_id,
                {
                    "protocolVersion": requested_version,
                    "capabilities": {
                        "tools": {"listChanged": False},
                        "resources": {"subscribe": False, "listChanged": False},
                    },
                    "serverInfo": {
                        "name": "open-trajectory-ot-probe",
                        "version": "0.1.0",
                    },
                },
            )
        elif method == "ping":
            response(request_id, {})
        elif method == "tools/list":
            response(
                request_id,
                {
                    "tools": [
                        {
                            "name": "read_canary",
                            "description": "Return the declared OT-0002 positive-control canary.",
                            "inputSchema": {"type": "object", "additionalProperties": False},
                        }
                    ]
                },
            )
        elif method == "tools/call":
            response(
                request_id,
                {"content": [{"type": "text", "text": canary}], "isError": False},
            )
        elif method == "resources/list":
            response(
                request_id,
                {
                    "resources": [
                        {
                            "uri": "ot://positive-control/canary",
                            "name": "OT-0002 positive-control canary",
                            "mimeType": "text/plain",
                        }
                    ]
                },
            )
        elif method == "resources/templates/list":
            response(request_id, {"resourceTemplates": []})
        elif method == "resources/read":
            response(
                request_id,
                {
                    "contents": [
                        {
                            "uri": "ot://positive-control/canary",
                            "mimeType": "text/plain",
                            "text": canary,
                        }
                    ]
                },
            )
        else:
            sys.stdout.write(
                json.dumps(
                    {
                        "jsonrpc": "2.0",
                        "id": request_id,
                        "error": {"code": -32601, "message": "Method not found"},
                    }
                )
                + "\n"
            )
            sys.stdout.flush()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
