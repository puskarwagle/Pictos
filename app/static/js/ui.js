/**
 * @file ui.js
 * @description Handles all DOM manipulations, rendering, and UI-specific logic.
 * Manages the view in sync with the global state, interactive components,
 * and rendering clip cards instead of image grids.
 */

import { state } from './state.js?v=1.0.2';
import { pinClip, saveSegments } from './api.js?v=1.0.2';

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
    rightSidebarClips: document.getElementById('rightSidebarClips'),
    deleteSelectedBtn: document.getElementById('deleteSelectedBtn'),
    pinSelectedBtn: document.getElementById('pinSelectedBtn'),
    editModeToggle: document.getElementById('editModeToggle'),
    darkModeToggle: document.getElementById('darkModeToggle'),
    translateToggle: document.getElementById('translateToggle'),
    videoModal: document.getElementById('videoModal'),
    videoIframe: document.getElementById('videoIframe'),
    modalCaption: document.getElementById('modalCaption'),
    closeModal: document.querySelector('.close-modal'),
    resizer: document.getElementById('resizer'),
    rightSidebar: document.getElementById('rightSidebar'),
    statusMsg: document.getElementById('statusMessage'),
    addSegmentBtn: document.getElementById('addSegmentBtn'),
    zenModeToggle: document.getElementById('zenModeToggle'),
    zenContent: document.getElementById('zenContent'),
    zenModeExit: document.getElementById('zenModeExit'),
    zenModeExitBtn: document.getElementById('zenModeExitBtn'),
};

/**
 * Returns the primary source strategy name for AI processing.
 */
export function getPrimarySource() {
    return 'dense';
}

/**
 * Generates default segments from raw script text using paragraph splitting.
 */
export function createDefaultSegments(text) {
    return text.split(/\n\s*\n/).filter(p => p.trim()).map((p, i) => ({
        id: i,
        text: p.trim(),
        keywords: [],
        clips: [],
        images: []
    }));
}

/**
 * Toast notification system.
 */
export function showToast(message, type = 'info', duration = 5000) {
    if (!elements.toastContainer) return;
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.textContent = message;
    elements.toastContainer.appendChild(toast);
    setTimeout(() => toast.classList.add('show'), 10);
    setTimeout(() => {
        toast.classList.remove('show');
        setTimeout(() => toast.remove(), 300);
    }, duration);
}

/**
 * Sets the application's global status message.
 */
export function setStatus(text, showLoader = false, isToast = true) {
    if (text && isToast) {
        showToast(text);
    }
}

/**
 * Toggles the disabled state on primary action buttons.
 */
export function toggleButtons(disabled) {
    elements.processBtn.disabled = disabled;
    elements.backBtn.disabled = disabled;
}

/**
 * Navigates back to the initial script list view.
 */
export function showScriptsList() {
    if (elements.scriptsListContainer) elements.scriptsListContainer.style.display = 'block';
    if (elements.scriptActions) elements.scriptActions.style.display = 'none';
    if (elements.activeScriptHeader) elements.activeScriptHeader.style.display = 'none';
    if (elements.editorContainer) elements.editorContainer.style.display = 'none';
    if (elements.segmentsContainer) elements.segmentsContainer.innerHTML = '';
    if (elements.rightSidebarClips) elements.rightSidebarClips.innerHTML = '<p>Select a segment to view clips.</p>';
    setStatus('Select a script to begin.');
}

/**
 * Renders state.processedSegments into interactive blocks.
 */
