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

# Load environment variables
load_dotenv()

app = Flask(__name__)

# Configure Flask using environment variables
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'fallback-secret-key-change-this')
app.config['UPLOAD_FOLDER'] = os.getenv('UPLOAD_FOLDER', 'uploads')
app.config['TEMP_FOLDER'] = os.getenv('TEMP_FOLDER', 'temp')
app.config['PROCESSED_FOLDER'] = os.getenv('PROCESSED_FOLDER', 'processed')

# Configure Flask URL generation for background threads
# Comment out SERVER_NAME as it can cause routing issues
# app.config['SERVER_NAME'] = os.getenv('SERVER_NAME', 'localhost:5000')
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
        
        # Generate voiceover
        result = voiceover_system.generate_speech(
            text=text,
            voice=voice,
            speed=speed,
            format=format_type,
            session_id=session.get('session_id'),
            background_image_path=background_image if background_image else None
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
        
        if not text:
            return jsonify({'error': 'No text provided'}), 400
        
        # Generate voiceover using the voiceover system
        result = voiceover_system.generate_speech(
            text=text,
            voice=voice,
            speed=speed,
            format=format_type,
            session_id=None,  # No session needed for standalone
            background_image_path=None
        )
        
        if result.get('success'):
            return jsonify({
                'file_url': result.get('file_url'),
                'format': result.get('format'),
                'duration': result.get('duration'),
                'file_path': result.get('file_path')
            })
        else:
            return jsonify({'error': result.get('error', 'Failed to generate voiceover')}), 500
        
    except Exception as e:
        print(f"Error generating standalone voiceover: {str(e)}")
        return jsonify({'error': str(e)}), 500

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

    temp_bg_path = None
    try:
        if bg_file and getattr(bg_file, 'filename', ''):
            os.makedirs(app.config['TEMP_FOLDER'], exist_ok=True)
            bg_name = secure_filename(bg_file.filename)
            temp_bg_path = os.path.join(app.config['TEMP_FOLDER'], f"bg_{uuid.uuid4()}_{bg_name}")
            bg_file.save(temp_bg_path)

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
            return jsonify({'error': 'No segments found in script'}), 400

        # Generate a portrait MP4 for each segment
        outputs = []
        file_paths = []  # list of tuples (idx, path, title)
        for idx, seg in enumerate(segments, start=1):
            res = voiceover_system.generate_speech(
                text=seg,
                voice=voice,
                speed=speed,
                format='mp4',
                session_id=None,
                background_image_path=temp_bg_path
            )
            if not res.get('success'):
                raise Exception(f"Failed to generate segment {idx}")

            # Capture the suggested download title for consistent naming
            seg_title = res.get('download_title') or f"short_{idx:02d}"
            outputs.append({
                'index': idx,
                'file_url': res['file_url'],
                'duration': res.get('duration'),
                'format': res.get('format', 'mp4'),
                # Optional: echo the actual download name used for individual downloads
                'download_name': seg_title + '.mp4'
            })
            # Keep actual file path and title for zipping
            fp = res.get('file_path')
            if fp and os.path.exists(fp):
                file_paths.append((idx, fp, seg_title))

        # Create a zip with all generated MP4s for one-click download
        os.makedirs(voiceover_system.output_folder, exist_ok=True)
        zip_name = f"shorts_{uuid.uuid4()}.zip"
        zip_path = os.path.join(voiceover_system.output_folder, zip_name)
        used_names = set()
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
            for idx, fp, title in file_paths:
                # Sanitize and ensure uniqueness; match individual download naming
                base = secure_filename(title) or f"short_{idx:02d}"
                # Remove any trailing extension from base if present
                if base.lower().endswith('.mp4'):
                    base = base[:-4]
                candidate = f"{base}.mp4"
                suffix = 2
                while candidate in used_names:
                    candidate = f"{base}-{suffix}.mp4"
                    suffix += 1
                used_names.add(candidate)
                try:
                    zf.write(fp, candidate)
                except Exception:
                    pass
        # Build a friendly suggested name with date
        today_str = datetime.now().strftime('%Y-%m-%d')
        zip_url = f"/download-voiceover/{zip_name}?dl=1&name=youtube_shorts_{today_str}"

        return jsonify({'success': True, 'count': len(outputs), 'items': outputs, 'zip_url': zip_url})
    except Exception as e:
        print(f"Error generating shorts: {e}")
        return jsonify({'error': str(e)}), 500
    finally:
        if temp_bg_path and os.path.exists(temp_bg_path):
            try:
                os.remove(temp_bg_path)
            except Exception:
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
        if voiceover_folder:
            os.makedirs(voiceover_folder, exist_ok=True)
    except Exception as e:
        print(f"Error ensuring folders exist: {e}")

    host = os.getenv('HOST', '0.0.0.0')
    port = int(os.getenv('PORT', 5000))
    debug = os.getenv('FLASK_DEBUG', 'false').lower() == 'true'

    # Run the Socket.IO server
    socketio.run(app, host=host, port=port, debug=debug, allow_unsafe_werkzeug=True)