/**
 * @file queue.js
 * @description Manages a concurrency-limited task queue for YouTube clip fetching.
 * Ensures we don't overwhelm the backend with simultaneous yt-dlp searches.
 */

import { state } from './state.js?v=1.0.2';
import { fetchClips, translateKeyword } from './api.js?v=1.0.2';
import * as ui from './ui.js?v=1.0.2';

/** @constant {number} MAX_CONCURRENT - Maximum parallel fetch requests. */
const MAX_CONCURRENT = 2;

/** @type {number} activeRequests - Counter for in-flight requests. */
let activeRequests = 0;

/** @type {Array<Object>} requestQueue - Pending fetch tasks. */
const requestQueue = [];

/**
 * Processes the next task in the queue if capacity is available.
 * @async
 * @private
 */
async function processQueue() {
    if (activeRequests >= MAX_CONCURRENT || requestQueue.length === 0) return;

    let { segmentIdx, keyword, tagElement } = requestQueue.shift();
    activeRequests++;

    try {
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
        if (statusMsg) {
            statusMsg.textContent = `Searching YouTube for "${keyword}"...`;
            statusMsg.style.display = 'block';
        }

        const startTime = performance.now();

        // Always fetch from YouTube
        const payload = {
            filename: state.selectedScript,
            segment_id: state.processedSegments[segmentIdx].id,
            keyword
        };

        const data = await fetchClips(payload);

        const endTime = performance.now();

        // Update timing stats
        if (statusMsg) {
            const timeSec = (endTime - startTime) / 1000;
            const timeValue = document.getElementById('timeValue');
            if (timeValue) timeValue.textContent = timeSec.toFixed(1);
            statusMsg.style.display = 'none';

            const headerStats = document.querySelector('.header-stats');
            if (headerStats) {
                headerStats.style.display = 'flex';
                if (window.statsTimeout) clearTimeout(window.statsTimeout);
                window.statsTimeout = setTimeout(() => {
                    headerStats.style.display = 'none';
                }, 10000);
            }
        }

        // Merge new clips into segment state
        const currentClips = state.processedSegments[segmentIdx].clips || [];
        const allClips = [...currentClips, ...data.clips];

        // Deduplicate by clip id
        const uniqueClipsMap = new Map();
        allClips.forEach(clip => {
            const key = clip.id || `${clip.video_id}_${clip.timestamp_start}`;
            if (!uniqueClipsMap.has(key)) {
                uniqueClipsMap.set(key, clip);
            }
        });

        state.processedSegments[segmentIdx].clips = Array.from(uniqueClipsMap.values());

        // Update tag appearance and refresh clip grid
        const hasClipsForKeyword = state.processedSegments[segmentIdx].clips.some(clip =>
            clip.keyword && clip.keyword.toLowerCase() === keyword.toLowerCase()
        );
        if (hasClipsForKeyword) {
            tagElement.classList.add('downloaded');
        } else {
            tagElement.classList.remove('downloaded');
        }
        if (state.activeSegmentIndex === segmentIdx) ui.showClips(segmentIdx);

    } catch (err) {
        console.error(`Failed to fetch clips for ${keyword}:`, err);
        const statusMsg = document.getElementById('statusMessage');
        if (statusMsg) {
            statusMsg.textContent = `Error: ${keyword}`;
        }
        ui.setStatus(`Failed to fetch: ${keyword}`, false, true);
    } finally {
        tagElement.classList.remove('downloading');
        activeRequests--;
        processQueue();
    }
}

/**
 * Adds a clip fetch task to the queue for a keyword.
 * @param {number} segmentIdx - Segment index in state.processedSegments.
 * @param {string} keyword - The search query.
 * @param {HTMLElement} tagElement - The keyword tag DOM element.
 */
export function queueDownload(segmentIdx, keyword, tagElement) {
    requestQueue.push({ segmentIdx, keyword, tagElement });
    processQueue();
}
