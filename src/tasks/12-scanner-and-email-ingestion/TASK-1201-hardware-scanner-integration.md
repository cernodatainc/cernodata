# TASK-1201: Direct hardware scanner integration and ingestion

Processing physical documents currently requires users to operate separate scanning software, save files to disk, and then manually import them into `cernodata`. Integrating hardware scanning directly enables zero-friction, one-touch ingestion from flatbeds and automatic document feeders (ADF).

- Implement scanner discovery and acquisition in `src/ingestion/scanner/`:
  - `ScannerDevice` dataclass in `src/schemas/scanner.py`: `scanner_id: str`, `name: str`, `protocol: str` (`"escl"`, `"sane"`, `"wia"`), `ip_address: Optional[str]`, `capabilities: dict[str, Any]` (supported resolutions, ADF duplex support, color modes).
  - `ScannerClient` base interface with concrete protocol implementations:
    - `EsclScannerClient`: Driverless network scanning over HTTP/eSCL (Apple AirScan / Mopria protocol used by modern HP, Canon, Brother, and Epson scanners). Discovers devices via mDNS.
    - `NativeScannerClient`: Local driver adapter using SANE on Linux/macOS and WIA/TWAIN on Windows.
  - `ScanJobOptions`: `resolution_dpi: int = 300`, `color_mode: str = "color"`, `source: str = "flatbed"` (`"flatbed"` or `"adf"`), `duplex: bool = False`.
  - Assemble scanned image pages into an output PDF in `output/scans/` and pipe directly into `run_pipeline` or planner execution.
- Add REST endpoints in `src/pipeline/server/routes_scanner.py`:
  - `GET /api/scanners`: List discovered network and local scanning devices.
  - `POST /api/scanners/scan`: Trigger scan job with selected device and options, returning document ID and auto-triggering pipeline parsing.
- Add "Scan Document" modal dialog to the Web Hub (`src/visualization/landing.html`) allowing users to pick scanner, preview scan, and click "Scan & Process".

Add unit tests in `src/tests/test_scanner_ingestion.py` verifying mock eSCL scanner communication, PDF assembly, and ingestion queueing.
