# Centralized Desktop Printing: Detailed Implementation Plan

**Implementation status (updated 2026-10-27): partial foundation implemented; not production-ready.** GHMC has a station/job migration, station enrollment and agent routes, an admin configuration screen, a shared PDF dispatcher foundation, and an initial Python Windows agent/installer build path. Migration `c2e3f4a5b6d7` was successfully applied to the development database and verified as Alembic head; verify each deployment environment separately. Unsigned installers v0.1.0 and v0.1.1 have been published; v0.1.1 adds Start/Resume behavior and the backend source defaults now point to its release URL and SHA-256. Deployment-specific `PRINT_AGENT_*` settings may override those defaults and must be updated separately. Authenticode signing is not required for download availability. Existing print callers have not been fully migrated, managed job creation is still restricted to printer-config managers, and kitchen integration is outstanding. Do not enable operational assignments yet.

## Progress and developer handoff

Use this section as the working status record. The detailed architecture and acceptance criteria below remain the target design; they do not mean the listed capabilities are complete.

### Implemented foundation

- GHMC backend includes station enrollment/revocation, agent heartbeat and queue inventory, assignment resolution and management, test print jobs, durable print jobs, atomic claim, acknowledgement, recent-job diagnostics, and installer release metadata.
- Migration `c2e3f4a5b6d7_desktop_print_agent.py` adds the station/job schema and claim function. The asyncpg migration execution issue was fixed by splitting multi-command SQL blocks. Development DB upgrade succeeded; current Alembic revision was `c2e3f4a5b6d7`.
- The frontend includes the permission-gated Printer Management screen and `app/lib/printing/printDispatcher.ts`. The helper resolves an assignment, preserves the caller's browser callback when no assignment exists, and submits managed PDF jobs when assigned.
- The `printer-config` repository includes the polling agent, Windows queue discovery, Credential Manager integration through `keyring`, SumatraPDF submission, and an Inno Setup/per-user startup packaging path.

### Outstanding work (next developer sequence)

1. Verify migration head against the intended database before every deployment; do not rely on the development DB result.
2. Reconcile the backend, frontend, and agent API contracts against the actual mounted route prefixes and OpenAPI. Add backend coverage for permission/source authorization, enrollment replay, revocation/station isolation, inventory validation, assignment routing, idempotency, concurrent claims/lease expiry, acknowledgement transitions, and payload/secret redaction.
3. Replace manager-only job creation with purpose-specific authorization and trusted server-side source/scope validation. Do this before enabling normal staff callers. The client must not be authoritative for printer selection or protected document access.
4. Harden the agent for recoverable operation: request/response and payload bounds, timeouts/backoff, structured redacted diagnostics, local in-flight/ambiguous submission journal and restart reconciliation, and explicit retry behavior. Validate the installed command, first-run enrollment, startup, upgrade, revoke, and uninstall on a clean Windows machine.
5. Inventory all frontend print callers and migrate in batches to the shared dispatcher, keeping browser printing for unassigned purposes and explicit errors for configured unavailable destinations. Do not silently fall back.
6. Integrate kitchen through its existing eligibility/claim/ack owner; do not create a competing generic kitchen queue or change kitchen permissions/order lifecycle.
7. Pilot one low-risk purpose on the actual station/printer from Windows, iOS, and Android clients. Verify printer queue visibility, silent PDF output, outage/restart/revocation handling, and duplicate risk after lost acknowledgement.
8. Build the Windows installer with reviewed dependencies, publish it at an approved immutable HTTPS artifact location, configure the GHMC release settings, and verify the admin download metadata. Authenticode signing is optional for installer availability.
9. Enable assignments gradually only after authorization, failure handling, caller coverage, and pilot acceptance pass. Keep the browser path as the documented unassign/disable recovery.

See `README.md` for the release build command and required Windows signing/build environment. Keep this status block and README synchronized as work proceeds.

## 1. Goal and operating model

