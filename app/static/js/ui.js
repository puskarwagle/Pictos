/**
 * @file ui.js
 * @description Handles all DOM manipulations, rendering, and UI-specific logic for the NarrateImage application.
 * This module is responsible for keeping the view in sync with the global state,
 * managing interactive components like the resizer and image modal, and 
 * rendering complex data structures like script segments and image grids.
 */

import { state } from './state.js';
import { pinImage, saveSegments } from './api.js';

export async function syncStateWithBackend() {
    if (!state.selectedScript) return;
    try {
        await saveSegments(state.selectedScript, state.processedSegments);
    } catch (e) {
        console.error("Failed to sync state:", e);
    }
}


/** 
 * Central registry of all DOM elements used by the application.
 * Facilitates easy updates if the HTML structure changes.
 * @namespace elements
 */
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
    translateToggle: document.getElementById('translateToggle'),
    imageModal: document.getElementById('imageModal'),
    modalImg: document.getElementById('modalImg'),
    modalCaption: document.getElementById('modalCaption'),
    closeModal: document.querySelector('.close-modal'),
    resizer: document.getElementById('resizer'),
    rightSidebar: document.getElementById('rightSidebar'),
    statusMsg: document.getElementById('statusMessage'),
    addSegmentBtn: document.getElementById('addSegmentBtn')
};

/**
 * Determines the primary mapping strategy for AI processing.
 * Currently defaults to 'dense' for high-retention visual sequences.
 * 
 * @function getPrimarySource
 * @returns {string} The primary source/strategy name.
 */
export function getPrimarySource() {
    return 'dense';
}

/**
 * Retrieves the currently selected image sources/scrapers from the UI settings.
 * Currently hardcoded to 'pinterest' but designed for future multi-source expansion.
 * 
 * @function getSelectedSources
 * @returns {string[]} Array of active source names.
 */
export function getSelectedSources() {
    return ['pinterest'];
}

/**
 * Generates a default set of segments from raw script text.
 * It uses double newlines (paragraphs) as the delimiter.
 * Each segment is initialized with empty keywords and image arrays.
 * 
 * @function createDefaultSegments
 * @param {string} text - The raw narration script text.
 * @returns {Array<Object>} Array of initialized segment objects.
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
 * Displays a non-blocking toast notification to the user.
 * 
 * @function showToast
 * @param {string} message - The text content of the notification.
 * @param {string} [type='info'] - The styling category (info, success, error).
 * @param {number} [duration=5000] - Time in milliseconds before the toast disappears.
 */
export function showToast(message, type = 'info', duration = 5000) {
    if (!elements.toastContainer) return;
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.textContent = message;
    elements.toastContainer.appendChild(toast);
    
    // Trigger reflow to ensure the CSS transition plays
    setTimeout(() => toast.classList.add('show'), 10);
    
    // Auto-remove the element after duration + transition time
    setTimeout(() => {
        toast.classList.remove('show');
        setTimeout(() => toast.remove(), 300);
    }, duration);
}

/**
 * Sets the application's global status message.
 * Optionally triggers a toast notification as well.
 * 
 * @function setStatus
 * @param {string} text - The status message.
 * @param {boolean} [showLoader=false] - Reserved for future loading spinner logic.
 * @param {boolean} [isToast=true] - Whether to show the message as a toast notification.
 */
export function setStatus(text, showLoader = false, isToast = true) {
    if (text && isToast) {
        showToast(text);
    }
}

/**
 * Toggles the 'disabled' attribute on primary navigation and action buttons.
 * Used during long-running async tasks like AI processing.
 * 
 * @function toggleButtons
 * @param {boolean} disabled - Whether the buttons should be inactive.
 */
export function toggleButtons(disabled) {
    elements.processBtn.disabled = disabled;
    elements.backBtn.disabled = disabled;
}

/**
 * Navigates the UI back to the initial script list view.
 * Hides all script-specific editors and image sidebars.
 * 
 * @function showScriptsList
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
 * Renders the state.processedSegments into interactive blocks in the main content area.
 * Handles both read-only (Segments Mode) and interactive keyword editing (Edit Mode).
 * Words in segment text are wrapped in clickable spans for manual keyword selection.
 * 
 * @function renderSegments
 * @param {Function} onKeywordClick - Callback invoked when a keyword tag is clicked.
 */
