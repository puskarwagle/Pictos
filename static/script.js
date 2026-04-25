document.addEventListener('DOMContentLoaded', () => {
    const scriptsListContainer = document.getElementById('scriptsListContainer');
    const scriptsList = document.getElementById('scriptsList');
    const scriptActions = document.getElementById('scriptActions');
    const activeScriptHeader = document.getElementById('activeScriptHeader');
    const selectedScriptName = document.getElementById('selectedScriptName');
    const backBtn = document.getElementById('backBtn');
    
    const editorContainer = document.getElementById('editorContainer');
    const scriptEditor = document.getElementById('scriptEditor');
    const processBtn = document.getElementById('processBtn');
    const toastContainer = document.getElementById('toastContainer');
    const segmentsContainer = document.getElementById('segmentsContainer');
    const rightSidebarImages = document.getElementById('rightSidebarImages');
    const deleteSelectedBtn = document.getElementById('deleteSelectedBtn');
    const editModeToggle = document.getElementById('editModeToggle');

    const getSelectedSource = () => {
        const checked = Array.from(document.querySelectorAll('input[name="platform"]:checked')).map(cb => cb.value);
        if (checked.length === 2) return 'both';
        if (checked.length === 1) return checked[0];
        return 'pinterest'; // Default fallback
    };

    // Modal elements
    const imageModal = document.getElementById('imageModal');
    const modalImg = document.getElementById('modalImg');
    const modalCaption = document.getElementById('modalCaption');
    const closeModal = document.querySelector('.close-modal');

    let selectedScript = null;
    let processedSegments = [];
    let isEditMode = false;
    let activeSegmentIndex = -1;
    let selectedImagePaths = new Set();

    // Concurrency Queue for Keyword Downloads
    const MAX_CONCURRENT_DOWNLOADS = 4;
    let activeDownloads = 0;
    const downloadQueue = [];

    async function processQueue() {
        if (activeDownloads >= MAX_CONCURRENT_DOWNLOADS || downloadQueue.length === 0) return;

        const { segmentIdx, keyword, tagElement, source } = downloadQueue.shift();
        activeDownloads++;
        
        try {
            tagElement.classList.add('downloading');
            tagElement.classList.remove('downloaded');
            
            const response = await fetch('/api/download-keyword-images', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    filename: selectedScript,
                    segment_id: processedSegments[segmentIdx].id,
                    keyword: keyword,
                    source: source
                })
            });

            if (!response.ok) throw new Error('Download failed');
            const data = await response.json();
            
            // Add new images to segment and remove duplicates by path
            const currentImages = processedSegments[segmentIdx].images || [];
            const allImages = [...currentImages, ...data.images];
            
            // Deduplicate by path
            const uniqueImagesMap = new Map();
            allImages.forEach(img => {
                const path = typeof img === 'string' ? img : img.path;
                if (!uniqueImagesMap.has(path)) {
                    uniqueImagesMap.set(path, img);
                }
            });
            
            processedSegments[segmentIdx].images = Array.from(uniqueImagesMap.values());

            tagElement.classList.add('downloaded');
            if (activeSegmentIndex === segmentIdx) showImages(segmentIdx);
        } catch (err) {
            console.error(`Failed to download images for ${keyword}:`, err);
            setStatus(`Failed to download: ${keyword}`, false, true);
        } finally {
            tagElement.classList.remove('downloading');
            activeDownloads--;
            processQueue();
        }
    }

    function queueDownload(segmentIdx, keyword, tagElement) {
        const source = getSelectedSource();
        downloadQueue.push({ segmentIdx, keyword, tagElement, source });
        processQueue();
    }

    function showToast(message, type = 'info', duration = 5000) {
        if (!toastContainer) return;
        const toast = document.createElement('div');
        toast.className = `toast ${type}`;
        toast.textContent = message;
        toastContainer.appendChild(toast);
        
        // Trigger reflow
        setTimeout(() => toast.classList.add('show'), 10);
        
        setTimeout(() => {
            toast.classList.remove('show');
            setTimeout(() => toast.remove(), 300);
        }, duration);
    }

    function setStatus(text, showLoader = false, isToast = true) {
        if (text) {
            showToast(text);
        }
    }

    function toggleButtons(disabled) {
        processBtn.disabled = disabled;
        backBtn.disabled = disabled;
    }

    // Dark Mode Toggle
    const darkModeToggle = document.getElementById('darkModeToggle');
    const isDarkMode = localStorage.getItem('darkMode') !== 'false';
    
    if (darkModeToggle) {
        darkModeToggle.checked = isDarkMode;
        darkModeToggle.addEventListener('change', (e) => {
            document.body.classList.toggle('dark-mode', e.target.checked);
            localStorage.setItem('darkMode', e.target.checked);
        });
    }
    if (isDarkMode) document.body.classList.add('dark-mode');

    // Edit Mode Toggle
    editModeToggle.addEventListener('change', (e) => {
        isEditMode = e.target.checked;
        document.body.classList.toggle('edit-mode', isEditMode);
        scriptEditor.readOnly = !isEditMode;
        
        // Mutually exclusive visibility
        editorContainer.style.display = isEditMode ? 'flex' : 'none';
        segmentsContainer.style.display = isEditMode ? 'none' : 'flex';
        
        if (!isEditMode) {
            renderSegments(); // Refresh segments when exiting edit mode
        }
    });

    async function loadScripts() {
        try {
            const response = await fetch('/api/scripts');
            if (!response.ok) throw new Error('Failed to fetch scripts');
            const scripts = await response.json();
            
            scriptsList.innerHTML = '';
            if (scripts.length === 0) {
                scriptsList.innerHTML = '<p>No scripts found in video-scripts/ folder.</p>';
                return;
            }

            const lastScript = localStorage.getItem('lastChosenScript');
            scripts.forEach(script => {
                const tile = document.createElement('div');
                tile.className = 'script-tile';
                tile.textContent = script;
                tile.onclick = () => selectScript(script);
                scriptsList.appendChild(tile);
                if (script === lastScript) selectScript(script);
            });
        } catch (err) {
            setStatus('Error loading scripts: ' + err.message);
        }
    }

    function showScriptsList() {
        scriptsListContainer.style.display = 'block';
        scriptActions.style.display = 'none';
        activeScriptHeader.style.display = 'none';
        editorContainer.style.display = 'none';
        segmentsContainer.innerHTML = '';
        rightSidebarImages.innerHTML = '<p style="color: var(--status-text); font-style: italic;">Select a segment to view images.</p>';
        setStatus('Select a script to begin.');
    }

    async function selectScript(filename) {
        selectedScript = filename;
        localStorage.setItem('lastChosenScript', filename);
        scriptsListContainer.style.display = 'none';
        scriptActions.style.display = 'block';
        activeScriptHeader.style.display = 'flex';
        selectedScriptName.textContent = filename;
        
        // Mutually exclusive visibility
        editorContainer.style.display = isEditMode ? 'flex' : 'none';
        segmentsContainer.style.display = isEditMode ? 'none' : 'flex';
        
        try {
            setStatus(`Loading script: ${filename}...`, true);
            toggleButtons(true);
            const response = await fetch(`/api/script/${filename}`);
            if (!response.ok) throw new Error('Failed to load script content');
            const data = await response.json();
            
            scriptEditor.value = data.content;
            scriptEditor.readOnly = !isEditMode;
            segmentsContainer.innerHTML = '';
            
            // Auto-load cached response
            try {
                const cacheResp = await fetch(`/api/script/${filename}/response`);
                if (cacheResp.ok) {
                    processedSegments = await cacheResp.json();
                    renderSegments();
                    setStatus(`Loaded: ${filename}. Cached AI response found.`, false, true);
                    setStatus('');
                } else {
                    setStatus('No cached response found. Click Process to start.');
                }
            } catch (cacheErr) {
                setStatus('Error checking cache.');
            }

        } catch (err) {
            setStatus('Error loading script: ' + err.message);
        } finally {
            toggleButtons(false);
        }
    }

    backBtn.addEventListener('click', () => {
        selectedScript = null;
        localStorage.removeItem('lastChosenScript');
        showScriptsList();
    });

    processBtn.addEventListener('click', async () => {
        if (!selectedScript) return;
        const scriptText = scriptEditor.value.trim();
        if (!scriptText) return alert('Editor is empty!');

        try {
            toggleButtons(true);
            setStatus('Extracting keywords with AI (DeepSeek)...', true);
            segmentsContainer.innerHTML = '';

            const response = await fetch('/api/process-script', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ 
                    filename: selectedScript, 
                    script_text: scriptText,
                    source: getSelectedSource() 
                })
            });
            if (!response.ok) throw new Error('Failed to process script');
            
            processedSegments = await response.json();
            renderSegments();
            setStatus('Keywords extracted. Click tags to download images.');
        } catch (err) {
            setStatus('Error: ' + err.message);
        } finally {
            toggleButtons(false);
        }
    });

    function renderSegments() {
        segmentsContainer.innerHTML = '';
        processedSegments.forEach((segment, idx) => {
            const block = document.createElement('div');
            const colorIdx = (idx % 5) + 1;
            block.className = `segment-block color-${colorIdx} ${idx === activeSegmentIndex ? 'active' : ''}`;
            
            const textDiv = document.createElement('div');
            textDiv.className = 'segment-block-text';
            textDiv.textContent = segment.text;
            if (isEditMode) {
                textDiv.contentEditable = true;
                textDiv.addEventListener('input', (e) => {
                    processedSegments[idx].text = e.target.textContent;
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
                tag.textContent = keyword;

                // Mark as downloaded if images exist for this keyword
                const isDownloaded = (segment.downloaded_keywords && segment.downloaded_keywords.includes(keyword)) || 
                                     (segment.images && segment.images.some(img => 
                                        (img.keyword && img.keyword.toLowerCase() === keyword.toLowerCase()) ||
                                        (typeof img === 'string' && img.toLowerCase().includes(keyword.toLowerCase().replace(/ /g, '_'))) ||
                                        (img.path && img.path.toLowerCase().includes(keyword.toLowerCase().replace(/ /g, '_')))
                                     ));
                if (isDownloaded) tag.classList.add('downloaded');

                if (isEditMode) {
                    tag.contentEditable = true;
                    tag.addEventListener('input', (e) => {
                        processedSegments[idx].keywords[kIdx] = e.target.textContent;
                    });
                } else {
                    tag.onclick = (e) => {
                        e.stopPropagation();
                        if (tag.classList.contains('downloaded')) {
                            console.log(`Images already exist for "${keyword}", skipping request.`);
                            return;
                        }
                        queueDownload(idx, keyword, tag);
                    };
                }
                keywordsDiv.appendChild(tag);
            });

            block.appendChild(textDiv);
            block.appendChild(keywordsDiv);
            
            block.addEventListener('click', () => {
                document.querySelectorAll('.segment-block').forEach(b => b.classList.remove('active'));
                block.classList.add('active');
                activeSegmentIndex = idx;
                showImages(idx);
            });

            segmentsContainer.appendChild(block);
        });
    }

    function showImages(idx) {
        const segment = processedSegments[idx];
        rightSidebarImages.innerHTML = '';
        selectedImagePaths.clear();
        updateDeleteButtonVisibility();

        if (segment.images && segment.images.length > 0) {
            const sources = {};
            
            segment.images.forEach(imgData => {
                const imgPath = typeof imgData === 'string' ? imgData : imgData.path;
                const source = (typeof imgData === 'object' ? imgData.source : 'unknown') || 'unknown';
                
                if (!sources[source]) sources[source] = [];
                sources[source].push(imgPath);
            });

            // Render each source in its own box
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
                    
                    const circle = document.createElement('div');
                    circle.className = 'selection-circle';
                    
                    const pin = document.createElement('div');
                    pin.className = 'pin-icon';
                    pin.innerHTML = '📌';
                    pin.title = 'Pin image to this text anchor';
                    
                    const img = document.createElement('img');
                    let relativePath = imgPath.split('narrateImage/')[1] || imgPath;
                    if (relativePath.startsWith('/')) relativePath = relativePath.substring(1);
                    img.src = '/' + relativePath;
                    
                    wrapper.appendChild(circle);
                    wrapper.appendChild(pin);
                    wrapper.appendChild(img);
                    
                    img.style.cursor = 'zoom-in';

                    circle.onclick = (e) => {
                        e.stopPropagation();
                        if (selectedImagePaths.has(imgPath)) {
                            selectedImagePaths.delete(imgPath);
                            wrapper.classList.remove('selected');
                        } else {
                            selectedImagePaths.add(imgPath);
                            wrapper.classList.add('selected');
                        }
                        updateDeleteButtonVisibility();
                    };

                    pin.onclick = async (e) => {
                        e.stopPropagation();
                        const isPinned = wrapper.classList.toggle('pinned');
                        try {
                            const response = await fetch('/api/pin-image', {
                                method: 'POST',
                                headers: { 'Content-Type': 'application/json' },
                                body: JSON.stringify({ image_path: imgPath, pin: isPinned })
                            });
                            if (!response.ok) throw new Error('Failed to pin image');
                        } catch (err) {
                            console.error(err);
                            wrapper.classList.toggle('pinned'); // revert
                        }
                    };

                    img.onclick = (e) => {
                        e.stopPropagation();
                        imageModal.style.display = "block";
                        modalImg.src = img.src;
                        modalCaption.innerHTML = imgPath.split('/').pop();
                    };

                    grid.appendChild(wrapper);
                });
                
                sourceBox.appendChild(grid);
                rightSidebarImages.appendChild(sourceBox);
            });
        } else {
            rightSidebarImages.innerHTML = '<p style="color: var(--status-text); font-style: italic;">No images downloaded for this segment yet. Click keywords to download.</p>';
        }
    }

    // Modal Close logic
    if (closeModal) {
        closeModal.onclick = () => imageModal.style.display = "none";
    }
    window.onclick = (event) => {
        if (event.target == imageModal) {
            imageModal.style.display = "none";
        }
    };

    function updateDeleteButtonVisibility() {
        if (selectedImagePaths.size > 0) {
            deleteSelectedBtn.style.display = 'block';
            deleteSelectedBtn.textContent = `Delete Selected (${selectedImagePaths.size})`;
        } else {
            deleteSelectedBtn.style.display = 'none';
        }
    }

    deleteSelectedBtn.onclick = async () => {
        if (selectedImagePaths.size === 0) return;
        if (!confirm(`Are you sure you want to delete ${selectedImagePaths.size} images?`)) return;

        const pathsToDelete = Array.from(selectedImagePaths);
        try {
            setStatus(`Deleting ${pathsToDelete.length} images...`, true);
            const response = await fetch('/api/delete-images', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ image_paths: pathsToDelete })
            });

            if (!response.ok) throw new Error('Failed to delete images');
            const data = await response.json();

            // Update local state
            if (activeSegmentIndex !== -1) {
                processedSegments[activeSegmentIndex].images = processedSegments[activeSegmentIndex].images.filter(
                    img => {
                        const path = typeof img === 'string' ? img : img.path;
                        return !data.deleted.includes(path);
                    }
                );
                showImages(activeSegmentIndex);
                renderSegments(); // Re-render to update keyword tag colors if needed
            }
            setStatus(`Deleted ${data.deleted.length} images.`, false, true);
        } catch (err) {
            setStatus('Error deleting images: ' + err.message);
        }
    };

    loadScripts();
});