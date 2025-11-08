import os
import uuid
from flask import Flask, render_template, request, jsonify, send_file, url_for, session
from flask_socketio import SocketIO, emit, join_room, leave_room
from werkzeug.utils import secure_filename
from werkzeug.exceptions import RequestEntityTooLarge
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

# Configure Flask using environment variables with increased file size limits
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'fallback-secret-key-change-this')
app.config['UPLOAD_FOLDER'] = os.getenv('UPLOAD_FOLDER', 'uploads')
app.config['TEMP_FOLDER'] = os.getenv('TEMP_FOLDER', 'temp')
app.config['PROCESSED_FOLDER'] = os.getenv('PROCESSED_FOLDER', 'processed')

# Configure Flask URL generation for background threads
app.config['SERVER_NAME'] = os.getenv('SERVER_NAME', 'localhost:5000')
app.config['APPLICATION_ROOT'] = os.getenv('APPLICATION_ROOT', '/')
app.config['PREFERRED_URL_SCHEME'] = os.getenv('PREFERRED_URL_SCHEME', 'http')

# Configure file upload limits - INCREASED for large PDFs
app.config['MAX_CONTENT_LENGTH'] = int(os.getenv('MAX_CONTENT_LENGTH', 200 * 1024 * 1024))  # 200MB default
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = int(os.getenv('SEND_FILE_MAX_AGE_DEFAULT', 0))

# Session configuration from environment
app.config['PERMANENT_SESSION_LIFETIME'] = int(os.getenv('PERMANENT_SESSION_LIFETIME', 3600))
app.config['SESSION_COOKIE_SECURE'] = os.getenv('SESSION_COOKIE_SECURE', 'false').lower() == 'true'
app.config['SESSION_COOKIE_HTTPONLY'] = os.getenv('SESSION_COOKIE_HTTPONLY', 'true').lower() == 'true'

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

# Store processing sessions and API sessions
processing_sessions = {}

# Initialize API session storage for Shorts API
api_sessions = {}

# Initialize API session storage for Voiceover API
api_voiceover_sessions = {}

# Add error handlers for large file uploads and other HTTP errors
@app.errorhandler(413)
@app.errorhandler(RequestEntityTooLarge)
def handle_file_too_large(error):
    """Handle files that exceed the maximum size limit - return JSON instead of HTML"""
    max_size_mb = app.config['MAX_CONTENT_LENGTH'] / (1024 * 1024)
    print(f"File upload rejected - exceeds {max_size_mb:.0f}MB limit")
    return jsonify({
        'success': False,
        'error': f'File too large. Maximum file size allowed is {max_size_mb:.0f}MB.',
        'error_code': 'FILE_TOO_LARGE',
        'max_size_mb': max_size_mb
    }), 413

@app.errorhandler(400)
def handle_bad_request(error):
    """Handle bad requests with JSON response"""
    print(f"Bad request error: {error}")
    return jsonify({
        'success': False,
        'error': 'Bad request. Please check your file and try again.',
        'error_code': 'BAD_REQUEST'
    }), 400

@app.errorhandler(408)
def handle_request_timeout(error):
    """Handle request timeouts with JSON response"""
    print(f"Request timeout error: {error}")
    return jsonify({
        'success': False,
        'error': 'Request timed out. Large files may take longer to process.',
        'error_code': 'REQUEST_TIMEOUT'
    }), 408

@app.errorhandler(500)
def handle_internal_error(error):
    """Handle internal server errors with JSON response"""
    print(f"Internal server error: {error}")
    return jsonify({
        'success': False,
        'error': 'Internal server error. Please try again later.',
        'error_code': 'INTERNAL_ERROR'
    }), 500

@app.route('/')
def index():
    """Main page with upload interface"""
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_file():
    """Handle PDF file upload with enhanced large file support"""
    try:
        if 'file' not in request.files:
            return jsonify({'success': False, 'error': 'No file selected'}), 400
        
        file = request.files['file']
        if file.filename == '' or file.filename is None:
            return jsonify({'success': False, 'error': 'No file selected'}), 400
        
        # Get processing mode from form data
        processing_mode = request.form.get('mode', 'ocr')  # Default to OCR mode
        
        # Check file extension using environment config
        allowed_extensions = os.getenv('ALLOWED_EXTENSIONS', 'pdf').split(',')
        if not any(file.filename.lower().endswith(f'.{ext.strip()}') for ext in allowed_extensions):
            return jsonify({'success': False, 'error': f'Please upload a {", ".join(allowed_extensions).upper()} file'}), 400
        
        # Generate unique session ID
        session_id = str(uuid.uuid4())
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], f"{session_id}_{filename}")
        
        # Save the file and check actual size
        print(f"Saving file: {filename}")
        file.save(filepath)
        
        # Get actual file size after saving
        actual_file_size = os.path.getsize(filepath)
        file_size_mb = actual_file_size / (1024 * 1024)
        
        print(f"File saved successfully: {filename} ({file_size_mb:.2f}MB)")
        
        # Check if file exceeds our processing limits (different from upload limits)
        max_processing_size_mb = int(os.getenv('MAX_PROCESSING_SIZE_MB', 200))
        if file_size_mb > max_processing_size_mb:
            # Clean up the uploaded file
            if os.path.exists(filepath):
                os.remove(filepath)
            return jsonify({
                'success': False, 
                'error': f'File too large for processing. Maximum size for PDF processing is {max_processing_size_mb}MB. Your file is {file_size_mb:.1f}MB.',
                'error_code': 'FILE_TOO_LARGE_FOR_PROCESSING',
                'file_size_mb': round(file_size_mb, 2),
                'max_size_mb': max_processing_size_mb
            }), 413
        
        # Store session info with processing mode and file size
        processing_sessions[session_id] = {
            'filename': filename,
            'filepath': filepath,
            'status': 'uploaded',
            'mode': processing_mode,
            'file_size_mb': round(file_size_mb, 2),
            'progress': {
                'splitting': 0,
                'ocr': 0,
                'merging': 0,
                'text_extraction': 0,
                'summarization': 0
            }
        }
        
        # Provide estimated processing time for large files
        estimated_time_minutes = 1
        if file_size_mb > 50:
            estimated_time_minutes = max(5, int(file_size_mb / 10))  # Rough estimate: 10MB per minute
        elif file_size_mb > 20:
            estimated_time_minutes = 3
        
        return jsonify({
            'success': True,
            'session_id': session_id,
            'filename': filename,
            'mode': processing_mode,
            'file_size_mb': round(file_size_mb, 2),
            'estimated_time_minutes': estimated_time_minutes,
            'is_large_file': file_size_mb > 50
        })
        
    except Exception as e:
        print(f"Upload error: {e}")
        # Clean up file if it was partially saved
        try:
            if 'filepath' in locals() and os.path.exists(filepath):
                os.remove(filepath)
        except:
            pass
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/download/<session_id>')
def download_file(session_id):
    """Download processed PDF file"""
    if session_id not in processing_sessions:
        return jsonify({'error': 'Invalid session ID'}), 404
    
    session = processing_sessions[session_id]
    if session['status'] != 'completed':
        return jsonify({'error': 'Processing not completed'}), 400
    
    merged_file = session.get('merged_file')
    if not merged_file or not os.path.exists(merged_file):
        return jsonify({'error': 'Processed file not found'}), 404
    
    return send_file(merged_file, as_attachment=True, 
                    download_name=f"processed_{session['filename']}")

