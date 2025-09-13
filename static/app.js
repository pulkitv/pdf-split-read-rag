// Basic state
let socket = null;
let currentSessionId = null;
let processedDownloadUrl = null;
let lastVoiceoverUrl = null;

// Helpers
function $(id) { return document.getElementById(id); }
function setDisplay(id, show) { const el = $(id); if (!el) return; el.hidden = !show; el.style.display = show ? '' : 'none'; if (show) { el.classList.remove('d-none'); } else { el.classList.add('d-none'); } }
function setText(id, txt) { const el = $(id); if (el) el.textContent = txt; }
function setProgress(id, pct) { const el = $(id); if (el) el.style.width = `${Math.max(0, Math.min(100, pct))}%`; }
function enable(el, on = true) { if (el) el.disabled = !on; }

// UI helpers
function setBadge(id, text, variant) {
  const el = $(id);
  if (!el) return;
  el.textContent = text;
  el.className = `badge bg-${variant}`;
}

function scrollIntoViewIfHidden(id) {
  const el = $(id);
  if (!el) return;
  const rect = el.getBoundingClientRect();
  const fullyVisible = rect.top >= 0 && rect.bottom <= (window.innerHeight || document.documentElement.clientHeight);
  if (!fullyVisible) el.scrollIntoView({ behavior: 'smooth', block: 'start' });
}

// Single socket initializer with all listeners
function ensureSocket() {
  if (socket) return socket;
  socket = io();

  socket.on('connect', () => {
    if (currentSessionId) socket.emit('join_session', { session_id: currentSessionId });
  });

  socket.on('session_joined', () => {
    // no-op
  });

  socket.on('progress_update', (data) => {
    if (!data || data.session_id !== currentSessionId) return;
    const { step, progress, message } = data;

    if (message) {
      if (step === 'splitting') setText('splitting-message', message);
      if (step === 'ocr') setText('ocr-message', message);
      if (step === 'merging') setText('merging-message', message);
      if (step === 'text-extraction') setText('text-extraction-message', message);
      if (step === 'summarization') setText('summarization-message', message);
    }

    if (typeof progress === 'number') {
      if (step === 'splitting') {
        setProgress('splitting-progress', progress);
        setBadge('splitting-status', progress >= 100 ? 'Complete' : 'In Progress', progress >= 100 ? 'success' : 'warning');
      }
      if (step === 'ocr') {
        setProgress('ocr-progress', progress);
        setBadge('ocr-status', progress >= 100 ? 'Complete' : 'In Progress', progress >= 100 ? 'success' : 'info');
      }
      if (step === 'merging') {
        setProgress('merging-progress', progress);
        setBadge('merging-status', progress >= 100 ? 'Complete' : 'In Progress', progress >= 100 ? 'success' : 'success');
      }
      if (step === 'text-extraction') {
        setProgress('text-extraction-progress', progress);
        setBadge('text-extraction-status', progress >= 100 ? 'Complete' : 'In Progress', progress >= 100 ? 'success' : 'warning');
      }
      if (step === 'summarization') {
        setDisplay('summary-progress-container', true);
        setProgress('summarization-progress', progress);
        setBadge('summarization-status', progress >= 100 ? 'Complete' : 'In Progress', progress >= 100 ? 'success' : 'primary');
      }
    }
  });

  socket.on('processing_complete', (data) => {
    if (!data || data.session_id !== currentSessionId) return;
    processedDownloadUrl = data.merged_file_url;

    // If direct upload, mark others as skipped
    if (data.direct_upload_mode) {
      ['splitting', 'ocr', 'merging'].forEach((k) => {
        setBadge(`${k}-status`, 'Skipped', 'secondary');
        setProgress(`${k}-progress`, 100);
        setText(`${k}-message`, 'Skipped for direct text extraction mode');
      });
      setBadge('text-extraction-status', 'Complete', 'success');
      setProgress('text-extraction-progress', 100);
    }

    setDisplay('processing-section', false);
    setDisplay('results-section', true);

    const downloadBtn = $('download-btn');
    if (downloadBtn) {
      downloadBtn.onclick = () => {
        if (processedDownloadUrl) window.open(processedDownloadUrl, '_blank');
      };
    }
  });

  socket.on('processing_error', (data) => {
    if (!data || (currentSessionId && data.session_id !== currentSessionId)) return;
    setText('error-message', data.error || 'Unknown error occurred.');
    setDisplay('error-section', true);
    setDisplay('processing-section', false);
  });

  socket.on('summary_complete', (data) => {
    if (!data || data.session_id !== currentSessionId) return;
    setDisplay('summary-progress-container', false);
    setDisplay('summary-result', true);
    setText('summary-text', data.summary || '');
    // Reveal voiceover entry if hidden
    setDisplay('voiceover-section', true);
  });

  socket.on('summary_error', (data) => {
    if (!data || data.session_id !== currentSessionId) return;
    setDisplay('summary-progress-container', false);
    setDisplay('summary-result', false);
    setText('error-message', data.error || 'Summarization failed.');
    setDisplay('error-section', true);
  });

  return socket;
}

