/**
 * @file main.js
 * @description The main entry point for the NarrateImage application.
 * Initializes the application, sets up event listeners, and orchestrates modules.
 */

import { state } from './state.js';
import * as api from './api.js';
import * as ui from './ui.js';
import { queueDownload } from './queue.js';

const { elements } = ui;

/**
 * Initializes the application once the DOM is fully loaded.
 */
document.addEventListener('DOMContentLoaded', () => {
    setupEventListeners();
    initDarkMode();
    loadScripts();
});

/**
 * Sets up all application-wide event listeners.
 */
function setupEventListeners() {
    // Back Button
    elements.backBtn.addEventListener('click', () => {
        state.selectedScript = null;
        localStorage.removeItem('lastChosenScript');
        ui.showScriptsList();
    });

    // Dark Mode Toggle
    if (elements.darkModeToggle) {
        elements.darkModeToggle.addEventListener('change', (e) => {
            document.body.classList.toggle('dark-mode', e.target.checked);
            localStorage.setItem('darkMode', e.target.checked);
        });
    }

    // Edit Mode Toggle
    elements.editModeToggle.addEventListener('change', (e) => {
        state.isEditMode = e.target.checked;
        document.body.classList.toggle('edit-mode', state.isEditMode);
        elements.scriptEditor.readOnly = !state.isEditMode;
        
        // Mutually exclusive visibility
        elements.editorContainer.style.display = state.isEditMode ? 'flex' : 'none';
        elements.segmentsContainer.style.display = state.isEditMode ? 'none' : 'flex';
        
        if (!state.isEditMode) {
            if (!state.isAiProcessed) {
                state.processedSegments = ui.createDefaultSegments(elements.scriptEditor.value);
            }
            ui.renderSegments(queueDownload);
        }
    });

    // Process with AI Button
    elements.processBtn.addEventListener('click', async () => {
        if (!state.selectedScript) return;
        const scriptText = elements.scriptEditor.value.trim();
        if (!scriptText) return alert('Editor is empty!');

        try {
            ui.toggleButtons(true);
            ui.setStatus('Extracting keywords with AI (DeepSeek)...', true);
            elements.segmentsContainer.innerHTML = '';

            const segments = await api.processScript({ 
                filename: state.selectedScript, 
                script_text: scriptText,
                source: ui.getPrimarySource() 
            });
            
            state.processedSegments = segments;
            state.isAiProcessed = true;
            ui.renderSegments(queueDownload);
            ui.setStatus('Keywords extracted. Click tags to download images.');
        } catch (err) {
            ui.setStatus('Error: ' + err.message);
        } finally {
            ui.toggleButtons(false);
        }
    });

    // Delete Selected Button
    elements.deleteSelectedBtn.onclick = async () => {
        if (state.selectedImagePaths.size === 0) return;
        if (!confirm(`Are you sure you want to delete ${state.selectedImagePaths.size} images?`)) return;

        const pathsToDelete = Array.from(state.selectedImagePaths);
        try {
            ui.setStatus(`Deleting ${pathsToDelete.length} images...`, true);
            const data = await api.deleteImages(pathsToDelete);

            // Update local state
            if (state.activeSegmentIndex !== -1) {
                state.processedSegments[state.activeSegmentIndex].images = state.processedSegments[state.activeSegmentIndex].images.filter(
                    img => {
                        const path = typeof img === 'string' ? img : img.path;
                        return !data.deleted.includes(path);
                    }
                );
                ui.showImages(state.activeSegmentIndex);
                ui.renderSegments(queueDownload);
            }
            ui.setStatus(`Deleted ${data.deleted.length} images.`, false, true);
        } catch (err) {
            ui.setStatus('Error deleting images: ' + err.message);
        }
    };

    // Modal Close Logic
    if (elements.closeModal) {
        elements.closeModal.onclick = () => elements.imageModal.style.display = "none";
    }
    window.onclick = (event) => {
        if (event.target == elements.imageModal) {
            elements.imageModal.style.display = "none";
        }
    };

    // Resizable Sidebar Logic
    setupResizer();
}

