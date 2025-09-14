# Newspaper Summary - PDF Processing & AI Summarization

A comprehensive web application for processing Economic Times newspaper PDFs with AI-powered summarization and voiceover generation capabilities.

## Features

🔄 **Dual Processing Modes**
- **OCR Processing**: For scanned PDFs that need text extraction via Tesseract OCR
- **Direct Upload**: For text-readable PDFs (faster processing, direct to AI summary)
- Split multi-page PDFs into individual page files
- Merge processed pages back into a single searchable PDF
- Real-time progress tracking for all operations

🤖 **AI-Powered Summarization**
- Extract text from processed PDFs
- Store content in ChromaDB vector database
- RAG (Retrieval-Augmented Generation) implementation
- OpenAI GPT integration for intelligent summarization
- Customizable prompts for different analysis needs

🎤 **AI Voiceover Generation** (NEW!)
- **Standalone Voiceover Creator**: Generate AI voiceovers without uploading PDFs
- **Summary-to-Voice**: Convert AI-generated summaries to professional voiceovers
- **Custom Text-to-Voice**: Create voiceovers from any text content
- **6 Voice Options**: Choose from Alloy, Echo, Fable, Onyx, Nova, and Shimmer
- **Speed Control**: Adjustable speech speed (0.7x to 1.5x)
- **Multiple Formats**: Generate MP3 audio, WAV audio, or MP4 video with waveforms
- **High-Quality TTS**: Powered by OpenAI's advanced text-to-speech models

🌐 **Modern Web Interface**
- Responsive Bootstrap UI
- Drag-and-drop file upload
- Real-time WebSocket progress updates
- Mobile-friendly design
- Collapsible panels for enhanced UX

## Prerequisites

### System Requirements
- Python 3.8 or higher
- Tesseract OCR engine (for OCR processing mode)
- FFmpeg (for video generation)

### Install Dependencies

**FFmpeg (required for video generation):**
```bash
# macOS (using Homebrew)
brew install ffmpeg

# Ubuntu/Debian
sudo apt update
sudo apt install ffmpeg

# Windows
# Download from: https://ffmpeg.org/download.html
```

**Tesseract OCR (for OCR processing mode):**
```bash
# macOS (using Homebrew)
brew install tesseract

# Ubuntu/Debian
sudo apt-get update
sudo apt-get install tesseract-ocr

# Windows
# Download from: https://github.com/UB-Mannheim/tesseract/wiki
```

## Installation

1. **Clone the repository:**
```bash
git clone https://github.com/pulkitv/pdf-split-read-rag.git
cd pdf-split-read-rag
```

2. **Install Python dependencies:**
```bash
pip install -r requirements.txt
```

3. **Set up environment variables:**
```bash
cp .env.template .env
```

Edit the `.env` file and add your OpenAI API key:
```bash
OPENAI_API_KEY=your_actual_openai_api_key_here
SECRET_KEY=your_secret_key_here
```

4. **Create required directories:**
```bash
mkdir -p uploads temp processed chroma_db voiceovers
```

## Usage

### Starting the Application

1. **Run the Flask application:**
```bash
python app.py
```

2. **Open your web browser and navigate to:**
```
http://localhost:5000
```

### Standalone AI Voiceover (New Feature!)

**Create voiceovers without uploading any PDFs:**
1. On the homepage, click "Create Voiceover Now"
2. Enter any text content (news summaries, announcements, etc.)
3. Choose voice type, speed, and output format
4. Generate and download professional AI voiceovers
5. Perfect for content creators, accessibility, and quick announcements

### PDF Processing Modes

#### OCR Processing Mode
For scanned PDFs that need text extraction:
1. Select "OCR Processing" mode
2. Upload PDF and click "Start Processing"
3. Monitor progress through 4 steps: Splitting → OCR → Merging → Vector DB
4. Download the searchable PDF
5. Generate AI summary and convert to voiceover

#### Direct Upload Mode  
For text-readable PDFs (faster processing):
1. Select "Direct Upload" mode
2. Upload PDF and click "Start Processing"
3. Monitor progress: Text Extraction & Vector DB Creation
4. Generate AI summary and convert to voiceover

