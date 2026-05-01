/**
 * @file api.js
 * @description Encapsulates all backend API communication for the application.
 */

/**
 * Fetches the list of available scripts from the server.
 * @returns {Promise<string[]>} A promise resolving to an array of script filenames.
 * @throws {Error} If the network request fails.
 */
export async function getScripts() {
    const response = await fetch('/api/scripts');
    if (!response.ok) throw new Error('Failed to fetch scripts');
    return await response.json();
}

/**
 * Fetches the raw content of a specific script.
 * @param {string} filename - The name of the script file to fetch.
 * @returns {Promise<Object>} Object containing the script content.
 */
export async function getScriptContent(filename) {
    const response = await fetch(`/api/script/${filename}`);
    if (!response.ok) throw new Error('Failed to load script content');
    return await response.json();
}

/**
 * Fetches the cached AI response (processed segments) for a specific script.
 * @param {string} filename - The name of the script file.
 * @returns {Promise<Object|null>} The processed segments or null if not found.
 */
export async function getScriptCache(filename) {
    const response = await fetch(`/api/script/${filename}/response`);
    if (response.ok) return await response.json();
    return null;
}

/**
 * Triggers the AI processing for a script to extract keywords and segments.
 * @param {Object} payload - The request body containing filename, text, and source.
 * @returns {Promise<Array<Object>>} The newly processed segments.
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
 * @param {Object} payload - The request body (filename, segment_id, keyword, source/provider).
 * @param {boolean} isApiProvider - Whether to use the general fetch endpoint or specialized download.
 * @returns {Promise<Object>} The download result including image paths.
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
 * Toggles the pinned status of an image on the server.
 * @param {string} image_path - The path to the image.
 * @param {boolean} pin - The new pinned status.
 * @returns {Promise<Object>} The server response.
 */
export async function pinImage(image_path, pin) {
    const response = await fetch('/api/pin-image', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ image_path, pin })
    });
    if (!response.ok) throw new Error('Failed to pin image');
    return await response.json();
}

/**
 * Deletes multiple images from the server.
 * @param {string[]} image_paths - Array of image paths to delete.
 * @returns {Promise<Object>} The server response containing lists of deleted paths.
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
