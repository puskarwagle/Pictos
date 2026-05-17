/**
 * @file queue.js
 * @description Manages a concurrency-limited task queue for image downloads.
 * This module ensures that the application doesn't overwhelm the browser's 
 * network stack or the backend server by limiting the number of simultaneous 
 * image download requests.
 */

import { state } from './state.js';
import { downloadKeywordImages, translateKeyword } from './api.js';
import * as ui from './ui.js';

/** @constant {number} MAX_CONCURRENT_DOWNLOADS - Maximum number of parallel download requests allowed. */
const MAX_CONCURRENT_DOWNLOADS = 4;

/** @type {number} activeDownloads - Counter for currently active/in-flight download requests. */
let activeDownloads = 0;

/** @type {Array<Object>} downloadQueue - Internal storage for pending download tasks. */
const downloadQueue = [];

/**
 * Processes the next task in the download queue if capacity is available.
 * This function orchestrates the entire download lifecycle for a single keyword:
 * 1. UI Feedback: Marks the keyword tag as 'downloading'.
 * 2. API Call: Sends the request to the backend.
 * 3. Stats Calculation: Calculates download speed and duration.
 * 4. State Update: Merges new images into the global state, ensuring no duplicates.
 * 5. UI Refresh: Re-renders the image sidebar if the segment is currently active.
 * 
 * @async
 * @function processQueue
 * @private
 */
async function processQueue() {
    // Check if we can start a new download
    if (activeDownloads >= MAX_CONCURRENT_DOWNLOADS || downloadQueue.length === 0) return;

    // Retrieve the next task from the front of the queue
    let { segmentIdx, keyword, tagElement, source } = downloadQueue.shift();
    activeDownloads++;
    
    try {
        // Visual feedback on the tag being processed
        tagElement.classList.add('downloading');
        tagElement.classList.remove('downloaded');
        
        // Translate keyword if toggle is checked
        if (ui.elements.translateToggle && ui.elements.translateToggle.checked) {
            try {
                const res = await translateKeyword(keyword);
                if (res && res.translated) {
                    keyword = res.translated;
                    console.log(`Translated keyword to: ${keyword}`);
                }
            } catch (err) {
                console.error("Translation failed:", err);
            }
        }
        
        const statusMsg = document.getElementById('statusMessage');
        const headerStats = document.querySelector('.header-stats');
        
        // Show progress in the status bar
        if (statusMsg) {
            statusMsg.textContent = `Downloading ${keyword}...`;
            statusMsg.style.display = 'block';
        }
        
        // Display the stats container (speed/time)
        if (headerStats) {
            headerStats.style.display = 'flex';
        }
        
        const startTime = performance.now();
        
        // Determine if we use an API Provider (NASA, etc.) or a Scraper (Pinterest, etc.)
        const isApiProvider = state.API_PROVIDERS.has(source);
        const bodyPayload = isApiProvider
            ? { filename: state.selectedScript, segment_id: state.processedSegments[segmentIdx].id, keyword, provider: source }
            : { filename: state.selectedScript, segment_id: state.processedSegments[segmentIdx].id, keyword, source };

        // Execute the download
        const data = await downloadKeywordImages(bodyPayload, isApiProvider);
        
        const endTime = performance.now();
        
        // Update download metrics
        if (statusMsg) {
            const timeSec = (endTime - startTime) / 1000;
            const kb = (data.downloaded_bytes || 0) / 1024;
            const speed = timeSec > 0 ? (kb / timeSec).toFixed(1) : 0;
            
            const speedValue = document.getElementById('speedValue');
            const timeValue = document.getElementById('timeValue');
            if (speedValue) speedValue.textContent = speed;
            if (timeValue) timeValue.textContent = timeSec.toFixed(1);
            
            statusMsg.style.display = 'none';
            
            // Auto-hide the stats container after a period of inactivity
            if (headerStats) {
                if (window.statsTimeout) clearTimeout(window.statsTimeout);
                window.statsTimeout = setTimeout(() => {
                    headerStats.style.display = 'none';
                }, 10000); // 10 seconds
            }
        }
        
        // Merge the new images into the existing state for this segment
        const currentImages = state.processedSegments[segmentIdx].images || [];
        const allImages = [...currentImages, ...data.images];
        
        // Deduplicate images based on their file path to avoid redundant entries in the UI
        const uniqueImagesMap = new Map();
        allImages.forEach(img => {
            const path = typeof img === 'string' ? img : img.path;
            if (!uniqueImagesMap.has(path)) {
                uniqueImagesMap.set(path, img);
            }
        });
        
        state.processedSegments[segmentIdx].images = Array.from(uniqueImagesMap.values());

        // Update tag appearance and refresh image grid if necessary
        tagElement.classList.add('downloaded');
        if (state.activeSegmentIndex === segmentIdx) ui.showImages(segmentIdx);

    } catch (err) {
        console.error(`Failed to download images for ${keyword}:`, err);
        const statusMsg = document.getElementById('statusMessage');
        if (statusMsg) {
            statusMsg.textContent = `Error: ${keyword}`;
        }
        ui.setStatus(`Failed to download: ${keyword}`, false, true);
    } finally {
        // Task complete: decrement counter and attempt to process next item
        tagElement.classList.remove('downloading');
        activeDownloads--;
        processQueue();
    }
}

/**
 * Adds one or more download tasks to the queue for a specific keyword.
 * If the tag has a 'data-provider' attribute (set by AI), only that provider is used.
 * Otherwise, it queues tasks for all globally selected sources (e.g., Pinterest).
 * 
 * @function queueDownload
 * @param {number} segmentIdx - The 0-based index of the segment in state.processedSegments.
 * @param {string} keyword - The search query string.
 * @param {HTMLElement} tagElement - The DOM element of the keyword tag for visual updates.
 */
export function queueDownload(segmentIdx, keyword, tagElement) {
    // Check if the AI has pinned a specific provider to this keyword
    const forcedProvider = tagElement.getAttribute('data-provider');
    
    if (forcedProvider) {
        // Use only the AI-selected provider
        downloadQueue.push({ segmentIdx, keyword, tagElement, source: forcedProvider });
    } else {
        // Fallback to globally selected sources from the UI
        const sources = ui.getSelectedSources();
        sources.forEach(source => {
            downloadQueue.push({ segmentIdx, keyword, tagElement, source });
        });
    }
    
    // Kickstart the queue processor
    processQueue();
}