/**
 * Initializes the Dark Mode state from localStorage.
 */
function initDarkMode() {
    const isDarkMode = localStorage.getItem('darkMode') !== 'false';
    if (elements.darkModeToggle) {
        elements.darkModeToggle.checked = isDarkMode;
    }
    if (isDarkMode) document.body.classList.add('dark-mode');
}

/**
 * Loads the list of scripts and selects the last chosen one if applicable.
 */
async function loadScripts() {
    try {
        const scripts = await api.getScripts();
        elements.scriptsList.innerHTML = '';
        
        if (scripts.length === 0) {
            elements.scriptsList.innerHTML = '<p>No scripts found in video-scripts/ folder.</p>';
            return;
        }

        const lastScript = localStorage.getItem('lastChosenScript');
        scripts.forEach(script => {
            const tile = document.createElement('div');
            tile.className = 'script-tile';
            tile.textContent = script;
            tile.onclick = () => selectScript(script);
            elements.scriptsList.appendChild(tile);
            if (script === lastScript) selectScript(script);
        });
    } catch (err) {
        ui.setStatus('Error loading scripts: ' + err.message);
    }
}

/**
 * Handles selecting a script, loading its content and any cached AI response.
 * @param {string} filename - The name of the script file.
 */
async function selectScript(filename) {
    state.selectedScript = filename;
    localStorage.setItem('lastChosenScript', filename);
    elements.scriptsListContainer.style.display = 'none';
    elements.scriptActions.style.display = 'block';
    elements.activeScriptHeader.style.display = 'flex';
    elements.selectedScriptName.textContent = filename;
    
    // Mutually exclusive visibility
    elements.editorContainer.style.display = state.isEditMode ? 'flex' : 'none';
    elements.segmentsContainer.style.display = state.isEditMode ? 'none' : 'flex';
    
    try {
        ui.setStatus(`Loading script: ${filename}...`, true);
        ui.toggleButtons(true);
        
        const data = await api.getScriptContent(filename);
        elements.scriptEditor.value = data.content;
        elements.scriptEditor.readOnly = !state.isEditMode;
        elements.segmentsContainer.innerHTML = '';
        
        // Auto-load cached response
        const cachedResponse = await api.getScriptCache(filename);
        if (cachedResponse) {
            state.processedSegments = cachedResponse;
            state.isAiProcessed = true;
            ui.renderSegments(queueDownload);
            ui.setStatus(`Loaded: ${filename}. Cached AI response found.`, false, true);
        } else {
            state.isAiProcessed = false;
            state.processedSegments = ui.createDefaultSegments(elements.scriptEditor.value);
            ui.renderSegments(queueDownload);
            ui.setStatus('No cached response found. Displaying raw script segments. Click Process to start.');
        }

    } catch (err) {
        ui.setStatus('Error loading script: ' + err.message);
    } finally {
        ui.toggleButtons(false);
    }
}

/**
 * Sets up the resizable right sidebar logic.
 */
function setupResizer() {
    const { resizer, rightSidebar } = elements;
    let isResizing = false;

    if (resizer && rightSidebar) {
        resizer.addEventListener('mousedown', () => {
            isResizing = true;
            document.body.style.cursor = 'col-resize';
            document.body.style.userSelect = 'none';
            resizer.classList.add('active');
        });

        document.addEventListener('mousemove', (e) => {
            if (!isResizing) return;

            let newWidth = window.innerWidth - e.clientX;
            const maxWidth = window.innerWidth * 0.5;
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

        // Load saved width
        const savedWidth = localStorage.getItem('rightSidebarWidth');
        if (savedWidth) {
            let width = parseInt(savedWidth);
            const maxWidth = window.innerWidth * 0.5;
            const minWidth = 200;
            width = Math.max(minWidth, Math.min(width, maxWidth));
            rightSidebar.style.width = `${width}px`;
        }
    }
}