// Upload interactions
function initUploadHandlers() {
  const fileInput = $('file-input');
  const uploadArea = $('upload-area');
  const browseBtn = $('browse-btn');
  const fileName = $('file-name');
  const startBtn = $('start-processing');

  function setSelectedFile(file) {
    if (!file) return;
    const dt = new DataTransfer();
    dt.items.add(file);
    fileInput.files = dt.files;
    setDisplay('file-info', true);
    fileName.textContent = file.name;
  }

  browseBtn?.addEventListener('click', () => fileInput?.click());
  fileInput?.addEventListener('change', () => {
    const f = fileInput.files?.[0];
    if (f) setSelectedFile(f);
  });

  ;['dragenter','dragover'].forEach(evt => uploadArea?.addEventListener(evt, (e) => {
    e.preventDefault(); e.stopPropagation();
    uploadArea.classList.add('bg-white');
  }));
  ;['dragleave','drop'].forEach(evt => uploadArea?.addEventListener(evt, (e) => {
    e.preventDefault(); e.stopPropagation();
    uploadArea.classList.remove('bg-white');
  }));
  uploadArea?.addEventListener('drop', (e) => {
    const f = e.dataTransfer?.files?.[0];
    if (f && (f.type === 'application/pdf' || f.name.toLowerCase().endsWith('.pdf'))) {
      setSelectedFile(f);
    }
  });

  startBtn?.addEventListener('click', async () => {
    setDisplay('error-section', false);
    const f = fileInput.files?.[0];
    if (!f) {
      setText('error-message', 'Please select a PDF file.');
      setDisplay('error-section', true);
      return;
    }

    const mode = (document.querySelector('input[name="processing-mode"]:checked')?.value) || 'ocr';

    try {
      const fd = new FormData();
      fd.append('file', f);
      fd.append('mode', mode);

      const uploadResp = await fetch('/upload', { method: 'POST', body: fd });
      const uploadJson = await uploadResp.json();
      if (!uploadResp.ok || !uploadJson.success) throw new Error(uploadJson.error || 'Upload failed');

      currentSessionId = uploadJson.session_id;
      ensureSocket();
      socket.emit('join_session', { session_id: currentSessionId });

      // Show processing UI
      setDisplay('processing-section', true);
      setDisplay('results-section', false);
      setDisplay('summary-section', false);
      setDisplay('voiceover-section', false);

      // Reset progress UI
      ['splitting','ocr','merging','text-extraction'].forEach((k) => {
        setProgress(`${k}-progress`, 0);
        setBadge(`${k}-status`, 'Waiting', 'secondary');
        setText(`${k}-message`, 'Waiting to start...');
      });

      // Start processing
      const procResp = await fetch(`/process/${currentSessionId}`);
      const procJson = await procResp.json();
      if (!procResp.ok || !procJson.success) throw new Error(procJson.error || 'Failed to start processing');
      scrollIntoViewIfHidden('processing-section');
    } catch (err) {
      setText('error-message', err.message || String(err));
      setDisplay('error-section', true);
    }
  });
}