### AI Voiceover Options

#### From Document Summary
1. Process a PDF and generate AI summary
2. Click "Generate AI Voiceover"
3. Choose "Summary to Voice" mode
4. Customize voice settings and generate

#### Custom Text Input
1. In any voiceover section, select "Custom Text to Voice"
2. Enter your own text content
3. Customize voice settings and generate

### Voice Customization Options

- **Voice Types**: Alloy (Neutral), Echo (Deep), Fable (Expressive), Onyx (Professional), Nova (Clear), Shimmer (Warm)
- **Speed Settings**: 0.7x (Slow), 1.0x (Normal), 1.2x (Fast), 1.5x (Very Fast)
- **Output Formats**: 
  - MP3 Audio (standard audio file)
  - WAV Audio (high-quality uncompressed)
  - MP4 Video (with waveform visualization and text overlay)

### Custom Prompts

You can customize the AI summarization by providing specific instructions, such as:
- "Focus on market analysis and stock movements"
- "Summarize policy announcements and their economic impact"
- "Extract key business deals and corporate news"

## Project Structure

```
pdf-split-read-rag/
├── app.py                 # Main Flask application with voiceover endpoints
├── pdf_processor.py       # PDF manipulation and OCR logic
├── rag_system.py         # Vector database and AI integration
├── voiceover_system.py   # AI text-to-speech and video generation
├── requirements.txt      # Python dependencies
├── .env.template        # Environment variables template
├── .gitignore           # Git ignore file
├── templates/
│   └── index.html       # Main web interface with voiceover UI
├── static/
│   ├── app.js          # Frontend JavaScript with voiceover logic
│   └── style.css       # Custom styling including voiceover components
├── uploads/            # User uploaded files
├── temp/              # Temporary processing files
├── processed/         # Final processed PDFs
├── voiceovers/        # Generated voiceover files
└── chroma_db/         # Vector database storage
```

## API Endpoints

### Web Interface Endpoints
- `GET /` - Main web interface
- `POST /upload` - Upload PDF file
- `GET /process/<session_id>` - Start processing pipeline
- `GET /download/<session_id>` - Download processed PDF
- `POST /summarize/<session_id>` - Generate AI summary
- `POST /generate-voiceover/<session_id>` - Generate AI voiceover (supports 'standalone' for independent usage)
- `GET /download-voiceover/<filename>` - Download generated voiceover file
- `GET /status/<session_id>` - Get processing status

### YouTube Shorts API (v1) 🎬

The application provides RESTful API endpoints for generating YouTube Shorts from external projects. Perfect for integrating with content management systems, automation workflows, or other applications.

#### 1. Generate YouTube Shorts
**Endpoint:** `POST /api/v1/generate-shorts`

Generate multiple YouTube Short videos from a script with pause markers.

**Request Headers:**
```
Content-Type: application/json
```

**Request Body:**
```json
{
    "script": "Your script content with — pause — markers to split into multiple shorts",
    "voice": "nova",
    "speed": 1.0,
    "background_image_url": "https://example.com/background.jpg",
    "webhook_url": "https://your-app.com/webhook"
}
```

**Parameters:**
- `script` (required): Text script with `— pause —` markers to create separate videos
- `voice` (optional): Voice type - `alloy`, `echo`, `fable`, `onyx`, `nova`, `shimmer` (default: `nova`)
- `speed` (optional): Speech speed between 0.25 and 4.0 (default: 1.0)
- `background_image_url` (optional): URL to download background image for videos
- `webhook_url` (optional): URL to receive progress notifications

**Response (202 Accepted):**
```json
{
    "success": true,
    "session_id": "api_12345-abcd-ef67-8901-234567890abc",
    "status": "processing",
    "message": "YouTube Shorts generation started",
    "estimated_completion_time": "2-5 minutes",
    "progress_url": "/api/v1/shorts-status/api_12345-abcd-ef67-8901-234567890abc",
    "webhook_enabled": true
}
```

**Error Response (400/500):**
```json
{
    "success": false,
    "error": "Script is required and cannot be empty",
    "code": "MISSING_SCRIPT"
}
```

#### 2. Check Generation Status
**Endpoint:** `GET /api/v1/shorts-status/{session_id}`

