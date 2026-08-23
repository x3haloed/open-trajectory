from __future__ import annotations

import json
import queue
import subprocess
import threading
import time
from pathlib import Path
from typing import Any, Callable


MODEL_VISIBLE_TOOL_INVENTORY_PREFIX = "OT_TOOL_INVENTORY_RECEIPT\t"


class AppServerError(RuntimeError):
    pass


class AppServerClient:
    """Small synchronous JSONL client for one Codex app-server process."""

    def __init__(
        self,
        *,
        command: list[str],
        cwd: Path,
        env: dict[str, str],
        request_timeout: float = 120.0,
        event_log: Path | None = None,
    ) -> None:
        self.command = command
        self.cwd = cwd
        self.env = env
        self.request_timeout = request_timeout
        self.event_log = event_log
        self.raw_events: list[dict[str, Any]] = []
        self.stderr_lines: list[str] = []
        self._responses: dict[int | str, dict[str, Any]] = {}
        self._notifications: list[dict[str, Any]] = []
        self._condition = threading.Condition()
        self._request_id = 0
        self._closed = False
        self._process = subprocess.Popen(
            command,
            cwd=cwd,
            env=env,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            bufsize=1,
        )
        self._stdout_thread = threading.Thread(target=self._read_stdout, daemon=True)
        self._stderr_thread = threading.Thread(target=self._read_stderr, daemon=True)
        self._stdout_thread.start()
        self._stderr_thread.start()
        self._initialize()

    def _record(self, direction: str, message: Any) -> None:
        event = {
            "sequence": len(self.raw_events),
            "monotonic_ns": time.monotonic_ns(),
            "direction": direction,
            "message": message,
        }
        self.raw_events.append(event)
        if self.event_log is not None:
            with self.event_log.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(event, sort_keys=True, separators=(",", ":")) + "\n")

    def _send(self, message: dict[str, Any]) -> None:
        if self._process.stdin is None:
            raise AppServerError("app-server stdin is unavailable")
        self._record("client_to_server", message)
        encoded = json.dumps(message, separators=(",", ":"))
        self._process.stdin.write(encoded + "\n")
        self._process.stdin.flush()

    def _read_stdout(self) -> None:
        if self._process.stdout is None:
            return
        for line in self._process.stdout:
            try:
                message = json.loads(line)
            except json.JSONDecodeError:
                message = {"unparsed_stdout": line.rstrip("\n")}
            with self._condition:
                self._record("server_to_client", message)
                if isinstance(message, dict) and "id" in message and (
                    "result" in message or "error" in message
                ):
                    self._responses[message["id"]] = message
                elif isinstance(message, dict) and "id" in message:
                    self._deny_server_request(message)
                elif isinstance(message, dict):
                    self._notifications.append(message)
                self._condition.notify_all()
        with self._condition:
            self._condition.notify_all()

    def _read_stderr(self) -> None:
        if self._process.stderr is None:
            return
        for line in self._process.stderr:
            with self._condition:
                self.stderr_lines.append(line.rstrip("\n"))
                self._record("server_stderr", line.rstrip("\n"))
                self._condition.notify_all()

    def _deny_server_request(self, message: dict[str, Any]) -> None:
        response = {
            "id": message["id"],
            "error": {
                "code": -32000,
                "message": "OT-0002 controller denies all server-initiated requests",
            },
        }
        self._send(response)

    def _initialize(self) -> None:
        result = self.request(
            "initialize",
            {
                "clientInfo": {
                    "name": "open_trajectory_ot0002",
                    "title": "Open Trajectory OT-0002",
                    "version": "0.1.0",
                }
            },
        )
        if "userAgent" not in result:
            raise AppServerError("initialize response omitted userAgent")
        self.initialize_result = result
        self.notify("initialized", {})

    def request(
        self,
        method: str,
        params: dict[str, Any] | None,
        *,
        timeout: float | None = None,
    ) -> dict[str, Any]:
        with self._condition:
            request_id = self._request_id
            self._request_id += 1
        message: dict[str, Any] = {"method": method, "id": request_id}
        if params is not None:
            message["params"] = params
        self._send(message)
        deadline = time.monotonic() + (timeout or self.request_timeout)
        with self._condition:
            while request_id not in self._responses:
                if self._process.poll() is not None:
                    raise AppServerError(
                        f"app-server exited while waiting for {method}: {self._process.returncode}"
                    )
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise AppServerError(f"timed out waiting for {method}")
                self._condition.wait(min(remaining, 1.0))
            response = self._responses.pop(request_id)
        if "error" in response:
            raise AppServerError(f"{method} failed: {response['error']}")
        result = response.get("result")
        if not isinstance(result, dict):
            raise AppServerError(f"{method} returned a non-object result")
        return result

    def notify(self, method: str, params: dict[str, Any]) -> None:
        self._send({"method": method, "params": params})

    def notification_count(self) -> int:
        with self._condition:
            return len(self._notifications)

    def wait_notification(
        self,
        method: str,
        *,
        after: int,
        predicate: Callable[[dict[str, Any]], bool] | None = None,
        timeout: float | None = None,
    ) -> dict[str, Any]:
        deadline = time.monotonic() + (timeout or self.request_timeout)
        with self._condition:
            while True:
                for notification in self._notifications[after:]:
                    if notification.get("method") != method:
                        continue
                    if predicate is None or predicate(notification):
                        return notification
                if self._process.poll() is not None:
                    raise AppServerError(
                        f"app-server exited while waiting for {method}: {self._process.returncode}"
                    )
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise AppServerError(f"timed out waiting for notification {method}")
                self._condition.wait(min(remaining, 1.0))

    def start_thread(self, params: dict[str, Any]) -> dict[str, Any]:
        return self.request("thread/start", params)["thread"]

    def run_turn(
        self,
        *,
        thread_id: str,
        input_text: str,
        output_schema: dict[str, Any],
        sandbox_policy: dict[str, Any],
        timeout: float | None = None,
    ) -> dict[str, Any]:
        after = self.notification_count()
        started = self.request(
            "turn/start",
            {
                "threadId": thread_id,
                "input": [{"type": "text", "text": input_text}],
                "outputSchema": output_schema,
                "approvalPolicy": "never",
                "sandboxPolicy": sandbox_policy,
                "effort": "low",
            },
            timeout=timeout,
        )
        turn_id = started["turn"]["id"]
        completed = self.wait_notification(
            "turn/completed",
            after=after,
            predicate=lambda item: item.get("params", {}).get("threadId") == thread_id
            and item.get("params", {}).get("turn", {}).get("id") == turn_id,
            timeout=timeout,
        )
        return completed["params"]["turn"]

    def completed_turn_items(self, *, thread_id: str, turn_id: str) -> list[dict[str, Any]]:
        """Return terminal item receipts from the event stream for one turn."""
        items: list[dict[str, Any]] = []
        with self._condition:
            events = list(self.raw_events)
        for event in events:
            message = event.get("message")
            if not isinstance(message, dict) or message.get("method") != "item/completed":
                continue
            params = message.get("params", {})
            if params.get("threadId") != thread_id or params.get("turnId") != turn_id:
                continue
            item = params.get("item")
            if isinstance(item, dict):
                items.append(item)
        return items

    def completed_turn_tool_calls(self, *, thread_id: str, turn_id: str) -> int:
        tool_types = {
            "commandExecution",
            "fileChange",
            "mcpToolCall",
            "dynamicToolCall",
            "webSearch",
            "imageView",
        }
        return sum(
            item.get("type") in tool_types
            for item in self.completed_turn_items(thread_id=thread_id, turn_id=turn_id)
        )

    def model_visible_tool_inventories(self) -> list[list[dict[str, Any]]]:
        """Parse inventories emitted by the pinned prompt-construction patch."""
        with self._condition:
            lines = list(self.stderr_lines)
        inventories: list[list[dict[str, Any]]] = []
        for line in lines:
            if not line.startswith(MODEL_VISIBLE_TOOL_INVENTORY_PREFIX):
                continue
            try:
                value = json.loads(line[len(MODEL_VISIBLE_TOOL_INVENTORY_PREFIX) :])
            except json.JSONDecodeError as error:
                raise AppServerError("malformed model-visible tool inventory receipt") from error
            if not isinstance(value, list) or not all(isinstance(item, dict) for item in value):
                raise AppServerError("model-visible tool inventory receipt is not an object list")
            inventories.append(value)
        return inventories

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        if self._process.stdin is not None:
            self._process.stdin.close()
        try:
            self._process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            self._process.terminate()
            try:
                self._process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._process.kill()
                self._process.wait(timeout=5)
        self._stdout_thread.join(timeout=2)
        self._stderr_thread.join(timeout=2)

    def __enter__(self) -> AppServerClient:
        return self

    def __exit__(self, exc_type: Any, exc: Any, traceback: Any) -> None:
        self.close()
