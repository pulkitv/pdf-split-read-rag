import os
import uuid
from flask import Flask, render_template, request, jsonify, send_file, url_for
from flask_socketio import SocketIO, emit, join_room, leave_room
from werkzeug.utils import secure_filename
import threading
from pdf_processor import PDFProcessor
from rag_system import RAGSystem
from voiceover_system import VoiceoverSystem
from dotenv import load_dotenv
import json

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
            }, room=session_id)
            
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
                    }, room=session_id)
                    
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
            }, room=session_id)
            
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
                    }, room=session_id)
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
            }, room=session_id)
            
            def merging_progress_callback(progress):
                try:
                    message = f'Merging pages... ({progress}%)'
                    print(f"Merging Progress Debug - Progress: {progress}%, Message: {message}", flush=True)
                    socketio.emit('progress_update', {
                        'session_id': session_id,
                        'step': 'merging',
                        'progress': progress,
                        'message': message
                    }, room=session_id)
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
            }, room=session_id)
            
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
                    }, room=session_id)
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
            }, room=session_id)
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
            }, room=session_id)
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
            }, room=session_id)
            
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
                    }, room=session_id)
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
            }, room=session_id)
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
            }, room=session_id)
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
            socketio.emit('progress_update', progress_data, room=session_id)

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
    
    data = request.get_json()
    custom_prompt = data.get('prompt', '')
    
    try:
        socketio.emit('progress_update', {
            'session_id': session_id,
            'step': 'summarization',
            'progress': 0,
            'message': 'Generating AI summary...'
        }, room=session_id)
        
        summary = rag_system.generate_summary(session_id, custom_prompt,
                                            progress_callback=lambda p: update_progress(session_id, 'summarization', p))
        
        socketio.emit('summary_complete', {
            'session_id': session_id,
            'summary': summary
        }, room=session_id)
        
        return jsonify({'success': True, 'summary': summary})
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/generate-voiceover/<session_id>', methods=['POST'])
def generate_voiceover(session_id):
    """Generate AI voiceover from text"""
    # Handle standalone voiceover requests (no session required)
    if session_id == 'standalone':
        data = request.get_json()
        text = data.get('text', '')
        voice = data.get('voice', 'nova')
        speed = float(data.get('speed', 1.0))
        format = data.get('format', 'mp3')
        
        if not text.strip():
            return jsonify({'error': 'No text provided for voiceover generation'}), 400
        
        try:
            print(f"Generating standalone voiceover")
            print(f"Text length: {len(text)} characters")
            print(f"Voice: {voice}, Speed: {speed}, Format: {format}")
            
            # Generate voiceover using the voiceover system without session ID
            result = voiceover_system.generate_speech(
                text=text,
                voice=voice,
                speed=speed,
                format=format,
                session_id=None  # No session for standalone
            )
            
            if result['success']:
                return jsonify({
                    'success': True,
                    'file_url': result['file_url'],
                    'format': result['format'],
                    'duration': result.get('duration', 0)
                })
            else:
                return jsonify({'error': 'Failed to generate voiceover'}), 500
                
        except Exception as e:
            print(f"Error generating standalone voiceover: {str(e)}")
            return jsonify({'error': str(e)}), 500
    
    # Handle session-based voiceover requests (original functionality)
    if session_id not in processing_sessions:
        return jsonify({'error': 'Invalid session ID'}), 404
    
    data = request.get_json()
    text = data.get('text', '')
    voice = data.get('voice', 'nova')
    speed = float(data.get('speed', 1.0))
    format = data.get('format', 'mp3')
    
    if not text.strip():
        return jsonify({'error': 'No text provided for voiceover generation'}), 400
    
    try:
        print(f"Generating voiceover for session {session_id}")
        print(f"Text length: {len(text)} characters")
        print(f"Voice: {voice}, Speed: {speed}, Format: {format}")
        
        # Generate voiceover using the voiceover system
        result = voiceover_system.generate_speech(
            text=text,
            voice=voice,
            speed=speed,
            format=format,
            session_id=session_id
        )
        
        if result['success']:
            return jsonify({
                'success': True,
                'file_url': result['file_url'],
                'format': result['format'],
                'duration': result.get('duration', 0)
            })
        else:
            return jsonify({'error': 'Failed to generate voiceover'}), 500
            
    except Exception as e:
        print(f"Error generating voiceover: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/download-voiceover/<filename>')
def download_voiceover(filename):
    """Download generated voiceover file"""
    try:
        voiceover_folder = voiceover_system.output_folder
        file_path = os.path.join(voiceover_folder, filename)
        
        if not os.path.exists(file_path):
            return jsonify({'error': 'File not found'}), 404
        
        # Get file info
        file_info = voiceover_system.get_file_info(filename)
        if not file_info:
            return jsonify({'error': 'File information not available'}), 404
        
        # Determine mimetype based on format
        mimetype = 'audio/mpeg'  # Default for MP3
        if filename.endswith('.wav'):
            mimetype = 'audio/wav'
        elif filename.endswith('.mp4'):
            mimetype = 'video/mp4'
        
        return send_file(
            file_path,
            as_attachment=True,
            download_name=filename,
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

if __name__ == '__main__':
    # Create necessary directories
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    os.makedirs(app.config['TEMP_FOLDER'], exist_ok=True)
    os.makedirs(app.config['PROCESSED_FOLDER'], exist_ok=True)
    
    # Get host and port from environment
    host = os.getenv('FLASK_HOST', '0.0.0.0')
    port = int(os.getenv('FLASK_PORT', 5000))
    debug = os.getenv('FLASK_DEBUG', 'true').lower() == 'true'
    
    # Run the application
    socketio.run(app, debug=debug, host=host, port=port)