GHMC users can make print requests from the website on Windows, iOS, Android, or another supported browser. One or more approved Windows PCs run the Python print agent. For the initial rollout, treat one dedicated PC as the shared print station; the architecture permits adding another station later if workload or availability requires it.

GHMC owns users, permissions, purpose/scope routing, job history, and workstation authorization. The Python agent runs quietly on the selected Windows PC, polls GHMC over outbound HTTPS, and submits authorized jobs to printers available to that PC. The GHMC admin management sidebar contains the printer configuration screen. The agent has no admin configuration UI; its installer and enrollment flow only connect a PC to GHMC.

Each installation is separately enrolled and authorized. Downloading or installing the agent alone does not authorize a PC to receive jobs. One installer package can be reused on multiple PCs, while each enrolled PC receives a distinct identity and revocable credential.

## 2. Repository findings and constraints

- `GHMC/printers/routes.py` contains authenticated printer/assignment CRUD and test-print handling. `GHMC/printers/agent_routes.py` contains the added station lifecycle, enrollment, inventory, claim/acknowledgement, job, and release endpoints. Check `GHMC/config/main.py` for their mounted prefixes before changing the agent or frontend paths.
- `GHMC/printers/contracts.py` and `GHMC/printers/models.py` define the current API/model shapes. The migration adds a station-local queue key and station relation alongside existing printer records. The running agent uses a bearer token stored by `keyring`; it does not use a backend service-role credential.
- GHMC follows FastAPI/Pydantic, Supabase/PostgREST for domain routes, SQLAlchemy/Alembic for schema, permission dependencies, and audit logging. The new SQL claim function is called using the service Supabase client. Preserve these conventions and verify grants/RLS in the target deployment.
- `gws-edss/app/components/Screens/PrinterManagementScreen.tsx` implements the admin UI, and `gws-edss/app/lib/printing/printDispatcher.ts` is the shared PDF dispatch foundation. `gws-edss/app/lib/api/endpoint.ts` defines paths. Only migrate callers after job authorization and trusted source validation are in place.
- `gws-edss/docs/centralized-printer-configuration-implementation-plan.md` requires explicit fallback, no silent cross-purpose routing, and idempotent jobs. `gws-edss/docs/kitchen-order-printing-plan.md` owns KitchenStaff-only ticket eligibility and claim/ack lifecycle. Integrate with that flow; do not create a second kitchen queue.
- `printer-config` now contains a Python package, Windows agent CLI, build script, Inno Setup installer, and quiet login launcher. It is not yet a signed/published release. The implementation is an initial slice and still needs lifecycle hardening and real Windows pilot validation.

## 3. End-to-end behavior

1. An authorized administrator opens the printer configuration screen in the GHMC admin management sidebar.
2. The administrator downloads the Windows agent installer from a versioned release link shown by GHMC.
3. The administrator installs the agent on the selected Windows print station. The installer starts the background agent and presents or opens a short enrollment step. Enrollment is authorized by GHMC, is single-use/short-lived, and binds that installation to a named station. The agent stores its resulting credential in Windows-protected storage.
4. The agent reports the installed printer queues it can use. The admin screen displays this station-reported inventory, lets the administrator refresh it, and allows eligible queues to be named and assigned.
5. An authorized admin configures purpose/scope assignments, such as table service area, kitchen, warehouse/raw materials, accounting, HR, or reports.
6. A user requests printing from any client platform. The frontend sends a typed purpose, trusted scope, idempotency key, and supported document payload/reference to GHMC. The frontend never chooses an authoritative printer ID.
7. GHMC validates the user action, purpose and scope, resolves the active assignment, validates the station/printer availability, and creates a durable job for the correct enrolled station. If no assignment exists, the caller uses its current browser/PDF print behavior instead.
8. The agent polls GHMC, atomically claims a leased job for its station, validates the document and printer destination, and submits it through the Windows print adapter.
9. The agent reports `submitted`, a classified `failed` result, or `unknown` if it cannot determine whether submission happened. GHMC exposes job status to authorized users/admins. `submitted` means accepted by the Windows print system; it does not prove paper output.
10. If an assigned printer or station is disabled, missing, offline, or unreachable, GHMC/frontend shows a clear failure. Do not silently use another printer. Offer retry and, if policy permits, a deliberate user-selected browser fallback.

