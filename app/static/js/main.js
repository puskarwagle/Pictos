/**
 * @file main.js
 * @description The main entry point for the NarrateImage application.
 * This module initializes the application, sets up global event listeners,
 * and orchestrates the interaction between the API, UI, State, and Download Queue modules.
 * It manages the high-level application lifecycle and view transitions.
 */

import { state } from './state.js';
import * as api from './api.js';
import * as ui from './ui.js';
import { queueDownload } from './queue.js';

/** @constant {Object} elements - Local reference to UI elements defined in ui.js */
const { elements } = ui;

/**
 * Initializes the application once the DOM is fully loaded.
 * Ensures all DOM elements are available before binding events or loading data.
 * 
 * @listens document#DOMContentLoaded
 */
document.addEventListener('DOMContentLoaded', () => {
    setupEventListeners();
    initDarkMode();
    loadScripts();
});

/**
 * Sets up all application-wide event listeners.
 * Covers navigation, mode toggles, AI processing, image management, and modal interactions.
 * 
 * @function setupEventListeners
 */
function setupEventListeners() {
    /**
     * Back Button: Resets the selected script and returns to the script list view.
     */
    elements.backBtn.addEventListener('click', () => {
        state.selectedScript = null;
        localStorage.removeItem('lastChosenScript');
        ui.showScriptsList();
    });

    /**
     * Dark Mode Toggle: Updates the body class and persists the preference to localStorage.
     */
    if (elements.darkModeToggle) {
        elements.darkModeToggle.addEventListener('change', (e) => {
            document.body.classList.toggle('dark-mode', e.target.checked);
            localStorage.setItem('darkMode', e.target.checked);
        });
    }

    /**
     * Translate Toggle: Updates localStorage.
     */
    if (elements.translateToggle) {
        elements.translateToggle.addEventListener('change', (e) => {
            localStorage.setItem('translateToggle', e.target.checked);
        });
    }

    /**
     * Edit Mode Toggle: Switches between the raw text editor and the interactive segments view.
     * When entering Segments Mode (Edit Mode OFF), it triggers a default re-segmentation
     * if the script hasn't been processed by AI yet.
     */
    elements.editModeToggle.addEventListener('change', (e) => {
        state.isEditMode = e.target.checked;
        document.body.classList.toggle('edit-mode', state.isEditMode);
        elements.scriptEditor.readOnly = !state.isEditMode;
        
        // Mutually exclusive visibility between the Editor and the Segments container
        elements.editorContainer.style.display = state.isEditMode ? 'flex' : 'none';
        elements.segmentsContainer.style.display = state.isEditMode ? 'none' : 'flex';
        
        if (!state.isEditMode) {
            // Auto-generate segments from current editor text if AI hasn't been used yet
            if (!state.isAiProcessed) {
                state.processedSegments = ui.createDefaultSegments(elements.scriptEditor.value);
            }
            ui.renderSegments(queueDownload);
        }
    });

    /**
     * Script Editor Input: Resets the isAiProcessed flag when the user types.
     * This ensures the user is warned that their current segments/keywords might be out of sync.
     */
    elements.scriptEditor.addEventListener('input', () => {
        if (state.isAiProcessed) {
            state.isAiProcessed = false;
            ui.setStatus('Script modified. AI keywords are now out of sync. Click Process to update.');
        }
    });

    /**
     * Process with AI Button: Sends the current script text to the DeepSeek pipeline.
     * Upon success, it updates the state with dense visual mapping and switches to Segments view.
     */
    elements.processBtn.addEventListener('click', async () => {
        if (!state.selectedScript) return;
        const scriptText = elements.scriptEditor.value.trim();
        if (!scriptText) return alert('Editor is empty!');

        try {
            ui.toggleButtons(true);
            elements.processBtn.classList.add('loading');
            ui.setStatus('Extracting keywords with AI (DeepSeek)...', true);
            elements.segmentsContainer.innerHTML = '';

            const segments = await api.processScript({ 
                filename: state.selectedScript, 
                script_text: scriptText,
                source: ui.getPrimarySource() 
            });
            
            state.processedSegments = segments;
            state.isAiProcessed = true;
            
            // Switch out of edit mode to show the new interactive segments
            state.isEditMode = false;
            elements.editModeToggle.checked = false;
            document.body.classList.remove('edit-mode');
            elements.scriptEditor.readOnly = true;
            elements.editorContainer.style.display = 'none';
            elements.segmentsContainer.style.display = 'flex';
            
            ui.renderSegments(queueDownload);
            ui.setStatus('Keywords extracted. Click tags to download images.');
        } catch (err) {
            ui.setStatus('Error: ' + err.message);
        } finally {
            ui.toggleButtons(false);
            elements.processBtn.classList.remove('loading');
        }
    });

    /**
     * Delete Selected Button: Deletes all images currently selected in the right sidebar.
     * Updates both the backend storage and the frontend state/UI.
     */
    elements.deleteSelectedBtn.onclick = async () => {
        if (state.selectedImagePaths.size === 0) return;
        if (!confirm(`Are you sure you want to delete ${state.selectedImagePaths.size} images?`)) return;

        const pathsToDelete = Array.from(state.selectedImagePaths);
        try {
            ui.setStatus(`Deleting ${pathsToDelete.length} images...`, true);
            const data = await api.deleteImages(pathsToDelete);

            // Update local state by filtering out deleted images from the active segment
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
            state.selectedImagePaths.clear();
            ui.updateDeleteButtonVisibility();
            ui.setStatus(`Deleted ${data.deleted.length} images.`, false, true);
        } catch (err) {
            ui.setStatus('Error deleting images: ' + err.message);
        }
    };

    /**
     * Pin Selected Button: Marks selected images as "pinned" in the database.
     */
    elements.pinSelectedBtn.onclick = async () => {
        await ui.pinSelectedImages();
    };

    /**
     * Modal Logic: Handles closing the full-screen image preview.
     */
    if (elements.closeModal) {
        elements.closeModal.onclick = () => elements.imageModal.style.display = "none";
    }
    window.onclick = (event) => {
        if (event.target == elements.imageModal) {
            elements.imageModal.style.display = "none";
        }
    };
    elements.imageModal.ondblclick = () => {
        elements.imageModal.style.display = "none";
    };

    /**
     * Add Segment Button: Creates a new empty segment for manual keyword entry.
     */
    if (elements.addSegmentBtn) {
        elements.addSegmentBtn.addEventListener('click', () => {
            ui.addManualSegment(queueDownload);
        });
    }

    // Initialize the draggable resizer for the right sidebar
    setupResizer();
}

