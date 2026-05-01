/**
 * @file state.js
 * @description Manages the global state of the NarrateImage application.
 * This module holds reactive variables that track the currently selected script,
 * processed segments, UI modes, and selection states.
 */

/**
 * Global application state object.
 */
export const state = {
    /** @type {string|null} The filename of the currently selected and loaded script. */
    selectedScript: null,

    /** 
     * @type {Array<Object>} 
     * Array of segment objects. Each segment contains text, keywords, and associated images.
     */
    processedSegments: [],

    /** @type {boolean} Whether the application is currently in Edit Mode. */
    isEditMode: false,

    /** @type {boolean} Whether the current segments have been processed by AI. */
    isAiProcessed: false,

    /** @type {number} The index of the currently active/selected segment. */
    activeSegmentIndex: -1,

    /** @type {Set<string>} A set of unique image paths currently selected for deletion. */
    selectedImagePaths: new Set(),

    /** @type {Set<string>} Set of supported API providers for image generation/fetching. */
    API_PROVIDERS: new Set(["picsum", "dicebear", "robohash", "uiavatars", "nasa", "met"])
};