// Results actions
function initResultHandlers() {
  $('summarize-btn')?.addEventListener('click', () => {
    setDisplay('summary-section', true);
    scrollIntoViewIfHidden('summary-section');
  });

  // Open search panel from results
  $('search-btn')?.addEventListener('click', () => {
    setDisplay('search-section', true);
    scrollIntoViewIfHidden('search-section');
  });

  $('generate-summary-btn')?.addEventListener('click', async () => {
    if (!currentSessionId) return;
    setDisplay('summary-result', false);
    setDisplay('summary-progress-container', true);
    setBadge('summarization-status', 'Processing', 'primary');
    setProgress('summarization-progress', 0);
    setText('summarization-message', 'Starting summarization...');

    const prompt = $('custom-prompt')?.value || '';
    try {
      const resp = await fetch(`/summarize/${currentSessionId}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ prompt })
      });
      const data = await resp.json();
      if (!resp.ok || data.error) throw new Error(data.error || 'Failed to summarize');
      // Server will also emit summary_complete; still set text as fallback
      if (data.summary) {
        setDisplay('summary-progress-container', false);
        setDisplay('summary-result', true);
        setText('summary-text', data.summary);
      }
    } catch (err) {
      setText('error-message', err.message || String(err));
      setDisplay('error-section', true);
    }
  });

  $('generate-voiceover-btn')?.addEventListener('click', () => {
    setDisplay('voiceover-section', true);
    scrollIntoViewIfHidden('voiceover-section');
  });
}

// Document search handlers
function initSearchHandlers() {
  const queryInput = $('search-query');
  const nInput = $('search-n');
  const runBtn = $('search-run-btn');
  const statsBtn = $('load-vector-stats-btn');
  const resultsContainer = $('search-results-container');
  const resultsList = $('search-results');
  const statsBox = $('vector-stats');

  function renderResults(items) {
    if (!resultsList) return;
    resultsList.innerHTML = '';
    if (!Array.isArray(items) || items.length === 0) {
      const empty = document.createElement('div');
      empty.className = 'text-muted';
      empty.textContent = 'No results found.';
      resultsList.appendChild(empty);
      return;
    }
    items.forEach((it, idx) => {
      const div = document.createElement('div');
      div.className = 'list-group-item';
      const content = (it.content || '').toString();
      const preview = content.length > 600 ? content.slice(0, 600) + '…' : content;
      const src = it.source || 'Unknown';
      const page = it.page_number ? `Page ${it.page_number}` : '';
      const score = (typeof it.relevance_score === 'number') ? it.relevance_score.toFixed(4) : '';
      div.innerHTML = `
        <div class="d-flex w-100 justify-content-between">
          <h6 class="mb-1">Result ${idx + 1}</h6>
          <small class="text-muted">${page}</small>
        </div>
        <p class="mb-1" style="white-space: pre-wrap">${preview}</p>
        <small class="text-muted">Source: ${src}${score ? ` • score: ${score}` : ''}</small>
      `;
      resultsList.appendChild(div);
    });
  }

  runBtn?.addEventListener('click', async () => {
    setDisplay('error-section', false);
    if (!currentSessionId) {
      setText('error-message', 'No active session. Upload and process a PDF first.');
      setDisplay('error-section', true);
      return;
    }
    const q = (queryInput?.value || '').trim();
    const n = Math.max(1, Math.min(20, parseInt(nInput?.value || '5', 10)));
    if (!q) {
      setText('error-message', 'Enter a search query.');
      setDisplay('error-section', true);
      return;
    }
    try {
      enable(runBtn, false);
      setDisplay('search-results-container', true);
      if (resultsList) resultsList.innerHTML = '<div class="text-muted">Searching…</div>';
      const resp = await fetch(`/search/${currentSessionId}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query: q, n })
      });
      const data = await resp.json();
      if (!resp.ok || data.error) throw new Error(data.error || 'Search failed');
      renderResults(data.results || []);
    } catch (err) {
      setText('error-message', err.message || String(err));
      setDisplay('error-section', true);
    } finally {
      enable(runBtn, true);
    }
  });

  // Enter key triggers search
  queryInput?.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      runBtn?.click();
    }
  });

  // Load vector DB stats
  statsBtn?.addEventListener('click', async () => {
    setDisplay('error-section', false);
    if (!currentSessionId) {
      setText('error-message', 'No active session. Upload and process a PDF first.');
      setDisplay('error-section', true);
      return;
    }
    try {
      statsBox.textContent = 'Loading…';
      const resp = await fetch(`/vector-stats/${currentSessionId}`);
      const data = await resp.json();
      if (!resp.ok || data.error) throw new Error(data.error || 'Failed to load stats');
      const parts = [];
      if (data.collection_name) parts.push(`Collection: ${data.collection_name}`);
      if (typeof data.total_chunks === 'number') parts.push(`Chunks: ${data.total_chunks}`);
      if (data.status) parts.push(`Status: ${data.status}`);
      statsBox.textContent = parts.join('\n');
    } catch (err) {
      statsBox.textContent = '';
      setText('error-message', err.message || String(err));
      setDisplay('error-section', true);
    }
  });
}

