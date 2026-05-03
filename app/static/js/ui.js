/**
 * @file ui.js
 * @description Handles all DOM manipulations, rendering, and UI-specific logic.
 */

import { state } from './state.js';
import { pinImage } from './api.js';

// DOM Elements
export const elements = {
    scriptsListContainer: document.getElementById('scriptsListContainer'),
    scriptsList: document.getElementById('scriptsList'),
    scriptActions: document.getElementById('scriptActions'),
    activeScriptHeader: document.getElementById('activeScriptHeader'),
    selectedScriptName: document.getElementById('selectedScriptName'),
    backBtn: document.getElementById('backBtn'),
    editorContainer: document.getElementById('editorContainer'),
    scriptEditor: document.getElementById('scriptEditor'),
    processBtn: document.getElementById('processBtn'),
    toastContainer: document.getElementById('toastContainer'),
    segmentsContainer: document.getElementById('segmentsContainer'),
    rightSidebarImages: document.getElementById('rightSidebarImages'),
    deleteSelectedBtn: document.getElementById('deleteSelectedBtn'),
    pinSelectedBtn: document.getElementById('pinSelectedBtn'),
    editModeToggle: document.getElementById('editModeToggle'),
    darkModeToggle: document.getElementById('darkModeToggle'),
    imageModal: document.getElementById('imageModal'),
    modalImg: document.getElementById('modalImg'),
    modalCaption: document.getElementById('modalCaption'),
    closeModal: document.querySelector('.close-modal'),
    resizer: document.getElementById('resizer'),
    rightSidebar: document.getElementById('rightSidebar'),
    statusMsg: document.getElementById('statusMessage')
};

/**
 * Determines the primary source for AI processing logic.
 * @returns {string} The primary source name or 'both' or 'dense'.
 */
export function getPrimarySource() {
    return 'dense';
}

/**
 * Gets the default image sources.
 * @returns {string[]} Array of source names.
 */
export function getSelectedSources() {
    return ['pinterest'];
}

/**
 * Creates a default set of segments from raw text by splitting on double newlines.
 * @param {string} text - The raw script text.
 * @returns {Array<Object>} Array of default segment objects.
 */
export function createDefaultSegments(text) {
    return text.split(/\n\s*\n/).filter(p => p.trim()).map((p, i) => ({
        id: i,
        text: p.trim(),
        keywords: [],
        images: []
    }));
}

/**
 * Displays a toast notification message.
 * @param {string} message - The message to display.
 * @param {string} [type='info'] - The type of toast (info, success, error).
 * @param {number} [duration=5000] - Visibility duration in milliseconds.
 */
export function showToast(message, type = 'info', duration = 5000) {
    if (!elements.toastContainer) return;
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.textContent = message;
    elements.toastContainer.appendChild(toast);
    
    // Trigger reflow for animation
    setTimeout(() => toast.classList.add('show'), 10);
    
    setTimeout(() => {
        toast.classList.remove('show');
        setTimeout(() => toast.remove(), 300);
    }, duration);
}

/**
 * Sets the application status message.
 * @param {string} text - The status text.
 * @param {boolean} [showLoader=false] - Whether to show a loading indicator (not fully implemented in CSS yet).
 * @param {boolean} [isToast=true] - Whether to also show the message as a toast.
 */
export function setStatus(text, showLoader = false, isToast = true) {
    if (text && isToast) {
        showToast(text);
    }
}

/**
 * Toggles the disabled state of primary action buttons.
 * @param {boolean} disabled - Whether to disable the buttons.
 */
export function toggleButtons(disabled) {
    elements.processBtn.disabled = disabled;
    elements.backBtn.disabled = disabled;
}

/**
 * Shows the initial scripts list view and hides the editor/actions.
 */
export function showScriptsList() {
    elements.scriptsListContainer.style.display = 'block';
    elements.scriptActions.style.display = 'none';
    elements.activeScriptHeader.style.display = 'none';
    elements.editorContainer.style.display = 'none';
    elements.segmentsContainer.innerHTML = '';
    elements.rightSidebarImages.innerHTML = '<p>Select a segment to view images.</p>';
    setStatus('Select a script to begin.');
}

