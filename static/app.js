// JavaScript for Newspaper Summary App
class PDFApp {
    constructor() {
        this.socket = io();
        this.currentMode = 'ocr'; // Default mode based on HTML
        this.selectedFile = null;
        this.init();
    }

    init() {
        this.setupModeSelection();
        this.setupEventListeners();
        this.setupSocketHandlers();
        this.setupFileUpload();
    }

    setupModeSelection() {
        const modeRadios = document.querySelectorAll('input[name="processing-mode"]');
        
        modeRadios.forEach(radio => {
            radio.addEventListener('change', (e) => {
                this.currentMode = e.target.value;
                this.updateUploadDescription();
                this.resetUI();
            });
        });
    }

    setupEventListeners() {
        // Process button
        const startBtn = document.getElementById('start-processing');
        if (startBtn) {
            startBtn.addEventListener('click', () => {
                this.startProcessing();
            });
        }
    }

    setupFileUpload() {
        const uploadArea = document.getElementById('upload-area');
        const fileInput = document.getElementById('file-input');
        const browseBtn = document.getElementById('browse-btn');

        // Browse button click handler
        if (browseBtn && fileInput) {
            browseBtn.addEventListener('click', (e) => {
                e.stopPropagation(); // Prevent event bubbling
                fileInput.click();
            });
        }

        // File input change handler
        if (fileInput) {
            fileInput.addEventListener('change', (e) => {
                this.handleFileSelect(e);
            });
        }

        // Drag and drop handlers
        if (uploadArea) {
            // Only allow upload area click if no file is selected
            uploadArea.addEventListener('click', (e) => {
                // Don't trigger if clicking on the browse button
                if (e.target.id === 'browse-btn' || e.target.closest('#browse-btn')) {
                    return;
                }
                
                // Only allow click to open file dialog if no file is currently selected
                if (!this.selectedFile && fileInput) {
                    fileInput.click();
                }
            });

            uploadArea.addEventListener('dragover', (e) => {
                e.preventDefault();
                uploadArea.classList.add('drag-over');
            });

            uploadArea.addEventListener('dragleave', (e) => {
                e.preventDefault();
                uploadArea.classList.remove('drag-over');
            });

            uploadArea.addEventListener('drop', (e) => {
                e.preventDefault();
                uploadArea.classList.remove('drag-over');
                
                const files = e.dataTransfer.files;
                if (files.length > 0) {
                    this.handleFileSelection(files[0]);
                }
            });
        }
    }

    setupSocketHandlers() {
        // Handle progress updates from the backend
        this.socket.on('progress_update', (data) => {
            console.log('Progress update received:', data);
            this.updateProgress(data);
        });

        // Handle processing errors
        this.socket.on('processing_error', (data) => {
            console.log('Processing error received:', data);
            this.showError(data.error || 'An error occurred during processing');
            this.resetProcessingButton();
        });

        // Handle processing completion
        this.socket.on('processing_complete', (data) => {
            console.log('Processing complete received:', data);
            this.handleProcessingComplete(data);
        });

        // Handle summary completion
        this.socket.on('summary_complete', (data) => {
            console.log('Summary complete received:', data);
            this.handleSummaryComplete(data);
        });

        // Handle session joined confirmation
        this.socket.on('session_joined', (data) => {
            console.log('Joined session room:', data.session_id);
        });
    }

    handleFileSelect(e) {
        const file = e.target.files[0];
        if (file) {
            this.handleFileSelection(file);
        }
    }

    handleFileSelection(file) {
        // Validate file type
        if (file.type !== 'application/pdf' && !file.name.toLowerCase().endsWith('.pdf')) {
            this.showError('Please select a PDF file.');
            return;
        }

        // Validate file size (50MB limit)
        const maxSize = 50 * 1024 * 1024; // 50MB in bytes
        if (file.size > maxSize) {
            this.showError('File size must be less than 50MB.');
            return;
        }

        this.selectedFile = file;
        this.showFileInfo(file);
    }