// Voiceover (session) handlers
function initVoiceoverHandlers() {
  // Source toggle
  const summaryRadio = $('summary-voice-mode');
  const customRadio = $('custom-voice-mode');
  function updateSourceUI() {
    const val = document.querySelector('input[name="voiceover-source"]:checked')?.value || 'summary';
    setDisplay('custom-text-container', val === 'custom');
  }
  summaryRadio?.addEventListener('change', updateSourceUI);
  customRadio?.addEventListener('change', updateSourceUI);
  updateSourceUI();

  $('start-voiceover-btn')?.addEventListener('click', async () => {
    if (!currentSessionId) return;

    const source = document.querySelector('input[name="voiceover-source"]:checked')?.value || 'summary';
    const voice = $('voice-select')?.value || 'nova';
    const speed = parseFloat($('speed-select')?.value || '1.0');
    const format = $('format-select')?.value || 'mp3';
    const bgFileInput = $('backgroundImageMain');
    const bgFile = bgFileInput?.files?.[0] || null;

    let text = '';
    if (source === 'summary') text = $('summary-text')?.textContent?.trim() || '';
    if (source === 'custom') text = $('voiceover-text')?.value?.trim() || '';
    if (!text) {
      setText('error-message', 'No text available for voiceover. Generate a summary or provide custom text.');
      setDisplay('error-section', true);
      return;
    }

    // Reset UI
    setDisplay('voiceover-result', false);
    setDisplay('voiceover-progress-container', true);
    setProgress('voiceover-progress', 10);
    setBadge('voiceover-status', 'Processing', 'dark');
    setText('voiceover-message', 'Preparing synthesis...');

    try {
      let resp, data;
      if (bgFile) {
        const fd = new FormData();
        fd.append('text', text);
        fd.append('voice', voice);
        fd.append('speed', String(speed));
        fd.append('format', format);
        fd.append('backgroundImage', bgFile);
        resp = await fetch(`/generate-voiceover/${currentSessionId}`, { method: 'POST', body: fd });
      } else {
        resp = await fetch(`/generate-voiceover/${currentSessionId}`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ text, voice, speed, format })
        });
      }
      data = await resp.json();
      if (!resp.ok || data.error) throw new Error(data.error || 'Failed to generate voiceover');

      // Show result
      lastVoiceoverUrl = data.file_url;
      const isVideo = (data.format || format) === 'mp4' || (lastVoiceoverUrl && lastVoiceoverUrl.endsWith('.mp4'));
      const audioEl = $('voiceover-audio');
      const videoEl = $('voiceover-video');
      if (isVideo) {
        audioEl.style.display = 'none';
        videoEl.style.display = '';
        videoEl.src = lastVoiceoverUrl;
      } else {
        videoEl.style.display = 'none';
        audioEl.style.display = '';
        audioEl.src = lastVoiceoverUrl;
      }
      setDisplay('voiceover-result', true);
      setDisplay('voiceover-progress-container', false);

      $('download-voiceover-btn').onclick = () => {
        if (lastVoiceoverUrl) window.open(`${lastVoiceoverUrl}?dl=1`, '_blank');
      };
    } catch (err) {
      setText('error-message', err.message || String(err));
      setDisplay('error-section', true);
      setDisplay('voiceover-progress-container', false);
    }
  });
}