export function renderSegments(onKeywordClick) {
    if (elements.segmentsContainer) elements.segmentsContainer.innerHTML = '';
    _onKeywordClick = onKeywordClick;

    state.processedSegments.forEach((segment, idx) => {
        const block = document.createElement('div');
        const colorIdx = (idx % 5) + 1;
        block.className = `segment-block color-${colorIdx} ${idx === state.activeSegmentIndex ? 'active' : ''}`;
        
        // Render Segment Text
        const textDiv = document.createElement('div');
        textDiv.className = 'segment-block-text';
        
        if (state.isEditMode) {
            textDiv.textContent = segment.text;
            textDiv.contentEditable = true;
            textDiv.addEventListener('input', (e) => {
                state.processedSegments[idx].text = e.target.textContent;
            });
            textDiv.addEventListener('blur', () => syncStateWithBackend());
        } else {
            _renderWordSpans(textDiv, segment.text, idx, onKeywordClick);
        }
        
        // Render Keyword Tags
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
            
            // Handle provider-prefixed keywords (e.g., "youtube: keyword")
            let displayKeyword = keyword;
            let provider = null;
            if (keyword.includes(':')) {
                const parts = keyword.split(':');
                provider = parts[0].trim();
                displayKeyword = parts.slice(1).join(':').trim();
                tag.setAttribute('data-provider', provider);
                tag.classList.add(`provider-${provider}`);
            }
            
            const textSpan = document.createElement('span');
            textSpan.textContent = displayKeyword;
            tag.appendChild(textSpan);

            // Delete button
            const deleteBtn = document.createElement('span');
            deleteBtn.innerHTML = '&times;';
            deleteBtn.className = 'keyword-delete-icon';
            deleteBtn.title = 'Remove keyword';
            deleteBtn.contentEditable = false;
            deleteBtn.onclick = (e) => {
                e.stopPropagation();
                segment.keywords.splice(kIdx, 1);
                syncStateWithBackend().then(() => renderSegments(onKeywordClick || _onKeywordClick));
            };
            tag.appendChild(deleteBtn);

            // Mark as downloaded if clips exist
            const isDownloaded = segment.clips && segment.clips.some(clip => 
                                    clip.keyword && clip.keyword.toLowerCase() === keyword.toLowerCase()
                                 );
            if (isDownloaded) tag.classList.add('downloaded');

            // Interactive behavior
            if (state.isEditMode) {
                textSpan.contentEditable = true;
                textSpan.addEventListener('input', (e) => {
                    state.processedSegments[idx].keywords[kIdx] = e.target.textContent;
                });
                textSpan.addEventListener('blur', () => syncStateWithBackend());
            } else {
                tag.onclick = (e) => {
                    e.stopPropagation();

                    // Activate this segment and show clips in the sidebar
                    const blocks = document.querySelectorAll('.segment-block');
                    blocks.forEach(b => b.classList.remove('active'));
                    const targetBlock = blocks[idx];
                    if (targetBlock) {
                        targetBlock.classList.add('active');
                    }
                    state.activeSegmentIndex = idx;
                    showClips(idx);

                    // Scroll to the corresponding keyword section in the right sidebar if it exists
                    if (elements.rightSidebarClips) {
                        const targetGroup = elements.rightSidebarClips.querySelector(`[data-keyword="${keyword.toLowerCase()}"]`);
                        if (targetGroup) {
                            targetGroup.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
                        }
                    }

                    if (tag.classList.contains('downloaded')) {
                        console.log(`Clips already exist for "${keyword}", skipping.`);
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
            showClips(idx);
        });

        if (elements.segmentsContainer) elements.segmentsContainer.appendChild(block);
    });

    // Add Segment button
    const addBtn = document.createElement('button');
    addBtn.className = 'add-segment-btn';
    addBtn.id = 'addSegmentBtnInline';
    addBtn.innerHTML = '<span>+</span> Add Segment';
    addBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        addManualSegment(onKeywordClick);
    });
    if (elements.segmentsContainer) elements.segmentsContainer.appendChild(addBtn);
}

let _onKeywordClick = null;

/**
 * Renders text as clickable word spans for keyword selection.
 */