/**
 * Renders the script segments into the main container.
 * @param {Function} onKeywordClick - Callback function for when a keyword tag is clicked.
 */
export function renderSegments(onKeywordClick) {
    elements.segmentsContainer.innerHTML = '';
    state.processedSegments.forEach((segment, idx) => {
        const block = document.createElement('div');
        const colorIdx = (idx % 5) + 1;
        block.className = `segment-block color-${colorIdx} ${idx === state.activeSegmentIndex ? 'active' : ''}`;
        
        const textDiv = document.createElement('div');
        textDiv.className = 'segment-block-text';
        textDiv.textContent = segment.text;
        if (state.isEditMode) {
            textDiv.contentEditable = true;
            textDiv.addEventListener('input', (e) => {
                state.processedSegments[idx].text = e.target.textContent;
            });
        }
        
        const keywordsDiv = document.createElement('div');
        keywordsDiv.className = 'segment-block-keywords';
        segment.keywords.forEach((keyword, kIdx) => {
            if (keyword === '|') {
                const separator = document.createElement('span');
                separator.className = 'keyword-separator';
                separator.textContent = '|';
                keywordsDiv.appendChild(separator);
                return;
            }

            const tag = document.createElement('span');
            tag.className = 'keyword-tag';
            
            // Handle provider prefix e.g., "nasa: pillars of creation"
            let displayKeyword = keyword;
            let provider = null;
            if (keyword.includes(':')) {
                const parts = keyword.split(':');
                provider = parts[0].trim();
                displayKeyword = parts.slice(1).join(':').trim();
                tag.setAttribute('data-provider', provider);
                tag.classList.add(`provider-${provider}`);
            }
            
            tag.textContent = displayKeyword;

            const isDownloaded = (segment.downloaded_keywords && segment.downloaded_keywords.includes(keyword)) || 
                                 (segment.images && segment.images.some(img => 
                                    (img.keyword && img.keyword.toLowerCase() === keyword.toLowerCase()) ||
                                    (typeof img === 'string' && img.toLowerCase().includes(keyword.toLowerCase().replace(/ /g, '_'))) ||
                                    (img.path && img.path.toLowerCase().includes(keyword.toLowerCase().replace(/ /g, '_')))
                                 ));
            if (isDownloaded) tag.classList.add('downloaded');

            if (state.isEditMode) {
                tag.contentEditable = true;
                tag.addEventListener('input', (e) => {
                    state.processedSegments[idx].keywords[kIdx] = e.target.textContent;
                });
            } else {
                tag.onclick = (e) => {
                    e.stopPropagation();
                    if (tag.classList.contains('downloaded')) {
                        console.log(`Images already exist for "${keyword}", skipping request.`);
                        return;
                    }
                    if (onKeywordClick) onKeywordClick(idx, keyword, tag);
                };
            }
            keywordsDiv.appendChild(tag);
        });

        block.appendChild(textDiv);
        block.appendChild(keywordsDiv);
        
        block.addEventListener('click', () => {
            document.querySelectorAll('.segment-block').forEach(b => b.classList.remove('active'));
            block.classList.add('active');
            state.activeSegmentIndex = idx;
            showImages(idx);
        });

        elements.segmentsContainer.appendChild(block);
    });
}

/**
 * Renders images associated with a segment into the right sidebar.
 * @param {number} idx - The index of the segment whose images should be shown.
 */
