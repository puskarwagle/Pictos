/**
 * @file main.js
 * @description The main entry point for the NarrateImage application.
 * Initializes the app, sets up event listeners, and orchestrates module interaction.
 */

import { state } from './state.js?v=1.0.2';
import * as api from './api.js?v=1.0.2';
import * as ui from './ui.js?v=1.0.2';
import { queueDownload } from './queue.js?v=1.0.2';

const { elements } = ui;

document.addEventListener('DOMContentLoaded', () => {
    setupEventListeners();
    initDarkMode();
    initZenMode();
    loadScripts();
});

function setupEventListeners() {
    // Back button
    if (elements.backBtn) {
        elements.backBtn.addEventListener('click', () => {
            if (state.isZenMode) ui.exitZenMode();
            state.selectedScript = null;
            localStorage.removeItem('lastChosenScript');
            ui.showScriptsList();
        });
    }

    // Dark Mode Toggle
    if (elements.darkModeToggle) {
        elements.darkModeToggle.addEventListener('change', (e) => {
            document.body.classList.toggle('dark-mode', e.target.checked);
            localStorage.setItem('darkMode', e.target.checked);
        });
    }

    // Translate Toggle
    if (elements.translateToggle) {
        elements.translateToggle.addEventListener('change', (e) => {
            localStorage.setItem('translateToggle', e.target.checked);
        });
    }

    // Zen Mode Toggle
    if (elements.zenModeToggle) {
        elements.zenModeToggle.addEventListener('change', (e) => {
            if (e.target.checked) {
                if (!state.selectedScript) {
                    e.target.checked = false;
                    ui.showToast('Select a script first', 'warning');
                    return;
                }
                ui.enterZenMode();
            } else {
                ui.exitZenMode();
            }
        });
    }

    // Edit Mode Toggle
    if (elements.editModeToggle) {
        elements.editModeToggle.addEventListener('change', (e) => {
            state.isEditMode = e.target.checked;
            document.body.classList.toggle('edit-mode', state.isEditMode);
            if (elements.scriptEditor) elements.scriptEditor.readOnly = !state.isEditMode;
            
            if (elements.editorContainer) elements.editorContainer.style.display = state.isEditMode ? 'flex' : 'none';
            if (elements.segmentsContainer) elements.segmentsContainer.style.display = state.isEditMode ? 'none' : 'flex';
            
            if (!state.isEditMode) {
                if (!state.isAiProcessed) {
                    const editorVal = elements.scriptEditor ? elements.scriptEditor.value : '';
                    state.processedSegments = ui.createDefaultSegments(editorVal);
                }
                ui.renderSegments(queueDownload);
            }
        });
    }

    // Script Editor input
    if (elements.scriptEditor) {
        elements.scriptEditor.addEventListener('input', () => {
            if (state.isAiProcessed) {
                state.isAiProcessed = false;
                ui.setStatus('Script modified. AI keywords are now out of sync. Click Process to update.');
            }
        });
    }

    // Process with AI
    if (elements.processBtn) {
        elements.processBtn.addEventListener('click', async () => {
            if (!state.selectedScript) return;
            const scriptText = elements.scriptEditor ? elements.scriptEditor.value.trim() : '';
            if (!scriptText) return alert('Editor is empty!');

            try {
                ui.toggleButtons(true);
                elements.processBtn.classList.add('loading');
                ui.setStatus('Extracting keywords with AI (DeepSeek)...', true);
                if (elements.segmentsContainer) elements.segmentsContainer.innerHTML = '';

                const segments = await api.processScript({ 
                    filename: state.selectedScript, 
                    script_text: scriptText,
                    source: ui.getPrimarySource() 
                });
                
                state.processedSegments = segments;
                state.isAiProcessed = true;
                
                state.isEditMode = false;
                if (elements.editModeToggle) elements.editModeToggle.checked = false;
                document.body.classList.remove('edit-mode');
                if (elements.scriptEditor) elements.scriptEditor.readOnly = true;
                if (elements.editorContainer) elements.editorContainer.style.display = 'none';
                if (elements.segmentsContainer) elements.segmentsContainer.style.display = 'flex';
                
                ui.renderSegments(queueDownload);
                ui.setStatus('Keywords extracted. Click tags to find YouTube clips.');
            } catch (err) {
                ui.setStatus('Error: ' + err.message);
            } finally {
                ui.toggleButtons(false);
                if (elements.processBtn) elements.processBtn.classList.remove('loading');
            }
        });
    }

    // Delete Selected Clips
    if (elements.deleteSelectedBtn) {
        elements.deleteSelectedBtn.onclick = async () => {
            if (state.selectedClipIds.size === 0) return;
            if (!confirm(`Are you sure you want to delete ${state.selectedClipIds.size} clips?`)) return;

            const idsToDelete = Array.from(state.selectedClipIds);
            try {
                ui.setStatus(`Deleting ${idsToDelete.length} clips...`, true);
                const data = await api.deleteClips(idsToDelete);

                if (state.activeSegmentIndex !== -1) {
                    state.processedSegments[state.activeSegmentIndex].clips = 
                        state.processedSegments[state.activeSegmentIndex].clips.filter(
                            clip => !data.deleted.includes(clip.id)
                        );
                    ui.showClips(state.activeSegmentIndex);
                    ui.renderSegments(queueDownload);
                }
                state.selectedClipIds.clear();
                ui.updateDeleteButtonVisibility();
                ui.setStatus(`Deleted ${data.deleted.length} clips.`, false, true);
            } catch (err) {
                ui.setStatus('Error deleting clips: ' + err.message);
            }
        };
    }

    // Pin Selected Clips
    if (elements.pinSelectedBtn) {
        elements.pinSelectedBtn.onclick = async () => {
            await ui.pinSelectedClips();
        };
    }

    // Video Modal close
    if (elements.closeModal) {
        elements.closeModal.onclick = () => {
            if (elements.videoModal) elements.videoModal.style.display = 'none';
            if (elements.videoIframe) elements.videoIframe.src = '';
        };
    }
    window.onclick = (event) => {
        if (event.target == elements.videoModal) {
            if (elements.videoModal) elements.videoModal.style.display = 'none';
            if (elements.videoIframe) elements.videoIframe.src = '';
        }
    };

    // Add Segment
    if (elements.addSegmentBtn) {
        elements.addSegmentBtn.addEventListener('click', () => {
            ui.addManualSegment(queueDownload);
        });
    }

    setupResizer();
}

