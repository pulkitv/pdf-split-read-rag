import os
import uuid
from flask import Flask, render_template, request, jsonify, send_file, url_for, session
from flask_socketio import SocketIO, emit, join_room, leave_room
from werkzeug.utils import secure_filename
import threading
from pdf_processor import PDFProcessor
from rag_system import RAGSystem
from voiceover_system import VoiceoverSystem
from dotenv import load_dotenv
import json
import zipfile
from datetime import datetime
import re  # Add regex import for API filename processing

# Load environment variables
load_dotenv()

app = Flask(__name__)

# Configure Flask using environment variables
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'fallback-secret-key-change-this')
app.config['UPLOAD_FOLDER'] = os.getenv('UPLOAD_FOLDER', 'uploads')
app.config['TEMP_FOLDER'] = os.getenv('TEMP_FOLDER', 'temp')
app.config['PROCESSED_FOLDER'] = os.getenv('PROCESSED_FOLDER', 'processed')

# Configure Flask URL generation for background threads
app.config['SERVER_NAME'] = os.getenv('SERVER_NAME', 'localhost:5000')
app.config['APPLICATION_ROOT'] = os.getenv('APPLICATION_ROOT', '/')
app.config['PREFERRED_URL_SCHEME'] = os.getenv('PREFERRED_URL_SCHEME', 'http')

# Configure file upload limits from environment
app.config['MAX_CONTENT_LENGTH'] = int(os.getenv('MAX_CONTENT_LENGTH', 52428800))
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = int(os.getenv('SEND_FILE_MAX_AGE_DEFAULT', 0))

# Session configuration from environment
app.config['PERMANENT_SESSION_LIFETIME'] = int(os.getenv('PERMANENT_SESSION_LIFETIME', 3600))
app.config['SESSION_COOKIE_SECURE'] = os.getenv('SESSION_COOKIE_SECURE', 'false').lower() == 'true'
app.config['SESSION_COOKIE_HTTPONLY'] = os.getenv('SESSION_COOKIE_HTTPONLY', 'true').lower() == 'true'
app.config['SESSION_COOKIE_SAMESITE'] = os.getenv('SESSION_COOKIE_SAMESITE', 'Lax')

# Initialize SocketIO with enhanced configuration for long-running processes
socketio = SocketIO(
    app, 
    cors_allowed_origins=os.getenv('SOCKETIO_CORS_ALLOWED_ORIGINS', "*"),
    max_http_buffer_size=int(os.getenv('SOCKETIO_MAX_HTTP_BUFFER_SIZE', 52428800)),
    ping_timeout=int(os.getenv('SOCKETIO_PING_TIMEOUT', 300)),  # Increased to 5 minutes
    ping_interval=int(os.getenv('SOCKETIO_PING_INTERVAL', 25)),  # More frequent pings
    engineio_logger=True,  # Enable logging for debugging
    logger=True  # Enable SocketIO logging
)

# Initialize processors
pdf_processor = PDFProcessor(
    upload_folder=app.config['UPLOAD_FOLDER'],
    temp_folder=app.config['TEMP_FOLDER'],
    processed_folder=app.config['PROCESSED_FOLDER']
)

rag_system = RAGSystem()
voiceover_system = VoiceoverSystem()

# Store processing sessions
processing_sessions = {}

@app.route('/')
def index():
    """Main page with upload interface"""
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_file():
    """Handle PDF file upload"""
    if 'file' not in request.files:
        return jsonify({'error': 'No file selected'}), 400
    
    file = request.files['file']
    if file.filename == '' or file.filename is None:
        return jsonify({'error': 'No file selected'}), 400
    
    # Get processing mode from form data
    processing_mode = request.form.get('mode', 'ocr')  # Default to OCR mode
    
    # Check file extension using environment config
    allowed_extensions = os.getenv('ALLOWED_EXTENSIONS', 'pdf').split(',')
    if not any(file.filename.lower().endswith(f'.{ext.strip()}') for ext in allowed_extensions):
        return jsonify({'error': f'Please upload a {", ".join(allowed_extensions).upper()} file'}), 400
    
    # Check file size using environment config
    max_size_mb = int(os.getenv('MAX_FILE_SIZE_MB', 50))
    if file.content_length and file.content_length > max_size_mb * 1024 * 1024:
        return jsonify({'error': f'File size must be less than {max_size_mb}MB'}), 400
    
    # Generate unique session ID
    session_id = str(uuid.uuid4())
    filename = secure_filename(file.filename)
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], f"{session_id}_{filename}")
    
    file.save(filepath)
    
    # Store session info with processing mode
    processing_sessions[session_id] = {
        'filename': filename,
        'filepath': filepath,
        'status': 'uploaded',
        'mode': processing_mode,
        'progress': {
            'splitting': 0,
            'ocr': 0,
            'merging': 0,
            'text_extraction': 0,
            'summarization': 0
        }
    }
    
    return jsonify({
        'success': True,
        'session_id': session_id,
        'filename': filename,
        'mode': processing_mode
    })

@app.route('/debug/<session_id>')
def debug_session(session_id):
    """Debug endpoint to check session status"""
    print(f"=== DEBUG ENDPOINT CALLED ===")
    print(f"Session ID: {session_id}")
    print(f"All sessions: {list(processing_sessions.keys())}")
    
    if session_id in processing_sessions:
        session_data = processing_sessions[session_id]
        print(f"Session found: {session_data}")
        return jsonify({
            'found': True,
            'session_data': session_data,
            'all_sessions': list(processing_sessions.keys())
        })
    else:
        print(f"Session NOT found!")
        return jsonify({
            'found': False,
            'session_id': session_id,
            'all_sessions': list(processing_sessions.keys())
        })

@app.route('/process/<session_id>')
def process_pdf(session_id):
    """Start PDF processing pipeline"""
    print(f"=== PROCESSING REQUEST RECEIVED ===")
    print(f"Session ID: {session_id}")
    print(f"Available sessions: {list(processing_sessions.keys())}")
    
    if session_id not in processing_sessions:
        print(f"ERROR: Session {session_id} not found in processing_sessions")
        return jsonify({'error': 'Invalid session ID'}), 404
    
    session = processing_sessions[session_id]
    processing_mode = session.get('mode', 'ocr')
    
    print(f"Session found: {session}")
    print(f"Processing mode: {processing_mode}")
    print(f"Starting background thread for session {session_id}")
    
    # Choose processing pipeline based on mode
    if processing_mode == 'direct':
        thread = threading.Thread(target=process_direct_upload_pipeline, args=(session_id,))
    else:
        thread = threading.Thread(target=process_pdf_pipeline, args=(session_id,))
    
    thread.daemon = True
    thread.start()
    
    print(f"Background thread started successfully for session {session_id}")
    return jsonify({'success': True, 'message': 'Processing started'})