## 4. Scope catalog and routing rules

Inventory all current print callers before finalizing the catalog. Use stable typed purpose and scope identifiers based on trusted business records, not page labels or mutable display names.

Initial scope candidates:

- **Table/order dockets:** route using the selected table's service area/category. Existing UI areas include Cove, Chifa, and Grill; resolve to backend-owned stable IDs/keys.
- **Kitchen tickets:** configure per kitchen routing scope. Retain exact KitchenStaff backend authorization and the existing kitchen ticket state machine.
- **Warehouse/raw materials:** identify distinct document purposes where routing differs (for example, stock receipt or issue documents) only after caller inventory.
- **Accounting/account management:** identify actual accounting/report print actions and retain their separate print permissions.
- **Human resources:** identify HR document families and protect sensitive document access; do not treat an assignment as permission to view/print a document.
- **Reports and remaining receipts:** add per-family or per-section targets only where an operational printer distinction is needed.

Routing rules:

- Resolve the most specific valid purpose + scope assignment first, then any explicitly supported purpose-wide assignment. Define and test precedence before exposing configuration.
- No active assignment means the existing browser/OS print path.
- A more specific disabled/unavailable assignment is an error; do not silently fall through to a broader or different department printer.
- Assignment writes validate that the printer is active, belongs to an enrolled station, and is in the discovered/approved inventory where applicable.
- If multiple stations are later supported, each printer belongs to one station or has an explicit network reachability policy. A job is leased only by the station responsible for its assigned printer.

## 5. Workstream A: GHMC backend

### A1. Data model and migration

Extend the existing printer module and add normalized persistent records for:

- **Print station:** stable ID, display name, active/revoked state, enrollment and last-seen timestamps, agent version, OS/platform metadata, creator/updater, and safe health summary.
- **Station credential:** credential identifier, hash/verification data, scopes, creation/rotation/revocation timestamps. Never store or return the raw long-lived secret.
- **Discovered printer:** station ID, stable local queue identifier, display name, driver/model metadata when available, connection details safe for operators, enabled/last-seen state. Treat discovery data as untrusted input; never expose arbitrary paths/commands to the browser.
- **Printer assignment:** stable target type/key/scope, printer FK, active state, audit actor/timestamps. Prevent duplicate effective assignments and prevent deleting a station/printer in a way that silently misroutes retained jobs.
- **Print job:** UUID, idempotency key, purpose/scope, source entity reference, selected assignment/printer/station, requesting actor, status, timestamps, claim lease/token, attempt count, safe failure code/message, and payload reference or protected short-lived payload.
- **Attempt/history:** append-only lifecycle attempts where needed for investigation, excluding document contents and secrets.

Inspect current Alembic heads, migration conventions, Supabase SQL/RPC grants, and deployed database revision before selecting ancestry. Use an atomic PostgreSQL function/RPC or equivalent transaction/locking mechanism for job claims; a GET-then-update sequence is not safe.

### A2. API contract

Define Pydantic request/response contracts and document them in the existing GHMC OpenAPI schema. Exact endpoint names and schemas should follow existing API conventions during implementation; do not build the agent against an informal or invented route.

Required capabilities:

1. **Station enrollment:** admin creates/revokes enrollment; one-time code expires quickly and can be redeemed once. Enrollment binds the agent to a named station. Return the raw credential once only, then store only a verifier/hash. Provide rotation and immediate revocation.
2. **Station lifecycle:** authorized list/detail/disable/rename and last-seen/version/health reporting. Agent credential can access only its own station.
3. **Printer inventory:** agent submits a bounded list of installed queues and safe metadata; admin reviews/enables supported queues. Agent refresh operation reports new/removed queues. A station cannot create or enable its own routing assignments.
4. **Assignment management:** list/create/update/delete purpose + scope assignment with server validation and audited changes. Report disabled, stale, or unreachable resources clearly.
5. **Job creation:** frontend caller submits purpose/scope, idempotency key, source reference, and the selected safe document payload/reference. Backend rechecks user permissions and document authorization, derives/validates scope from trusted server data where available, resolves the printer, and rejects missing/invalid configured destinations. Do not trust a frontend printer ID.
6. **Atomic claim:** agent claims a bounded batch for its own station. GHMC sets a lease and claim token atomically; concurrent claims cannot receive the same active job. Expired leases become recoverable under an explicit duplicate-risk policy.
7. **Acknowledgement:** agent reports `submitted`, `failed`, or `unknown` idempotently for a job/claim. Validate station, lease/token, state transition, and printer assignment. Never label OS submission as physical print confirmation.
8. **Authorized diagnostics:** admin can inspect jobs, attempts, station health and failure codes. Do not return payload data or credentials in list/detail diagnostics.
9. **Test print:** admin requests a standard safe test document through the selected enrolled station and printer. This is a real end-to-end OS submission test; show status semantics accurately.

### A3. Security and reliability

- Require TLS in production; agent validates the server certificate.
- Use high-entropy credentials, secure hash/verification, Windows-protected local storage, rotation, revocation, least-privilege station scope, and redaction.
- Separate permissions for printer config management, station enrollment, and print-job diagnostics. Keep report print permission separate from screen write access.
- Revalidate user access, source document access, assignment, station, printer state, and scope server-side on every job creation.
- Restrict payload size, content type, and document references. Never accept arbitrary executable instructions, shell commands, printer commands, URLs, or arbitrary network destinations.
- Make job creation idempotent. Use atomic claims, bounded leases/retries, safe failure codes, expiry recovery, and explicit handling for ambiguous acknowledgements.
- Audit assignment, enrollment, revocation, and lifecycle changes without including credentials, customer data, or document contents.
- Restrict job retention and payload lifetime; document cleanup and access policy.

### A4. Backend verification

Cover authorization, one-time enrollment and reuse rejection, credential rotation/revocation, station scoping, invalid/stale printer inventory, invalid scopes, duplicate assignments, idempotent job creation, disabled/unreachable destinations, concurrent claims, lease expiry, acknowledgement idempotency, failure recovery, payload redaction, audit records, and migration behavior. Include PostgreSQL concurrency tests for atomic claim.

## 6. Workstream B: GHMC frontend

### B1. Admin management sidebar screen

Add a permission-gated printer management screen/tab in the existing admin management sidebar, using current navigation, API client, React Query, modal/form, and permission patterns. Inspect actual sidebar and role/permission catalogs before choosing the insertion point.

Screen sections:

- **Agent download and setup:** display current supported Windows installer version, release notes, checksum/signature information, download action, enrollment/setup instructions, and a one-time enrollment code or link created by an authorized admin. Do not display reusable station credentials. Show install/enrollment status.
- **Stations:** list name, active/revoked state, agent version, last seen, inventory refresh time, and health. Provide create enrollment, rotate/revoke, rename, and disable actions with confirmation and audit context.
- **Available printers:** list station-reported queues, display name/model/connection where safe, last discovered time, enabled state, and test status. Provide refresh discovery, enable/disable, rename/label, and test print. Show stale station inventory clearly.
- **Purpose assignments:** map valid target purposes/scopes to enabled printers. Include the table/service area scopes and kitchen routing scopes supported by existing data, then department purposes discovered in caller inventory. Show “Browser print” for unassigned targets. Warn/block invalid or stale assignments.
- **Jobs/health:** show a suitably permissioned recent-job view with purpose, scope, requesting actor, selected printer/station, state, timestamps, and safe error. Avoid showing sensitive payload data. Provide retry only under a defined idempotent policy.

All configuration writes require server connectivity, show loading/error/permission/offline states, and are not placed in offline queues or local browser persistence. Refresh relevant query caches after mutations.

### B2. Installer hosting and download