/**
 * Initializes the Dark Mode state from localStorage on page load.
 * Defaults to light mode if no preference is found.
 * 
 * @function initDarkMode
 */
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

/**
 * Fetches the list of scripts from the API and renders them as clickable tiles.
 * Automatically selects the last used script if stored in localStorage.
 * 
 * @async
 * @function loadScripts
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
 * Handles the selection of a specific script.
 * Loads the script content and checks for a cached AI response.
 * If cache is found, it populates the interactive segments immediately.
 * 
 * @async
 * @function selectScript
 * @param {string} filename - The name of the script file to load.
 */
async function selectScript(filename) {
    state.selectedScript = filename;
    localStorage.setItem('lastChosenScript', filename);
    elements.scriptsListContainer.style.display = 'none';
    elements.scriptActions.style.display = 'block';
    elements.activeScriptHeader.style.display = 'flex';
    elements.selectedScriptName.textContent = filename;
    
    // Ensure visibility matches current mode
    elements.editorContainer.style.display = state.isEditMode ? 'flex' : 'none';
    elements.segmentsContainer.style.display = state.isEditMode ? 'none' : 'flex';
    
    try {
        ui.setStatus(`Loading script: ${filename}...`, true);
        ui.toggleButtons(true);
        
        const data = await api.getScriptContent(filename);
        elements.scriptEditor.value = data.content;
        elements.scriptEditor.readOnly = !state.isEditMode;
        elements.segmentsContainer.innerHTML = '';
        
        // Attempt to auto-load cached response from previous AI runs
        const cachedResponse = await api.getScriptCache(filename);
        if (cachedResponse) {
            state.processedSegments = cachedResponse;
            state.isAiProcessed = true;
            ui.renderSegments(queueDownload);
            ui.setStatus(`Loaded: ${filename}. Cached AI response found.`, false, true);
        } else {
            // No cache: start with a fresh paragraph-based segmentation
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
 * Sets up the resizable right sidebar logic using mouse events.
 * Persists the sidebar width to localStorage for a consistent user experience.
 * 
 * @function setupResizer
 */
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

            // Calculate new width based on mouse movement delta (right-to-left increases width)
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

        // Restore saved width from previous session
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