// Standalone voiceover handlers
function initStandaloneVoiceover() {
  $('show-standalone-voiceover-btn')?.addEventListener('click', () => {
    const panel = $('standalone-voiceover-panel');
    const visible = panel && panel.style.display !== 'none';
    setDisplay('standalone-voiceover-panel', !visible);
    if (!visible) scrollIntoViewIfHidden('standalone-voiceover-panel');
  });

  $('generate-standalone-voiceover-btn')?.addEventListener('click', async () => {
    setDisplay('error-section', false);
    const text = $('standalone-voiceover-text')?.value?.trim() || '';
    const voice = $('standalone-voice-select')?.value || 'nova';
    const speed = $('standalone-speed-select')?.value || '1.0';
    const format = $('standalone-format-select')?.value || 'mp3';
    const bgFile = $('backgroundImageStandalone')?.files?.[0] || null;

    if (!text) {
      setText('error-message', 'Enter text to generate a voiceover.');
      setDisplay('error-section', true);
      return;
    }

    // Reset progress UI
    setDisplay('standalone-voiceover-result', false);
    setDisplay('standalone-voiceover-progress', true);
    setProgress('standalone-voiceover-progress-bar', 15);
    setBadge('standalone-voiceover-status', 'Processing', 'info');
    setText('standalone-voiceover-message', 'Generating voiceover...');

    try {
      let resp, data;
      if (bgFile) {
        const fd = new FormData();
        fd.append('text', text);
        fd.append('voice', voice);
        fd.append('speed', String(speed));
        fd.append('format', format);
        // Server expects field name 'backgroundImage'
        fd.append('backgroundImage', bgFile);
        resp = await fetch(`/generate-voiceover/standalone`, { method: 'POST', body: fd });
      } else {
        resp = await fetch(`/generate-voiceover/standalone`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ text, voice, speed: parseFloat(speed), format })
        });
      }
      data = await resp.json();
      if (!resp.ok || data.error) throw new Error(data.error || 'Failed to generate voiceover');

      const url = data.file_url;
      const fmt = (data.format || format || '').toLowerCase();

      const audioEl = $('standalone-voiceover-audio');
      const videoEl = $('standalone-voiceover-video');
      if (fmt === 'mp4' || (url && url.endsWith('.mp4'))) {
        audioEl.style.display = 'none';
        videoEl.style.display = '';
        videoEl.src = url;
      } else {
        videoEl.style.display = 'none';
        audioEl.style.display = '';
        audioEl.src = url;
      }

      $('download-standalone-voiceover-btn').onclick = () => {
        if (url) window.open(`${url}?dl=1`, '_blank');
      };

      setProgress('standalone-voiceover-progress-bar', 100);
      setBadge('standalone-voiceover-status', 'Complete', 'success');
      setText('standalone-voiceover-message', 'Voiceover ready.');
      setDisplay('standalone-voiceover-progress', false);
      setDisplay('standalone-voiceover-result', true);
    } catch (err) {
      setText('error-message', err.message || String(err));
      setDisplay('error-section', true);
      setDisplay('standalone-voiceover-progress', false);
    }
  });
}

// YouTube Shorts handlers
function initYoutubeShortsHandlers() {
  // Show/hide shorts generator panel
  $('show-shorts-generator-btn')?.addEventListener('click', () => {
    const panel = $('shorts-generator-panel');
    const visible = panel && panel.style.display !== 'none';
    setDisplay('shorts-generator-panel', !visible);
    if (!visible) scrollIntoViewIfHidden('shorts-generator-panel');
  });

  $('generate-shorts-btn')?.addEventListener('click', async () => {
    setDisplay('error-section', false);
    
    const script = $('shorts-script-text')?.value?.trim() || '';
    const voice = $('shorts-voice-select')?.value || 'nova';
    const speed = parseFloat($('shorts-speed-select')?.value || '1.0');
    const bgFile = $('shorts-background-image')?.files?.[0] || null;
    
    if (!script) {
      setText('error-message', 'Please enter a script for the YouTube Shorts.');
      setDisplay('error-section', true);
      return;
    }
    
    // Show progress
    setDisplay('shorts-progress', true);
    setDisplay('shorts-result', false);
    setProgress('shorts-progress-bar', 10);
    setBadge('shorts-status', 'Processing', 'danger');
    setText('shorts-message', 'Generating YouTube Shorts...');
    
    try {
      let resp, data;
      if (bgFile) {
        const fd = new FormData();
        fd.append('script', script);
        fd.append('voice', voice);
        fd.append('speed', String(speed));
        fd.append('backgroundImage', bgFile);
        resp = await fetch('/generate-shorts', { method: 'POST', body: fd });
      } else {
        resp = await fetch('/generate-shorts', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            script: script,
            voice: voice,
            speed: speed
          })
        });
      }
      
      data = await resp.json();
      
      if (!resp.ok || data.error) {
        throw new Error(data.error || 'Failed to generate YouTube Shorts');
      }
      
      // Update progress to completion
      setProgress('shorts-progress-bar', 100);
      setBadge('shorts-status', 'Complete', 'success');
      setText('shorts-message', 'YouTube Shorts generated successfully!');
      
      // Show results
      displayShortsResults(data.videos || [], data.zip_url || null);
      
      setTimeout(() => {
        setDisplay('shorts-progress', false);
      }, 1000);
      
    } catch (err) {
      setText('error-message', err.message || String(err));
      setDisplay('error-section', true);
      setDisplay('shorts-progress', false);
    }
  });
  
  // Speed slider handler
  $('shorts-speed')?.addEventListener('input', (e) => {
    const speedDisplay = $('shorts-speed-display');
    if (speedDisplay) {
      speedDisplay.textContent = `${e.target.value}x`;
    }
  });
  
  // Keyboard shortcut for generation
  $('shorts-script')?.addEventListener('keydown', (e) => {
    if (e.ctrlKey && e.key === 'Enter') {
      e.preventDefault();
      $('generate-shorts-btn')?.click();
    }
  });
}