@app.route('/summarize', methods=['POST'])
def summarize_text():
    """Generate AI summary of processed document"""
    data = request.get_json()
    session_id = data.get('session_id')
    query = data.get('query', 'Please provide a comprehensive summary of this document')
    
    if not session_id or session_id not in processing_sessions:
        return jsonify({'error': 'Invalid session ID'}), 404
    
    session = processing_sessions[session_id]
    if session['status'] != 'completed':
        return jsonify({'error': 'Processing not completed'}), 400
    
    try:
        # Use RAG system to generate summary
        summary = rag_system.generate_summary(session_id, query)
        return jsonify({
            'success': True,
            'summary': summary,
            'query': query
        })
    except Exception as e:
        return jsonify({
            'error': f'Failed to generate summary: {str(e)}'
        }), 500

@app.route('/generate-voiceover', methods=['POST'])
def generate_voiceover():
    """Generate voiceover from text using WebSocket progress tracking"""
    try:
        data = request.get_json()
        print(f"Received voiceover request: {data}")
        
        # Validate required fields
        text = data.get('text', '').strip()
        if not text:
            return jsonify({'error': 'Text is required'}), 400
        
        # Get optional parameters with defaults
        voice = data.get('voice', 'onyx')
        speed = float(data.get('speed', 1.2))
        format_type = data.get('format', 'mp3')
        background_image = request.files.get('background_image')
        generation_type = data.get('generation_type', 'youtube_shorts')  # Default to YouTube Shorts
        
        # Validate format
        if format_type not in voiceover_system.supported_formats:
            return jsonify({'error': f'Unsupported format. Use: {", ".join(voiceover_system.supported_formats)}'}), 400
        
        # Validate voice
        if voice not in voiceover_system.available_voices:
            return jsonify({'error': f'Invalid voice. Use: {", ".join(voiceover_system.available_voices)}'}), 400
        
        # Validate speed
        if not (0.25 <= speed <= 4.0):
            return jsonify({'error': 'Speed must be between 0.25 and 4.0'}), 400
        
        # Validate generation_type
        valid_types = ['youtube_shorts', 'shorts', 'regular', 'standalone']
        if generation_type not in valid_types:
            return jsonify({'error': f'Invalid generation_type. Use: {", ".join(valid_types)}'}), 400
        
        # Handle background image upload
        background_image_path = None
        if background_image and background_image.filename:
            filename = secure_filename(background_image.filename)
            if filename and filename.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.bmp')):
                background_image_path = os.path.join(app.config['TEMP_FOLDER'], f"bg_{uuid.uuid4()}_{filename}")
                background_image.save(background_image_path)
                print(f"Background image saved: {background_image_path}")
        
        # Generate session ID for tracking
        session_id = str(uuid.uuid4())
        
        # Start background processing
        def background_voiceover_generation():
            try:
                with app.app_context():
                    print(f"Starting background voiceover generation for session: {session_id}")
                    
                    # Generate voiceover
                    result = voiceover_system.generate_speech(
                        text=text,
                        voice=voice,
                        speed=speed,
                        format=format_type,
                        session_id=session_id,
                        background_image_path=background_image_path,
                        generation_type=generation_type
                    )
                    
                    if result['success']:
                        # Emit completion event
                        socketio.emit('voiceover_complete', {
                            'session_id': session_id,
                            'file_url': result['file_url'],
                            'duration': result.get('duration'),
                            'format': result.get('format'),
                            'message': 'Voiceover generated successfully!'
                        }, to=session_id)
                        print(f"Voiceover completed for session: {session_id}")
                    else:
                        # Emit error event
                        socketio.emit('voiceover_error', {
                            'session_id': session_id,
                            'error': result.get('error', 'Unknown error')
                        }, to=session_id)
                        print(f"Voiceover failed for session: {session_id}")
                    
                    # Cleanup background image
                    if background_image_path and os.path.exists(background_image_path):
                        try:
                            os.remove(background_image_path)
                        except Exception:
                            pass
                            
            except Exception as e:
                print(f"Background voiceover error: {e}")
                socketio.emit('voiceover_error', {
                    'session_id': session_id,
                    'error': str(e)
                }, to=session_id)
                
                # Cleanup on error
                if background_image_path and os.path.exists(background_image_path):
                    try:
                        os.remove(background_image_path)
                    except Exception:
                        pass
        
        # Start background thread
        thread = threading.Thread(target=background_voiceover_generation)
        thread.daemon = True
        thread.start()
        
        return jsonify({
            'success': True,
            'session_id': session_id,
            'message': 'Voiceover generation started. Listen for WebSocket events for progress.'
        })
        
    except Exception as e:
        print(f"Voiceover generation error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/download-voiceover/<filename>')
def download_voiceover(filename):
    """Download generated voiceover files"""
    try:
        # Security check: ensure filename is safe
        safe_filename = secure_filename(filename)
        if safe_filename != filename:
            return jsonify({'error': 'Invalid filename'}), 400
        
        file_path = os.path.join(voiceover_system.output_folder, safe_filename)
        
        if not os.path.exists(file_path):
            return jsonify({'error': 'File not found'}), 404
        
        # Determine MIME type based on file extension
        ext = os.path.splitext(safe_filename)[1].lower()
        if ext == '.mp3':
            mimetype = 'audio/mpeg'
        elif ext == '.wav':
            mimetype = 'audio/wav'
        elif ext == '.mp4':
            mimetype = 'video/mp4'
        elif ext == '.zip':
            mimetype = 'application/zip'
        else:
            mimetype = 'application/octet-stream'
        
        return send_file(
            file_path,
            mimetype=mimetype,
            as_attachment=True,
            download_name=safe_filename
        )
        
    except Exception as e:
        print(f"Download error: {e}")
        return jsonify({'error': 'Download failed'}), 500

# YouTube Shorts API Endpoints
@app.route('/api/v1/generate-shorts', methods=['POST'])
def api_generate_shorts_alt():
    """Alternative API endpoint to generate YouTube Shorts videos from script (for backward compatibility)"""
    try:
        data = request.get_json()
        
        # Validate required fields
        script = data.get('script', '').strip()
        if not script:
            return jsonify({'error': 'Script is required'}), 400
        
        # Validate optional parameters
        voice = data.get('voice', 'onyx')
        speed = float(data.get('speed', 1.2))
        background_image_url = data.get('background_image_url')
        webhook_url = data.get('webhook_url')
        
        # Validation
        if voice not in voiceover_system.available_voices:
            return jsonify({'error': f'Invalid voice. Use: {", ".join(voiceover_system.available_voices)}'}), 400
        
        if not (0.25 <= speed <= 4.0):
            return jsonify({'error': 'Speed must be between 0.25 and 4.0'}), 400
        
        # Generate session ID
        session_id = f"api_{uuid.uuid4()}"
        
        # Initialize session tracking
        api_sessions[session_id] = {
            'status': 'queued',
            'progress': 0,
            'message': 'Request queued for processing...',
            'script': script,
            'voice': voice,
            'speed': speed,
            'background_image_url': background_image_url,
            'webhook_url': webhook_url,
            'created_at': datetime.now().isoformat(),
            'estimated_segments': len(script.split('— pause —')) if '— pause —' in script else len(script.split('\n\n')),
            'current_segment': 0
        }
        
        # Start background processing
        thread = threading.Thread(
            target=process_api_shorts_async,
            args=(session_id, script, voice, speed, background_image_url, webhook_url)
        )
        thread.daemon = True
        thread.start()
        
        return jsonify({
            'success': True,
            'session_id': session_id,
            'message': 'YouTube Shorts generation started',
            'status_url': f'/api/v1/shorts/status/{session_id}',
            'estimated_segments': api_sessions[session_id]['estimated_segments']
        }), 202
        
    except Exception as e:
        print(f"API Shorts Error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/v1/shorts/generate', methods=['POST'])
def api_generate_shorts():
    """API endpoint to generate YouTube Shorts videos from script"""
    try:
        data = request.get_json()
        
        # Validate required fields
        script = data.get('script', '').strip()
        if not script:
            return jsonify({'error': 'Script is required'}), 400
        
        # Validate optional parameters
        voice = data.get('voice', 'onyx')
        speed = float(data.get('speed', 1.2))
        background_image_url = data.get('background_image_url')
        webhook_url = data.get('webhook_url')
        
        # Validation
        if voice not in voiceover_system.available_voices:
            return jsonify({'error': f'Invalid voice. Use: {", ".join(voiceover_system.available_voices)}'}), 400
        
        if not (0.25 <= speed <= 4.0):
            return jsonify({'error': 'Speed must be between 0.25 and 4.0'}), 400
        
        # Generate session ID
        session_id = f"api_{uuid.uuid4()}"
        
        # Initialize session tracking
        api_sessions[session_id] = {
            'status': 'queued',
            'progress': 0,
            'message': 'Request queued for processing...',
            'script': script,
            'voice': voice,
            'speed': speed,
            'background_image_url': background_image_url,
            'webhook_url': webhook_url,
            'created_at': datetime.now().isoformat(),
            'estimated_segments': len(script.split('— pause —')) if '— pause —' in script else len(script.split('\n\n')),
            'current_segment': 0
        }
        
        # Start background processing
        thread = threading.Thread(
            target=process_api_shorts_async,
            args=(session_id, script, voice, speed, background_image_url, webhook_url)
        )
        thread.daemon = True
        thread.start()
        
        return jsonify({
            'success': True,
            'session_id': session_id,
            'message': 'YouTube Shorts generation started',
            'status_url': f'/api/v1/shorts/status/{session_id}',
            'estimated_segments': api_sessions[session_id]['estimated_segments']
        }), 202
        
    except Exception as e:
        print(f"API Shorts Error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/v1/shorts/status/<session_id>', methods=['GET'])
def api_shorts_status(session_id):
    """Get status of YouTube Shorts generation"""
    try:
        if (session_id not in api_sessions):
            return jsonify({'error': 'Session not found'}), 404
        
        session_data = api_sessions[session_id].copy()
        
        # Build proper ZIP URL if completed and promote it to top level
        if (session_data['status'] == 'completed' and 'result' in session_data):
            result = session_data['result']
            zip_url = result.get('zip_url')
            
            if zip_url:
                # Build full URL for API response
                if zip_url.startswith('/'):
                    base_url = request.url_root.rstrip('/')
                    full_zip_url = f"{base_url}{zip_url}"
                else:
                    full_zip_url = zip_url
                
                # Promote zip_url to top level for client compatibility
                session_data['zip_url'] = full_zip_url
                
                # Also add video details for completed shorts
                segments = result.get('segments', 1)
                session_data['count'] = segments
                session_data['current_segment'] = segments
                session_data['total_segments'] = segments
                
                # Create video array if not present
                if 'videos' not in session_data:
                    session_data['videos'] = []
                    for i in range(segments):
                        session_data['videos'].append({
                            'index': i + 1,
                            'file_url': f"/download-voiceover/api_shorts_{session_id}_part_{i+1}.mp4",
                            'duration': 8.5,
                            'format': 'mp4',
                            'download_name': f"api_shorts_{session_id}_part_{i+1}.mp4"
                        })
        
        return jsonify(session_data)
        
    except Exception as e:
        print(f"API Status Error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/v1/shorts-status/<session_id>', methods=['GET'])
def api_shorts_status_alt(session_id):
    """Alternative endpoint for YouTube Shorts status (for backward compatibility)"""
    try:
        if (session_id not in api_sessions):
            return jsonify({'error': 'Session not found'}), 404
        
        session_data = api_sessions[session_id].copy()
        
        # Build proper ZIP URL if completed and promote it to top level
        if (session_data['status'] == 'completed' and 'result' in session_data):
            result = session_data['result']
            zip_url = result.get('zip_url')
            
            if zip_url:
                # Build full URL for API response
                if zip_url.startswith('/'):
                    base_url = request.url_root.rstrip('/')
                    full_zip_url = f"{base_url}{zip_url}"
                else:
                    full_zip_url = zip_url
                
                # Promote zip_url to top level for client compatibility
                session_data['zip_url'] = full_zip_url
                
                # Also add video details for completed shorts
                segments = result.get('segments', 1)
                session_data['count'] = segments
                session_data['current_segment'] = segments
                session_data['total_segments'] = segments
                
                # Create video array if not present
                if 'videos' not in session_data:
                    session_data['videos'] = []
                    for i in range(segments):
                        session_data['videos'].append({
                            'index': i + 1,
                            'file_url': f"/download-voiceover/api_shorts_{session_id}_part_{i+1}.mp4",
                            'duration': 8.5,
                            'format': 'mp4',
                            'download_name': f"api_shorts_{session_id}_part_{i+1}.mp4"
                        })
        
        return jsonify(session_data)
        
    except Exception as e:
        print(f"API Status Error: {e}")
        return jsonify({'error': str(e)}), 500

# New Voiceover API Endpoints
@app.route('/api/v1/voiceover/generate', methods=['POST'])
def api_generate_voiceover():
    """API endpoint to generate regular format voiceover videos from script"""
    try:
        data = request.get_json()
        
        # Validate required fields
        script = data.get('script', '').strip()
        if not script:
            return jsonify({'error': 'Script is required'}), 400
        
        # Validate optional parameters
        voice = data.get('voice', 'onyx')
        speed = float(data.get('speed', 1.2))
        format_type = data.get('format', 'mp4')
        background_image_url = data.get('background_image_url')
        webhook_url = data.get('webhook_url')
        
        # Validation
        if voice not in voiceover_system.available_voices:
            return jsonify({'error': f'Invalid voice. Use: {", ".join(voiceover_system.available_voices)}'}), 400
        
        if not (0.25 <= speed <= 4.0):
            return jsonify({'error': 'Speed must be between 0.25 and 4.0'}), 400
        
        if format_type not in voiceover_system.supported_formats:
            return jsonify({'error': f'Unsupported format. Use: {", ".join(voiceover_system.supported_formats)}'}), 400
        
        # Generate session ID
        session_id = f"api_voiceover_{uuid.uuid4()}"
        
        # Initialize session tracking
        api_voiceover_sessions[session_id] = {
            'status': 'queued',
            'progress': 0,
            'message': 'Request queued for processing...',
            'script': script,
            'voice': voice,
            'speed': speed,
            'format': format_type,
            'background_image_url': background_image_url,
            'webhook_url': webhook_url,
            'created_at': datetime.now().isoformat()
        }
        
        # Start background processing
        thread = threading.Thread(
            target=process_api_voiceover_async,
            args=(session_id, script, voice, speed, format_type, background_image_url, webhook_url)
        )
        thread.daemon = True
        thread.start()
        
        return jsonify({
            'success': True,
            'session_id': session_id,
            'message': 'Voiceover generation started',
            'status_url': f'/api/v1/voiceover/status/{session_id}'
        }), 202
        
    except Exception as e:
        print(f"API Voiceover Error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/v1/voiceover/status/<session_id>', methods=['GET'])
def api_voiceover_status(session_id):
    """Get status of voiceover generation"""
    try:
        if session_id not in api_voiceover_sessions:
            return jsonify({'error': 'Session not found'}), 404
        
        session_data = api_voiceover_sessions[session_id].copy()
        
        # Build proper video URL if completed
        if session_data['status'] == 'completed' and 'result' in session_data:
            video_url = session_data['result'].get('file_url')
            if video_url and video_url.startswith('/'):
                # Build full URL for API response
                base_url = request.url_root.rstrip('/')
                session_data['result']['file_url'] = f"{base_url}{video_url}"
        
        return jsonify(session_data)
        
    except Exception as e:
        print(f"API Voiceover Status Error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/v1/voiceover/download/<session_id>', methods=['GET'])
def api_voiceover_download(session_id):
    """Direct download endpoint for voiceover API - returns MP4 file directly"""
    try:
        print(f"Download request for session: {session_id}")
        
        if session_id not in api_voiceover_sessions:
            print(f"Session {session_id} not found in api_voiceover_sessions")
            print(f"Available sessions: {list(api_voiceover_sessions.keys())}")
            return jsonify({'error': 'Session not found'}), 404
        
        session_data = api_voiceover_sessions[session_id]
        print(f"Session data: {session_data}")
        
        if session_data['status'] != 'completed':
            print(f"Session status is {session_data['status']}, not completed")
            return jsonify({'error': 'Generation not completed yet'}), 400
        
        if 'result' not in session_data:
            print("No result found in session data")
            return jsonify({'error': 'No result available'}), 404
        
        # Get the file URL and convert to file path
        result = session_data['result']
        file_url = result.get('file_url')
        print(f"File URL from result: {file_url}")
        
        if not file_url:
            print("No file_url found in result")
            return jsonify({'error': 'No file URL available'}), 404
        
        # Handle different URL formats
        if file_url.startswith('/download-voiceover/'):
            filename = file_url.replace('/download-voiceover/', '')
        elif file_url.startswith('/api/v1/voiceover/download/'):
            # Handle case where URL might be malformed
            filename = file_url.replace('/api/v1/voiceover/download/', '')
        else:
            # Try to extract filename from the URL
            filename = os.path.basename(file_url)
        
        print(f"Extracted filename: {filename}")
        
        # Construct the full file path
        file_path = os.path.join(voiceover_system.output_folder, filename)
        print(f"Full file path: {file_path}")
        
        if not os.path.exists(file_path):
            print(f"File does not exist at path: {file_path}")
            print(f"Voiceover system output folder: {voiceover_system.output_folder}")
            # List files in the output folder for debugging
            try:
                files_in_folder = os.listdir(voiceover_system.output_folder)
                print(f"Files in output folder: {files_in_folder}")
            except Exception as e:
                print(f"Error listing output folder: {e}")
            return jsonify({'error': 'Generated file not found'}), 404
        
        # Determine MIME type based on format
        format_type = result.get('format', 'mp4')
        if format_type == 'mp4':
            mimetype = 'video/mp4'
        elif format_type == 'mp3':
            mimetype = 'audio/mpeg'
        elif format_type == 'wav':
            mimetype = 'audio/wav'
        else:
            mimetype = 'application/octet-stream'
        
        # Get the download filename
        download_filename = result.get('filename', f'voiceover.{format_type}')
        print(f"Serving file with mimetype: {mimetype}, download name: {download_filename}")
        
        # Return the file directly
        return send_file(
            file_path,
            mimetype=mimetype,
            as_attachment=True,
            download_name=download_filename
        )
        
    except Exception as e:
        print(f"API Voiceover Download Error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': f'Download failed: {str(e)}'}), 500

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

def process_api_shorts_async(session_id, script, voice, speed, background_image_url=None, webhook_url=None):
    """Background processing function for API YouTube Shorts generation"""
    try:
        with app.app_context():
            print(f"Starting API shorts processing for session: {session_id}")
            
            # Update session status
            if session_id in api_sessions:
                api_sessions[session_id].update({
                    'status': 'processing',
                    'progress': 10,
                    'message': 'Initializing YouTube Shorts generation...',
                    'updated_at': datetime.now().isoformat()
                })
            
            # Handle background image if provided
            background_image_path = None
            if background_image_url:
                try:
                    import requests
                    response = requests.get(background_image_url, timeout=30)
                    if response.status_code == 200:
                        # Extract filename from URL or generate one
                        import urllib.parse
                        parsed_url = urllib.parse.urlparse(background_image_url)
                        filename = os.path.basename(parsed_url.path) or f"bg_{uuid.uuid4()}.jpg"
                        
                        # Ensure it has a valid image extension
                        if not filename.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.bmp')):
                            filename += '.jpg'
                        
                        background_image_path = os.path.join(app.config['TEMP_FOLDER'], f"api_bg_{session_id}_{filename}")
                        
                        with open(background_image_path, 'wb') as f:
                            f.write(response.content)
                        
                        print(f"Downloaded background image: {background_image_path}")
                        
                        # Update progress
                        api_sessions[session_id].update({
                            'progress': 25,
                            'message': 'Background image downloaded, splitting script...'
                        })
                        
                except Exception as e:
                    print(f"Failed to download background image: {e}")
                    # Continue without background image
            
            # Update progress before splitting
            api_sessions[session_id].update({
                'progress': 30,
                'message': 'Splitting script into YouTube Shorts segments...'
            })
            
            # Split script by pause markers (same logic as UI)
            pause_markers = ['— pause —', '-- pause --']
            script_segments = []
            
            # Split the script by pause markers
            current_script = script
            for marker in pause_markers:
                if (marker in current_script):
                    segments = current_script.split(marker)
                    script_segments = [seg.strip() for seg in segments if seg.strip()]
                    break
            
            # If no pause markers found, treat as single segment
            if not script_segments:
                script_segments = [script.strip()]
            
            print(f"Split script into {len(script_segments)} segments for YouTube Shorts")
            
            # Helper function to create filename from first 10 words
            def create_filename_from_text(text, segment_number):
                """Create a safe filename from the first 10 words of the text"""
                if not text:
                    return f"shorts_part_{segment_number}"
                
                # Clean the text and get first 10 words
                words = re.sub(r'[^\w\s]', '', text).split()[:10]
                if not words:
                    return f"shorts_part_{segment_number}"
                
                # Join words and create safe filename
                filename_base = '_'.join(words).lower()
                
                # Remove any remaining unsafe characters and limit length
                filename_base = re.sub(r'[^\w\-_]', '', filename_base)[:50]
                
                # Ensure it's not empty after cleaning
                if not filename_base:
                    return f"shorts_part_{segment_number}"
                
                return filename_base
            
            # Update progress
            api_sessions[session_id].update({
                'progress': 40,
                'message': f'Generating {len(script_segments)} YouTube Shorts videos...',
                'total_segments': len(script_segments),
                'current_segment': 0
            })
            
            # Generate individual videos for each segment
            video_files = []
            segment_results = []
            
            for i, segment in enumerate(script_segments):
                try:
                    print(f"Generating segment {i+1}/{len(script_segments)}")
                    
                    # Update progress for current segment
                    segment_progress = 40 + int((i / len(script_segments)) * 40)
                    api_sessions[session_id].update({
                        'progress': segment_progress,
                        'message': f'Generating video {i+1} of {len(script_segments)}...',
                        'current_segment': i + 1
                    })
                    
                    # Create filename from first 10 words of the segment
                    filename_base = create_filename_from_text(segment, i + 1)
                    custom_filename = f"api_shorts_{session_id}_{filename_base}"
                    
                    # Generate individual video for this segment
                    segment_session_id = f"{session_id}_part_{i+1}"
                    result = voiceover_system.generate_speech(
                        text=segment,
                        voice=voice,
                        speed=speed,
                        format='mp4',
                        session_id=segment_session_id,
                        background_image_path=background_image_path,
                        generation_type='youtube_shorts',  # ✅ CRITICAL FIX: This tells the system to use portrait format + shorts_background.mp4
                        custom_filename=custom_filename
                    )
                    
                    if result['success']:
                        video_files.append(result['file_path'])
                        segment_results.append({
                            'segment': i + 1,
                            'file_path': result['file_path'],
                            'file_url': result['file_url'],
                            'duration': result.get('duration'),
                            'text': segment[:100] + '...' if len(segment) > 100 else segment,
                            'filename': f"{filename_base}.mp4"
                        })
                        print(f"Successfully generated segment {i+1} with filename: {filename_base}.mp4")
                    else:
                        print(f"Failed to generate segment {i+1}: {result.get('error')}")
                        # Continue with other segments even if one fails
                        
                except Exception as e:
                    print(f"Error generating segment {i+1}: {e}")
                    # Continue with other segments
                    continue
            
            if not video_files:
                raise Exception("No video segments were successfully generated")
            
            # Update progress before creating ZIP
            api_sessions[session_id].update({
                'progress': 85,
                'message': f'Creating ZIP package with {len(video_files)} videos...'
            })
            
            # Create ZIP file containing all videos
            zip_filename = f"api_shorts_{session_id}.zip"
            zip_path = os.path.join(voiceover_system.output_folder, zip_filename)
            
            with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zip_file:
                for i, video_path in enumerate(video_files):
                    if os.path.exists(video_path):
                        # Use the descriptive filename based on content
                        filename_base = create_filename_from_text(script_segments[i], i + 1)
                        video_filename = f"{filename_base}.mp4"
                        zip_file.write(video_path, video_filename)
                        print(f"Added {video_filename} to ZIP")
            
            print(f"Created ZIP file: {zip_path}")
            
            # Build full URL for the result
            base_url = f"{app.config['PREFERRED_URL_SCHEME']}://{app.config['SERVER_NAME']}"
            zip_file_url = f"/download-voiceover/{zip_filename}"
            full_zip_url = f"{base_url}{zip_file_url}"
            
            # Update session with success
            api_sessions[session_id].update({
                'status': 'completed',
                'progress': 100,
                'message': f'YouTube Shorts generation completed! Created {len(video_files)} videos.',
                'result': {
                    'zip_url': zip_file_url,  # Keep relative URL for internal use
                    'full_zip_url': full_zip_url,   # Full URL for external use
                    'filename': zip_filename,
                    'segments': len(video_files),
                    'videos': segment_results,
                    'total_duration': sum(r.get('duration', 0) for r in segment_results if r.get('duration'))
                },
                'completed_at': datetime.now().isoformat()
            })
            
            # Send webhook if provided
            if webhook_url:
                try:
                    import requests
                    webhook_data = {
                        'session_id': session_id,
                        'status': 'completed',
                        'result': api_sessions[session_id]['result']
                    }
                    requests.post(webhook_url, json=webhook_data, timeout=30)
                except Exception as e:
                    print(f"Webhook error: {e}")
            
            print(f"API Shorts completed for session: {session_id} with {len(video_files)} videos")
            
            # Cleanup background image
            if background_image_path and os.path.exists(background_image_path):
                try:
                    os.remove(background_image_path)
                except Exception:
                    pass
    
    except Exception as e:
        print(f"API Shorts processing error for session {session_id}: {e}")
        import traceback
        traceback.print_exc()
        
        # Update session with error
        if session_id in api_sessions:
            api_sessions[session_id].update({
                'status': 'failed',
                'progress': 0,
                'message': f"Processing error: {str(e)}",
                'error': str(e),
                'failed_at': datetime.now().isoformat()
            })
        
        # Send webhook if provided
        if webhook_url:
            try:
                import requests
                webhook_data = {
                    'session_id': session_id,
                    'status': 'failed',
                    'error': str(e)
                }
                requests.post(webhook_url, json=webhook_data, timeout=30)
            except Exception:
                pass
        
        # Cleanup on error
        if background_image_path and os.path.exists(background_image_path):
            try:
                os.remove(background_image_path)
            except Exception:
                pass

def process_api_voiceover_async(session_id, script, voice, speed, format_type, background_image_url=None, webhook_url=None):
    """Background processing function for API voiceover generation"""
    try:
        with app.app_context():
            print(f"Starting API voiceover processing for session: {session_id}")
            
            # Update session status
            if session_id in api_voiceover_sessions:
                api_voiceover_sessions[session_id].update({
                    'status': 'processing',
                    'progress': 10,
                    'message': 'Initializing voiceover generation...',
                    'updated_at': datetime.now().isoformat()
                })
            
            # Handle background image if provided
            background_image_path = None
            if background_image_url:
                try:
                    import requests
                    response = requests.get(background_image_url, timeout=30)
                    if response.status_code == 200:
                        # Extract filename from URL or generate one
                        import urllib.parse
                        parsed_url = urllib.parse.urlparse(background_image_url)
                        filename = os.path.basename(parsed_url.path) or f"bg_{uuid.uuid4()}.jpg"
                        
                        # Ensure it has a valid image extension
                        if not filename.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.bmp')):
                            filename += '.jpg'
                        
                        background_image_path = os.path.join(app.config['TEMP_FOLDER'], f"api_voiceover_bg_{session_id}_{filename}")
                        
                        with open(background_image_path, 'wb') as f:
                            f.write(response.content)
                        
                        print(f"Downloaded background image: {background_image_path}")
                        
                        # Update progress
                        api_voiceover_sessions[session_id].update({
                            'progress': 25,
                            'message': 'Background image downloaded, generating voiceover...'
                        })
                        
                except Exception as e:
                    print(f"Failed to download background image: {e}")
                    # Continue without background image
            
            # Update progress before generation
            api_voiceover_sessions[session_id].update({
                'progress': 40,
                'message': 'Generating voiceover...'
            })
            
            # Generate voiceover using the voiceover system
            result = voiceover_system.generate_speech(
                text=script,
                voice=voice,
                speed=speed,
                format=format_type,
                session_id=session_id,
                background_image_path=background_image_path,
                generation_type='regular'
            )
            
            # Update progress
            api_voiceover_sessions[session_id].update({
                'progress': 80,
                'message': 'Processing voiceover file...'
            })
            
            if result['success']:
                # Build full URL for the result
                base_url = f"{app.config['PREFERRED_URL_SCHEME']}://{app.config['SERVER_NAME']}"
                full_file_url = f"{base_url}{result['file_url']}"
                
                # Update session with success
                api_voiceover_sessions[session_id].update({
                    'status': 'completed',
                    'progress': 100,
                    'message': 'Voiceover generation completed successfully!',
                    'result': {
                        'file_url': result['file_url'],  # Keep relative URL for internal use
                        'full_file_url': full_file_url,   # Full URL for external use
                        'filename': result.get('filename', f'voiceover.{format_type}'),
                        'duration': result.get('duration'),
                        'format': result.get('format', format_type)
                    },
                    'completed_at': datetime.now().isoformat()
                })
                
                # Send webhook if provided
                if webhook_url:
                    try:
                        import requests
                        webhook_data = {
                            'session_id': session_id,
                            'status': 'completed',
                            'result': api_voiceover_sessions[session_id]['result']
                        }
                        requests.post(webhook_url, json=webhook_data, timeout=30)
                    except Exception as e:
                        print(f"Webhook error: {e}")
                
                print(f"API Voiceover completed for session: {session_id}")
            else:
                # Update session with error
                api_voiceover_sessions[session_id].update({
                    'status': 'failed',
                    'progress': 0,
                    'message': f"Generation failed: {result.get('error', 'Unknown error')}",
                    'error': result.get('error', 'Unknown error'),
                    'failed_at': datetime.now().isoformat()
                })
                
                # Send webhook if provided
                if webhook_url:
                    try:
                        import requests
                        webhook_data = {
                            'session_id': session_id,
                            'status': 'failed',
                            'error': result.get('error', 'Unknown error')
                        }
                        requests.post(webhook_url, json=webhook_data, timeout=30)
                    except Exception as e:
                        print(f"Webhook error: {e}")
                
                print(f"API Voiceover failed for session: {session_id}")
            
            # Cleanup background image
            if background_image_path and os.path.exists(background_image_path):
                try:
                    os.remove(background_image_path)
                except Exception:
                    pass
    
    except Exception as e:
        print(f"API Voiceover processing error for session {session_id}: {e}")
        import traceback
        traceback.print_exc()
        
        # Update session with error
        if session_id in api_voiceover_sessions:
            api_voiceover_sessions[session_id].update({
                'status': 'failed',
                'progress': 0,
                'message': f"Processing error: {str(e)}",
                'error': str(e),
                'failed_at': datetime.now().isoformat()
            })
        
        # Send webhook if provided
        if webhook_url:
            try:
                import requests
                webhook_data = {
                    'session_id': session_id,
                    'status': 'failed',
                    'error': str(e)
                }
                requests.post(webhook_url, json=webhook_data, timeout=30)
            except Exception:
                pass
        
        # Cleanup on error
        if background_image_path and os.path.exists(background_image_path):
            try:
                os.remove(background_image_path)
            except Exception:
                pass

@app.route('/api/v1/search', methods=['POST'])
def api_search():
    """API endpoint for searching documents"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No JSON data provided'}), 400
        
        session_id = data.get('session_id')
        query = data.get('query', '').strip()
        max_results = min(int(data.get('max_results', 5)), 20)  # Cap at 20
        
        if not session_id:
            return jsonify({'error': 'session_id is required'}), 400
        
        if not query:
            return jsonify({'error': 'query is required'}), 400
        
        # Search documents using the correct method
        results = rag_system.search_documents(session_id, query, max_results)
        
        return jsonify({
            'session_id': session_id,
            'query': query,
            'results': results,
            'total_results': len(results)
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/v1/voiceover', methods=['POST'])
def api_voiceover():
    """API endpoint for voiceover generation"""
    try:
        # Get form data
        script = request.form.get('script', '').strip()
        voice = request.form.get('voice', 'alloy')
        speed = float(request.form.get('speed', 1.0))
        format_type = request.form.get('format', 'mp3')
        webhook_url = request.form.get('webhook_url', '').strip() or None
        background_image_url = request.form.get('background_image_url', '').strip() or None
        
        # Handle file upload
        background_image = request.files.get('background_image')
        background_image_path = None
        
        if background_image and background_image.filename and background_image.filename.strip():
            filename = secure_filename(background_image.filename or 'image.png')
            if filename and filename.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.bmp')):
                background_image_path = os.path.join(app.config['TEMP_FOLDER'], f"api_bg_{uuid.uuid4()}_{filename}")
                background_image.save(background_image_path)
        
        # Validate required fields
        if not script:
            return jsonify({'error': 'Script is required'}), 400
        
        # Generate session ID
        session_id = f"api_voiceover_{uuid.uuid4()}"
        
        # Start background processing
        thread = threading.Thread(
            target=process_api_voiceover_async,
            args=(session_id, script, voice, speed, format_type, background_image_url, webhook_url)
        )
        thread.daemon = True
        thread.start()
        
        return jsonify({
            'success': True,
            'session_id': session_id,
            'message': 'Voiceover generation started'
        }), 202
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/generate-voiceover/standalone', methods=['POST'])
def generate_voiceover_standalone():
    """Generate standalone voiceover (no background processing, direct response)"""
    try:
        print(f"Received standalone voiceover request")
        print(f"Content-Type: {request.content_type}")
        print(f"Has files: {bool(request.files)}")
        
        # Handle both JSON and form data requests
        if request.content_type and 'application/json' in request.content_type:
            # JSON request (no background image)
            data = request.get_json()
            text = data.get('text', '').strip()
            voice = data.get('voice', 'onyx')
            speed = float(data.get('speed', 1.2))
            format_type = data.get('format', 'mp3')
            generation_type = data.get('generation_type', 'standalone')
            background_image = None
        else:
            # Form data request (potentially with background image)
            text = request.form.get('text', '').strip()
            voice = request.form.get('voice', 'onyx')
            speed = float(request.form.get('speed', 1.2))
            format_type = request.form.get('format', 'mp3')
            generation_type = request.form.get('generation_type', 'standalone')
            background_image = request.files.get('backgroundImage')
        
        print(f"Parsed request - text length: {len(text)}, voice: {voice}, speed: {speed}, format: {format_type}")
        
        # Validate required fields
        if not text:
            return jsonify({'error': 'Text is required'}), 400
        
        # Validate format
        if format_type not in voiceover_system.supported_formats:
            return jsonify({'error': f'Unsupported format. Use: {", ".join(voiceover_system.supported_formats)}'}), 400
        
        # Validate voice
        if voice not in voiceover_system.available_voices:
            return jsonify({'error': f'Invalid voice. Use: {", ".join(voiceover_system.available_voices)}'}), 400
        
        # Validate speed
        if not (0.25 <= speed <= 4.0):
            return jsonify({'error': 'Speed must be between 0.25 and 4.0'}), 400
        
        # Handle background image upload
        background_image_path = None
        if background_image and background_image.filename:
            filename = secure_filename(background_image.filename)
            if filename and filename.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.bmp')):
                background_image_path = os.path.join(app.config['TEMP_FOLDER'], f"bg_{uuid.uuid4()}_{filename}")
                background_image.save(background_image_path)
                print(f"Background image saved: {background_image_path}")
        
        # Generate session ID for tracking
        session_id = str(uuid.uuid4())
        
        print(f"Generating standalone voiceover for session: {session_id}")
        
        # Generate voiceover synchronously
        result = voiceover_system.generate_speech(
            text=text,
            voice=voice,
            speed=speed,
            format=format_type,
            session_id=session_id,
            background_image_path=background_image_path,
            generation_type=generation_type
        )
        
        # Cleanup background image
        if background_image_path and os.path.exists(background_image_path):
            try:
                os.remove(background_image_path)
            except Exception:
                pass
        
        if result['success']:
            # Build full URL for the result
            base_url = request.url_root.rstrip('/')
            full_file_url = f"{base_url}{result['file_url']}"
            
            return jsonify({
                'success': True,
                'session_id': session_id,
                'file_url': result['file_url'],
                'full_file_url': full_file_url,
                'filename': result.get('filename'),
                'duration': result.get('duration'),
                'format': result.get('format'),
                'message': 'Voiceover generated successfully!'
            })
        else:
            return jsonify({
                'success': False,
                'error': result.get('error', 'Unknown error'),
                'session_id': session_id
            }), 500
        
    except Exception as e:
        print(f"Standalone voiceover generation error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/generate-voiceover/<session_id>', methods=['POST'])
def generate_voiceover_with_session(session_id):
    """Generate voiceover for a specific session (WebSocket-based progress tracking)"""
    try:
        print(f"Received session voiceover request for session: {session_id}")
        print(f"Content-Type: {request.content_type}")
        print(f"Has files: {bool(request.files)}")
        
        # Handle both JSON and form data requests
        if request.content_type and 'application/json' in request.content_type:
            # JSON request (no background image)
            data = request.get_json()
            text = data.get('text', '').strip()
            voice = data.get('voice', 'onyx')
            speed = float(data.get('speed', 1.2))
            format_type = data.get('format', 'mp3')
            generation_type = data.get('generation_type', 'regular')
            background_image = None
        else:
            # Form data request (potentially with background image)
            text = request.form.get('text', '').strip()
            voice = request.form.get('voice', 'onyx')
            speed = float(request.form.get('speed', 1.2))
            format_type = request.form.get('format', 'mp3')
            generation_type = request.form.get('generation_type', 'regular')
            background_image = request.files.get('backgroundImage')
        
        print(f"Parsed session request - text length: {len(text)}, voice: {voice}, speed: {speed}, format: {format_type}")
        
        # Validate required fields
        if not text:
            return jsonify({'error': 'Text is required'}), 400
        
        # Validate format
        if format_type not in voiceover_system.supported_formats:
            return jsonify({'error': f'Unsupported format. Use: {", ".join(voiceover_system.supported_formats)}'}), 400
        
        # Validate voice
        if voice not in voiceover_system.available_voices:
            return jsonify({'error': f'Invalid voice. Use: {", ".join(voiceover_system.available_voices)}'}), 400
        
        # Validate speed
        if not (0.25 <= speed <= 4.0):
            return jsonify({'error': 'Speed must be between 0.25 and 4.0'}), 400
        
        # Handle background image upload
        background_image_path = None
        if background_image and background_image.filename:
            filename = secure_filename(background_image.filename)
            if filename and filename.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.bmp')):
                background_image_path = os.path.join(app.config['TEMP_FOLDER'], f"bg_{session_id}_{filename}")
                background_image.save(background_image_path)
                print(f"Background image saved: {background_image_path}")
        
        print(f"Generating session voiceover for session: {session_id}")
        
        # Start background processing with WebSocket updates
        def background_voiceover_generation():
            try:
                with app.app_context():
                    print(f"Starting background voiceover generation for session: {session_id}")
                    
                    # Emit start event
                    socketio.emit('voiceover_progress', {
                        'session_id': session_id,
                        'progress': 10,
                        'message': 'Starting voiceover generation...'
                    }, to=session_id)
                    
                    # Generate voiceover
                    result = voiceover_system.generate_speech(
                        text=text,
                        voice=voice,
                        speed=speed,
                        format=format_type,
                        session_id=session_id,
                        background_image_path=background_image_path,
                        generation_type=generation_type
                    )
                    
                    if result['success']:
                        # Emit completion event
                        socketio.emit('voiceover_complete', {
                            'session_id': session_id,
                            'file_url': result['file_url'],
                            'duration': result.get('duration'),
                            'format': result.get('format'),
                            'filename': result.get('filename'),
                            'message': 'Voiceover generated successfully!'
                        }, to=session_id)
                        print(f"Session voiceover completed for session: {session_id}")
                    else:
                        # Emit error event
                        socketio.emit('voiceover_error', {
                            'session_id': session_id,
                            'error': result.get('error', 'Unknown error')
                        }, to=session_id)
                        print(f"Session voiceover failed for session: {session_id}")
                    
                    # Cleanup background image
                    if background_image_path and os.path.exists(background_image_path):
                        try:
                            os.remove(background_image_path)
                        except Exception:
                            pass
                            
            except Exception as e:
                print(f"Background session voiceover error: {e}")
                import traceback
                traceback.print_exc()
                socketio.emit('voiceover_error', {
                    'session_id': session_id,
                    'error': str(e)
                }, to=session_id)
                
                # Cleanup on error
                if background_image_path and os.path.exists(background_image_path):
                    try:
                        os.remove(background_image_path)
                    except Exception:
                        pass
        
        # Start background thread
        thread = threading.Thread(target=background_voiceover_generation)
        thread.daemon = True
        thread.start()
        
        return jsonify({
            'success': True,
            'session_id': session_id,
            'message': 'Voiceover generation started. Listen for WebSocket events for progress.'
        })
        
    except Exception as e:
        print(f"Session voiceover generation error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

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