Check the progress and status of a YouTube Shorts generation request.

**Response (Processing):**
```json
{
    "success": true,
    "session_id": "api_12345-abcd-ef67-8901-234567890abc",
    "status": "processing",
    "progress": 75,
    "message": "Generating video 3 of 4...",
    "estimated_time_remaining": "1-2 minutes",
    "created_at": "2025-09-13T10:30:00"
}
```

**Response (Completed):**
```json
{
    "success": true,
    "session_id": "api_12345-abcd-ef67-8901-234567890abc",
    "status": "completed",
    "progress": 100,
    "message": "Successfully generated 4 YouTube Shorts!",
    "zip_url": "https://your-domain.com/download-voiceover/api_shorts_xyz.zip?dl=1",
    "created_at": "2025-09-13T10:30:00",
    "completed_at": "2025-09-13T10:33:15"
}
```

**Response (Failed):**
```json
{
    "success": false,
    "session_id": "api_12345-abcd-ef67-8901-234567890abc",
    "status": "failed",
    "error": "Failed to generate segment 2: TTS service unavailable",
    "failed_at": "2025-09-13T10:32:45"
}
```

#### API Usage Examples

**Python Example:**
```python
import requests
import time

# Start YouTube Shorts generation
response = requests.post('http://localhost:5000/api/v1/generate-shorts', 
    json={
        "script": "Market update today. Stocks are up significantly. — pause — Tech sector leading gains. Apple hit new highs. — pause — Tomorrow outlook positive.",
        "voice": "nova",
        "speed": 1.2,
        "background_image_url": "https://example.com/news-bg.jpg",
        "webhook_url": "https://your-app.com/shorts-complete"
    })

if response.status_code == 202:
    data = response.json()
    session_id = data['session_id']
    print(f"Generation started. Session ID: {session_id}")
    
    # Poll for completion
    while True:
        status_response = requests.get(f'http://localhost:5000/api/v1/shorts-status/{session_id}')
        status_data = status_response.json()
        
        if status_data['status'] == 'completed':
            print(f"✅ Complete! Download ZIP: {status_data['zip_url']}")
            break
        elif status_data['status'] == 'failed':
            print(f"❌ Failed: {status_data['error']}")
            break
        
        print(f"🔄 Progress: {status_data['progress']}% - {status_data['message']}")
        time.sleep(10)
else:
    print(f"❌ Error: {response.json()}")
```

**JavaScript/Node.js Example:**
```javascript
const axios = require('axios');

async function generateShorts() {
    try {
        // Start generation
        const response = await axios.post('http://localhost:5000/api/v1/generate-shorts', {
            script: "Welcome to today's news. Market is bullish. — pause — Tech stocks performing well. Innovation driving growth. — pause — Stay tuned for more updates.",
            voice: "onyx",
            speed: 1.0,
            webhook_url: "https://myapp.com/shorts-webhook"
        });

        const { session_id } = response.data;
        console.log(`Generation started: ${session_id}`);

        // Poll for completion
        const pollStatus = async () => {
            const status = await axios.get(`http://localhost:5000/api/v1/shorts-status/${session_id}`);
            const { status: currentStatus, progress, message, zip_url } = status.data;

            if (currentStatus === 'completed') {
                console.log(`✅ Complete! ZIP URL: ${zip_url}`);
                return;
            } else if (currentStatus === 'failed') {
                console.log(`❌ Failed: ${status.data.error}`);
                return;
            }

            console.log(`🔄 ${progress}% - ${message}`);
            setTimeout(pollStatus, 10000); // Poll every 10 seconds
        };

        pollStatus();
    } catch (error) {
        console.error('❌ Error:', error.response?.data || error.message);
    }
}

generateShorts();
```

**cURL Example:**
```bash
# Start generation
curl -X POST http://localhost:5000/api/v1/generate-shorts \
  -H "Content-Type: application/json" \
  -d '{
    "script": "Breaking news today. Markets show strong performance. — pause — Technology sector leads with innovation. — pause — Economic outlook remains positive.",
    "voice": "nova",
    "speed": 1.1
  }'