Host a versioned Windows installer at a stable HTTPS release URL reachable from the admin frontend. Authenticode signing is optional; publish the artifact SHA-256 with its immutable version URL. Prefer the organization’s existing deployment/static artifact hosting if it supports installer size, immutable versioned artifacts, access policy, and cache behavior; otherwise use an existing approved release/artifact store. Do not check installer binaries into the frontend source repository or create a new hosting service without a need.

The frontend download button should point to the latest approved stable version and show version, release date, SHA-256 checksum, and supported Windows versions. Use immutable versioned artifact URLs and a small release manifest or deployment configuration to update the latest link. Only authorized admins see enrollment controls; installer download may be visible according to the organization’s distribution policy. Confirm whether the installer should be public to signed-in staff or restricted to admins.

Signing, release promotion, checksum publication, and rollback are required. The browser is only a distribution surface; the agent still authenticates directly to GHMC after enrollment.

### B3. Shared print dispatcher and migration

Create one shared frontend print dispatcher used by all in-scope print callers. Its input includes typed purpose/scope, source metadata, document representation/reference, and existing browser fallback callback. The backend remains authoritative for assignments and access.

Behavior:

- No assignment: run current browser/PDF behavior on the requesting Windows/iOS/Android device.
- Active managed assignment: create a backend job; show queued and subsequent status where the interaction supports it.
- Configured but inactive/unreachable station/printer: show an actionable error, retry action, and explicit browser fallback only where policy allows. Never silently select another printer.
- Preserve current print layouts, manual reprint behavior, downloads, popup-blocked fallback, checkout completion, and domain permissions.

Inventory and migrate every print entry point, including order/settlement/update receipts, table/order dockets, kitchen tickets, stock-sale receipts, warehouse/raw-materials documents, accounting reports/documents, HR documents, and other report/receipt paths found in the actual frontend. Migrate in batches and record purpose/scope mapping for each caller. The final audit should find no in-scope caller bypassing the dispatcher, except deliberate browser-only targets documented in the catalog.

### B4. Frontend verification

Cover screen permission, station/printer loading and stale states, enrollment flow, install download metadata, printer refresh and test, assignment create/update/delete, invalid destination blocking, exact scope resolution, no-assignment browser fallback, configured failure behavior, retry, and job status display. Add caller tests proving each print surface supplies the intended purpose/scope and retains existing permission checks.

## 7. Workstream C: Python Windows agent

### C1. Runtime structure

Create a small standalone Python package in `printer-config` with clear boundaries:

- configuration and protected credential storage;
- typed GHMC API client with TLS, bounded timeouts, and retry/backoff;
- enrollment exchange flow;
- station health and printer inventory discovery;
- polling and atomic-claim loop;
- payload/type/size validation;
- local submission journal for in-flight/ambiguous jobs;
- Windows print adapter interface and first validated implementation;
- structured, redacted logs and local diagnostics;
- orderly startup/shutdown and update/version reporting.

Keep the agent headless after enrollment. Admin printer management remains in the web frontend. A minimal local setup step may open the browser to a GHMC enrollment page or accept a one-time enrollment code; it must not become a second printer configuration interface.

### C2. Enrollment and installation behavior

- Provide a Windows installer that bundles a pinned Python runtime and required dependencies; target PCs must not need Python preinstalled.
- Installer registers the agent to start automatically in the background. Choose Windows service versus per-user startup only after validating printer visibility and user-session requirements. Some locally installed queues may be user-scoped; a service account may not see them. Pilot with the actual printer setup before selecting the default.
- First-run enrollment obtains a short-lived one-time code/link from an authorized admin workflow. Exchange it for a station-scoped credential, store it using Windows DPAPI/Credential Manager or equivalent OS protection, and erase the one-time code.
- Installation does not embed GHMC service-role secrets, static shared keys, or a universal credential.
- Support clean upgrade, uninstall, credential revoke, and station replacement. Uninstall should offer a documented choice to revoke credentials; it must not silently retain an active station when removed.
- Package with pinned dependencies, version metadata, code signing, checksum, and documented support/recovery process. Avoid automatic self-update in the first release; make updates explicit through signed installer releases and admin visibility.