export function showImages(idx) {
    const segment = state.processedSegments[idx];
    elements.rightSidebarImages.innerHTML = '';
    state.selectedImagePaths.clear();
    updateDeleteButtonVisibility();

    if (segment.images && segment.images.length > 0) {
        const sources = {};
        
        segment.images.forEach(imgData => {
            const imgPath = typeof imgData === 'string' ? imgData : imgData.path;
            const source = (typeof imgData === 'object' ? imgData.source : 'unknown') || 'unknown';
            
            if (!sources[source]) sources[source] = [];
            sources[source].push(imgPath);
        });

        Object.keys(sources).sort().forEach(source => {
            const sourceBox = document.createElement('div');
            sourceBox.className = `source-box source-${source}`;
            
            const title = document.createElement('h4');
            title.textContent = source.charAt(0).toUpperCase() + source.slice(1);
            sourceBox.appendChild(title);
            
            const grid = document.createElement('div');
            grid.className = 'image-grid';
            
            sources[source].forEach(imgPath => {
                const wrapper = document.createElement('div');
                wrapper.className = 'image-wrapper';
                wrapper.setAttribute('data-path', imgPath);
                
                // If it was already pinned, mark it
                const imgObj = segment.images.find(i => (typeof i === 'string' ? i : i.path) === imgPath);
                if (imgObj && imgObj.pinned) {
                    wrapper.classList.add('pinned');
                }

                const img = document.createElement('img');
                let relativePath = imgPath.split('narrateImage/')[1] || imgPath;
                if (relativePath.startsWith('/')) relativePath = relativePath.substring(1);
                img.src = '/' + relativePath;
                img.loading = 'lazy';
                
                // Single Click to Toggle Selection
                wrapper.onclick = (e) => {
                    e.stopPropagation();
                    const isSelected = wrapper.classList.toggle('selected');
                    if (isSelected) {
                        state.selectedImagePaths.add(imgPath);
                    } else {
                        state.selectedImagePaths.delete(imgPath);
                    }
                    updateDeleteButtonVisibility();
                };

                // Double Click to Zoom (Modal)
                wrapper.ondblclick = (e) => {
                    e.stopPropagation();
                    elements.imageModal.style.display = "flex";
                    elements.modalImg.src = img.src;
                    elements.modalCaption.innerHTML = imgPath.split('/').pop();
                };

                wrapper.appendChild(img);
                grid.appendChild(wrapper);
            });
            
            sourceBox.appendChild(grid);
            elements.rightSidebarImages.appendChild(sourceBox);
        });
    } else {
        elements.rightSidebarImages.innerHTML = '<p>No images downloaded for this segment yet. Click keywords to download.</p>';
    }
}

/**
 * Updates the visibility and tooltips of action buttons based on current selection.
 */
export function updateDeleteButtonVisibility() {
    const hasSelection = state.selectedImagePaths.size > 0;
    // Buttons are always visible now as per user request
    elements.deleteSelectedBtn.style.opacity = hasSelection ? '1' : '0.4';
    elements.deleteSelectedBtn.style.pointerEvents = hasSelection ? 'auto' : 'none';
    elements.pinSelectedBtn.style.opacity = hasSelection ? '1' : '0.4';
    elements.pinSelectedBtn.style.pointerEvents = hasSelection ? 'auto' : 'none';
    
    if (hasSelection) {
        elements.deleteSelectedBtn.title = `Delete Selected (${state.selectedImagePaths.size})`;
        elements.pinSelectedBtn.title = `Pin Selected (${state.selectedImagePaths.size})`;
    } else {
        elements.deleteSelectedBtn.title = 'Delete Selected';
        elements.pinSelectedBtn.title = 'Pin Selected';
    }
}

/**
 * Toggles selection of all visible images in the sidebar.
 */
export function toggleSelectAll() {
    const images = elements.rightSidebarImages.querySelectorAll('.image-wrapper');
    if (images.length === 0) return;

    const allSelected = Array.from(images).every(img => img.classList.contains('selected'));
    
    images.forEach(wrapper => {
        const imgPath = wrapper.getAttribute('data-path');
        if (allSelected) {
            wrapper.classList.remove('selected');
            state.selectedImagePaths.delete(imgPath);
        } else {
            wrapper.classList.add('selected');
            state.selectedImagePaths.add(imgPath);
        }
    });
    
    updateDeleteButtonVisibility();
}

/**
 * Pins all selected images.
 */
export async function pinSelectedImages() {
    if (state.selectedImagePaths.size === 0) return;
    
    const pathsToPin = Array.from(state.selectedImagePaths);
    try {
        setStatus(`Pinning ${pathsToPin.length} images...`, true);
        for (const path of pathsToPin) {
            await pinImage(path, true);
        }
        
        // Refresh UI to show pinned status
        if (state.activeSegmentIndex !== -1) {
            showImages(state.activeSegmentIndex);
        }
        
        state.selectedImagePaths.clear();
        updateDeleteButtonVisibility();
        setStatus('Images pinned successfully.');
    } catch (err) {
        console.error('Failed to pin images:', err);
        setStatus('Error pinning images', false, true);
    }
}