# Check status (replace SESSION_ID with actual session ID)
curl http://localhost:5000/api/v1/shorts-status/SESSION_ID
```

#### Webhook Integration

If you provide a `webhook_url`, the system will send POST requests to your endpoint with progress updates:

**Webhook Payload:**
```json
{
    "session_id": "api_12345-abcd-ef67-8901-234567890abc",
    "status": "completed",
    "progress": 100,
    "message": "Successfully generated 4 YouTube Shorts!",
    "zip_url": "https://your-domain.com/download-voiceover/api_shorts_xyz.zip?dl=1"
}
```

#### API Error Codes

| Code | Description |
|------|-------------|
| `INVALID_CONTENT_TYPE` | Request must use `application/json` |
| `MISSING_SCRIPT` | Script parameter is required |
| `INVALID_VOICE` | Voice must be one of the supported options |
| `INVALID_SPEED` | Speed must be between 0.25 and 4.0 |
| `INVALID_SPEED_FORMAT` | Speed must be a valid number |
| `SESSION_NOT_FOUND` | Session ID does not exist |
| `INTERNAL_ERROR` | Server-side processing error |

#### Rate Limiting & Best Practices

- **Concurrent Requests**: The API can handle multiple concurrent requests
- **Polling Frequency**: Check status every 10-15 seconds to avoid overwhelming the server
- **Timeout Handling**: Set appropriate timeouts for long-running generations
- **Error Handling**: Always check response status codes and handle errors gracefully
- **Webhook Reliability**: Implement retry logic for webhook endpoints
- **File Cleanup**: Downloaded ZIP files contain meaningful filenames based on script content

#### Integration Use Cases

- **Content Management Systems**: Bulk generation of social media content
- **News Automation**: Convert news articles to video format automatically  
- **Marketing Workflows**: Create promotional videos from product descriptions
- **Educational Platforms**: Transform text lessons into engaging video content
- **Social Media Tools**: Automate YouTube Shorts creation for consistent posting

## Technologies Used

- **Backend**: Flask, Flask-SocketIO, Python
- **PDF Processing**: PyPDF, pdf2image, Tesseract OCR
- **AI/ML**: OpenAI GPT, OpenAI TTS, LangChain, ChromaDB
- **Media Processing**: FFmpeg for audio/video conversion
- **Frontend**: Bootstrap 5, JavaScript, WebSocket
- **Real-time Updates**: Socket.IO
- **File Handling**: Werkzeug, UUID for session management

## Configuration

### Key Environment Variables

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `OPENAI_API_KEY` | OpenAI API key for summarization and TTS | - | ✅ |
| `SECRET_KEY` | Flask secret key for sessions | - | ✅ |
| `FLASK_DEBUG` | Enable debug mode | true | ❌ |
| `FLASK_PORT` | Server port | 5000 | ❌ |
| `MAX_FILE_SIZE_MB` | Max file upload size | 50 | ❌ |
| `OCR_DPI` | OCR image resolution | 150 | ❌ |
| `OPENAI_MODEL` | GPT model to use | gpt-3.5-turbo-16k | ❌ |
| `TEXT_CHUNK_SIZE` | Vector DB chunk size | 1000 | ❌ |
| `VOICEOVER_FOLDER` | Voiceover output directory | voiceovers | ❌ |
| `VIDEO_WIDTH` | Video output width | 1920 | ❌ |
| `VIDEO_HEIGHT` | Video output height | 1080 | ❌ |

### File Limits

- Maximum PDF file size: 50MB
- Supported format: PDF only
- Recommended: 15-20 pages for optimal processing time
- Text length for voiceover: No strict limit (OpenAI TTS handles up to ~4096 characters efficiently)

## Troubleshooting

### Common Issues

1. **Tesseract not found error:**
   - Ensure Tesseract is properly installed
   - Check the path configuration in `pdf_processor.py`

2. **FFmpeg not found error:**
   - Install FFmpeg using the system package manager
   - Ensure it's available in your system PATH

3. **OpenAI API errors:**
   - Verify your API key is correct in `.env`
   - Check your OpenAI account has sufficient credits
   - Ensure you have access to both GPT and TTS APIs

4. **Memory issues with large PDFs:**
   - Process smaller files or increase system memory
   - Consider splitting very large documents

5. **WebSocket connection issues:**
   - Check firewall settings
   - Ensure port 5000 is available

6. **"No module named" errors:**
   - Ensure all dependencies are installed: `pip install -r requirements.txt`
   - Consider using a virtual environment

7. **Voiceover generation fails:**
   - Check FFmpeg installation
   - Verify OpenAI API key has TTS access
   - Ensure sufficient disk space in voiceovers folder

### Debug Mode

Run the application in debug mode for detailed error messages:
```bash
export FLASK_DEBUG=1
python app.py
```

## Development

### Adding New Features

1. **PDF Processing**: Extend `pdf_processor.py`
2. **AI Features**: Modify `rag_system.py`
3. **Voiceover Features**: Update `voiceover_system.py`
4. **Web Interface**: Update templates and static files
5. **API Endpoints**: Add routes in `app.py`

### Testing

Test with sample Economic Times PDFs and various text inputs to ensure all features work correctly.

### Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly with both PDF processing and standalone voiceover features
5. Submit a pull request

## Recent Updates (v2.0)

### New Features
- **Standalone AI Voiceover Generator**: Create professional voiceovers without PDF processing
- **Enhanced Voice Options**: 6 different voice personalities with speed control
- **Multiple Output Formats**: MP3 audio, WAV audio, and MP4 video with waveform visualization
- **Improved UI/UX**: Collapsible panels and better organization
- **Video Generation**: Automatic creation of MP4 videos with audio waveforms and text overlays

### Technical Improvements
- **FFmpeg Integration**: Professional audio/video processing capabilities
- **Session Management**: Better handling of standalone vs. document-based workflows
- **Error Handling**: Enhanced error messages and fallback mechanisms
- **Performance**: Optimized processing for both small and large text inputs

## License

This project is for educational and research purposes.

## Support

For issues and questions:
- Check the troubleshooting section
- Review code comments for implementation details
- Open an issue on the GitHub repository

---

**Perfect for:** News organizations, content creators, accessibility applications, educational institutions, and anyone needing AI-powered document processing with professional voiceover capabilities.

# YouTube Shorts Automation

An automated system that generates YouTube Shorts videos using your PDF Processing API and uploads them to your YouTube channel on a scheduled basis.

## Overview

This project connects to your existing "Newspaper Summary - PDF Processing & AI Summarization" API to generate YouTube Shorts videos, then automatically uploads them to your YouTube channel following a schedule of **2 videos every 2.5 hours**.

## Features

🤖 **Automated Video Generation**
- Integrates with your PDF processing API to generate YouTube Shorts
- Downloads and extracts videos from ZIP files automatically
- Supports custom scripts with pause markers for multiple videos
- Configurable voice options and speech speed

📅 **Intelligent Scheduling**
- Uploads 2 videos every 2.5 hours automatically
- Queue management with retry logic for failed uploads
- Persistent upload queue survives system restarts
- Automatic cleanup of old files

🎬 **YouTube Integration**
- Full YouTube Data API v3 integration
- Resumable uploads with error handling
- Custom video titles, descriptions, and tags
- Channel authentication and management

📊 **Monitoring & Management**
- Real-time status monitoring
- Comprehensive logging system
- Manual override capabilities
- Upload statistics and reporting

## Project Structure

```
yt_shorts_upload/
├── automation_scheduler.py    # Main automation orchestrator
├── youtube_uploader.py        # YouTube API integration
├── pdf_api_client.py         # PDF processing API client
├── youtube_auth_helper.py    # OAuth authentication helper
├── requirements.txt          # Python dependencies
├── setup.sh                 # Automated setup script
├── .env.template           # Environment configuration template
├── README.md              # This file
├── downloads/            # Downloaded video files
├── processed/           # Successfully uploaded videos
└── upload_queue.json   # Persistent upload queue
```

## Quick Start

### 1. Setup

Run the automated setup script:

```bash
chmod +x setup.sh
./setup.sh
```

This will:
- Create a Python virtual environment
- Install all dependencies
- Create necessary directories
- Set up configuration files

### 2. Configure Environment

Edit the `.env` file with your credentials:

```bash
# YouTube API Configuration
YOUTUBE_CLIENT_ID=your_youtube_client_id_here
YOUTUBE_CLIENT_SECRET=your_youtube_client_secret_here
YOUTUBE_REFRESH_TOKEN=your_youtube_refresh_token_here