### C3. Poll, print, and report

- Poll GHMC outbound over HTTPS with bounded interval/jitter, backoff during outages, and no inbound listener.
- Claim only jobs for the enrolled station. Process serially by default to preserve predictable printer ordering.
- Validate signed/authorized job identity, allowed content type and size, destination membership in the station’s enabled inventory, and supported paper/format parameters.
- Use a Windows API or a vetted local PDF print component selected after checking silent printing, printer selection, paper sizing, licensing, maintenance, and security. Do not shell-interpolate payload strings. Do not bundle drivers or accept raw arbitrary printer commands.
- Submit to the configured installed queue. Report OS acceptance as `submitted`; report safe classified printer/format/authorization errors; use `unknown` when outcome cannot be determined.
- On restart, reconcile local in-flight records against GHMC state before resubmitting. Document the unavoidable ambiguity where the OS accepted a job but the agent lost the acknowledgement; do not claim exactly-once physical printing.
- Emit no document contents, credentials, customer contact details, or unsafe local paths in logs. Avoid a local unauthenticated web control endpoint.

### C4. Agent verification

Use a fake GHMC client and fake printer adapter for deterministic development. Verify enrollment, credential protection boundaries, poll backoff, lease handling, payload rejection, allowed destination checks, printer missing/offline states, duplicate/ambiguous submission recovery, redacted logs, restart/shutdown, and Windows integration on a real pilot PC. The agent must never print arbitrary jobs supplied by a local unauthenticated caller.

## 8. Kitchen integration boundary

The existing kitchen plan owns which tickets are eligible, exact KitchenStaff authorization, claim/ack/reprint semantics, and ticket identity. Before implementation, choose and document one integration model:

1. The existing kitchen claim operation creates/links a generic print job atomically and the agent reports local OS submission back to that ticket; or
2. The kitchen ticket remains its authoritative queue and its claim payload is extended to dispatch to the configured agent/printer.

Do not run both as competing queues. Administrators/executives must not gain kitchen auto-print access through printer configuration permissions. A kitchen print failure must remain recoverable without changing order lifecycle or falsely acknowledging paper output.

## 9. Phases and exit criteria

### Phase 0 — Discovery and contract decisions

1. Confirm the dedicated Windows station OS/version, account/session model, service-install rights, uptime/backup expectations, network path, and replacement procedure.
2. Inventory printer make/model, local queue names, drivers already installed, paper sizes, USB/network reachability from the station, and which printer queues can be visible to a Windows service account.
3. Inventory all frontend print callers and derive stable purpose/scope catalog from actual data. Confirm exact assignment precedence and department/kitchen access policy.
4. Choose supported first document type (prefer PDF if existing caller output supports it), Windows print adapter, service/startup model, and what a physical test means.
5. Decide installer visibility, authorized enrollment roles, hosting location, retention, retry, and ambiguous-acknowledgement policy.
6. Inspect current GHMC migration heads/deployment revision and kitchen-plan implementation status.

**Exit:** reviewed architecture, API contract draft, station/printer inventory, purpose catalog, authorization matrix, installer distribution policy, and pilot acceptance checklist.

### Phase 1 — Backend configuration and agent API

1. Add station/printer inventory and secure enrollment/credential lifecycle.
2. Add normalized assignments and purpose/scope validation.
3. Add durable job persistence, idempotency, source authorization, atomic station claim/lease, acknowledgement, health, and diagnostics.
4. Add permission catalog/role grants, audit events, migrations/RPC grants, and retention policy.
5. Integrate kitchen via the selected ownership model.
6. Add focused API, authorization, security, migration, and PostgreSQL concurrency coverage.

**Exit:** a test station can enroll, report inventory, receive a valid test job exactly once per active lease, and report accurate status; unauthorized stations/users are rejected.

### Phase 2 — Python agent and pilot packaging

