"""Manual Mac smoke: real curl -> loopback POS server -> MockTransport, never cloud.

Run from repository root with PYTHONPATH=agent/src. All values are synthetic.
Passwords/QR are passed to curl through stdin config, not process arguments.
"""

from __future__ import annotations

import json
import subprocess
import tempfile
from pathlib import Path

import httpx
from pydantic import SecretStr

from poscenter_loyalty_agent.config import AgentSettings
from poscenter_loyalty_agent.pos_server import PosServer


def main() -> int:
    password = "synthetic-smoke-password-" + "s" * 32
    token = "C1" + "A" * 32
    cloud_calls = 0

    def cloud(request: httpx.Request) -> httpx.Response:
        nonlocal cloud_calls
        cloud_calls += 1
        assert str(request.url) == "https://mock.invalid/agent/qr/resolve"
        return httpx.Response(200, json={"barcode": "000000123456", "card_id": "mock-only"})

    with tempfile.TemporaryDirectory(prefix="pos-qr-smoke-") as directory:
        root = Path(directory)
        settings = AgentSettings(
            _env_file=None,
            agent_env="test",
            agent_api_key="synthetic-smoke-agent-key-not-real",
            agent_cloud_base_url="https://mock.invalid",
            agent_pos_server_enabled=True,
            agent_pos_listen_host="127.0.0.1",
            agent_pos_token=SecretStr(password),
            agent_state_db_path=root / "unused.db",
            one_state_key_path=root / "unused.key",
            one_mapping_path=root / "unused-mapping.json",
            agent_log_dir=root / "unused-logs",
        )
        service = PosServer(settings, listen_port=0, transport=httpx.MockTransport(cloud))
        assert service.start()
        assert service.address is not None
        base = f"http://127.0.0.1:{service.address[1]}"
        print(f"LOOPBACK={base}; cloud=MockTransport; all credentials/data synthetic")
        try:
            cases = [
                ("health, correct password", "GET", "/v1/health", password, None, 200, {"status": "ok"}),
                ("resolve, correct password", "POST", "/v1/qr/resolve", password, token, 200, {"barcode": "000000123456"}),
                ("resolve, wrong password", "POST", "/v1/qr/resolve", "wrong-synthetic", token, 401, None),
                ("resolve, malformed QR", "POST", "/v1/qr/resolve", password, "C1bad", 400, None),
            ]
            for label, method, path, supplied, qr, expected_status, expected_body in cases:
                lines = [f"url = {json.dumps(base + path)}", f"request = {json.dumps(method)}", f"header = {json.dumps('X-Pos-Token: ' + supplied)}"]
                if qr is not None:
                    lines += ['header = "Content-Type: application/json"', f"data = {json.dumps(json.dumps({'token': qr}))}"]
                print(f"\n{label}: curl --silent --show-error --max-time 7 --config - --write-out '\\nHTTP_CODE=%{{http_code}}\\n'")
                print("(stdin config: URL + X-Pos-Token redacted + JSON when applicable)")
                result = subprocess.run(
                    ["curl", "--silent", "--show-error", "--max-time", "7", "--noproxy", "*", "--config", "-", "--write-out", "\nHTTP_CODE=%{http_code}\n"],
                    input="\n".join(lines) + "\n", capture_output=True, text=True, timeout=9,
                )
                print(result.stdout, end="")
                print(result.stderr, end="")
                print(f"CURL_EXIT_CODE={result.returncode}")
                assert result.returncode == 0
                body, status = result.stdout.rsplit("\nHTTP_CODE=", 1)
                assert int(status.strip()) == expected_status
                decoded = json.loads(body)
                if expected_body is not None:
                    assert decoded == expected_body
                elif expected_status == 401:
                    assert decoded["error"]["code"] == "POS_UNAUTHORIZED"
                else:
                    assert decoded["error"]["code"] == "QR_TOKEN_MALFORMED"
            assert cloud_calls == 1
            assert list(root.iterdir()) == []
            print(f"\nMOCK_CLOUD_CALLS={cloud_calls}; STATE_FILES_CREATED=0; no retries")
        finally:
            service.stop()
        assert service.address is None
        print("LISTENER_STOPPED=True")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
