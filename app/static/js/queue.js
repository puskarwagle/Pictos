/**
 * @file queue.js
 * @description Manages a concurrency-limited queue for keyword image downloads.
 * This prevents overwhelming the server or the browser's network stack.
 */

import { state } from './state.js';
import { downloadKeywordImages } from './api.js';
import * as ui from './ui.js';

const MAX_CONCURRENT_DOWNLOADS = 4;
let activeDownloads = 0;
const downloadQueue = [];

/**
 * Processes the next item in the download queue if capacity is available.
 * Orchestrates the API call and updates the UI upon completion.
 */
async function processQueue() {
    if (activeDownloads >= MAX_CONCURRENT_DOWNLOADS || downloadQueue.length === 0) return;

    const { segmentIdx, keyword, tagElement, source } = downloadQueue.shift();
    activeDownloads++;
    
    try {
        tagElement.classList.add('downloading');
        tagElement.classList.remove('downloaded');
        
        const statusMsg = document.getElementById('statusMessage');
        const headerStats = document.querySelector('.header-stats');
        
        if (statusMsg) {
            statusMsg.textContent = `Downloading ${keyword}...`;
            statusMsg.style.display = 'block';
        }
        
        if (headerStats) {
            headerStats.style.display = 'flex';
        }
        
        const startTime = performance.now();
        
        const isApiProvider = state.API_PROVIDERS.has(source);
        const bodyPayload = isApiProvider
            ? { filename: state.selectedScript, segment_id: state.processedSegments[segmentIdx].id, keyword, provider: source }
            : { filename: state.selectedScript, segment_id: state.processedSegments[segmentIdx].id, keyword, source };

        const data = await downloadKeywordImages(bodyPayload, isApiProvider);
        
        const endTime = performance.now();
        if (statusMsg) {
            const timeSec = (endTime - startTime) / 1000;
            const kb = (data.downloaded_bytes || 0) / 1024;
            const speed = timeSec > 0 ? (kb / timeSec).toFixed(1) : 0;
            
            // Update stats
            const speedValue = document.getElementById('speedValue');
            const timeValue = document.getElementById('timeValue');
            if (speedValue) speedValue.textContent = speed;
            if (timeValue) timeValue.textContent = timeSec.toFixed(1);
            
            statusMsg.style.display = 'none';
            
            // Hide stats after a delay
            if (headerStats) {
                if (window.statsTimeout) clearTimeout(window.statsTimeout);
                window.statsTimeout = setTimeout(() => {
                    headerStats.style.display = 'none';
                }, 10000); // 10 seconds
            }
        }
        
        // Add new images to segment and remove duplicates by path
        const currentImages = state.processedSegments[segmentIdx].images || [];
        const allImages = [...currentImages, ...data.images];
        
        // Deduplicate by path
        const uniqueImagesMap = new Map();
        allImages.forEach(img => {
            const path = typeof img === 'string' ? img : img.path;
            if (!uniqueImagesMap.has(path)) {
                uniqueImagesMap.set(path, img);
            }
        });
        
        state.processedSegments[segmentIdx].images = Array.from(uniqueImagesMap.values());

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
        tagElement.classList.remove('downloading');
        activeDownloads--;
        processQueue();
    }
}

/**
 * Adds a download task to the queue for a specific keyword across all selected sources.
 * @param {number} segmentIdx - The index of the segment requesting the download.
 * @param {string} keyword - The keyword to search for.
 * @param {HTMLElement} tagElement - The DOM element representing the keyword tag.
 */
export function queueDownload(segmentIdx, keyword, tagElement) {
    // If the tag has a specific provider assigned by AI, use only that
    const forcedProvider = tagElement.getAttribute('data-provider');
    if (forcedProvider) {
        downloadQueue.push({ segmentIdx, keyword, tagElement, source: forcedProvider });
    } else {
        const sources = ui.getSelectedSources();
        sources.forEach(source => {
            downloadQueue.push({ segmentIdx, keyword, tagElement, source });
        });
    }
    processQueue();
}