export function renderSegments(onKeywordClick) {
    elements.segmentsContainer.innerHTML = '';
    // Store the callback for use by addManualKeyword
    _onKeywordClick = onKeywordClick;

    state.processedSegments.forEach((segment, idx) => {
        const block = document.createElement('div');
        const colorIdx = (idx % 5) + 1;
        block.className = `segment-block color-${colorIdx} ${idx === state.activeSegmentIndex ? 'active' : ''}`;
        
        // Render Segment Text with interactive word spans
        const textDiv = document.createElement('div');
        textDiv.className = 'segment-block-text';
        
        // Inline editing support for segments (enabled only in Edit Mode)
        if (state.isEditMode) {
            textDiv.textContent = segment.text;
            textDiv.contentEditable = true;
            textDiv.addEventListener('input', (e) => {
                state.processedSegments[idx].text = e.target.textContent;
            });
            textDiv.addEventListener('blur', () => syncStateWithBackend());
        } else {
            // Wrap each word in a <span> for clickable keyword selection
            _renderWordSpans(textDiv, segment.text, idx, onKeywordClick);
        }
        
        // Render Keyword Tags
        const keywordsDiv = document.createElement('div');
        keywordsDiv.className = 'segment-block-keywords';
        segment.keywords.forEach((keyword, kIdx) => {
            // Visual separator for grouping keywords (e.g., from the same anchor)
            if (keyword === '|') {
                const separator = document.createElement('span');
                separator.className = 'keyword-separator';
                separator.textContent = '|';
                keywordsDiv.appendChild(separator);
                return;
            }

            const tag = document.createElement('span');
            tag.className = 'keyword-tag';
            
            // Handle provider-prefixed keywords (e.g., "nasa: galaxy")
            let displayKeyword = keyword;
            let provider = null;
            if (keyword.includes(':')) {
                const parts = keyword.split(':');
                provider = parts[0].trim();
                displayKeyword = parts.slice(1).join(':').trim();
                tag.setAttribute('data-provider', provider);
                tag.classList.add(`provider-${provider}`);
            }
            
            // We wrap the text in a span so edit-mode only affects the text, not the delete button
            const textSpan = document.createElement('span');
            textSpan.textContent = displayKeyword;
            tag.appendChild(textSpan);

            // Add delete button
            const deleteBtn = document.createElement('span');
            deleteBtn.innerHTML = '&times;';
            deleteBtn.className = 'keyword-delete-icon';
            deleteBtn.title = 'Remove keyword';
            deleteBtn.contentEditable = false;
            deleteBtn.onclick = (e) => {
                e.stopPropagation();
                // Remove keyword
                segment.keywords.splice(kIdx, 1);
                // Save and re-render
                syncStateWithBackend().then(() => renderSegments(onKeywordClick || _onKeywordClick));
            };
            tag.appendChild(deleteBtn);

            // Mark tag as 'downloaded' if images already exist for this keyword/segment
            const isDownloaded = (segment.downloaded_keywords && segment.downloaded_keywords.includes(keyword)) || 
                                 (segment.images && segment.images.some(img => 
                                    (img.keyword && img.keyword.toLowerCase() === keyword.toLowerCase()) ||
                                    (typeof img === 'string' && img.toLowerCase().includes(keyword.toLowerCase().replace(/ /g, '_'))) ||
                                    (img.path && img.path.toLowerCase().includes(keyword.toLowerCase().replace(/ /g, '_')))
                                 ));
            if (isDownloaded) tag.classList.add('downloaded');

            // Interactive behavior for tags
            if (state.isEditMode) {
                textSpan.contentEditable = true;
                textSpan.addEventListener('input', (e) => {
                    state.processedSegments[idx].keywords[kIdx] = e.target.textContent;
                });
                textSpan.addEventListener('blur', () => syncStateWithBackend());
            } else {
                tag.onclick = (e) => {
                    e.stopPropagation();
                    // Prevent duplicate download requests for already downloaded assets
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
        
        // Clicking a block activates it and shows associated images in the right sidebar
        block.addEventListener('click', () => {
            document.querySelectorAll('.segment-block').forEach(b => b.classList.remove('active'));
            block.classList.add('active');
            state.activeSegmentIndex = idx;
            showImages(idx);
        });

        elements.segmentsContainer.appendChild(block);
    });

    // Append "Add Segment" button at the bottom of the segments list
    const addBtn = document.createElement('button');
    addBtn.className = 'add-segment-btn';
    addBtn.id = 'addSegmentBtnInline';
    addBtn.innerHTML = '<span>+</span> Add Segment';
    addBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        addManualSegment(onKeywordClick);
    });
    elements.segmentsContainer.appendChild(addBtn);
}

/**
 * Stored reference to the keyword click callback for use by addManualKeyword.
 * @private
 * @type {Function|null}
 */
let _onKeywordClick = null;

/**
 * Renders the text of a segment as individual word <span> elements.
 * Clicking a word adds it as a keyword. Selecting multiple words (phrase) via
 * native text selection adds the entire phrase as a keyword.
 * 
 * @function _renderWordSpans
 * @private
 * @param {HTMLElement} container - The DOM element to populate with word spans.
 * @param {string} text - The raw segment text.
 * @param {number} segmentIdx - The index of the segment in state.processedSegments.
 * @param {Function} onKeywordClick - Callback for triggering downloads.
 */
function _renderWordSpans(container, text, segmentIdx, onKeywordClick) {
    // Split text preserving whitespace tokens
    const tokens = text.split(/(\s+)/);
    tokens.forEach(token => {
        if (/^\s+$/.test(token)) {
            // Whitespace token — render as-is
            container.appendChild(document.createTextNode(token));
        } else if (token.length > 0) {
            const span = document.createElement('span');
            span.className = 'segment-word';
            span.textContent = token;

            // Single-word click handler
            span.addEventListener('click', (e) => {
                e.stopPropagation();
                // If the user has an active text selection (phrase), don't fire single-word click
                const sel = window.getSelection();
                if (sel && sel.toString().trim().length > 0) return;

                const word = token.replace(/[^\w\s'-]/g, '').trim();
                if (word.length === 0) return;
                addManualKeyword(segmentIdx, word, onKeywordClick);
                span.classList.add('selected-as-keyword');
            });

            container.appendChild(span);
        }
    });

    // Mouseup handler for detecting multi-word phrase selections
    container.addEventListener('mouseup', (e) => {
        const sel = window.getSelection();
        if (!sel || sel.isCollapsed) return;

        const selectedText = sel.toString().trim();
        if (selectedText.length === 0 || selectedText.split(/\s+/).length < 2) return;

        // Verify selection is within this container
        if (!container.contains(sel.anchorNode) || !container.contains(sel.focusNode)) return;

        addManualKeyword(segmentIdx, selectedText, onKeywordClick);

        // Highlight selected word spans
        const wordSpans = container.querySelectorAll('.segment-word');
        wordSpans.forEach(ws => {
            if (sel.containsNode(ws, true)) {
                ws.classList.add('selected-as-keyword');
            }
        });

        // Clear the browser selection after capturing the phrase
        sel.removeAllRanges();

        showToast(`Added phrase: "${selectedText}"`, 'success', 3000);
    });
}

/**
 * Adds a manually selected keyword to a segment's keyword list.
 * Updates the state, re-renders the UI, and triggers the initial download.
 * 
 * @function addManualKeyword
 * @param {number} segmentIdx - The index of the segment.
 * @param {string} keyword - The keyword text to add.
 * @param {Function} onKeywordClick - Callback to trigger the download queue.
 */
export function addManualKeyword(segmentIdx, keyword, onKeywordClick) {
    const segment = state.processedSegments[segmentIdx];
    if (!segment) return;

    // Avoid adding duplicate keywords (case-insensitive)
    const normalised = keyword.toLowerCase();
    if (segment.keywords.some(k => k.toLowerCase() === normalised)) {
        showToast(`"${keyword}" is already a keyword.`, 'info', 2000);
        return;
    }

    segment.keywords.push(keyword);

    // Re-render segments to show the new tag
    renderSegments(onKeywordClick || _onKeywordClick);
    
    // Save state to backend to ensure DB is synced before downloading
    syncStateWithBackend().then(() => {
        // Find the newly created keyword tag and trigger download
        const blocks = elements.segmentsContainer.querySelectorAll('.segment-block');
        const targetBlock = blocks[segmentIdx];
        if (targetBlock) {
            const tags = targetBlock.querySelectorAll('.keyword-tag');
            const newTag = Array.from(tags).find(t => t.textContent.toLowerCase() === normalised);
            if (newTag && onKeywordClick) {
                onKeywordClick(segmentIdx, keyword, newTag);
            }
        }
    });

    showToast(`Keyword added: "${keyword}"`, 'success', 2000);
}

/**
 * Creates a new empty segment and appends it to the segments list.
 * The user can then click words or edit it in Edit Mode.
 * 
 * @function addManualSegment
 * @param {Function} onKeywordClick - Callback for keyword downloads.
 */
export function addManualSegment(onKeywordClick) {
    const newSegment = {
        id: state.processedSegments.length,
        text: '(New segment — edit in Edit Mode)',
        keywords: [],
        images: []
    };
    state.processedSegments.push(newSegment);
    renderSegments(onKeywordClick || _onKeywordClick);
    syncStateWithBackend();

    // Auto-scroll to the new segment
    const blocks = elements.segmentsContainer.querySelectorAll('.segment-block');
    const lastBlock = blocks[blocks.length - 1];
    if (lastBlock) lastBlock.scrollIntoView({ behavior: 'smooth', block: 'center' });

    showToast('New segment added. Switch to Edit Mode to set its text.', 'info', 4000);
}

/**
 * Populates the right sidebar with images associated with the active segment.
 * Images are grouped by their source (e.g., Pinterest, Unsplash).
 * 
 * @function showImages
 * @param {number} idx - The index of the segment to display images for.
 */
export function showImages(idx) {
    const segment = state.processedSegments[idx];
    elements.rightSidebarImages.innerHTML = '';
    state.selectedImagePaths.clear();
    updateDeleteButtonVisibility();

    if (segment.images && segment.images.length > 0) {
        // Group images by provider/source
        const sources = {};
        segment.images.forEach(imgData => {
            const imgPath = typeof imgData === 'string' ? imgData : imgData.path;
            const source = (typeof imgData === 'object' ? imgData.source : 'unknown') || 'unknown';
            
            if (!sources[source]) sources[source] = [];
            sources[source].push(imgPath);
        });

        // Render each source group
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
                
                // Visual indicator for pinned images
                const imgObj = segment.images.find(i => (typeof i === 'string' ? i : i.path) === imgPath);
                if (imgObj && imgObj.pinned) {
                    wrapper.classList.add('pinned');
                }

                const img = document.createElement('img');
                // Ensure we use a relative path for the <img> src
                let relativePath = imgPath.split('narrateImage/')[1] || imgPath;
                if (relativePath.startsWith('/')) relativePath = relativePath.substring(1);
                img.src = '/' + relativePath;
                img.loading = 'lazy';
                
                // Toggle selection for bulk actions (pin/delete)
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

                // Double click zooms the image into the modal view
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
 * Updates the visual state and tooltips of image action buttons (Pin/Delete).
 * Disables buttons if no images are currently selected.
 * 
 * @function updateDeleteButtonVisibility
 */
export function updateDeleteButtonVisibility() {
    const hasSelection = state.selectedImagePaths.size > 0;
    
    // Adjust opacity and interaction based on selection state
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
 * Toggles selection for ALL currently visible images in the sidebar.
 * Used for rapid bulk management.
 * 
 * @function toggleSelectAll
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
 * Persists the "pinned" status for all currently selected images to the server.
 * Pinned images are protected from being cleaned up as 'orphans'.
 * 
 * @async
 * @function pinSelectedImages
 */
export async function pinSelectedImages() {
    if (state.selectedImagePaths.size === 0) return;
    
    const pathsToPin = Array.from(state.selectedImagePaths);
    try {
        setStatus(`Pinning ${pathsToPin.length} images...`, true);
        for (const path of pathsToPin) {
            await pinImage(path, true);
        }
        
        // Refresh the image grid to show pin icons
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
