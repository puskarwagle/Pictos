document.addEventListener('DOMContentLoaded', () => {
    const scriptsListContainer = document.getElementById('scriptsListContainer');
    const scriptsList = document.getElementById('scriptsList');
    const scriptActions = document.getElementById('scriptActions');
    const selectedScriptName = document.getElementById('selectedScriptName');
    const backBtn = document.getElementById('backBtn');
    
    const editorContainer = document.getElementById('editorContainer');
    const scriptEditor = document.getElementById('scriptEditor');
    const loadBtn = document.getElementById('loadBtn');
    const processBtn = document.getElementById('processBtn');
    const downloadBtn = document.getElementById('downloadBtn');
    const status = document.getElementById('status');
    const statusText = document.getElementById('statusText');
    const loader = document.getElementById('loader');
    const resultsDiv = document.getElementById('results');

    let selectedScript = null;
    let processedSegments = [];

    function setStatus(text, showLoader = false) {
        if (statusText) statusText.textContent = text;
        if (loader) {
            if (showLoader) loader.classList.add('active');
            else loader.classList.remove('active');
        }
    }

    function toggleButtons(disabled) {
        loadBtn.disabled = disabled;
        processBtn.disabled = disabled;
        downloadBtn.disabled = disabled;
        backBtn.disabled = disabled;
    }

    // Dark Mode Toggle Logic
    const darkModeToggle = document.getElementById('darkModeToggle');
    const isDarkMode = localStorage.getItem('darkMode') !== 'false';
    
    if (darkModeToggle) {
        darkModeToggle.checked = isDarkMode;
        darkModeToggle.addEventListener('change', (e) => {
            if (e.target.checked) {
                document.body.classList.add('dark-mode');
                localStorage.setItem('darkMode', 'true');
            } else {
                document.body.classList.remove('dark-mode');
                localStorage.setItem('darkMode', 'false');
            }
        });
    }

    if (isDarkMode) {
        document.body.classList.add('dark-mode');
    }

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
            let scriptToAutoSelect = null;

            scripts.forEach(script => {
                const tile = document.createElement('div');
                tile.className = 'script-tile';
                tile.textContent = script;
                tile.onclick = () => selectScript(script);
                scriptsList.appendChild(tile);

                if (script === lastScript) {
                    scriptToAutoSelect = script;
                }
            });

            if (scriptToAutoSelect) {
                selectScript(scriptToAutoSelect);
            } else {
                showScriptsList();
            }
        } catch (err) {
            setStatus('Error loading scripts: ' + err.message);
        }
    }

    function showScriptsList() {
        scriptsListContainer.style.display = 'block';
        scriptActions.style.display = 'none';
        editorContainer.style.display = 'none';
        resultsDiv.innerHTML = '';
        setStatus('Select a script to begin.');
    }

    function showScriptActions(filename) {
        scriptsListContainer.style.display = 'none';
        scriptActions.style.display = 'block';
        selectedScriptName.textContent = filename;
        editorContainer.style.display = 'flex';
    }

    async function selectScript(filename) {
        selectedScript = filename;
        localStorage.setItem('lastChosenScript', filename);
        showScriptActions(filename);
        
        try {
            setStatus(`Loading script: ${filename}...`, true);
            toggleButtons(true);
            const response = await fetch(`/api/script/${filename}`);
            if (!response.ok) throw new Error('Failed to load script content');
            const data = await response.json();
            
            scriptEditor.value = data.content;
            downloadBtn.style.display = 'none';
            resultsDiv.innerHTML = '';
            setStatus(`Editing: ${filename}. You can Load last response or Process again.`);
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

    loadBtn.addEventListener('click', async () => {
        if (!selectedScript) return;
        try {
            toggleButtons(true);
            setStatus('Loading cached response...', true);
            const response = await fetch(`/api/script/${selectedScript}/response`);
            if (!response.ok) {
                if (response.status === 404) throw new Error('No cached response found. Please Process with AI first.');
                throw new Error('Failed to load cached response');
            }
            
            processedSegments = await response.json();
            renderSegments(processedSegments);
            setStatus('Cached response loaded.');
            downloadBtn.style.display = 'inline-block';
        } catch (err) {
            setStatus('Error: ' + err.message);
        } finally {
            toggleButtons(false);
        }
    });

    processBtn.addEventListener('click', async () => {
        if (!selectedScript) return;
        const scriptText = scriptEditor.value.trim();
        if (!scriptText) {
            alert('Editor is empty!');
            return;
        }

        try {
            toggleButtons(true);
            setStatus('Extracting keywords with AI (DeepSeek)...', true);
            resultsDiv.innerHTML = '';

            const response = await fetch('/api/process-script', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ 
                    filename: selectedScript,
                    script_text: scriptText
                })
            });

            if (!response.ok) throw new Error('Failed to process script');
            
            processedSegments = await response.json();
            renderSegments(processedSegments);
            
            setStatus('Keywords extracted. Ready to download images.');
            downloadBtn.style.display = 'inline-block';
        } catch (err) {
            setStatus('Error: ' + err.message);
        } finally {
            toggleButtons(false);
        }
    });

    downloadBtn.addEventListener('click', async () => {
        try {
            toggleButtons(true);
            setStatus('Downloading images from Pinterest...', true);

            const response = await fetch('/api/download-images', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(processedSegments)
            });

            if (!response.ok) throw new Error('Failed to download images');
            
            processedSegments = await response.json();
            renderSegments(processedSegments);
            
            setStatus('Image download complete!');
        } catch (err) {
            setStatus('Error: ' + err.message);
        } finally {
            toggleButtons(false);
        }
    });

    function renderSegments(segments) {
        resultsDiv.innerHTML = '';
        segments.forEach(segment => {
            const card = document.createElement('div');
            card.className = 'segment-card';
            
            const info = document.createElement('div');
            info.className = 'segment-info';
            info.innerHTML = `
                <div class="segment-text">${segment.text}</div>
                <div class="segment-keywords">
                    ${segment.keywords.map(k => `<span class="keyword-tag">${k}</span>`).join('')}
                </div>
            `;
            
            const imagesDiv = document.createElement('div');
            imagesDiv.className = 'segment-images';
            if (segment.images && segment.images.length > 0) {
                segment.images.forEach(imgPath => {
                    const img = document.createElement('img');
                    const relativePath = imgPath.split('narrateImage/')[1] || imgPath;
                    img.src = '/' + relativePath;
                    imagesDiv.appendChild(img);
                });
            } else {
                imagesDiv.innerHTML = '<em>No images yet</em>';
            }
            
            card.appendChild(info);
            card.appendChild(imagesDiv);
            resultsDiv.appendChild(card);
        });
    }

    loadScripts();
});