def process_pdf_pipeline(session_id):
    """Main processing pipeline"""
    import sys
    print(f"=== PROCESSING PIPELINE START for session {session_id} ===", flush=True)
    try:
        with app.app_context():  # Add Flask application context
            session = processing_sessions[session_id]
            filepath = session['filepath']
            
            print(f"Starting processing pipeline for session {session_id}", flush=True)
            print(f"File path: {filepath}", flush=True)
            print(f"File exists: {os.path.exists(filepath)}", flush=True)
            
            # Step 1: Split PDF
            print(f"=== STEP 1: SPLITTING PDF ===", flush=True)
            socketio.emit('progress_update', {
                'session_id': session_id,
                'step': 'splitting',
                'progress': 0,
                'message': 'Starting PDF splitting...'
            }, to=session_id)
            
            def splitting_progress_callback(progress):
                try:
                    message = f'Splitting PDF pages... ({progress}%)'
                    if progress >= 100:
                        message = 'PDF splitting completed!'
                    
                    print(f"Splitting Progress Debug - Progress: {progress}%, Message: {message}", flush=True)
                    
                    socketio.emit('progress_update', {
                        'session_id': session_id,
                        'step': 'splitting',
                        'progress': progress,
                        'message': message
                    }, to=session_id)
                    
                    # Add small delay to make progress visible
                    import time
                    time.sleep(0.1)
                except Exception as e:
                    print(f"Error in splitting progress callback: {e}", flush=True)
            
            print(f"Calling pdf_processor.split_pdf with filepath: {filepath}", flush=True)
            split_files = pdf_processor.split_pdf(filepath, session_id, 
                                                progress_callback=splitting_progress_callback)
            print(f"PDF splitting completed: {len(split_files)} pages", flush=True)
            print(f"Split files: {split_files[:3]}..." if len(split_files) > 3 else f"Split files: {split_files}", flush=True)
            
            # Step 2: OCR Processing
            print(f"=== STEP 2: OCR PROCESSING ===", flush=True)
            socketio.emit('progress_update', {
                'session_id': session_id,
                'step': 'ocr',
                'progress': 0,
                'message': 'Starting OCR processing - converting pages to images...'
            }, to=session_id)
            
            # Get total pages for better progress tracking
            from pypdf import PdfReader
            reader = PdfReader(filepath)
            total_files = len(reader.pages)
            print(f"Total pages for OCR: {total_files}", flush=True)
            
            def ocr_progress_callback(progress):
                try:
                    # Calculate which page we're currently processing
                    current_page = min(int(progress / (100 / total_files)) + 1, total_files)
                    
                    # Calculate progress within the current page (0-100%)
                    page_progress = (progress % (100 / total_files)) * total_files if total_files > 1 else progress
                    
                    # Determine what sub-step we're in based on page progress
                    if page_progress < 25:
                        message = f'Converting page {current_page}/{total_files} to image... ({progress}%)'
                    elif page_progress < 50:
                        message = f'Resizing page {current_page}/{total_files} for OCR... ({progress}%)'
                    elif page_progress < 75:
                        message = f'Running OCR on page {current_page}/{total_files}... ({progress}%)'
                    elif page_progress < 95:
                        if progress >= 100:
                            message = f'OCR processing complete for all {total_files} pages! ({progress}%)'
                        else:
                            message = f'Completing page {current_page}/{total_files}... ({progress}%)'
                    
                    print(f"OCR Progress Debug - Page: {current_page}/{total_files}, Progress: {progress}%, Page Progress: {page_progress}%, Message: {message}", flush=True)
                    
                    socketio.emit('progress_update', {
                        'session_id': session_id,
                        'step': 'ocr',
                        'progress': progress,
                        'message': message
                    }, to=session_id)
                except Exception as e:
                    print(f"Error in OCR progress callback: {e}", flush=True)
            
            print(f"Calling pdf_processor.process_ocr with {len(split_files)} files", flush=True)
            ocr_files = pdf_processor.process_ocr(split_files, session_id,
                                                progress_callback=ocr_progress_callback)
            print(f"OCR processing completed: {len(ocr_files)} files processed", flush=True)
            
            # Step 3: Merge PDFs
            print(f"=== STEP 3: MERGING PDFS ===", flush=True)
            socketio.emit('progress_update', {
                'session_id': session_id,
                'step': 'merging',
                'progress': 0,
                'message': 'Starting PDF merging...'
            }, to=session_id)
            
            def merging_progress_callback(progress):
                try:
                    message = f'Merging pages... ({progress}%)'
                    print(f"Merging Progress Debug - Progress: {progress}%, Message: {message}", flush=True)
                    socketio.emit('progress_update', {
                        'session_id': session_id,
                        'step': 'merging',
                        'progress': progress,
                        'message': message
                    }, to=session_id)
                except Exception as e:
                    print(f"Error in merging progress callback: {e}", flush=True)
            
            print(f"Calling pdf_processor.merge_pdfs with {len(ocr_files)} files", flush=True)
            merged_file = pdf_processor.merge_pdfs(ocr_files, session_id,
                                                 progress_callback=merging_progress_callback)
            print(f"PDF merging completed: {merged_file}", flush=True)
            
            # Step 4: Text Extraction and Vector Storage
            print(f"=== STEP 4: TEXT EXTRACTION ===", flush=True)
            socketio.emit('progress_update', {
                'session_id': session_id,
                'step': 'text-extraction',
                'progress': 0,
                'message': 'Extracting text and creating vector database...'
            }, to=session_id)
            
            # Extract text from the OCR processed files
            print(f"Extracting text from {len(ocr_files)} OCR files", flush=True)
            extracted_text = pdf_processor.extract_text_from_pdfs(ocr_files)
            print(f"Text extraction completed: {len(extracted_text)} text chunks", flush=True)
            
            # Create vector database
            print(f"Creating vector database", flush=True)
            def text_extraction_progress_callback(progress):
                try:
                    message = f'Creating vector database... ({progress}%)'
                    print(f"Text Extraction Progress Debug - Progress: {progress}%, Message: {message}", flush=True)
                    socketio.emit('progress_update', {
                        'session_id': session_id,
                        'step': 'text-extraction',
                        'progress': progress,
                        'message': message
                    }, to=session_id)
                except Exception as e:
                    print(f"Error in text extraction progress callback: {e}", flush=True)
                    
            rag_system.create_vector_db(extracted_text, session_id,
                                      progress_callback=text_extraction_progress_callback)
            print(f"Vector database creation completed", flush=True)
            
            # Update session with results
            session['merged_file'] = merged_file
            session['text_content'] = extracted_text
            session['status'] = 'completed'
            
            # Clean up temporary files
            print(f"Cleaning up temporary files", flush=True)
            pdf_processor.cleanup_temp_files(session_id)
            print(f"Cleanup completed for session {session_id}", flush=True)
            
            # Generate download URL within app context
            download_url = url_for('download_file', session_id=session_id)
            
            # Send final completion notification
            print(f"Sending completion notification for session {session_id}", flush=True)
            socketio.emit('processing_complete', {
                'session_id': session_id,
                'merged_file_url': download_url,
                'message': 'Processing completed successfully! Your document is ready for download and summarization.'
            }, to=session_id)
            print(f"=== PROCESSING PIPELINE COMPLETED for session {session_id} ===", flush=True)
        
    except Exception as e:
        print(f"=== PROCESSING ERROR for session {session_id} ===", flush=True)
        print(f"Error type: {type(e).__name__}", flush=True)
        print(f"Error message: {str(e)}", flush=True)
        import traceback
        print("Full traceback:", flush=True)
        traceback.print_exc()
        
        try:
            socketio.emit('processing_error', {
                'session_id': session_id,
                'error': str(e)
            }, to=session_id)
        except Exception as emit_error:
            print(f"Error emitting error message: {emit_error}", flush=True)
        
        # Clean up on error
        try:
            pdf_processor.cleanup_temp_files(session_id)
        except Exception as cleanup_error:
            print(f"Error during cleanup: {str(cleanup_error)}", flush=True)
            pass