    showFileInfo(file) {
        // Show the file info section
        const fileInfoDiv = document.getElementById('file-info');
        const fileNameSpan = document.getElementById('file-name');
        const startBtn = document.getElementById('start-processing');
        
        if (fileInfoDiv) {
            fileInfoDiv.style.display = 'block';
        }
        
        if (fileNameSpan) {
            fileNameSpan.textContent = `${file.name} (${this.formatFileSize(file.size)})`;
        }
        
        if (startBtn) {
            startBtn.style.display = 'inline-block';
            startBtn.disabled = false;
        }

        // Hide the upload area browse button since file is selected
        const browseBtn = document.getElementById('browse-btn');
        if (browseBtn) {
            browseBtn.textContent = 'Change File';
        }

        // Clear any previous errors
        this.clearError();
    }

    updateUploadDescription() {
        const uploadDescription = document.getElementById('upload-description');
        const startBtnText = document.getElementById('start-btn-text');
        
        if (uploadDescription) {
            switch (this.currentMode) {
                case 'ocr':
                    uploadDescription.textContent = 'For scanned PDFs that need OCR text extraction';
                    break;
                case 'direct':
                    uploadDescription.textContent = 'For text-readable PDFs (faster processing - direct to AI summary)';
                    break;
            }
        }

        if (startBtnText) {
            startBtnText.textContent = 'Start Processing';
        }
    }