// Display YouTube Shorts results
function displayShortsResults(videos, zipUrl = null) {
  const resultsContainer = $('shorts-result');
  const videosContainer = $('shorts-videos-container');
  
  if (!resultsContainer || !videosContainer) return;
  
  if (!videos || videos.length === 0) {
    videosContainer.innerHTML = '<div class="alert alert-warning">No videos were generated.</div>';
    setDisplay('shorts-result', true);
    return;
  }
  
  let html = '';
  
  // Add "Download All" section if zip URL is provided
  if (zipUrl) {
    html += `
      <div class="alert alert-success d-flex align-items-center mb-4">
        <i class="fas fa-check-circle me-3 fs-4"></i>
        <div class="flex-grow-1">
          <h6 class="mb-1">Successfully generated ${videos.length} YouTube Shorts!</h6>
          <small class="text-muted">All videos are ready for download individually or as a complete package.</small>
        </div>
      </div>
      
      <div class="card bg-light mb-4">
        <div class="card-body text-center">
          <h6 class="card-title">
            <i class="fas fa-archive me-2 text-primary"></i>
            Download All Videos
          </h6>
          <p class="card-text text-muted mb-3">
            Get all ${videos.length} YouTube Shorts videos in a single ZIP file for easy sharing and storage.
          </p>
          <a href="${zipUrl}" class="btn btn-primary btn-lg">
            <i class="fas fa-download me-2"></i>
            Download All Shorts (ZIP)
          </a>
        </div>
      </div>
      
      <hr class="my-4">
      <h6 class="mb-3">
        <i class="fab fa-youtube me-2 text-danger"></i>
        Individual Videos
      </h6>
    `;
  }
  
  html += '<div class="row">';
  
  videos.forEach((video, index) => {
    html += `
      <div class="col-md-6 col-lg-4 mb-3">
        <div class="card h-100">
          <div class="card-body">
            <h6 class="card-title">
              <i class="fab fa-youtube text-danger me-2"></i>
              Short ${index + 1}
            </h6>
            <p class="card-text">
              <small class="text-muted">
                Duration: ${video.duration || 'Unknown'}s<br>
                Format: ${video.format?.toUpperCase() || 'MP4'}
              </small>
            </p>
            <div class="d-grid gap-2">
              <a href="${video.file_url}" class="btn btn-outline-primary btn-sm" target="_blank">
                <i class="fas fa-play me-1"></i>Preview
              </a>
              <a href="${video.file_url}?dl=1" class="btn btn-success btn-sm">
                <i class="fas fa-download me-1"></i>Download
              </a>
            </div>
          </div>
        </div>
      </div>
    `;
  });
  
  html += '</div>';
  videosContainer.innerHTML = html;
  setDisplay('shorts-result', true);
}

// Show Shorts section
function showShortsSection() {
  setDisplay('upload-section', false);
  setDisplay('processing-section', false);
  setDisplay('results-section', false);
  setDisplay('voiceover-section', false);
  setDisplay('shorts-section', true);
  
  // Update navigation
  document.querySelectorAll('.nav-link').forEach(link => {
    link.classList.remove('active');
  });
  
  const shortsNavLink = document.querySelector('[onclick*="showShortsSection"]');
  if (shortsNavLink) {
    shortsNavLink.classList.add('active');
  }
  
  scrollIntoViewIfHidden('shorts-section');
}

// App init
document.addEventListener('DOMContentLoaded', () => {
  // Ensure error panel is hidden on load
  setDisplay('error-section', false);
  setText('error-message', '');

  ensureSocket();
  initUploadHandlers();
  initResultHandlers();
  initSearchHandlers();
  initVoiceoverHandlers();
  initStandaloneVoiceover();
  initYoutubeShortsHandlers();
});