def process_direct_upload_pipeline(session_id):
    """Direct upload pipeline for text-readable PDFs"""
    import sys
    print(f"=== DIRECT UPLOAD PIPELINE START for session {session_id} ===", flush=True)
    try:
        with app.app_context():
            session = processing_sessions[session_id]
            filepath = session['filepath']
            
            print(f"Starting direct upload pipeline for session {session_id}", flush=True)
            print(f"File path: {filepath}", flush=True)
            print(f"File exists: {os.path.exists(filepath)}", flush=True)
            
            # Step 1: Direct text extraction from text-readable PDF
            print(f"=== STEP 1: DIRECT TEXT EXTRACTION ===", flush=True)
            socketio.emit('progress_update', {
                'session_id': session_id,
                'step': 'text-extraction',
                'progress': 0,
                'message': 'Extracting text from PDF...'
            }, to=session_id)
            
            def text_extraction_progress_callback(progress):
                try:
                    if progress <= 50:
                        message = f'Reading PDF content... ({progress}%)'
                    else:
                        message = f'Creating vector database... ({progress}%)'
                    
                    print(f"Direct Text Extraction Progress - Progress: {progress}%, Message: {message}", flush=True)
                    
                    socketio.emit('progress_update', {
                        'session_id': session_id,
                        'step': 'text-extraction',
                        'progress': progress,
                        'message': message
                    }, to=session_id)
                except Exception as e:
                    print(f"Error in direct text extraction progress callback: {e}", flush=True)
            
            # Extract text directly from the uploaded PDF
            extracted_text = pdf_processor.extract_text_from_single_pdf(filepath, 
                                                                       progress_callback=text_extraction_progress_callback)
            print(f"Text extraction completed: {len(extracted_text)} characters", flush=True)
            
            # Format the text data for the RAG system (expects list of dicts with 'content' and 'file' keys)
            formatted_text_data = [{
                'file': session['filename'],
                'content': extracted_text
            }]
            
            # Create vector database for RAG
            print(f"Creating vector database for direct upload", flush=True)
            rag_system.create_vector_db(formatted_text_data, session_id,
                                      progress_callback=text_extraction_progress_callback)
            print(f"Vector database creation completed", flush=True)
            
            # Update session with results
            session['text_content'] = formatted_text_data
            session['status'] = 'completed'
            session['merged_file'] = filepath  # Use original file as "processed" file
            
            # Send completion notification
            print(f"Sending completion notification for direct upload session {session_id}", flush=True)
            socketio.emit('processing_complete', {
                'session_id': session_id,
                'merged_file_url': url_for('download_file', session_id=session_id),
                'message': 'PDF processed successfully! Ready for AI summarization.',
                'direct_upload_mode': True
            }, to=session_id)
            print(f"=== DIRECT UPLOAD PIPELINE COMPLETED for session {session_id} ===", flush=True)
        
    except Exception as e:
        print(f"=== DIRECT UPLOAD ERROR for session {session_id} ===", flush=True)
        print(f"Error type: {type(e).__name__}", flush=True)
        print(f"Error message: {str(e)}", flush=True)
        import traceback
        print("Full traceback:", flush=True)
        traceback.print_exc()
        
        try:
            socketio.emit('processing_error', {
                'session_id': session_id,
                'error': str(e)
            }, to=session_id)
        except Exception as emit_error:
            print(f"Error emitting error message: {emit_error}", flush=True)

def update_progress(session_id, step, progress, message=None):
    """Update progress for a specific step with enhanced WebSocket handling"""
    with app.app_context():  # Ensure Flask context for all progress updates
        if session_id in processing_sessions:
            processing_sessions[session_id]['progress'][step] = progress
            
            # Prepare progress update data
            progress_data = {
                'session_id': session_id,
                'step': step,
                'progress': progress
            }
            
            # Add message if provided
            if message:
                progress_data['message'] = message
            
            # Send progress update with correct Flask-SocketIO syntax
            print(f"Emitting progress update: {progress_data}")
            socketio.emit('progress_update', progress_data, to=session_id)

@app.route('/download/<session_id>')
def download_file(session_id):
    """Download the processed PDF file"""
    if session_id not in processing_sessions:
        return jsonify({'error': 'Invalid session ID'}), 404
    
    session = processing_sessions[session_id]
    if 'merged_file' not in session:
        return jsonify({'error': 'File not ready for download'}), 400
    
    return send_file(session['merged_file'], as_attachment=True, 
                    download_name=f"processed_{session['filename']}")

@app.route('/summarize/<session_id>', methods=['POST'])
def summarize_document(session_id):
    """Generate AI summary of the document"""
    if session_id not in processing_sessions:
        return jsonify({'error': 'Invalid session ID'}), 404
    
    # Be tolerant to missing/invalid JSON
    data = request.get_json(silent=True) or {}
    custom_prompt = data.get('prompt', '')
    
    try:
        socketio.emit('progress_update', {
            'session_id': session_id,
            'step': 'summarization',
            'progress': 0,
            'message': 'Generating AI summary...'
        }, to=session_id)
        
        summary = rag_system.generate_summary(session_id, custom_prompt,
                                            progress_callback=lambda p: update_progress(session_id, 'summarization', p))
        
        socketio.emit('summary_complete', {
            'session_id': session_id,
            'summary': summary
        }, to=session_id)
        
        return jsonify({'success': True, 'summary': summary})
        
    except Exception as e:
        # Inform UI about the failure as well
        try:
            socketio.emit('summary_error', {
                'session_id': session_id,
                'error': str(e)
            }, to=session_id)
        except Exception:
            pass
        return jsonify({'error': str(e)}), 500

