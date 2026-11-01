/**
 * src/visualization/landing/discovery.js
 *
 * Workspace file discovery and document path registration client runtime.
 * Discovers new files by opening the system native file explorer window and
 * registering the document paths with the backend without uploading file contents.
 */

/** Triggers opening the system native file explorer window to make document paths known to backend. */
async function triggerAddFileDiscovery() {
    try {
        const resp = await fetch('/api/open_file_dialog', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({}),
        });

        if (resp.ok) {
            const data = await resp.json();
            if (data.cancelled) {
                return;
            }
            if (data.success && data.paths && data.paths.length > 0) {
                const targetDoc = data.active_file || data.paths[0];
                if (typeof selectExplorerDoc === 'function') {
                    selectExplorerDoc(targetDoc);
                }
                if (typeof loadFileRunMappings === 'function') {
                    await loadFileRunMappings();
                }
                return;
            }
        }
    } catch (e) {
        console.log('[WARN] Native file explorer dialog unavailable:', e);
    }

    // Fallback if dialog cannot be opened (e.g. headless/browser sandbox): prompt for path
    const fallbackInput = document.getElementById('explorerFileInput');
    if (fallbackInput) {
        fallbackInput.value = '';
        fallbackInput.click();
    } else {
        const enteredPath = window.prompt('Enter path to PDF document:');
        if (enteredPath && enteredPath.trim()) {
            await addDocumentByPath(enteredPath.trim());
        }
    }
}

/** Handles file input fallback when native OS dialog cannot be invoked directly. */
async function handleExplorerFileInputChange(event) {
    const files = event.target ? event.target.files : null;
    if (!files || files.length === 0) return;

    for (let i = 0; i < files.length; i++) {
        const file = files[i];
        if (!file.name.toLowerCase().endsWith('.pdf')) {
            console.log('[WARN] Only PDF documents are supported for discovery:', file.name);
            continue;
        }
        await addDocumentByPath(file.name);
    }
}

/** Makes a document path known to the backend and refreshes explorer mappings. */
async function addDocumentByPath(filePath) {
    if (!filePath) return null;
    try {
        const resp = await fetch('/api/documents', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ file_path: filePath }),
        });
        if (!resp.ok) return null;
        const data = await resp.json();
        if (data.success) {
            const targetDoc = data.active_file || data.file_path || (data.paths ? data.paths[0] : filePath);
            if (typeof selectExplorerDoc === 'function') {
                selectExplorerDoc(targetDoc);
            }
            if (typeof loadFileRunMappings === 'function') {
                await loadFileRunMappings();
            }
        }
        return data;
    } catch (e) {
        console.log('[WARN] Error registering document path:', e);
        return null;
    }
}