# PDF Processing API Configuration
PDF_API_BASE_URL=http://localhost:5000
PDF_API_ENDPOINT=/api/v1/generate-shorts

# Video Configuration
CHANNEL_ID=your_youtube_channel_id_here
DEFAULT_TITLE_PREFIX=Daily News Shorts
DEFAULT_DESCRIPTION=Automated YouTube Shorts generated from news content
DEFAULT_TAGS=news,shorts,ai,automation,daily

# Scheduling Configuration
VIDEOS_PER_BATCH=2
SCHEDULE_INTERVAL_HOURS=2.5
```

### 3. Get YouTube API Credentials

#### Step 1: Google Cloud Setup
1. Go to [Google Cloud Console](https://console.cloud.google.com)
2. Create a new project or select an existing one
3. Enable the **YouTube Data API v3**
4. Go to **Credentials** → **Create Credentials** → **OAuth 2.0 Client IDs**
5. Choose **Desktop application**
6. Download the JSON file and rename it to `client_secrets.json`

#### Step 2: Get Refresh Token
```bash
source venv/bin/activate
python youtube_auth_helper.py
```

This will:
- Open your browser for OAuth authentication
- Generate your refresh token
- Save credentials to `youtube_credentials.json`
- Display the values to add to your `.env` file

### 4. Start Automation

```bash
source venv/bin/activate
python automation_scheduler.py
```

Choose from the menu:
1. **Start automatic scheduler** - Runs continuously with 2.5-hour intervals
2. **Manual video generation** - Generate videos on-demand
3. **Upload pending videos** - Process any queued uploads
4. **Show status** - View current statistics
5. **Exit** - Stop the automation

## Configuration Options

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `YOUTUBE_CLIENT_ID` | OAuth client ID | Required |
| `YOUTUBE_CLIENT_SECRET` | OAuth client secret | Required |
| `YOUTUBE_REFRESH_TOKEN` | OAuth refresh token | Required |
| `PDF_API_BASE_URL` | Your API base URL | `http://localhost:5000` |
| `PDF_API_ENDPOINT` | API endpoint path | `/api/v1/generate-shorts` |
| `VIDEOS_PER_BATCH` | Videos per upload cycle | `2` |
| `SCHEDULE_INTERVAL_HOURS` | Hours between uploads | `2.5` |
| `MAX_RETRIES` | Upload retry attempts | `3` |
| `DEFAULT_TITLE_PREFIX` | Video title prefix | `Daily News Shorts` |
| `DEFAULT_DESCRIPTION` | Video description | Auto-generated |
| `DEFAULT_TAGS` | Comma-separated tags | `news,shorts,ai,automation,daily` |