    startProcessing() {
        if (!this.selectedFile) {
            this.showError('Please select a PDF file first.');
            return;
        }

        const formData = new FormData();
        formData.append('file', this.selectedFile);
        formData.append('mode', this.currentMode);

        // Show progress section
        this.showProgressSection();
        
        // Disable start button
        const startBtn = document.getElementById('start-processing');
        if (startBtn) {
            startBtn.disabled = true;
            startBtn.textContent = 'Processing...';
        }

        // Send file for processing
        fetch('/upload', {
            method: 'POST',
            body: formData
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                this.sessionId = data.session_id;
                this.updateProgress({ step: 'upload', progress: 100, message: 'File uploaded successfully' });
                
                // Join the session room for real-time updates
                this.socket.emit('join_session', { session_id: this.sessionId });
                
                // Now start the actual processing pipeline
                return fetch(`/process/${this.sessionId}`, {
                    method: 'GET'
                });
            } else {
                throw new Error(data.error || 'Failed to upload file');
            }
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                console.log('Processing pipeline started successfully');
                // Processing updates will come through WebSocket
            } else {
                throw new Error(data.message || 'Failed to start processing');
            }
        })
        .catch(error => {
            console.error('Error:', error);
            this.showError(error.message || 'An error occurred while processing the file.');
            this.resetProcessingButton();
        });
    }

    showProgressSection() {
        const processingSection = document.getElementById('processing-section');
        const resultsSection = document.getElementById('results-section');
        
        if (processingSection) {
            processingSection.style.display = 'block';
        }
        
        if (resultsSection) {
            resultsSection.style.display = 'none';
        }

        // Reset all progress indicators and hide unnecessary steps for direct mode
        this.resetProgressIndicators();
        this.updateProgressVisibility();
    }

    updateProgressVisibility() {
        // Hide unnecessary steps for direct upload mode
        if (this.currentMode === 'direct') {
            // Hide OCR-related steps for direct upload
            const stepsToHide = ['splitting', 'ocr', 'merging'];
            stepsToHide.forEach(step => {
                const stepElement = document.querySelector(`#${step}-status`).closest('.processing-step');
                if (stepElement) {
                    stepElement.style.display = 'none';
                }
            });
            
            // Show only text extraction step
            const textExtractionStep = document.querySelector('#text-extraction-status').closest('.processing-step');
            if (textExtractionStep) {
                textExtractionStep.style.display = 'block';
                // Update the step title for direct mode
                const stepTitle = textExtractionStep.querySelector('h6');
                if (stepTitle) {
                    stepTitle.innerHTML = '<i class="fas fa-database me-2"></i>Step 1: Extracting Text & Creating Vector Database';
                }
            }
        } else {
            // Show all steps for OCR mode
            const allSteps = ['splitting', 'ocr', 'merging', 'text-extraction'];
            allSteps.forEach(step => {
                const stepElement = document.querySelector(`#${step}-status`).closest('.processing-step');
                if (stepElement) {
                    stepElement.style.display = 'block';
                }
            });
            
            // Reset text extraction title for OCR mode
            const textExtractionStep = document.querySelector('#text-extraction-status').closest('.processing-step');
            if (textExtractionStep) {
                const stepTitle = textExtractionStep.querySelector('h6');
                if (stepTitle) {
                    stepTitle.innerHTML = '<i class="fas fa-database me-2"></i>Step 4: Creating Vector Database';
                }
            }
        }
    }

    resetProgressIndicators() {
        // Reset all step statuses to waiting
        const steps = ['splitting', 'ocr', 'merging', 'text-extraction'];
        steps.forEach(step => {
            const status = document.getElementById(`${step}-status`);
            const progress = document.getElementById(`${step}-progress`);
            const message = document.getElementById(`${step}-message`);
            
            if (status) {
                status.textContent = 'Waiting';
                status.className = 'badge bg-secondary';
            }
            if (progress) {
                progress.style.width = '0%';
            }
            if (message) {
                message.textContent = 'Waiting to start...';
            }
        });
    }

    updateProgress(data) {
        // Map the step names to match the HTML IDs
        const stepMapping = {
            'splitting': 'splitting',
            'ocr': 'ocr', 
            'merging': 'merging',
            'text_extraction': 'text-extraction',
            'upload': 'splitting' // Map upload to splitting for initial display
        };
        
        const step = stepMapping[data.step] || data.step;
        
        if (step && step !== 'complete') {
            const status = document.getElementById(`${step}-status`);
            const progress = document.getElementById(`${step}-progress`);
            const message = document.getElementById(`${step}-message`);
            
            if (status) {
                if (data.progress === 100) {
                    status.textContent = 'Complete';
                    status.className = 'badge bg-success';
                } else {
                    status.textContent = 'Processing';
                    status.className = 'badge bg-primary';
                }
            }
            
            if (progress) {
                progress.style.width = `${data.progress}%`;
                progress.className = data.progress === 100 ? 'progress-bar bg-success' : 'progress-bar bg-primary';
            }
            
            if (message) {
                message.textContent = data.message || `Processing ${step}...`;
            }
        }
    }

    handleProcessingComplete(data) {
        const resultsSection = document.getElementById('results-section');
        const downloadBtn = document.getElementById('download-btn');
        const summaryBtn = document.getElementById('summarize-btn');
        
        if (resultsSection) {
            resultsSection.style.display = 'block';
        }
        
        if (downloadBtn) {
            downloadBtn.onclick = () => this.downloadProcessedFile(data.session_id);
        }
        
        if (summaryBtn) {
            summaryBtn.onclick = () => this.showSummarySection();
        }

        // Mark all steps as complete
        const steps = ['splitting', 'ocr', 'merging', 'text-extraction'];
        steps.forEach(step => {
            const status = document.getElementById(`${step}-status`);
            const progress = document.getElementById(`${step}-progress`);
            const message = document.getElementById(`${step}-message`);
            
            if (status) {
                status.textContent = 'Complete';
                status.className = 'badge bg-success';
            }
            if (progress) {
                progress.style.width = '100%';
                progress.className = 'progress-bar bg-success';
            }
            if (message) {
                message.textContent = 'Completed successfully';
            }
        });
        
        // Reset start button
        this.resetProcessingButton();
    }

    handleSummaryComplete(data) {
        const progressContainer = document.getElementById('summary-progress-container');
        const resultContainer = document.getElementById('summary-result');
        const summaryText = document.getElementById('summary-text');
        
        if (progressContainer) {
            progressContainer.style.display = 'none';
        }
        
        if (data.summary && summaryText) {
            summaryText.innerHTML = data.summary.replace(/\n/g, '<br>');
        }
        
        if (resultContainer) {
            resultContainer.style.display = 'block';
        }
    }

    resetProcessingButton() {
        const startBtn = document.getElementById('start-processing');
        if (startBtn) {
            startBtn.disabled = false;
            startBtn.textContent = this.currentMode === 'quick-summary' ? 'Generate Summary' : 'Start Processing';
        }
    }

    showSummarySection() {
        const summarySection = document.getElementById('summary-section');
        if (summarySection) {
            summarySection.style.display = 'block';
        }
        
        // Set up the generate summary button
        const generateBtn = document.getElementById('generate-summary-btn');
        if (generateBtn) {
            generateBtn.onclick = () => this.generateSummary();
        }
    }

    generateSummary() {
        if (!this.sessionId) {
            this.showError('No processed file available. Please process a PDF first.');
            return;
        }

        const customPrompt = document.getElementById('custom-prompt').value;
        const generateBtn = document.getElementById('generate-summary-btn');
        const progressContainer = document.getElementById('summary-progress-container');
        const resultContainer = document.getElementById('summary-result');
        const summaryText = document.getElementById('summary-text');
        
        if (generateBtn) {
            generateBtn.disabled = true;
            generateBtn.innerHTML = '<i class="fas fa-spinner fa-spin me-2"></i>Generating...';
        }
        
        if (progressContainer) {
            progressContainer.style.display = 'block';
        }
        
        if (resultContainer) {
            resultContainer.style.display = 'none';
        }

        fetch(`/summarize/${this.sessionId}`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                prompt: customPrompt
            })
        })
        .then(response => response.json())
        .then(data => {
            if (progressContainer) {
                progressContainer.style.display = 'none';
            }
            
            if (data.success) {
                if (summaryText) {
                    summaryText.innerHTML = data.summary.replace(/\n/g, '<br>');
                }
                if (resultContainer) {
                    resultContainer.style.display = 'block';
                }
            } else {
                this.showError(data.error || 'Failed to generate summary');
            }
        })
        .catch(error => {
            console.error('Error:', error);
            this.showError('An error occurred while generating the summary.');
            if (progressContainer) {
                progressContainer.style.display = 'none';
            }
        })
        .finally(() => {
            if (generateBtn) {
                generateBtn.disabled = false;
                generateBtn.innerHTML = '<i class="fas fa-magic me-2"></i>Generate Summary';
            }
        });
    }

    downloadProcessedFile(sessionId) {
        if (sessionId) {
            window.location.href = `/download/${sessionId}`;
        }
    }

    resetUI() {
        // Clear selected file
        this.selectedFile = null;
        this.sessionId = null;
        
        // Reset file input
        const fileInput = document.getElementById('file-input');
        if (fileInput) {
            fileInput.value = '';
        }
        
        // Reset upload area text
        const uploadTitle = document.getElementById('upload-title');
        const browseBtn = document.getElementById('browse-btn');
        
        if (uploadTitle) {
            uploadTitle.textContent = 'Drop your PDF file here or click to browse';
        }
        
        if (browseBtn) {
            browseBtn.innerHTML = '<i class="fas fa-folder-open me-2"></i>Browse Files';
        }
        
        // Hide file info section
        const fileInfoDiv = document.getElementById('file-info');
        if (fileInfoDiv) {
            fileInfoDiv.style.display = 'none';
        }
        
        // Hide processing elements
        const processingSection = document.getElementById('processing-section');
        const resultsSection = document.getElementById('results-section');
        const summarySection = document.getElementById('summary-section');
        
        if (processingSection) {
            processingSection.style.display = 'none';
        }
        
        if (resultsSection) {
            resultsSection.style.display = 'none';
        }
        
        if (summarySection) {
            summarySection.style.display = 'none';
        }
        
        // Clear any errors
        this.clearError();
    }

    showError(message) {
        const errorSection = document.getElementById('error-section');
        const errorMessage = document.getElementById('error-message');
        
        if (errorSection) {
            errorSection.style.display = 'block';
        }
        
        if (errorMessage) {
            errorMessage.textContent = message;
        }
    }

    clearError() {
        const errorSection = document.getElementById('error-section');
        
        if (errorSection) {
            errorSection.style.display = 'none';
        }
    }

    formatFileSize(bytes) {
        if (bytes === 0) return '0 Bytes';
        const k = 1024;
        const sizes = ['Bytes', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
    }
}

// Initialize the app when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    new PDFApp();
});