@app.route('/generate-voiceover', methods=['POST'])
def generate_voiceover():
    try:
        data = request.get_json()
        text = data.get('text', '').strip()
        voice = data.get('voice', 'nova')
        speed = float(data.get('speed', 1.0))
        format_type = data.get('format', 'mp3')
        background_image = data.get('background_image', '')
        
        if not text:
            return jsonify({'success': False, 'error': 'No text provided'})
        
        # Generate voiceover with PORTRAIT format for YouTube Shorts
        result = voiceover_system.generate_speech(
            text=text,
            voice=voice,
            speed=speed,
            format=format_type,
            session_id=session.get('session_id'),
            background_image_path=background_image if background_image else None,
            generation_type='shorts'  # Portrait format for YouTube Shorts Generator
        )
        
        return jsonify(result)
        
    except Exception as e:
        print(f"Error generating voiceover: {str(e)}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/generate-voiceover/standalone', methods=['POST'])
def generate_voiceover_standalone():
    """Standalone voiceover generation endpoint for direct text-to-speech conversion"""
    try:
        data = request.get_json()
        text = data.get('text', '').strip()
        voice = data.get('voice', 'nova')
        speed = float(data.get('speed', 1.0))
        format_type = data.get('format', 'mp3')
        background_image = data.get('background_image', '')
        
        if not text:
            return jsonify({'success': False, 'error': 'No text provided'})
        
        # Generate voiceover with REGULAR format for Standalone AI Voiceover Generator
        result = voiceover_system.generate_speech(
            text=text,
            voice=voice,
            speed=speed,
            format=format_type,
            session_id=None,  # No session needed for standalone
            background_image_path=background_image if background_image else None,
            generation_type='regular'  # Regular format (landscape) for Standalone Generator
        )
        
        return jsonify(result)
        
    except Exception as e:
        print(f"Error generating standalone voiceover: {str(e)}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/download-voiceover/<filename>')
def download_voiceover(filename):
    """Download or stream generated voiceover file. Inline by default; force download with ?dl=1. Optional ?name=Custom Title to set download filename (first line of script)."""
    try:
        voiceover_folder = voiceover_system.output_folder
        file_path = os.path.join(voiceover_folder, filename)
        
        if not os.path.exists(file_path):
            return jsonify({'error': 'File not found'}), 404
        
        # Get file info (basic file stats since get_file_info method doesn't exist)
        file_stat = os.stat(file_path)
        file_info = {
            'filename': filename,
            'size': file_stat.st_size,
            'modified': file_stat.st_mtime
        }
        
        # Determine mimetype based on format
        mimetype = 'audio/mpeg'  # Default for MP3
        if filename.endswith('.wav'):
            mimetype = 'audio/wav'
        elif filename.endswith('.mp4'):
            mimetype = 'video/mp4'
        elif filename.endswith('.zip'):
            mimetype = 'application/zip'
        
        # Determine disposition and download name
        dl = request.args.get('dl', '').lower() in ('1', 'true', 'yes')
        suggested_name = None
        if dl:
            base = request.args.get('name', '')
            base = secure_filename(base) if base else os.path.splitext(filename)[0]
            if not base:
                base = 'voiceover'
            ext = os.path.splitext(filename)[1]
            suggested_name = f"{base}{ext}"
        
        return send_file(
            file_path,
            as_attachment=dl,
            download_name=suggested_name,
            mimetype=mimetype
        )
        
    except Exception as e:
        print(f"Error downloading voiceover: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/voiceovers/download-all', methods=['GET'])
def download_all_voiceovers():
    """Download all generated voiceover files as a zip archive."""
    try:
        base = voiceover_system.output_folder
        os.makedirs(base, exist_ok=True)
        allowed_exts = {'.mp3', '.wav', '.mp4', '.zip', '.srt'}
        
        # Collect all voiceover files
        files_to_zip = []
        for name in os.listdir(base):
            if not name or name.startswith('.'):
                continue
            path = os.path.join(base, name)
            if not os.path.isfile(path):
                continue
            ext = os.path.splitext(name)[1].lower()
            if ext not in allowed_exts:
                continue
            files_to_zip.append((name, path))
        
        if not files_to_zip:
            return jsonify({'error': 'No voiceover files found'}), 404
        
        # Create a temporary zip file
        import tempfile
        with tempfile.NamedTemporaryFile(suffix='.zip', delete=False) as temp_zip:
            temp_zip_path = temp_zip.name
        
        # Create zip with all voiceover files
        with zipfile.ZipFile(temp_zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
            for filename, filepath in files_to_zip:
                try:
                    zf.write(filepath, filename)
                except Exception as e:
                    print(f"Error adding {filename} to zip: {e}")
                    continue
        
        # Generate download filename with current date
        today_str = datetime.now().strftime('%Y-%m-%d')
        download_name = f"all_voiceovers_{today_str}.zip"
        
        # Send the zip file and clean up
        def remove_temp_file(response):
            try:
                os.unlink(temp_zip_path)
            except Exception:
                pass
            return response
        
        response = send_file(
            temp_zip_path,
            as_attachment=True,
            download_name=download_name,
            mimetype='application/zip'
        )
        
        # Schedule cleanup after response is sent
        import atexit
        atexit.register(lambda: os.path.exists(temp_zip_path) and os.unlink(temp_zip_path))
        
        return response
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/status/<session_id>')
def get_status(session_id):
    """Get current processing status"""
    if session_id not in processing_sessions:
        return jsonify({'error': 'Invalid session ID'}), 404
    
    session = processing_sessions[session_id]
    return jsonify({
        'status': session['status'],
        'progress': session['progress'],
        'filename': session['filename']
    })

@app.route('/vector-stats/<session_id>')
def vector_stats(session_id):
    """Get vector DB stats for a session"""
    if session_id not in processing_sessions:
        return jsonify({'error': 'Invalid session ID'}), 404
    try:
        stats = rag_system.get_document_stats(session_id)
        return jsonify(stats)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/search/<session_id>', methods=['POST'])
def search_documents(session_id):
    """Semantic search within a processed document"""
    if session_id not in processing_sessions:
        return jsonify({'error': 'Invalid session ID'}), 404
    data = request.get_json(silent=True) or {}
    query = data.get('query', '')
    n = int(data.get('n', 5))
    if not query.strip():
        return jsonify({'error': 'Query is required'}), 400
    try:
        results = rag_system.search_documents(session_id, query, max_results=n)
        return jsonify({'results': results})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/generate-shorts', methods=['POST'])
def generate_shorts():
    """Generate multiple portrait MP4 voiceover videos from a single script using pause markers."""
    # Parse JSON or multipart
    def parse_payload():
        content_type = request.content_type or ''
        if 'multipart/form-data' in content_type:
            form = request.form
            files = request.files
            return {
                'script': form.get('script', ''),
                'voice': form.get('voice', 'nova'),
                'speed': float(form.get('speed', 1.0)),
                'background_file': files.get('backgroundImage') if files else None
            }
        else:
            data = request.get_json(silent=True) or {}
            return {
                'script': data.get('script', ''),
                'voice': data.get('voice', 'nova'),
                'speed': float(data.get('speed', 1.0)),
                'background_file': None
            }

    payload = parse_payload()
    script = (payload['script'] or '').strip()
    if not script:
        return jsonify({'error': 'Script is required'}), 400

    voice = payload['voice']
    speed = payload['speed']
    bg_file = payload['background_file']

    # Generate a unique session ID for progress tracking
    shorts_session_id = str(uuid.uuid4())
    
    print(f"=== YOUTUBE SHORTS GENERATION START ===")
    print(f"Shorts Session ID: {shorts_session_id}")
    print(f"Script length: {len(script)} characters")
    print(f"Voice: {voice}, Speed: {speed}")

    temp_bg_path = None
    try:
        # Emit initial progress
        socketio.emit('progress_update', {
            'session_id': shorts_session_id,
            'step': 'shorts-generation',
            'progress': 0,
            'message': 'Preparing script for YouTube Shorts generation...'
        })

        if (bg_file and getattr(bg_file, 'filename', '')):
            os.makedirs(app.config['TEMP_FOLDER'], exist_ok=True)
            bg_name = secure_filename(bg_file.filename)
            temp_bg_path = os.path.join(app.config['TEMP_FOLDER'], f"bg_{uuid.uuid4()}_{bg_name}")
            bg_file.save(temp_bg_path)
            print(f"Background image saved: {temp_bg_path}")

        # Split the script by pause markers into shorts segments
        def split_into_scripts(script_text):
            """Split script into segments using pause markers like [PAUSE] or line breaks"""
            # Split by [PAUSE] markers first
            segments = []
            if '— pause —' in script_text:
                parts = script_text.split('— pause —')
            else:
                # Fallback to splitting by double line breaks
                parts = script_text.split('\n\n')
            
            for part in parts:
                cleaned = part.strip()
                if cleaned:
                    segments.append(cleaned)
            
            return segments
        
        segments = split_into_scripts(script)
        if not segments:
            socketio.emit('processing_error', {
                'session_id': shorts_session_id,
                'error': 'No segments found in script'
            })
            return jsonify({'error': 'No segments found in script'}), 400

        print(f"Split script into {len(segments)} segments")
        
        # Emit progress for script splitting
        socketio.emit('progress_update', {
            'session_id': shorts_session_id,
            'step': 'shorts-generation',
            'progress': 10,
            'message': f'Script split into {len(segments)} shorts segments. Starting video generation...'
        })

        # Generate a portrait MP4 for each segment
        outputs = []
        file_paths = []  # list of tuples (idx, path, actual_download_name)
        
        for idx, seg in enumerate(segments, start=1):
            # Calculate progress for this segment
            segment_progress = 10 + (idx - 1) * (70 / len(segments))
            
            socketio.emit('progress_update', {
                'session_id': shorts_session_id,
                'step': 'shorts-generation',
                'progress': int(segment_progress),
                'message': f'Generating video {idx} of {len(segments)}...'
            })
            
            print(f"Generating segment {idx}/{len(segments)}: {seg[:50]}...")
            
            # Generate a meaningful filename from the segment content
            def create_meaningful_filename(text_content, segment_index):
                """Create a descriptive filename from the text content"""
                if not text_content:
                    return f"short_{segment_index:02d}"
                
                import re
                
                # Clean the text and extract the first sentence
                text = text_content.strip()
                sentences = re.split(r'[.!?]+', text)
                first_sentence = sentences[0].strip() if sentences else text
                
                # Match the specific pattern: "<company name> as on <date>"
                pattern = r'^(.+?)\s+as\s+on\s+(.+?)(?:\s*[.—]|$)'
                match = re.search(pattern, first_sentence, re.IGNORECASE)
                
                if match:
                    company_name = match.group(1).strip()
                    date_part = match.group(2).strip()
                    
                    # Clean company name for filename
                    company_clean = re.sub(r'[^\w\s]', '', company_name)
                    company_clean = re.sub(r'\s+', '_', company_clean)
                    
                    # Clean date for filename
                    date_clean = re.sub(r'[^\w\s]', '', date_part)
                    date_clean = re.sub(r'\s+', '_', date_clean)
                    
                    # Create filename in format: Company_Name_as_on_Date
                    filename = f"{company_clean}_as_on_{date_clean}"
                    
                    # Limit length and ensure it's valid
                    if len(filename) > 50:
                        filename = filename[:50]
                    
                    return filename
                
                # Fallback: use first 10 words from the script
                words = first_sentence.split()[:10]
                if words:
                    filename = '_'.join(words)
                    # Clean filename to be filesystem-safe
                    filename = re.sub(r'[^\w\s-]', '', filename)
                    filename = re.sub(r'[-\s]+', '_', filename)
                    
                    # Limit length
                    if len(filename) > 50:
                        filename = filename[:50]
                    
                    # Ensure filename is not empty after cleaning
                    if len(filename) > 3:
                        return filename
                
                # Final fallback if everything fails
                return f"short_{segment_index:02d}"
            
            # Create meaningful filename for this segment
            custom_filename = create_meaningful_filename(seg, idx)
            
            res = voiceover_system.generate_speech(
                text=seg,
                voice=voice,
                speed=speed,
                format='mp4',
                session_id=None,
                background_image_path=temp_bg_path,
                custom_filename=custom_filename  # Pass our custom filename
            )
            
            if not res.get('success'):
                error_msg = f"Failed to generate segment {idx}: {res.get('error', 'Unknown error')}"
                print(f"ERROR: {error_msg}")
                socketio.emit('processing_error', {
                    'session_id': shorts_session_id,
                    'error': error_msg
                })
                raise Exception(error_msg)

            print(f"Successfully generated segment {idx}")

            # Use the custom filename we created for consistency
            actual_download_name = f"{custom_filename}.mp4"
            
            outputs.append({
                'index': idx,
                'file_url': res['file_url'],
                'duration': res.get('duration'),
                'format': res.get('format', 'mp4'),
                'download_name': actual_download_name  # Consistent naming
            })
            
            # Store file path with the exact download name for ZIP creation
            fp = res.get('file_path')
            if fp and os.path.exists(fp):
                file_paths.append((idx, fp, actual_download_name))

        # Emit progress for zip creation
        socketio.emit('progress_update', {
            'session_id': shorts_session_id,
            'step': 'shorts-generation',
            'progress': 80,
            'message': 'Creating download package...'
        })

        # Create a zip with all generated MP4s using exact same filenames as individual downloads
        os.makedirs(voiceover_system.output_folder, exist_ok=True)
        zip_name = f"shorts_{uuid.uuid4()}.zip"
        zip_path = os.path.join(voiceover_system.output_folder, zip_name)
        used_names = set()
        
        print(f"Creating zip file: {zip_path}")
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
            for idx, fp, actual_download_name in file_paths:
                # Use the exact same filename as individual downloads
                zip_filename = actual_download_name
                
                # Handle duplicate names (rare but possible)
                if zip_filename in used_names:
                    base_name = os.path.splitext(zip_filename)[0]
                    ext = os.path.splitext(zip_filename)[1]
                    suffix = 2
                    while f"{base_name}-{suffix}{ext}" in used_names:
                        suffix += 1
                    zip_filename = f"{base_name}-{suffix}{ext}"
                
                used_names.add(zip_filename)
                
                try:
                    zf.write(fp, zip_filename)
                    print(f"Added {zip_filename} to zip (matches individual download name)")
                except Exception as e:
                    print(f"Error adding {zip_filename} to zip: {e}")
                    pass
        
        # Build a friendly suggested name with date
        today_str = datetime.now().strftime('%Y-%m-%d')
        zip_url = f"/download-voiceover/{zip_name}?dl=1&name=youtube_shorts_{today_str}"

        # Emit completion
        socketio.emit('progress_update', {
            'session_id': shorts_session_id,
            'step': 'shorts-generation',
            'progress': 100,
            'message': f'Successfully generated {len(outputs)} YouTube Shorts!'
        })

        print(f"=== YOUTUBE SHORTS GENERATION COMPLETED ===")
        print(f"Generated {len(outputs)} videos")
        print(f"Zip file: {zip_path}")

        # Return response with both 'items' and 'videos' for compatibility
        response_data = {
            'success': True, 
            'count': len(outputs), 
            'items': outputs,  # Backend format
            'videos': outputs,  # Frontend expected format
            'zip_url': zip_url,
            'session_id': shorts_session_id
        }
        
        return jsonify(response_data)
        
    except Exception as e:
        error_msg = f"Error generating shorts: {e}"
        print(f"ERROR: {error_msg}")
        
        # Emit error to WebSocket
        socketio.emit('processing_error', {
            'session_id': shorts_session_id,
            'error': str(e)
        })
        
        return jsonify({'error': str(e)}), 500
    finally:
        if temp_bg_path and os.path.exists(temp_bg_path):
            try:
                os.remove(temp_bg_path)
                print(f"Cleaned up temp background image: {temp_bg_path}")
            except Exception as e:
                print(f"Error cleaning up temp file: {e}")
                pass

@app.route('/voices', methods=['GET'])
def list_voices():
    """List available TTS voices and supported output formats."""
    try:
        # Return default provider info since get_available_providers method doesn't exist
        providers = [('OpenAI TTS', [
            {'name': 'alloy', 'language': 'en-US'},
            {'name': 'echo', 'language': 'en-US'},
            {'name': 'fable', 'language': 'en-US'},
            {'name': 'onyx', 'language': 'en-US'},
            {'name': 'nova', 'language': 'en-US'},
            {'name': 'shimmer', 'language': 'en-US'}
        ])]
        
        # Format response with provider information
        response_data = {
            'success': True,
            'providers': [],
            'formats': getattr(voiceover_system, 'supported_formats', ['mp3', 'wav', 'mp4'])
        }
        
        for provider_name, voices in providers:
            provider_info = {
                'name': provider_name,
                'voices': voices
            }
            response_data['providers'].append(provider_info)
        
        return jsonify(response_data)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/tts-providers', methods=['GET'])
def list_tts_providers():
    """Get detailed information about available TTS providers."""
    try:
        # Return default provider info since get_available_providers method doesn't exist
        providers = [('OpenAI TTS', [
            {'name': 'alloy', 'language': 'en-US'},
            {'name': 'echo', 'language': 'en-US'},
            {'name': 'fable', 'language': 'en-US'},
            {'name': 'onyx', 'language': 'en-US'},
            {'name': 'nova', 'language': 'en-US'},
            {'name': 'shimmer', 'language': 'en-US'}
        ])]
        
        provider_details = []
        for provider_name, voices in providers:
            # Count voices by language
            languages = {}
            for voice in voices:
                lang = voice.get('language', 'unknown')
                if lang not in languages:
                    languages[lang] = 0
                languages[lang] += 1
            
            provider_info = {
                'name': provider_name,
                'voice_count': len(voices),
                'languages': languages,
                'is_open_source': 'OpenAI' not in provider_name,
                'cost': 'Free' if 'OpenAI' not in provider_name else 'Paid',
                'quality': 'High' if provider_name in ['Coqui TTS (Open Source)', 'OpenAI TTS'] else 'Good',
                'indian_english_support': any('en-IN' in voice.get('language', '') or 'Indian' in voice.get('name', '') for voice in voices),
                'voices': voices
            }
            provider_details.append(provider_info)
        
        return jsonify({
            'success': True,
            'providers': provider_details,
            'total_providers': len(provider_details),
            'open_source_available': any(p['is_open_source'] for p in provider_details)
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/voiceovers', methods=['GET'])
def list_voiceovers():
    """List generated voiceover files with basic metadata.
    Query params:
      - page (int, default 1)
      - per_page (int, default 50)
      - sort ("asc"|"desc", default "desc" by modified time)
    """
    try:
        base = voiceover_system.output_folder
        os.makedirs(base, exist_ok=True)
        allowed_exts = {'.mp3', '.wav', '.mp4', '.zip', '.srt'}
        items = []
        for name in os.listdir(base):
            if not name or name.startswith('.'):
                continue
            path = os.path.join(base, name)
            if not os.path.isfile(path):
                continue
            ext = os.path.splitext(name)[1].lower()
            if ext not in allowed_exts:
                continue
            stat = os.stat(path)
            info = {
                'filename': name,
                'bytes': stat.st_size,
                'mtime': int(stat.st_mtime),
            }
            # Duration (best-effort) - skip since get_file_info method doesn't exist
            # Could be implemented if VoiceoverSystem adds this method in the future
            try:
                # vinfo = voiceover_system.get_file_info(path)
                # info['duration'] = vinfo['duration']
                pass
            except Exception:
                pass
            # Attach sidecar subtitle URL for mp4
            if ext == '.mp4':
                srt_name = os.path.splitext(name)[0] + '.srt'
                srt_path = os.path.join(base, srt_name)
                if os.path.exists(srt_path):
                    info['subtitle'] = srt_name
                    info['subtitle_url'] = f"/download-voiceover/{srt_name}?dl=1"
            items.append(info)
        sort = (request.args.get('sort', 'desc') or 'desc').lower()
        items.sort(key=lambda x: x.get('mtime', 0), reverse=(sort != 'asc'))
        page = max(1, int(request.args.get('page', 1) or 1))
        per_page = min(200, max(1, int(request.args.get('per_page', 50) or 50)))
        start = (page - 1) * per_page
        sliced = items[start:start + per_page]
        return jsonify({
            'success': True,
            'total': len(items),
            'page': page,
            'per_page': per_page,
            'items': sliced
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/voiceovers/<path:filename>', methods=['DELETE'])
def delete_voiceover(filename):
    """Delete a generated voiceover file by filename.
    Optional query params:
      - delete_subtitles (1|0, default 1): also delete matching .srt sidecar
    """
    try:
        # Normalize and ensure path is inside the voiceover folder
        base = os.path.abspath(voiceover_system.output_folder)
        os.makedirs(base, exist_ok=True)
        safe_name = os.path.basename(filename)
        target = os.path.abspath(os.path.join(base, safe_name))
        if not target.startswith(base + os.sep):
            return jsonify({'error': 'Invalid filename'}), 400
        if not os.path.exists(target) or not os.path.isfile(target):
            return jsonify({'error': 'File not found'}), 404
        # Delete file
        try:
            os.remove(target)
        except Exception as e:
            return jsonify({'error': f'Failed to delete file: {str(e)}'}), 500
        deleted = [safe_name]
        # Optionally delete sidecar .srt with same basename
        delete_srt = (request.args.get('delete_subtitles', '1').lower() in ('1', 'true', 'yes'))
        root, ext = os.path.splitext(safe_name)
        if delete_srt:
            srt_path = os.path.join(base, root + '.srt')
            if os.path.exists(srt_path):
                try:
                    os.remove(os.path.abspath(srt_path))
                    deleted.append(os.path.basename(srt_path))
                except Exception:
                    pass
        return jsonify({'success': True, 'deleted': deleted})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# API Endpoints for External Integration
@app.route('/api/v1/generate-shorts', methods=['POST'])
def api_generate_shorts():
    """
    API endpoint for generating YouTube Shorts from external projects.
    
    Expected JSON payload:
    {
        "script": "Your script with — pause — markers",
        "voice": "nova",
        "speed": 1.0,
        "background_image_url": "https://example.com/background.jpg",
        "webhook_url": "https://your-app.com/webhook"
    }
    
    Returns (202 Accepted):
    {
        "success": true,
        "session_id": "api_12345-abcd-ef67-8901-234567890abc", 
        "status": "processing",
        "message": "YouTube Shorts generation started",
        "estimated_completion_time": "2-5 minutes",
        "progress_url": "/api/v1/shorts-status/{session_id}",
        "webhook_enabled": true
    }
    """
    try:
        # Validate content type
        if not request.is_json:
            return jsonify({
                'success': False,
                'error': 'Content-Type must be application/json',
                'code': 'INVALID_CONTENT_TYPE'
            }), 400
        
        data = request.get_json()
        if not data:
            return jsonify({
                'success': False,
                'error': 'Invalid JSON payload',
                'code': 'INVALID_JSON'
            }), 400
        
        # Extract and validate parameters
        script = (data.get('script', '') or '').strip()
        if not script:
            return jsonify({
                'success': False,
                'error': 'Script is required and cannot be empty',
                'code': 'MISSING_SCRIPT'
            }), 400
        
        voice = data.get('voice', 'nova')
        if voice not in voiceover_system.available_voices:
            return jsonify({
                'success': False,
                'error': f'Voice must be one of: {", ".join(voiceover_system.available_voices)}',
                'code': 'INVALID_VOICE'
            }), 400
        
        try:
            speed = float(data.get('speed', 1.0))
            if speed < 0.25 or speed > 4.0:
                return jsonify({
                    'success': False,
                    'error': 'Speed must be between 0.25 and 4.0',
                    'code': 'INVALID_SPEED'
                }), 400
        except (TypeError, ValueError):
            return jsonify({
                'success': False,
                'error': 'Speed must be a valid number',
                'code': 'INVALID_SPEED_FORMAT'
            }), 400
        
        # Optional parameters
        background_image_url = data.get('background_image_url', '')
        webhook_url = data.get('webhook_url', '')
        
        # Estimate completion time and segments
        estimated_segments = len(script.split('— pause —')) if '— pause —' in script else len(script.split('\n\n'))
        estimated_segments = max(1, estimated_segments)
        
        # Estimate completion time based on segments (roughly 30-60 seconds per segment)
        if estimated_segments <= 2:
            estimated_completion = "1-2 minutes"
        elif estimated_segments <= 5:
            estimated_completion = "2-5 minutes"
        elif estimated_segments <= 10:
            estimated_completion = "5-8 minutes"
        else:
            estimated_completion = "8-15 minutes"
        
        # Generate unique session ID with API prefix
        api_session_id = f"api_{uuid.uuid4()}"
        
        print(f"=== API YOUTUBE SHORTS REQUEST ===")
        print(f"API Session ID: {api_session_id}")
        print(f"Script length: {len(script)} characters")
        print(f"Voice: {voice}, Speed: {speed}")
        print(f"Estimated segments: {estimated_segments}")
        print(f"Background image URL: {background_image_url}")
        print(f"Webhook URL: {webhook_url}")
        
        # Store session info for status tracking
        if not hasattr(app, 'api_sessions'):
            app.api_sessions = {}
        
        app.api_sessions[api_session_id] = {
            'status': 'processing',
            'created_at': datetime.now().isoformat(),
            'script': script,
            'voice': voice,
            'speed': speed,
            'background_image_url': background_image_url,
            'webhook_url': webhook_url,
            'progress': 0,
            'message': 'Initializing YouTube Shorts generation...',
            'estimated_segments': estimated_segments,
            'estimated_completion': estimated_completion,
            'current_segment': 0,
            'result': None,
            'error': None
        }
        
        # Start background processing
        socketio.start_background_task(target=process_api_shorts_async, 
                                     session_id=api_session_id,
                                     script=script, 
                                     voice=voice, 
                                     speed=speed,
                                     background_image_url=background_image_url,
                                     webhook_url=webhook_url)
        
        # Return 202 Accepted with comprehensive response
        response = {
            'success': True,
            'session_id': api_session_id,
            'status': 'processing',
            'message': 'YouTube Shorts generation started',
            'estimated_completion_time': estimated_completion,
            'progress_url': f'/api/v1/shorts-status/{api_session_id}',
            'webhook_enabled': bool(webhook_url)
        }
        
        print(f"API: Returning 202 response: {response}")
        return jsonify(response), 202  # 202 Accepted for async processing
        
    except Exception as e:
        error_msg = f"API Error: {str(e)}"
        print(error_msg)
        return jsonify({
            'success': False,
            'error': str(e),
            'code': 'INTERNAL_ERROR'
        }), 500

@app.route('/api/v1/shorts-status/<session_id>', methods=['GET'])
def api_shorts_status(session_id):
    """
    Check the status of a YouTube Shorts generation session.
    
    Returns:
    {
        "success": true,
        "session_id": "api_12345-abcd-ef67-8901-234567890abc",
        "status": "processing|completed|failed",
        "progress": 75,
        "message": "Generating video 3 of 4...",
        "estimated_time_remaining": "1-2 minutes",
        "created_at": "2025-09-13T10:30:00",
        "zip_url": "download_link" (when completed),
        "completed_at": "timestamp" (when completed),
        "failed_at": "timestamp" (when failed)
    }
    """
    try:
        if not hasattr(app, 'api_sessions'):
            app.api_sessions = {}
        
        if session_id not in app.api_sessions:
            return jsonify({
                'success': False,
                'error': 'Session not found',
                'code': 'SESSION_NOT_FOUND'
            }), 404
        
        session_data = app.api_sessions[session_id]
        
        # Calculate estimated time remaining
        progress = session_data.get('progress', 0)
        if progress < 20:
            estimated_time_remaining = session_data.get('estimated_completion', '2-5 minutes')
        elif progress < 50:
            estimated_time_remaining = "2-4 minutes"
        elif progress < 80:
            estimated_time_remaining = "1-2 minutes"
        else:
            estimated_time_remaining = "30 seconds"
        
        response = {
            'success': True,
            'session_id': session_id,
            'status': session_data['status'],
            'progress': progress,
            'message': session_data.get('message', ''),
            'estimated_time_remaining': estimated_time_remaining,
            'created_at': session_data.get('created_at')
        }
        
        if session_data['status'] == 'completed' and session_data.get('result'):
            result = session_data['result']
            
            # Construct proper absolute URL based on current request
            zip_path = result.get('zip_url', '')
            if zip_path.startswith('/'):
                # Build absolute URL from current request
                scheme = request.environ.get('HTTP_X_FORWARDED_PROTO', request.scheme)
                host = request.environ.get('HTTP_HOST', request.host)
                zip_url = f"{scheme}://{host}{zip_path}"
            else:
                zip_url = zip_path
            
            response.update({
                'zip_url': zip_url,
                'completed_at': datetime.now().isoformat()
            })
            print(f"API Status: Session {session_id} completed with {result.get('count', 0)} videos")
            print(f"API Status: ZIP URL returned: {zip_url}")
        elif session_data['status'] == 'failed':
            response.update({
                'error': session_data.get('error', 'Unknown error'),
                'failed_at': datetime.now().isoformat()
            })
            print(f"API Status: Session {session_id} failed: {response['error']}")
        else:
            print(f"API Status: Session {session_id} - {session_data['status']} - {progress}%")
        
        return jsonify(response)
        
    except Exception as e:
        error_msg = f"API Status Error: {str(e)}"
        print(error_msg)
        return jsonify({
            'success': False,
            'error': str(e),
            'code': 'INTERNAL_ERROR'
        }), 500

def process_api_shorts_async(session_id, script, voice, speed, background_image_url=None, webhook_url=None):
    """Background task to process YouTube Shorts generation for API requests."""
    import requests
    
    def split_into_scripts(script_text):
        """Split script into segments using pause markers"""
        segments = []
        if '— pause —' in script_text:
            parts = script_text.split('— pause —')
        else:
            parts = script_text.split('\n\n')
        
        for part in parts:
            cleaned = part.strip()
            if cleaned:
                segments.append(cleaned)
        return segments
    
    def send_webhook(status, progress, message, **kwargs):
        """Send webhook notification if webhook_url is provided"""
        if not webhook_url:
            return
        
        try:
            payload = {
                'session_id': session_id,
                'status': status,
                'progress': progress,
                'message': message,
                **kwargs
            }
            
            response = requests.post(webhook_url, json=payload, timeout=10)
            print(f"API: Webhook sent to {webhook_url} - Status: {response.status_code}")
        except Exception as e:
            print(f"API: Failed to send webhook: {e}")
    
    try:
        with app.app_context():
            print(f"Starting async processing for API session: {session_id}")
            
            # Download background image if URL provided
            temp_bg_path = None
            if background_image_url:
                try:
                    print(f"API: Downloading background image: {background_image_url}")
                    response = requests.get(background_image_url, timeout=30)
                    response.raise_for_status()
                    
                    # Create temp file
                    os.makedirs(app.config['TEMP_FOLDER'], exist_ok=True)
                    temp_bg_path = os.path.join(app.config['TEMP_FOLDER'], f"api_bg_{uuid.uuid4()}.jpg")
                    
                    with open(temp_bg_path, 'wb') as f:
                        f.write(response.content)
                    
                    print(f"API: Background image downloaded: {temp_bg_path}")
                except Exception as e:
                    print(f"API: Failed to download background image: {e}")
                    # Continue without background image
            
            # Update session status
            app.api_sessions[session_id]['status'] = 'processing'
            app.api_sessions[session_id]['progress'] = 10
            app.api_sessions[session_id]['message'] = 'Splitting script into segments...'
            app.api_sessions[session_id]['current_segment'] = 0
            
            send_webhook('processing', 10, 'Splitting script into segments...')
            
            # Split script into segments
            segments = split_into_scripts(script)
            if not segments:
                raise Exception('No valid segments found in script')
            
            print(f"API: Split script into {len(segments)} segments")
            
            # Update estimated segments count if different from initial estimate
            app.api_sessions[session_id]['estimated_segments'] = len(segments)
            app.api_sessions[session_id]['progress'] = 20
            app.api_sessions[session_id]['message'] = f'Starting generation of {len(segments)} video segments...'
            
            send_webhook('processing', 20, f'Starting generation of {len(segments)} video segments...')
            
            # Generate videos for each segment
            outputs = []
            file_paths = []
            
            for idx, seg in enumerate(segments, start=1):
                segment_progress = 20 + (idx - 1) * (60 / len(segments))
                app.api_sessions[session_id]['progress'] = int(segment_progress)
                app.api_sessions[session_id]['current_segment'] = idx
                app.api_sessions[session_id]['message'] = f'Generating video {idx} of {len(segments)}...'
                
                print(f"API: Generating segment {idx}/{len(segments)}: {seg[:30]}...")
                
                # Send webhook for progress updates (every few segments)
                if idx % 2 == 0 or idx == len(segments):
                    send_webhook('processing', int(segment_progress), f'Generating video {idx} of {len(segments)}...')
                
                # Create meaningful filename
                def create_api_filename(text_content, segment_index):
                    if not text_content:
                        return f"short_{segment_index:02d}"
                    
                    sentences = re.split(r'[.!?]+', text_content.strip())
                    first_sentence = sentences[0].strip() if sentences else text_content
                    
                    # Match the specific pattern: "<company name> as on <date>"
                    pattern = r'^(.+?)\s+as\s+on\s+(.+?)(?:\s*[.—]|$)'
                    match = re.search(pattern, first_sentence, re.IGNORECASE)
                    
                    if match:
                        company_name = match.group(1).strip()
                        date_part = match.group(2).strip()
                        
                        # Clean company name for filename
                        company_clean = re.sub(r'[^\w\s]', '', company_name)
                        company_clean = re.sub(r'\s+', '_', company_clean)
                        
                        # Clean date for filename
                        date_clean = re.sub(r'[^\w\s]', '', date_part)
                        date_clean = re.sub(r'\s+', '_', date_clean)
                        
                        # Create filename in format: Company_Name_as_on_Date
                        filename = f"{company_clean}_as_on_{date_clean}"
                        
                        # Limit length and ensure it's valid
                        if len(filename) > 40:
                            filename = filename[:40]
                        
                        return filename
                    
                    # Fallback: use first 10 words from the script
                    words = first_sentence.split()[:10]
                    if words:
                        filename = '_'.join(words)
                        # Clean filename to be filesystem-safe
                        filename = re.sub(r'[^\w\s-]', '', filename)
                        filename = re.sub(r'[-\s]+', '_', filename)
                        
                        # Limit length
                        if len(filename) > 40:
                            filename = filename[:40]
                        
                        # Ensure filename is not empty after cleaning
                        if len(filename) > 3:
                            return filename
                    
                    # Final fallback if everything fails
                    return f"short_{segment_index:02d}"
                
                custom_filename = create_api_filename(seg, idx)
                
                # Generate the voiceover video
                result = voiceover_system.generate_speech(
                    text=seg,
                    voice=voice,
                    speed=speed,
                    format='mp4',
                    session_id=None,
                    background_image_path=temp_bg_path,
                    generation_type='youtube_shorts',
                    custom_filename=custom_filename
                )
                
                if not result.get('success'):
                    error_msg = f"Failed to generate segment {idx}: {result.get('error', 'Unknown error')}"
                    print(f"API: ERROR - {error_msg}")
                    raise Exception(error_msg)
                
                print(f"API: Successfully generated segment {idx}")
                
                actual_download_name = f"{custom_filename}.mp4"
                outputs.append({
                    'index': idx,
                    'file_url': result['file_url'],
                    'duration': result.get('duration'),
                    'format': result.get('format', 'mp4'),
                    'download_name': actual_download_name
                })
                
                # Store file path for ZIP creation
                fp = result.get('file_path')
                if fp and os.path.exists(fp):
                    file_paths.append((idx, fp, actual_download_name))
                    print(f"API: Added file to ZIP queue: {actual_download_name}")
                else:
                    print(f"API: WARNING - File not found for segment {idx}: {fp}")
            
            # Create ZIP file
            app.api_sessions[session_id]['progress'] = 85
            app.api_sessions[session_id]['message'] = 'Creating download package...'
            
            send_webhook('processing', 85, 'Creating download package...')
            
            # Ensure voiceovers folder exists
            os.makedirs(voiceover_system.output_folder, exist_ok=True)
            
            zip_name = f"api_shorts_{session_id.replace('api_', '')}_{uuid.uuid4().hex[:8]}.zip"
            zip_path = os.path.join(voiceover_system.output_folder, zip_name)
            
            print(f"API: Creating ZIP file: {zip_path} with {len(file_paths)} files")
            with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
                for idx, fp, download_name in file_paths:
                    try:
                        if os.path.exists(fp):
                            zf.write(fp, download_name)
                            print(f"API: Added {download_name} to ZIP successfully")
                        else:
                            print(f"API: ERROR - File not found when creating ZIP: {fp}")
                    except Exception as e:
                        print(f"API: Error adding {download_name} to ZIP: {e}")
            
            # Verify ZIP was created
            if not os.path.exists(zip_path):
                raise Exception("Failed to create ZIP file")
            
            zip_size = os.path.getsize(zip_path)
            print(f"API: ZIP file created successfully: {zip_path} ({zip_size} bytes)")
            
            # Create download URL
            zip_url = f"/download-voiceover/{zip_name}"
            
            # Update session with final result
            app.api_sessions[session_id]['status'] = 'completed'
            app.api_sessions[session_id]['progress'] = 100
            app.api_sessions[session_id]['current_segment'] = len(segments)
            app.api_sessions[session_id]['message'] = f'Successfully generated {len(outputs)} YouTube Shorts!'
            app.api_sessions[session_id]['result'] = {
                'count': len(outputs),
                'videos': outputs,
                'zip_url': zip_url,
                'zip_name': zip_name,
                'total_segments': len(segments)
            }
            
            # Send completion webhook
            # Build proper webhook URL using the same logic as status endpoint
            webhook_zip_url = zip_url
            if webhook_url:
                # For webhook, we need to construct a full URL since the webhook recipient 
                # won't have access to the request context
                # Use environment variable or default to localhost for webhook URLs
                webhook_host = os.getenv('WEBHOOK_BASE_URL', 'http://localhost:5000')
                if zip_url.startswith('/'):
                    webhook_zip_url = f"{webhook_host}{zip_url}"
            
            send_webhook('completed', 100, f'Successfully generated {len(outputs)} YouTube Shorts!', 
                        zip_url=webhook_zip_url)
            
            print(f"API: Completed processing for session {session_id}")
            print(f"API: Generated {len(outputs)} videos, ZIP: {zip_name}")
            print(f"API: Webhook ZIP URL: {webhook_zip_url}")
            
            # Cleanup background image
            if temp_bg_path and os.path.exists(temp_bg_path):
                try:
                    os.remove(temp_bg_path)
                    print(f"API: Cleaned up temp background image: {temp_bg_path}")
                except Exception as e:
                    print(f"API: Error cleaning up temp file: {e}")
            
    except Exception as e:
        error_msg = f"API Background Error for session {session_id}: {str(e)}"
        print(error_msg)
        import traceback
        print("Full traceback:", flush=True)
        traceback.print_exc()
        
        app.api_sessions[session_id]['status'] = 'failed'
        app.api_sessions[session_id]['error'] = str(e)
        app.api_sessions[session_id]['message'] = f'Generation failed: {str(e)}'
        
        # Send failure webhook
        send_webhook('failed', app.api_sessions[session_id].get('progress', 0), 
                    f'Generation failed: {str(e)}', error=str(e))
        
        # Cleanup background image on error
        if 'temp_bg_path' in locals() and temp_bg_path and os.path.exists(temp_bg_path):
            try:
                os.remove(temp_bg_path)
                print(f"API: Cleaned up temp background image after error: {temp_bg_path}")
            except Exception:
                pass

@socketio.on('connect')
def handle_connect():
    """Handle client connection"""
    print('Client connected')

@socketio.on('disconnect')
def handle_disconnect():
    """Handle client disconnection"""
    print('Client disconnected')

@socketio.on('join_session')
def handle_join_session(data):
    """Handle client joining a specific session room"""
    session_id = data.get('session_id')
    if session_id:
        join_room(session_id)
        print(f'Client joined session room: {session_id}')
        emit('session_joined', {'session_id': session_id})

@socketio.on('leave_session')
def handle_leave_session(data):
    """Handle client leaving a specific session room"""
    session_id = data.get('session_id')
    if session_id:
        leave_room(session_id)
        print(f'Client left session room: {session_id}')
        emit('session_left', {'session_id': session_id})


if __name__ == '__main__':
    # Ensure required folders exist
    try:
        os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
        os.makedirs(app.config['TEMP_FOLDER'], exist_ok=True)
        os.makedirs(app.config['PROCESSED_FOLDER'], exist_ok=True)
        # Voiceover folder is managed by VoiceoverSystem, but create if env provided
        voiceover_folder = os.getenv('VOICEOVER_FOLDER')
        if (voiceover_folder):
            os.makedirs(voiceover_folder, exist_ok=True)
    except Exception as e:
        print(f"Error ensuring folders exist: {e}")

    host = os.getenv('HOST', '0.0.0.0')
    port = int(os.getenv('PORT', 5000))
    debug = os.getenv('FLASK_DEBUG', 'false').lower() == 'true'

    # Run the Socket.IO server
    socketio.run(app, host=host, port=port, debug=debug, allow_unsafe_werkzeug=True)