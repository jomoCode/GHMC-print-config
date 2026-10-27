# GHMC Desktop Print Agent

This repository contains the GHMC Windows print station agent, packaging path, and implementation handoff. The project is a partial implementation and is not ready for production-wide automatic printing.

## Progress snapshot (2026-10-25)

- **Database:** migration `c2e3f4a5b6d7` was applied successfully to the development database; Alembic reported it as `head`. It creates station, job, and attempt tables, extends printer records, installs the atomic claim function, and grants the required service-role access. Verify the revision independently in every target environment before deploying code there.
- **GHMC backend:** source includes one-time station enrollment, token-based agent lifecycle, station inventory reporting, printer assignment and resolution, test jobs, job creation, claim, acknowledgement, and release metadata routes. Review and test the current code and authorization boundaries before production rollout.
- **Web frontend:** the permission-gated Printer Management screen supports enrollment codes, station/printer inventory, refresh/revoke, test print, assignments, and recent jobs. Report actions use `report/report` and require `print-reports`; saved table-order dockets and stock-sale receipts use a source order where available; staff profile/directory printing requires staff-management read access; HR printing requires HR management access; department-request printing validates request visibility. Unassigned purposes retain browser printing. Kitchen tickets still use a separate KitchenStaff workflow and are not routed through the generic agent job queue.
- **Agent:** `src/ghmc_print_agent` is a Python polling implementation. It discovers Windows queues through PowerShell, stores its station token with `keyring`, and submits PDFs with SumatraPDF. It is an initial slice; see the gaps below before calling it production-ready.
- **Installer:** `build_windows.ps1` and `packaging/installer.iss` define a per-user Windows installer and login startup. Unsigned installer v0.1.1 is published at `https://github.com/jomoCode/GHMC-print-config/releases/download/v0.1.1/GHMCPrintAgent-Setup-0.1.1.exe`. The backend source defaults point to its version, URL, and SHA-256; deployment-specific `PRINT_AGENT_*` variables can override them. Authenticode signing is optional for download availability.
- **v0.1.1 checksum:** `507090959656084391D05502C29EF63F2794B1DEEAC7A547FAA3A63A4CFD92EA`. The release adds a Start or Resume shortcut and repeat-launch enrollment handling.
- **Rollout boundary:** report job creation is authorized by `print-reports`; table dockets require order view permission or order-creation permission for the caller's own order. Other ordinary print-job creation is still restricted to printer-configuration managers. Configuration changes remain administrator-only. Each remaining purpose must be authorized against its caller's existing permission and validated source document on the server before its callers are migrated; kitchen must retain its existing queue ownership.

## Developer handoff: next steps

Do these in order; update this list as each item is completed.

1. **Confirm environment state.** Run `python -m alembic current` with the GHMC environment configuration for the database being deployed. Confirm `c2e3f4a5b6d7` before deploying routes that use the new schema. Never infer production migration state from the development database.
2. **Close backend contract and security gaps.** Verify OpenAPI paths and frontend/agent request shapes against the mounted route prefixes. Add focused coverage for enrollment single-use/replay, token revocation and station scoping, permission checks, queue inventory validation, assignment resolution, idempotent job creation, claim/lease concurrency, acknowledgement transitions, and payload redaction. Fix any discrepancies before enabling more callers. The job-create route currently requires `manage-printer-config`; separate dispatch permission from configuration permission, and enforce caller-specific authorization plus trusted source/document/scope validation before ordinary staff can submit jobs. Do not treat a client-supplied PDF or target scope as proof of access.
3. **Harden the agent lifecycle.** Validate the packaged invocation end to end, including API base path, first enrollment, login startup, credential removal, revoked credentials, and upgrade/uninstall. Add bounded response/payload sizes, explicit HTTP timeouts and retry/backoff behavior, resilient handling of malformed API responses, redacted file-based diagnostics, and a local in-flight/ambiguous-job recovery policy. Preserve the documented fact that OS acceptance is not physical-print confirmation.
4. **Integrate the shared dispatcher safely.** Inventory every frontend print entry point and migrate in small batches only after step 2. Keep current browser printing when no assignment exists. A configured but unavailable destination must surface an error; it must not silently fall back. Keep kitchen ticket eligibility and claim/ack ownership in the existing kitchen flow; do not create a competing kitchen queue.
5. **Pilot on the actual Windows setup.** Confirm printer queue visibility for the signed-in account, document size/paper behavior, silent PDF submission, duplicate risk after a lost acknowledgement, station restart/offline behavior, and the operational account's uptime. Test requests initiated from Windows, iOS, and Android against the same enrolled station.
6. **Build and release the installer.** Use the requirements below, review/sign all bundled binaries, build the installer, calculate its SHA-256, upload the immutable version to the approved HTTPS artifact host, and configure `PRINT_AGENT_DOWNLOAD_URL`, `PRINT_AGENT_VERSION`, and `PRINT_AGENT_SHA256` in GHMC. Confirm the authorized admin screen displays the correct release metadata and download link.
7. **Enable assignments only after acceptance.** Start with one low-risk purpose/printer, verify authorization and failure behavior, and then expand. Keep a documented disable/unassign path and operational owner for station updates and incidents.

