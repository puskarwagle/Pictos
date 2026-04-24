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
    const resultsDiv = document.getElementById('results');

    let selectedScript = null;
    let processedSegments = [];

    // Dark Mode Toggle Logic
    const darkModeToggle = document.getElementById('darkModeToggle');
    // Enable dark mode by default if no preference is saved
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

    // Load available scripts on startup
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
            status.textContent = 'Error loading scripts: ' + err.message;
            console.error(err);
        }
    }

    function showScriptsList() {
        scriptsListContainer.style.display = 'block';
        scriptActions.style.display = 'none';
        editorContainer.style.display = 'none';
        resultsDiv.innerHTML = '';
        status.textContent = 'Select a script to begin.';
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
        
        // Fetch script content
        try {
            status.textContent = `Loading script: ${filename}...`;
            const response = await fetch(`/api/script/${filename}`);
            if (!response.ok) throw new Error('Failed to load script content');
            const data = await response.json();
            
            scriptEditor.value = data.content;
            downloadBtn.style.display = 'none';
            resultsDiv.innerHTML = '';
            status.textContent = `Editing: ${filename}. You can Load last response or Process again.`;
        } catch (err) {
            status.textContent = 'Error loading script: ' + err.message;
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
            loadBtn.disabled = true;
            status.textContent = 'Loading cached response...';
            const response = await fetch(`/api/script/${selectedScript}/response`);
            if (!response.ok) {
                if (response.status === 404) throw new Error('No cached response found. Please Process with AI first.');
                throw new Error('Failed to load cached response');
            }
            
            processedSegments = await response.json();
            renderSegments(processedSegments);
            status.textContent = 'Cached response loaded.';
            downloadBtn.style.display = 'inline-block';
        } catch (err) {
            status.textContent = 'Error: ' + err.message;
        } finally {
            loadBtn.disabled = false;
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
            processBtn.disabled = true;
            status.textContent = 'Extracting keywords with AI (DeepSeek)...';
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
            
            status.textContent = 'Keywords extracted. Ready to download images.';
            downloadBtn.style.display = 'inline-block';
        } catch (err) {
            status.textContent = 'Error: ' + err.message;
        } finally {
            processBtn.disabled = false;
        }
    });

    downloadBtn.addEventListener('click', async () => {
        try {
            downloadBtn.disabled = true;
            status.textContent = 'Downloading images from Pinterest...';

            const response = await fetch('/api/download-images', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(processedSegments)
            });

            if (!response.ok) throw new Error('Failed to download images');
            
            processedSegments = await response.json();
            renderSegments(processedSegments);
            
            status.textContent = 'Image download complete!';
        } catch (err) {
            status.textContent = 'Error: ' + err.message;
        } finally {
            downloadBtn.disabled = false;
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
