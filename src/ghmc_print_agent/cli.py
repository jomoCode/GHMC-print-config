from __future__ import annotations

import argparse
import base64
import json
import logging
import os
import platform
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import keyring

from ghmc_print_agent import __version__

SERVICE_NAME = "GHMC Desktop Print Agent"
CONFIG_DIR = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local")) / "GHMC" / "PrintAgent"
CONFIG_PATH = CONFIG_DIR / "config.json"
TOKEN_KEY = "agent-token"
DEFAULT_API_BASE_URL = "https://ghmc-production.up.railway.app/api/v1"
LOG = logging.getLogger("ghmc-print-agent")


def request_json(base_url: str, path: str, *, token: str | None = None, body: Any = None) -> Any:
    data = json.dumps(body).encode("utf-8") if body is not None else None
    headers = {"Accept": "application/json"}
    if data is not None:
        headers["Content-Type"] = "application/json"
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(
        f"{base_url.rstrip('/')}{path}", data=data, headers=headers
    )
    with urllib.request.urlopen(request, timeout=20) as response:
        return json.loads(response.read().decode("utf-8"))


def discover_printers() -> list[dict[str, str]]:
    script = (
        "Get-Printer | Select-Object Name,DriverName,PortName "
        "| ConvertTo-Json -Compress"
    )
    result = subprocess.run(
        ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", script],
        check=True,
        capture_output=True,
        text=True,
        timeout=30,
    )
    rows = json.loads(result.stdout or "[]")
    if isinstance(rows, dict):
        rows = [rows]
    printers = []
    for row in rows:
        name = str(row.get("Name", "")).strip()
        if not name:
            continue
        printers.append(
            {
                "queue_key": name,
                "name": name[:150],
                "model": str(row.get("DriverName", ""))[:150] or None,
            }
        )
    return printers


def enroll(base_url: str, code: str, sumatra: Path | None) -> None:
    response = request_json(
        base_url,
        "/print-agent/enroll",
        body={"enrollment_code": code.strip()},
    )
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(
        json.dumps(
            {
                "api_base_url": base_url.rstrip("/"),
                "sumatra_path": str(sumatra) if sumatra else None,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    keyring.set_password(SERVICE_NAME, TOKEN_KEY, response["agent_token"])
    print(f"Enrolled print station: {response['station']['name']}")
    if getattr(sys, "frozen", False):
        launcher = Path(sys.executable).resolve().parent / "start_agent.vbs"
        if launcher.is_file():
            subprocess.Popen(
                ["wscript.exe", str(launcher)],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=0x00000008 | 0x08000000,
                close_fds=True,
            )


def print_pdf(job: dict[str, Any], sumatra: Path) -> None:
    if job.get("document_type") != "application/pdf":
        raise ValueError("Unsupported document type")
    payload = base64.b64decode(job["payload_base64"], validate=True)
    if not payload.startswith(b"%PDF-"):
        raise ValueError("The print job payload is not a PDF")
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as handle:
        handle.write(payload)
        pdf_path = Path(handle.name)
    try:
        printer_name = job.get("printer", {}).get("queue_key") or job.get("queue_key")
        if not printer_name:
            raise ValueError("Print job does not specify an installed queue")
        installed = {printer["queue_key"] for printer in discover_printers()}
        if printer_name not in installed:
            raise OSError("Assigned Windows printer queue is not installed")
        subprocess.run(
            [str(sumatra), "-silent", "-print-to", str(printer_name), str(pdf_path)],
            check=True,
            capture_output=True,
            timeout=120,
        )
    finally:
        pdf_path.unlink(missing_ok=True)


def run_agent(base_url: str, sumatra: Path) -> None:
    token = keyring.get_password(SERVICE_NAME, TOKEN_KEY)
    if not token:
        raise RuntimeError("Agent is not enrolled; run the enroll command first")
    last_inventory = 0.0
    while True:
        try:
            heartbeat = request_json(
                base_url,
                "/print-agent/heartbeat",
                token=token,
                body={"agent_version": __version__, "platform": platform.platform()},
            )
            if heartbeat.get("refresh_printers") or time.monotonic() - last_inventory > 300:
                request_json(
                    base_url,
                    "/print-agent/printers/discovered",
                    token=token,
                    body={"printers": discover_printers()},
                )
                last_inventory = time.monotonic()
            jobs = request_json(base_url, "/print-agent/jobs/claim", token=token, body={}).get("jobs", [])
            for job in jobs:
                claim = job.get("claim_token")
                try:
                    print_pdf(job, sumatra)
                    outcome = {"status": "submitted"}
                except (OSError, ValueError, subprocess.SubprocessError) as error:
                    LOG.error("Print job %s failed: %s", job.get("id"), type(error).__name__)
                    outcome = {"status": "failed", "failure_code": "local_submission_failed", "failure_message": "The local print queue could not accept this document."}
                request_json(
                    base_url,
                    f"/print-agent/jobs/{job['id']}/acknowledge",
                    token=token,
                    body={"claim_token": claim, **outcome},
                )
            time.sleep(3 if jobs else 8)
        except (OSError, urllib.error.URLError, TimeoutError, ValueError) as error:
            if isinstance(error, urllib.error.HTTPError) and error.code in {401, 403}:
                LOG.error("Agent credential is rejected or revoked; stopping the print agent")
                raise SystemExit(2) from error
            LOG.warning("Print service unavailable; retrying (%s)", type(error).__name__)
            time.sleep(15)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    parser = argparse.ArgumentParser(prog="ghmc-print-agent")
    parser.add_argument("--api-base", help="GHMC API base URL including API version prefix")
    parser.add_argument("--enroll", action="store_true", help="Enroll this print station")
    parser.add_argument("--remove-local-credential", action="store_true", help="Remove this user's local enrollment credential")
    parser.add_argument("--sumatra", type=Path, help="Path to the approved SumatraPDF executable")
    args = parser.parse_args()
    if args.remove_local_credential:
        try:
            keyring.delete_password(SERVICE_NAME, TOKEN_KEY)
        except keyring.errors.PasswordDeleteError:
            pass
        CONFIG_PATH.unlink(missing_ok=True)
        return
    base_url = args.api_base
    if args.enroll:
        if not base_url:
            base_url = DEFAULT_API_BASE_URL
        base_url = base_url.rstrip("/")
        if not urlparse(base_url).path.rstrip("/").endswith("/api/v1"):
            base_url = f"{base_url}/api/v1"
        parsed_base = urlparse(base_url)
        local_development = parsed_base.hostname in {"localhost", "127.0.0.1", "::1"}
        if parsed_base.scheme != "https" and not local_development:
            parser.error("Use an HTTPS GHMC API URL (localhost is allowed for development)")
        if not parsed_base.netloc or parsed_base.username or parsed_base.password:
            parser.error("Enter a valid GHMC API base URL without embedded credentials")
        code = input("One-time GHMC enrollment code: ")
        enroll(base_url, code, args.sumatra)
        return
    if not base_url and CONFIG_PATH.exists():
        base_url = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))["api_base_url"]
    if not base_url:
        parser.error("--api-base is required until the agent is enrolled")
    sumatra = args.sumatra
    if not sumatra and CONFIG_PATH.exists():
        configured_sumatra = json.loads(CONFIG_PATH.read_text(encoding="utf-8")).get("sumatra_path")
        sumatra = Path(configured_sumatra) if configured_sumatra else None
    if not sumatra or not sumatra.is_file():
        parser.error("--sumatra must point to the approved SumatraPDF executable")
    run_agent(base_url, sumatra)


if __name__ == "__main__":
    main()
