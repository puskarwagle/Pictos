/**
 * @file api.js
 * @description Encapsulates all backend API communication for the application.
 * All functions are asynchronous and return Promises.
 */

/**
 * Fetches the list of available scripts from the server.
 * @returns {Promise<string[]>}
 */
export async function getScripts() {
    const response = await fetch('/api/scripts');
    if (!response.ok) throw new Error('Failed to fetch scripts');
    return await response.json();
}

/**
 * Fetches the raw content of a specific script file.
 * @param {string} filename
 * @returns {Promise<{content: string}>}
 */
export async function getScriptContent(filename) {
    const response = await fetch(`/api/script/${filename}`);
    if (!response.ok) throw new Error('Failed to load script content');
    return await response.json();
}

/**
 * Fetches the cached AI response (processed segments) for a specific script.
 * @param {string} filename
 * @returns {Promise<Array<Object>|null>}
 */
export async function getScriptCache(filename) {
    const response = await fetch(`/api/script/${filename}/response`);
    if (response.ok) return await response.json();
    return null;
}

/**
 * Triggers the AI processing pipeline for a script.
 * @param {Object} payload
 * @returns {Promise<Array<Object>>}
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
 * Fetches YouTube clips for a keyword in a specific segment.
 * @param {Object} payload - {filename, segment_id, keyword}
 * @returns {Promise<{clips: Array<Object>}>}
 */
export async function fetchClips(payload) {
    const response = await fetch('/api/fetch-clips', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
    });
    if (!response.ok) throw new Error('Clip fetch failed');
    return await response.json();
}

/**
 * Toggles the pinned status of a clip.
 * @param {string} clip_id
 * @param {boolean} pin
 * @param {string} [note]
 * @returns {Promise<{status: string}>}
 */
export async function pinClip(clip_id, pin, note = null) {
    const response = await fetch('/api/pin-clip', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ clip_id, pin, note })
    });
    if (!response.ok) throw new Error('Failed to pin clip');
    return await response.json();
}

/**
 * Deletes multiple clips from the database.
 * @param {string[]} clip_ids
 * @returns {Promise<{deleted: string[]}>}
 */
export async function deleteClips(clip_ids) {
    const response = await fetch('/api/delete-clips', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ clip_ids })
    });
    if (!response.ok) throw new Error('Failed to delete clips');
    return await response.json();
}

/**
 * Translates a keyword to English via DeepSeek API.
 * @param {string} keyword
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
 * Saves the raw script file content to disk.
 * @param {string} filename
 * @param {string} content
 */
export async function saveScriptFile(filename, content) {
    const response = await fetch(`/api/script/${filename}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ content })
    });
    if (!response.ok) throw new Error('Failed to save script');
    return await response.json();
}

/**
 * Saves the current segments to the backend, syncing DB and JSON cache.
 * @param {string} filename
 * @param {Array<Object>} segments
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