function _renderWordSpans(container, text, segmentIdx, onKeywordClick) {
    const tokens = text.split(/(\s+)/);
    tokens.forEach(token => {
        if (/^\s+$/.test(token)) {
            container.appendChild(document.createTextNode(token));
        } else if (token.length > 0) {
            const span = document.createElement('span');
            span.className = 'segment-word';
            span.textContent = token;

            span.addEventListener('click', (e) => {
                e.stopPropagation();
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

    container.addEventListener('mouseup', (e) => {
        const sel = window.getSelection();
        if (!sel || sel.isCollapsed) return;

        const selectedText = sel.toString().trim();
        if (selectedText.length === 0 || selectedText.split(/\s+/).length < 2) return;

        if (!container.contains(sel.anchorNode) || !container.contains(sel.focusNode)) return;

        addManualKeyword(segmentIdx, selectedText, onKeywordClick);

        const wordSpans = container.querySelectorAll('.segment-word');
        wordSpans.forEach(ws => {
            if (sel.containsNode(ws, true)) {
                ws.classList.add('selected-as-keyword');
            }
        });

        sel.removeAllRanges();
        showToast(`Added phrase: "${selectedText}"`, 'success', 3000);
    });
}

/**
 * Adds a manually selected keyword and triggers clip fetching.
 */
export function addManualKeyword(segmentIdx, keyword, onKeywordClick) {
    const segment = state.processedSegments[segmentIdx];
    if (!segment) return;

    const normalised = keyword.toLowerCase();
    if (segment.keywords.some(k => k.toLowerCase() === normalised)) {
        showToast(`"${keyword}" is already a keyword.`, 'info', 2000);
        return;
    }

    segment.keywords.push(keyword);
    renderSegments(onKeywordClick || _onKeywordClick);
    
    syncStateWithBackend().then(() => {
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
 * Creates a new empty segment.
 */
export function addManualSegment(onKeywordClick) {
    const newSegment = {
        id: state.processedSegments.length,
        text: '(New segment — edit in Edit Mode)',
        keywords: [],
        clips: [],
        images: []
    };
    state.processedSegments.push(newSegment);
    renderSegments(onKeywordClick || _onKeywordClick);
    syncStateWithBackend();

    const blocks = elements.segmentsContainer.querySelectorAll('.segment-block');
    const lastBlock = blocks[blocks.length - 1];
    if (lastBlock) lastBlock.scrollIntoView({ behavior: 'smooth', block: 'center' });

    showToast('New segment added. Switch to Edit Mode to set its text.', 'info', 4000);
}

/**
 * Populates the right sidebar with YouTube clip cards for the active segment.
 */
export function showClips(idx) {
    const segment = state.processedSegments[idx];
    if (elements.rightSidebarClips) elements.rightSidebarClips.innerHTML = '';
    state.selectedClipIds.clear();
    updateDeleteButtonVisibility();

    const clips = segment.clips || [];

    if (clips.length > 0) {
        // Group clips by keyword
        const groups = {};
        clips.forEach(clip => {
            const kw = clip.keyword || 'general';
            if (!groups[kw]) groups[kw] = [];
            groups[kw].push(clip);
        });

        Object.keys(groups).sort().forEach(keyword => {
            const groupBox = document.createElement('div');
            groupBox.className = 'source-box source-youtube';
            groupBox.setAttribute('data-keyword', keyword.toLowerCase());

            const title = document.createElement('h4');
            title.innerHTML = `<span style="color:#ff0000">▶</span> ${keyword}`;
            groupBox.appendChild(title);

            const grid = document.createElement('div');
            grid.className = 'clip-grid';

            groups[keyword].forEach(clip => {
                const card = document.createElement('div');
                card.className = 'clip-card';
                card.setAttribute('data-clip-id', clip.id);

                // Thumbnail
                const thumbWrapper = document.createElement('div');
                thumbWrapper.className = 'clip-thumbnail-wrapper';
                
                const thumb = document.createElement('img');
                // Use local thumbnail if available, otherwise YouTube URL
                if (clip.thumbnail_path) {
                    let src = clip.thumbnail_path;
                    if (!src.startsWith('/')) src = '/' + src;
                    thumb.src = src;
                } else {
                    thumb.src = clip.thumbnail || `https://i.ytimg.com/vi/${clip.video_id}/hqdefault.jpg`;
                }
                thumb.loading = 'lazy';
                thumb.alt = clip.title || '';
                thumbWrapper.appendChild(thumb);

                // Timestamp badge
                if (clip.timestamp_start > 0) {
                    const badge = document.createElement('span');
                    badge.className = 'clip-timestamp-badge';
                    const mins = Math.floor(clip.timestamp_start / 60);
                    const secs = Math.floor(clip.timestamp_start % 60);
                    badge.textContent = `${mins}:${secs.toString().padStart(2, '0')}`;
                    thumbWrapper.appendChild(badge);
                }

                // Play icon overlay
                const playIcon = document.createElement('div');
                playIcon.className = 'clip-play-icon';
                playIcon.innerHTML = '▶';
                thumbWrapper.appendChild(playIcon);

                card.appendChild(thumbWrapper);

                // Info section
                const info = document.createElement('div');
                info.className = 'clip-info';

                const clipTitle = document.createElement('div');
                clipTitle.className = 'clip-title';
                clipTitle.textContent = clip.title || 'Untitled';
                clipTitle.title = clip.title || '';
                info.appendChild(clipTitle);

                if (clip.transcript_snippet) {
                    const snippet = document.createElement('div');
                    snippet.className = 'clip-snippet';
                    snippet.textContent = `"${clip.transcript_snippet}"`;
                    info.appendChild(snippet);
                }

                card.appendChild(info);

                // Click to select
                card.onclick = (e) => {
                    e.stopPropagation();
                    const isSelected = card.classList.toggle('selected');
                    if (isSelected) {
                        state.selectedClipIds.add(clip.id);
                    } else {
                        state.selectedClipIds.delete(clip.id);
                    }
                    updateDeleteButtonVisibility();
                };

                // Double click to open YouTube at timestamp
                card.ondblclick = (e) => {
                    e.stopPropagation();
                    const startSec = Math.floor(clip.timestamp_start || 0);
                    const embedUrl = `https://www.youtube.com/embed/${clip.video_id}?start=${startSec}&autoplay=1`;
                    
                    if (elements.videoModal && elements.videoIframe) {
                        elements.videoIframe.src = embedUrl;
                        elements.modalCaption.textContent = clip.title || '';
                        elements.videoModal.style.display = 'flex';
                    } else {
                        window.open(`${clip.url}&t=${startSec}`, '_blank');
                    }
                };

                grid.appendChild(card);
            });

            groupBox.appendChild(grid);
            if (elements.rightSidebarClips) elements.rightSidebarClips.appendChild(groupBox);
        });
    } else {
        if (elements.rightSidebarClips) elements.rightSidebarClips.innerHTML = '<p>No clips found for this segment yet. Click keywords to search YouTube.</p>';
    }
}

/**
 * Updates the visual state of action buttons based on selection.
 */
export function updateDeleteButtonVisibility() {
    const hasSelection = state.selectedClipIds.size > 0;
    
    if (elements.deleteSelectedBtn) {
        elements.deleteSelectedBtn.style.opacity = hasSelection ? '1' : '0.4';
        elements.deleteSelectedBtn.style.pointerEvents = hasSelection ? 'auto' : 'none';
    }
    if (elements.pinSelectedBtn) {
        elements.pinSelectedBtn.style.opacity = hasSelection ? '1' : '0.4';
        elements.pinSelectedBtn.style.pointerEvents = hasSelection ? 'auto' : 'none';
    }
    
    if (hasSelection) {
        if (elements.deleteSelectedBtn) elements.deleteSelectedBtn.title = `Delete Selected (${state.selectedClipIds.size})`;
        if (elements.pinSelectedBtn) elements.pinSelectedBtn.title = `Pin Selected (${state.selectedClipIds.size})`;
    } else {
        if (elements.deleteSelectedBtn) elements.deleteSelectedBtn.title = 'Delete Selected';
        if (elements.pinSelectedBtn) elements.pinSelectedBtn.title = 'Pin Selected';
    }
}

/**
 * Persists pinned status for all selected clips.
 */
export async function pinSelectedClips() {
    if (state.selectedClipIds.size === 0) return;
    
    const idsToPin = Array.from(state.selectedClipIds);
    try {
        setStatus(`Pinning ${idsToPin.length} clips...`, true);
        for (const id of idsToPin) {
            await pinClip(id, true);
        }
        
        if (state.activeSegmentIndex !== -1) {
            showClips(state.activeSegmentIndex);
        }
        
        state.selectedClipIds.clear();
        updateDeleteButtonVisibility();
        setStatus('Clips pinned successfully.');
    } catch (err) {
        console.error('Failed to pin clips:', err);
        setStatus('Error pinning clips', false, true);
    }
}

let zenModeFadeTimer = null;

function simpleMarkdown(text) {
    let html = text
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;');

    html = html.replace(/```([\s\S]*?)```/g, '<pre><code>$1</code></pre>');
    html = html.replace(/`([^`]+)`/g, '<code>$1</code>');
    html = html.replace(/^### (.+)$/gm, '<h3>$1</h3>');
    html = html.replace(/^## (.+)$/gm, '<h2>$1</h2>');
    html = html.replace(/^# (.+)$/gm, '<h1>$1</h1>');
    html = html.replace(/^\* (.+)$/gm, '<li>$1</li>');
    html = html.replace(/^- (.+)$/gm, '<li>$1</li>');
    html = html.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
    html = html.replace(/\*(.+?)\*/g, '<em>$1</em>');
    html = html.replace(/^---+\s*$/gm, '<hr>');

    const lines = html.split('\n');
    const result = [];
    let inList = false;
    for (let i = 0; i < lines.length; i++) {
        const line = lines[i];
        if (line === '') {
            if (inList) { result.push('</ul>'); inList = false; }
            continue;
        }
        if (line.match(/^<(h[123]|li|ul|ol|pre|hr|blockquote)/)) {
            if (inList && !line.startsWith('<li>')) { result.push('</ul>'); inList = false; }
            result.push(line);
            continue;
        }
        if (line.startsWith('<li>')) {
            if (!inList) { result.push('<ul>'); inList = true; }
            result.push(line);
            continue;
        }
        if (inList) { result.push('</ul>'); inList = false; }
        result.push('<p>' + line + '</p>');
    }
    if (inList) result.push('</ul>');

    return result.join('\n');
}

export function enterZenMode() {
    if (!state.selectedScript) return;
    const editorVal = elements.scriptEditor ? elements.scriptEditor.value : '';
    if (!editorVal) return;

    state.isZenMode = true;
    document.body.classList.add('zen-mode');

    if (elements.zenContent) {
        elements.zenContent.innerHTML = simpleMarkdown(editorVal);
    }

    if (elements.zenModeExit) {
        elements.zenModeExit.classList.add('visible');
        clearTimeout(zenModeFadeTimer);
        zenModeFadeTimer = setTimeout(() => {
            elements.zenModeExit.classList.remove('visible');
        }, 3000);
    }

    if (elements.zenModeExitBtn) {
        elements.zenModeExitBtn.onclick = () => exitZenMode();
    }

    document.addEventListener('keydown', onZenEscape);

    localStorage.setItem('zenMode', 'true');
}

function onZenEscape(e) {
    if (e.key === 'Escape') {
        e.preventDefault();
        exitZenMode();
    }
}

export function exitZenMode() {
    state.isZenMode = false;
    document.body.classList.remove('zen-mode');

    if (elements.zenContent) {
        elements.zenContent.innerHTML = '';
    }
    if (elements.zenModeExit) {
        elements.zenModeExit.classList.remove('visible');
    }
    if (elements.zenModeToggle) {
        elements.zenModeToggle.checked = false;
    }

    document.removeEventListener('keydown', onZenEscape);
    clearTimeout(zenModeFadeTimer);
    localStorage.setItem('zenMode', 'false');
}
