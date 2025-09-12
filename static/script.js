// YouTube Shorts functionality
function showShortsSection() {
    // Hide other sections
    document.getElementById('upload-section').style.display = 'none';
    document.getElementById('processing-section').style.display = 'none';
    document.getElementById('results-section').style.display = 'none';
    document.getElementById('voiceover-section').style.display = 'none';
    
    // Show shorts section
    document.getElementById('shorts-section').style.display = 'block';
    
    // Update navigation
    updateNavigation('shorts');
}

function updateNavigation(activeSection) {
    // Remove active class from all nav items
    document.querySelectorAll('.nav-link').forEach(link => {
        link.classList.remove('active');
    });
    
    // Add active class to current section
    const activeLink = document.querySelector(`[onclick="show${activeSection.charAt(0).toUpperCase() + activeSection.slice(1)}Section()"]`);
    if (activeLink) {
        activeLink.classList.add('active');
    }
}

function generateShorts() {
    const script = document.getElementById('shorts-script').value.trim();
    if (!script) {
        showAlert('Please enter a script for your YouTube Shorts.', 'warning');
        return;
    }
    
    const voice = document.getElementById('shorts-voice').value;
    const speed = parseFloat(document.getElementById('shorts-speed').value);
    const backgroundFile = document.getElementById('shorts-background').files[0];
    
    // Show progress
    document.getElementById('shorts-progress').style.display = 'block';
    document.getElementById('shorts-results').style.display = 'none';
    document.getElementById('generate-shorts-btn').disabled = true;
    
    updateShortsProgress('Preparing to generate YouTube Shorts...', 10);
    
    // Prepare form data
    const formData = new FormData();
    formData.append('script', script);
    formData.append('voice', voice);
    formData.append('speed', speed);
    if (backgroundFile) {
        formData.append('backgroundImage', backgroundFile);
    }
    
    updateShortsProgress('Generating YouTube Shorts videos...', 30);
    
    fetch('/generate-shorts', {
        method: 'POST',
        body: formData
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            updateShortsProgress('YouTube Shorts generated successfully!', 100);
            displayShortsResults(data);
        } else {
            throw new Error(data.error || 'Failed to generate YouTube Shorts');
        }
    })
    .catch(error => {
        console.error('Error generating shorts:', error);
        showAlert(`Error generating YouTube Shorts: ${error.message}`, 'danger');
        document.getElementById('shorts-progress').style.display = 'none';
    })
    .finally(() => {
        document.getElementById('generate-shorts-btn').disabled = false;
    });
}

function updateShortsProgress(message, progress) {
    const progressBar = document.querySelector('#shorts-progress .progress-bar');
    const progressText = document.querySelector('#shorts-progress .progress-text');
    
    if (progressBar) {
        progressBar.style.width = progress + '%';
        progressBar.setAttribute('aria-valuenow', progress);
    }
    
    if (progressText) {
        progressText.textContent = message;
    }
}

function displayShortsResults(data) {
    const resultsDiv = document.getElementById('shorts-results');
    const resultsContent = document.getElementById('shorts-results-content');
    
    let html = `
        <div class="alert alert-success">
            <i class="fas fa-check-circle"></i>
            Successfully generated ${data.count} YouTube Shorts videos!
        </div>
        
        <div class="row mb-4">
            <div class="col-12">
                <h5><i class="fas fa-download"></i> Download All</h5>
                <a href="${data.zip_url}" class="btn btn-primary btn-lg">
                    <i class="fas fa-archive"></i> Download All Shorts (ZIP)
                </a>
            </div>
        </div>
        
        <div class="row">
    `;
    
    data.items.forEach((item, index) => {
        html += `
            <div class="col-md-6 col-lg-4 mb-4">
                <div class="card h-100">
                    <div class="card-body">
                        <h6 class="card-title">
                            <i class="fab fa-youtube"></i> Short ${item.index}
                        </h6>
                        <p class="card-text">
                            <small class="text-muted">
                                Duration: ${item.duration || 'Unknown'}s<br>
                                Format: ${item.format?.toUpperCase() || 'MP4'}
                            </small>
                        </p>
                        <div class="d-grid gap-2">
                            <a href="${item.file_url}" class="btn btn-outline-primary btn-sm" target="_blank">
                                <i class="fas fa-play"></i> Preview
                            </a>
                            <a href="${item.file_url}?dl=1" class="btn btn-success btn-sm">
                                <i class="fas fa-download"></i> Download
                            </a>
                        </div>
                    </div>
                </div>
            </div>
        `;
    });
    
    html += '</div>';
    
    resultsContent.innerHTML = html;
    resultsDiv.style.display = 'block';
    
    // Hide progress
    document.getElementById('shorts-progress').style.display = 'none';
    
    // Scroll to results
    resultsDiv.scrollIntoView({ behavior: 'smooth' });
}

function clearShortsForm() {
    document.getElementById('shorts-script').value = '';
    document.getElementById('shorts-voice').value = 'nova';
    document.getElementById('shorts-speed').value = '1.0';
    document.getElementById('shorts-background').value = '';
    document.getElementById('shorts-results').style.display = 'none';
    document.getElementById('shorts-progress').style.display = 'none';
    updateSpeedDisplay();
}

// Add event listeners when document loads
document.addEventListener('DOMContentLoaded', function() {
    const generateShortsBtn = document.getElementById('generate-shorts-btn');
    if (generateShortsBtn) {
        generateShortsBtn.addEventListener('click', generateShorts);
    }
    
    const shortsSpeedSlider = document.getElementById('shorts-speed');
    if (shortsSpeedSlider) {
        shortsSpeedSlider.addEventListener('input', updateSpeedDisplay);
    }
    
    const shortsScript = document.getElementById('shorts-script');
    if (shortsScript) {
        shortsScript.addEventListener('keydown', function(e) {
            if (e.ctrlKey && e.key === 'Enter') {
                e.preventDefault();
                generateShorts();
            }
        });
    }
    
    const shortsBackgroundInput = document.getElementById('shorts-background');
    if (shortsBackgroundInput) {
        shortsBackgroundInput.addEventListener('change', function() {
            const file = this.files[0];
            const preview = document.getElementById('shorts-background-preview');
            
            if (file && preview) {
                const reader = new FileReader();
                reader.onload = function(e) {
                    preview.innerHTML = `
                        <div class="mt-2">
                            <img src="${e.target.result}" alt="Background preview" 
                                 style="max-width: 200px; max-height: 150px; border-radius: 8px;">
                            <div class="small text-muted mt-1">${file.name}</div>
                        </div>
                    `;
                };
                reader.readAsDataURL(file);
            } else if (preview) {
                preview.innerHTML = '';
            }
        });
    }
});