### Script Format

Your scripts should use `— pause —` markers to create separate videos:

```
Today's market update shows strong performance. — pause — Technology stocks lead with innovation. — pause — Economic outlook remains positive.
```

This creates 3 separate YouTube Shorts videos.

## API Integration

### Your PDF Processing API

The system expects your API to:

1. **Accept POST requests** to `/api/v1/generate-shorts` with:
   ```json
   {
     "script": "Your script with — pause — markers",
     "voice": "nova",
     "speed": 1.0
   }
   ```

2. **Return session tracking** with:
   ```json
   {
     "success": true,
     "session_id": "api_12345-abcd-ef67-8901-234567890abc",
     "status": "processing"
   }
   ```

3. **Provide status endpoint** at `/api/v1/shorts-status/{session_id}`

4. **Return download link** when complete:
   ```json
   {
     "status": "completed",
     "zip_url": "https://your-domain.com/download-voiceover/file.zip"
   }
   ```

## Usage Examples

### Automated Scheduling

Start the scheduler for continuous operation:
```bash
python automation_scheduler.py
# Choose option 1: Start automatic scheduler
```

The system will:
- Generate videos every 2.5 hours
- Upload 2 videos per cycle
- Retry failed uploads automatically
- Clean up old files weekly

### Manual Video Generation

