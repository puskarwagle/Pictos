/**
 * @file api.js
 * @description Encapsulates all backend API communication for the application.
 * All functions are asynchronous and return Promises. They handle the low-level
 * fetch calls, header management, and basic response validation.
 */

/**
 * Fetches the list of available scripts from the server.
 * Scripts are typically stored as .md files in the data/video_scripts/ folder.
 * 
 * @async
 * @function getScripts
 * @returns {Promise<string[]>} A promise resolving to an array of script filenames (e.g., ["script1.md", "script2.md"]).
 * @throws {Error} If the network request fails or the server returns a non-OK status.
 */
export async function getScripts() {
    const response = await fetch('/api/scripts');
    if (!response.ok) throw new Error('Failed to fetch scripts');
    return await response.json();
}

/**
 * Fetches the raw content of a specific script file.
 * 
 * @async
 * @function getScriptContent
 * @param {string} filename - The name of the script file to fetch (including extension).
 * @returns {Promise<{content: string}>} Object containing the raw string content of the script.
 * @throws {Error} If the script cannot be found or loaded.
 */
export async function getScriptContent(filename) {
    const response = await fetch(`/api/script/${filename}`);
    if (!response.ok) throw new Error('Failed to load script content');
    return await response.json();
}

/**
 * Fetches the cached AI response (processed segments) for a specific script.
 * The server looks for a matching .json file in the data/ai_responses/ folder.
 * 
 * @async
 * @function getScriptCache
 * @param {string} filename - The name of the script file.
 * @returns {Promise<Array<Object>|null>} The processed segments array or null if no cache exists (404).
 * Each segment object contains {id, text, keywords, images, downloaded_keywords}.
 */
export async function getScriptCache(filename) {
    const response = await fetch(`/api/script/${filename}/response`);
    if (response.ok) return await response.json();
    return null;
}

/**
 * Triggers the AI processing pipeline for a script.
 * The backend will chunk the script, perform vibe analysis, and extract dense visual mapping.
 * 
 * @async
 * @function processScript
 * @param {Object} payload - The request body.
 * @param {string} payload.filename - Name of the script for reference.
 * @param {string} payload.script_text - The full text of the script to process.
 * @param {string} payload.source - The mapping strategy to use (e.g., 'dense').
 * @returns {Promise<Array<Object>>} The newly processed segments with AI-extracted keywords.
 * @throws {Error} If the AI processing fails on the backend.
 */
export async function processScript(payload) {
    const response = await fetch('/api/process-script', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
    });
    if (!response.ok) throw new Error('Failed to process script');
    return await response.json();
}

/**
 * Requests the server to download images for a specific keyword in a segment.
 * Can use either a scraper (Pinterest/Unsplash) or a direct API provider (NASA, etc.).
 * 
 * @async
 * @function downloadKeywordImages
 * @param {Object} payload - The download configuration.
 * @param {string} payload.filename - The current script filename.
 * @param {number} payload.segment_id - The ID of the segment this keyword belongs to.
 * @param {string} payload.keyword - The search term.
 * @param {string} [payload.source] - The scraper source ('pinterest', 'unsplash', 'both').
 * @param {string} [payload.provider] - The API provider name (for isApiProvider=true).
 * @param {boolean} isApiProvider - Whether to use the general fetch endpoint (/api/fetch) or scraper (/api/download-keyword-images).
 * @returns {Promise<{images: Array<{path: string, source: string, keyword: string}>, downloaded_bytes: number}>} 
 * Object containing the new image paths and total size of downloaded files.
 * @throws {Error} If the download request fails.
 */
export async function downloadKeywordImages(payload, isApiProvider) {
    const endpoint = isApiProvider ? '/api/fetch' : '/api/download-keyword-images';
    const response = await fetch(endpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
    });
    if (!response.ok) throw new Error('Download failed');
    return await response.json();
}

/**
 * Toggles the pinned status of an image.
 * Pinned images are preserved during script re-segmentation or "orphaned image" cleanup.
 * 
 * @async
 * @function pinImage
 * @param {string} image_path - The relative path to the image file.
 * @param {boolean} pin - True to pin, false to unpin.
 * @param {string} [note] - Optional custom note to attach to the pin.
 * @returns {Promise<{status: string}>} The new status ('pinned' or 'active').
 * @throws {Error} If the database update fails.
 */
export async function pinImage(image_path, pin, note = null) {
    const response = await fetch('/api/pin-image', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ image_path, pin, note })
    });
    if (!response.ok) throw new Error('Failed to pin image');
    return await response.json();
}

/**
 * Deletes multiple images from the server's storage and database.
 * 
 * @async
 * @function deleteImages
 * @param {string[]} image_paths - Array of relative image paths to delete.
 * @returns {Promise<{deleted: string[]}>} The list of paths successfully deleted.
 * @throws {Error} If the deletion request fails.
 */
export async function deleteImages(image_paths) {
    const response = await fetch('/api/delete-images', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ image_paths })
    });
    if (!response.ok) throw new Error('Failed to delete images');
    return await response.json();
}

/**
 * Translates a keyword to English via DeepSeek API.
 * 
 * @async
 * @function translateKeyword
 * @param {string} keyword - The keyword to translate.
 * @returns {Promise<{translated: string}>}
 */
export async function translateKeyword(keyword) {
    const response = await fetch('/api/translate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ keyword })
    });
    if (!response.ok) throw new Error('Failed to translate keyword');
    return await response.json();
}

/**
 * Saves the current segments to the backend, syncing DB and JSON cache.
 * 
 * @async
 * @function saveSegments
 * @param {string} filename - The script filename.
 * @param {Array<Object>} segments - The array of segment objects.
 */
export async function saveSegments(filename, segments) {
    const response = await fetch('/api/save-segments', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ filename, segments })
    });
    if (!response.ok) throw new Error('Failed to save segments');
    return await response.json();
}