function initDarkMode() {
    const isDarkMode = localStorage.getItem('darkMode') !== 'false';
    if (elements.darkModeToggle) {
        elements.darkModeToggle.checked = isDarkMode;
    }
    if (isDarkMode) document.body.classList.add('dark-mode');

    const shouldTranslate = localStorage.getItem('translateToggle') === 'true';
    if (elements.translateToggle) {
        elements.translateToggle.checked = shouldTranslate;
    }
}

function initZenMode() {
    const isZen = localStorage.getItem('zenMode') === 'true';
    if (isZen && elements.zenModeToggle) {
        if (!state.selectedScript) {
            elements.zenModeToggle.checked = false;
            localStorage.setItem('zenMode', 'false');
        } else {
            elements.zenModeToggle.checked = true;
            ui.enterZenMode();
        }
    }
}

async function loadScripts() {
    try {
        const scripts = await api.getScripts();
        if (elements.scriptsList) elements.scriptsList.innerHTML = '';
        
        if (scripts.length === 0) {
            if (elements.scriptsList) elements.scriptsList.innerHTML = '<p>No scripts found in video-scripts/ folder.</p>';
            return;
        }

        const lastScript = localStorage.getItem('lastChosenScript');
        scripts.forEach(script => {
            const tile = document.createElement('div');
            tile.className = 'script-tile';
            tile.textContent = script;
            tile.onclick = () => selectScript(script);
            if (elements.scriptsList) elements.scriptsList.appendChild(tile);
            if (script === lastScript) selectScript(script);
        });
    } catch (err) {
        ui.setStatus('Error loading scripts: ' + err.message);
    }
}

async function selectScript(filename) {
    state.selectedScript = filename;
    localStorage.setItem('lastChosenScript', filename);
    if (elements.scriptsListContainer) elements.scriptsListContainer.style.display = 'none';
    if (elements.scriptActions) elements.scriptActions.style.display = 'block';
    if (elements.activeScriptHeader) elements.activeScriptHeader.style.display = 'flex';
    if (elements.selectedScriptName) elements.selectedScriptName.textContent = filename;
    
    if (elements.editorContainer) elements.editorContainer.style.display = state.isEditMode ? 'flex' : 'none';
    if (elements.segmentsContainer) elements.segmentsContainer.style.display = state.isEditMode ? 'none' : 'flex';
    
    try {
        ui.setStatus(`Loading script: ${filename}...`, true);
        ui.toggleButtons(true);
        
        const data = await api.getScriptContent(filename);
        if (elements.scriptEditor) {
            elements.scriptEditor.value = data.content;
            elements.scriptEditor.readOnly = !state.isEditMode;
        }
        if (elements.segmentsContainer) elements.segmentsContainer.innerHTML = '';
        
        const cachedResponse = await api.getScriptCache(filename);
        if (cachedResponse) {
            state.processedSegments = cachedResponse;
            state.isAiProcessed = true;
            ui.renderSegments(queueDownload);
            ui.setStatus(`Loaded: ${filename}. Cached AI response found.`, false, true);
        } else {
            state.isAiProcessed = false;
            const editorVal = elements.scriptEditor ? elements.scriptEditor.value : '';
            state.processedSegments = ui.createDefaultSegments(editorVal);
            ui.renderSegments(queueDownload);
            ui.setStatus('No cached response found. Displaying raw script segments. Click Process to start.');
        }

    } catch (err) {
        ui.setStatus('Error loading script: ' + err.message);
    } finally {
        ui.toggleButtons(false);
    }
}

function setupResizer() {
    const { resizer, rightSidebar } = elements;
    let isResizing = false;
    let startX, startWidth;

    if (resizer && rightSidebar) {
        resizer.addEventListener('mousedown', (e) => {
            isResizing = true;
            startX = e.clientX;
            startWidth = parseInt(document.defaultView.getComputedStyle(rightSidebar).width, 10);
            
            document.body.style.cursor = 'col-resize';
            document.body.style.userSelect = 'none';
            resizer.classList.add('active');
        });

        document.addEventListener('mousemove', (e) => {
            if (!isResizing) return;
            let newWidth = startWidth + (startX - e.clientX);
            const maxWidth = window.innerWidth * 0.7;
            const minWidth = 200;
            
            if (newWidth > maxWidth) newWidth = maxWidth;
            if (newWidth < minWidth) newWidth = minWidth;

            rightSidebar.style.width = `${newWidth}px`;
            localStorage.setItem('rightSidebarWidth', newWidth);
        });

        document.addEventListener('mouseup', () => {
            if (isResizing) {
                isResizing = false;
                document.body.style.cursor = '';
                document.body.style.userSelect = '';
                resizer.classList.remove('active');
            }
        });

        const savedWidth = localStorage.getItem('rightSidebarWidth');
        if (savedWidth) {
            let width = parseInt(savedWidth);
            const maxWidth = window.innerWidth * 0.7;
            const minWidth = 200;
            width = Math.max(minWidth, Math.min(width, maxWidth));
            rightSidebar.style.width = `${width}px`;
        }
    }
}
