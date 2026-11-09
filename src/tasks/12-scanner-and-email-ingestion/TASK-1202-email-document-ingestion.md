# TASK-1202: Inbound email document receiver and scan-to-email consumer

Many office multifunction printers (MFPs) and departmental network scanners do not expose direct network scanning APIs, but instead offer a standard "Scan-to-Email" feature where scanned documents are emailed directly to an assigned inbox. Additionally, organizations frequently receive invoices, agreements, and reports as incoming email attachments.

Implementing an email document ingestion receiver solves both requirements simultaneously: it consumes Scan-to-Email outputs from network scanners and handles incoming documents sent by email.

- Implement email ingestion daemon in `src/ingestion/email/`:
  - `EmailIngestionConfig` in `src/schemas/email_ingestion.py`:
    - `protocol: str = "imap"` (`"imap"` or `"pop3"`)
    - `host: str`, `port: int = 993`, `use_ssl: bool = True`
    - `username: str`, `password_env: str = "CERNODATA_EMAIL_PASSWORD"`
    - `folder: str = "INBOX"`, `poll_interval_seconds: int = 60`
    - `allowed_senders: list[str] = []` (scanner email addresses or authorized sender domains)
    - `post_action: str = "archive"` (`"archive"`, `"mark_read"`, or `"delete"`)
  - `EmailIngestionWorker`:
    - Polls the configured mailbox periodically in a background thread.
    - Inspects MIME messages and extracts document attachments matching supported extensions (`.pdf`, `.png`, `.jpg`, `.jpeg`, `.tiff`).
    - Attaches email metadata (sender, subject, message date, body notes) to document ingestion plan attributes.
    - Saves attachments into `output/inbox/email/` and enqueues them for automated processing.
- Add Web Hub management in `src/pipeline/server/routes_email.py`:
  - `GET /api/email-ingestion/status`: Connection state, last poll time, and unread document count.
  - `POST /api/email-ingestion/poll`: Manually trigger immediate mailbox fetch.
  - Settings card in Web Hub dashboard (`src/visualization/landing.html`) for configuring IMAP credentials and auto-process toggles.

Add unit tests in `src/tests/test_email_ingestion.py` using synthetic MIME messages with PDF attachments and mock IMAP client.
