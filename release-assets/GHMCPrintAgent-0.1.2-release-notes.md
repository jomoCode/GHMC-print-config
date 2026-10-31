# GHMC Desktop Print Agent 0.1.2

This release corrects the bundled SumatraPDF executable. The previous package included the SumatraPDF installer renamed as `SumatraPDF.exe`; the agent expects the portable viewer executable for silent PDF submission.

The build now requires SumatraPDF's official portable release filename, checks its product metadata and Authenticode signature, and verifies the staged executable's SHA-256 matches the supplied file.

## Installer

- File: `GHMCPrintAgent-Setup-0.1.2.exe`
- SHA-256: `084B99B511C8DC6074037A8C61952973FDF4CD6295F3AF22DBA813A23C2D6F3A`
- Bundled SumatraPDF: 3.6.1 portable, SHA-256 `719F689B34F47BE8CA105CE8484948474DAFDE0E106BAB599E4A89326070C3D0`
- Build: unsigned installer; Windows may show an unknown publisher warning.

Install this version on the Windows print station. The existing station enrollment and configuration are preserved by the per-user installer.