1. Implement agent core against the finalized backend contracts.
2. Validate local queue discovery and print adapter on the selected real Windows station/printer.
3. Create installer with background startup, protected credential storage, upgrade/uninstall, version, checksum, and operator guide. Code signing may be added separately but is not required for download availability.
4. Exercise outage, restart, revocation, printer unavailable, lease expiry, ambiguous OS submission, and logs.

**Exit:** a clean Windows PC can install, enroll, print a GHMC test job silently to the selected queue, and recover/report failures accurately without separately installing Python.

### Phase 3 — Admin configuration screen and artifact download

1. Add permission-gated admin sidebar screen and typed API hooks.
2. Add download/version/checksum and enrollment workflow.
3. Add station health, discovered printer inventory, refresh/test print, and assignment editor.
4. Add job/failure diagnostics and invalidate queries after writes.
5. Wire release manifest/approved artifact hosting and document signing/release promotion.

**Exit:** an authorized admin can download/install/enroll a station, see its printers, test them, assign system purposes/scopes, and understand offline/stale/failure states from the web app.

### Phase 4 — Shared dispatcher and caller migration

1. Implement shared print dispatcher with browser fallback and managed-job submission.
2. Migrate one low-risk non-sensitive printable and verify routing/status.
3. Migrate receipts and table/order dockets, preserving transactional behavior.
4. Integrate kitchen through the established kitchen ownership model.
5. Migrate warehouse/raw-materials, accounting, HR, reports, and remaining in-scope print callers.
6. Audit for bypasses, scope correctness, permission preservation, and explicit fallback.

**Exit:** all in-scope printables route by configured purpose/scope or intentionally use browser printing when unassigned; unavailable configured destinations are visible errors.

### Phase 5 — Controlled rollout and operations

1. Pilot one station and one low-risk printer; test requests from Windows, iOS, and Android clients.
2. Test multiple sections/departments, concurrent users, station offline/restart, queue unavailable, revoked agent, retries, manual reprint, browser fallback, and permission boundaries.
3. Train operators on station status, printer assignment, retry, fallback, credential revocation, and agent upgrade.
4. Roll out in controlled stages. Keep an immediate disable/unassign route to browser fallback and station revocation.
5. Monitor agent version/last-seen, stale inventory, queue age, failures, retries, and ambiguous states without logging print payloads.

**Exit:** support can diagnose and recover failures, and measured behavior matches routing, authorization, privacy, and status expectations.

## 10. Cross-system acceptance criteria

- One Windows installer can be downloaded from the authorized frontend release link and installed on a selected PC without preinstalled Python.
- Each installed PC has an independent enrollment identity and revocable credential; download does not grant job access.
- The admin management sidebar can see station health and station-reported printers, refresh inventory, run a test print, and configure purpose/scope assignments.
- Browser requests from Windows, iOS, and Android are routed by server-validated assignment to the intended printer through the enrolled Windows agent.
- Every in-scope printable uses the shared dispatcher or has an explicitly documented browser-only reason.
- Unassigned print purposes use current browser/PDF printing. Configured but unavailable printers show an actionable error and never silently route elsewhere.
- Concurrent claims, retries, lease recovery, idempotency, revocation, and permission checks are enforced server-side.
- Job status never claims physical output without printer feedback. Logs and diagnostics exclude secrets and document/customer payloads.
- Kitchen ticket eligibility, exact KitchenStaff-only authorization, order lifecycle, and reprint controls remain intact.
- Installer release, signature/checksum, versioning, upgrade/uninstall, station replacement, and operational rollback are documented.

## 11. Out of scope for first release

- Separate native agent builds for iOS and Android. Mobile devices use the GHMC website; only the shared print station runs the agent.
- Printer driver installation or OS printer configuration changes.
- Browser-to-agent local network connections, inbound workstation listeners, or backend-to-LAN printing independent of the station.
- Arbitrary raw printer command execution, arbitrary URLs, or executable job payloads.
- Claiming paper was physically printed without printer hardware feedback.
- Silent rerouting to another area or printer when the configured destination fails.