The GHMC backend defaults to the published v0.1.1 installer URL, version, and SHA-256. Railway `PRINT_AGENT_*` variables can override these values. The endpoint requires HTTPS and a 64-character SHA-256, but does not require an Authenticode signature; Windows may still show a publisher warning for an unsigned installer.

## Known implementation gaps

- Report management, shared report-style table actions, saved table-order dockets, stock-sale receipts, staff profile/directory printouts, HR documents, and department-request printouts are migrated with purpose-specific checks. Table-docket scope is derived by the backend. Unassigned purposes preserve browser printing; unavailable configured destinations surface errors.
- Kitchen auto-print is not integrated with managed assignments. It has a separate KitchenStaff-only persistence/claim plan and must be completed without bypassing that workflow. Configuration writes remain administrator-only.
- Kitchen integration has not been completed through the kitchen queue's existing ownership model.
- The frontend installer release link is available when the backend release URL, version, and SHA-256 are valid.
- The agent is an early implementation, not a supported service deployment. The installer uses a signed-in user's login startup because printer queues and Credential Manager may be user-scoped; validate that model with the pilot account and printer.
- Validate retries, lease expiry, ambiguous submissions, station replacement, retention/cleanup, and security behavior. The agent currently has no durable local submission journal, so a crash around OS submission/acknowledgement needs explicit recovery work.

## Build requirements

Build on a supported 64-bit Windows workstation with Python 3.12, Inno Setup 6, and a reviewed Authenticode-signed SumatraPDF executable. For a local unsigned build, run:

```powershell
./build_windows.ps1 -SumatraPdfPath C:\approved\SumatraPDF.exe -Version 0.1.1 -Unsigned
```

Unsigned builds can be published as the GHMC release. Windows may display an unknown publisher warning. To create a signed build instead, install Windows SDK `signtool.exe` and the approved code-signing certificate, then run:

```powershell
./build_windows.ps1 -SumatraPdfPath C:\approved\SumatraPDF.exe -Version 0.1.1
```

Set `GHMC_SIGNING_CERT_THUMBPRINT` to the release certificate thumbprint. The script stages the agent and SumatraPDF, builds the installer, signs the executable and installer, and prints the installer SHA-256. The resulting installer still needs a release upload and deployment settings update before the admin screen can offer a working download.

The installer runs under the signed-in Windows user so that it can see that user's installed printer queues and Credential Manager. Enrollment defaults to `https://ghmc-production.up.railway.app/api/v1`, based on GHMC's `BACKEND_API_URL`. To enroll against another backend, supply `--api-base https://your-backend.example` (the agent adds `/api/v1` when it is absent), then enter the short-lived code created in the admin screen. After enrollment, it starts the agent quietly and configures it to start at that user's next logon. The Start menu includes **Start or Resume GHMC Print Agent** for manual recovery; the enrollment launcher also resumes an existing local enrollment without asking for another code. Repeated launches are safe and do not create competing agent processes. Use a dedicated print-station account and validate its session, queue visibility, and uptime during the pilot.

The Windows agent and installer use the GHMC app icon from `assets/ghmc.ico`, generated from the app icon at `assets/icon.png`.

## Current integration boundary

This is not yet a production-wide managed-print rollout. Report printing and saved table-order dockets are migrated callers. Reports use the `report/report` assignment and require `print-reports`; dockets provide a source order ID and the server checks order access and derives service-area scope from its table booking. Both preserve browser printing when unassigned and surface configured printer/station errors. Payment receipts, kitchen tickets, and other print actions have not yet been migrated. Ordinary staff can use these authorized print paths while only administrators may change printer configuration. Each remaining purpose requires purpose-specific server authorization and trusted source/document/scope validation. Kitchen tickets must be integrated through their existing eligibility and claim/acknowledgement owner, without a competing queue. Pilot and security verification remain outstanding.

`submitted` means the Windows print submission utility accepted the request. It does not verify that paper physically printed. A crash after local submission but before backend acknowledgement can still cause a duplicate when the lease expires.
