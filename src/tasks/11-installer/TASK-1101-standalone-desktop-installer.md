# TASK-1101: Standalone desktop installer and self-contained runtime packager

Setting up `cernodata` currently requires a complete developer environment: Python 3.10+, virtual environment management, pip dependency installation, PyTorch, OCR binaries, and command-line execution (`python main.py`). This creates a steep barrier for non-technical users, document analysts, legal teams, and enterprise operators who need a ready-to-use desktop tool.

Implement a self-contained desktop installer that delivers `cernodata` as an installable, click-to-run desktop application without requiring manual Python or terminal setup.

- Bundled runtime packaging:
  - Package the Python backend, dependencies, OCR engine binaries, and pre-compiled Vite frontend into an isolated executable using PyInstaller or PyOxidizer.
  - Provide a single entrypoint script (`src/desktop/launcher.py`) that manages the local HTTP server lifecycle, chooses an open port, and opens the default browser to the web hub.
- Native installers:
  - Windows: Inno Setup installer script generating a setup executable (`cernodata-setup.exe`), creating Start Menu shortcuts, desktop icons, uninstaller registry entries, and optional Explorer right-click context menu ("Parse with cernodata").
  - macOS: Application bundle (`cernodata.app`) packaged into a DMG with drag-to-Applications layout.
  - Linux: Standalone AppImage and `.deb` distribution package with desktop menu entry.
- Background tray process:
  - Implement a lightweight system tray supervisor displaying application status with actions: "Open Hub", "Open Viewer", "Show Logs", and "Shut Down".
  - Prevent terminal window popups on desktop execution.
- Build automation:
  - Add build configuration script (`tools/build_installer.py`) to automate compiling frontend assets, freezing Python binaries, and packaging installer artifacts.

Add verification tests in `src/tests/test_desktop_launcher.py` checking clean startup, port discovery, and graceful shutdown handling.