Generate videos on-demand:
```bash
python automation_scheduler.py
# Choose option 2: Manual video generation
```

Enter your script with pause markers and the system will:
- Call your API to generate videos
- Download and extract video files
- Add them to the upload queue
- Immediately attempt to upload them

### Monitoring

Check system status:
```bash
python automation_scheduler.py
# Choose option 4: Show status
```

View:
- Pending uploads count
- Successful uploads count
- Failed uploads count
- Next scheduled run time
- Total videos processed

## Advanced Features

### Queue Management

The upload queue (`upload_queue.json`) persists between restarts and tracks:
- Video file paths
- Upload attempts
- Success/failure status
- Metadata and timestamps

### Error Handling

- **API Failures**: Retries with exponential backoff
- **Upload Failures**: Queue persistence with retry logic
- **Network Issues**: Resumable uploads with chunk management
- **File Issues**: Automatic cleanup and error reporting

### Logging

Comprehensive logging to `youtube_automation.log`:
- API calls and responses
- Upload progress and results
- Error details and stack traces
- Scheduling and queue operations

### File Management

- **Downloads**: Temporary storage for extracted videos
- **Processed**: Archive of successfully uploaded videos
- **Cleanup**: Automatic removal of files older than 7 days

## Troubleshooting

### Common Issues

1. **YouTube Authentication Errors**
   ```
   Failed to authenticate with YouTube API
   ```
   - Verify your credentials in `.env`
   - Run `youtube_auth_helper.py` to regenerate tokens
   - Check API quotas in Google Cloud Console

2. **API Connection Errors**
   ```
   Failed to connect to API
   ```
   - Ensure your PDF processing API is running
   - Verify `PDF_API_BASE_URL` in `.env`
   - Check network connectivity

3. **Upload Failures**
   ```
   Failed to upload video
   ```
   - Check YouTube API quotas
   - Verify video file integrity
   - Review network connectivity

4. **Permission Errors**
   ```
   Permission denied
   ```
   - Check file permissions on directories
   - Verify YouTube channel ownership
   - Ensure OAuth scopes are correct

### Debug Mode

Enable detailed logging:
```bash
export LOG_LEVEL=DEBUG
python automation_scheduler.py
```

### Reset Queue

Clear the upload queue:
```bash
rm upload_queue.json
```

## Security Considerations

- **API Keys**: Never commit `.env` files to version control
- **Tokens**: Refresh tokens provide ongoing access - keep secure
- **Files**: Uploaded videos are moved to processed folder
- **Logs**: May contain sensitive information - secure appropriately

## Performance Optimization

### API Efficiency
- Batch video generation when possible
- Monitor API rate limits
- Use appropriate timeout values

### Upload Optimization
- Videos upload in sequence to avoid rate limits
- Resumable uploads handle network interruptions
- Failed uploads retry with exponential backoff

### Storage Management
- Automatic cleanup prevents disk space issues
- Processed files are archived separately
- Temporary files are cleaned after extraction

## Integration Examples

### Custom Script Sources

Replace the sample scripts in `automation_scheduler.py`:

```python
def get_daily_script(self):
    """Get script from your content source"""
    # Example: RSS feed, database, file system
    return "Your dynamic content — pause — More content"
```

### Webhook Integration

Add webhook support for external triggers:

```python
@app.route('/trigger-generation', methods=['POST'])
def trigger_generation():
    script = request.json.get('script')
    automation.run_manual_generation(script)
    return {'status': 'started'}
```

### Custom Video Metadata

Enhance video information:

```python
def generate_video_title(self, script_content):
    """Generate dynamic titles based on content"""
    # Use AI or keywords to create engaging titles
    return f"Breaking: {extracted_keywords}"
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Test thoroughly with your API
4. Submit a pull request

## License

This project is for educational and research purposes.

## Support

For issues and questions:
- Check the troubleshooting section
- Review log files for error details
- Ensure your PDF processing API is compatible
- Verify YouTube API setup and quotas

---

**Perfect for:** Content creators, news organizations, automated social media management, and anyone wanting to maintain a consistent YouTube Shorts publishing schedule.