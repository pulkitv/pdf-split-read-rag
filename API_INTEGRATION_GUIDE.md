# API Integration Guide - Newspaper Summary Video Generation

This guide provides complete instructions for integrating with the Newspaper Summary Project's video generation APIs to create automated video content from PDF newspaper summaries and text scripts.

## Overview

The Newspaper Summary Project offers two powerful APIs for video content generation:

### YouTube Shorts API
- Generate multiple short videos from newspaper summaries or scripts
- Split content using pause markers (`— pause —`)
- Create portrait 1080x1920 videos optimized for social media
- Download individual videos or bulk ZIP files
- Perfect for breaking news segments and social media content

### Regular Format Voiceover API
- Generate single landscape 1920x1080 videos from newspaper summaries
- Perfect for presentations, news broadcasts, and general content
- Direct MP4/MP3/WAV file downloads
- No script splitting - treats entire text as one comprehensive video
- Supports multiple output formats
- Ideal for full newspaper article summaries

Both APIs support:
- OpenAI TTS voice customization and speech speed control
- Real-time progress tracking via WebSocket
- Background image integration for branded content
- Webhook notifications for automated workflows
- Processing of newspaper PDF summaries from the main application

## Integration with Newspaper Summary Workflow

These APIs can be integrated into your newspaper processing pipeline:

1. **PDF Upload & Processing** → Main Flask application processes newspaper PDFs
2. **AI Summarization** → Generate summaries using RAG system
3. **Video Generation** → Use these APIs to convert summaries to videos
4. **Content Distribution** → Deploy videos to social media or broadcast systems

## Quick Start

### Base URL
```
https://your-domain.com/api/v1/
```

### Authentication
Currently no authentication required. For production deployment, consider adding API keys:
```bash
# Add to .env file
API_KEY_REQUIRED=true
VALID_API_KEYS=key1,key2,key3
```

## API Endpoints

### 1. Generate YouTube Shorts

**Endpoint:** `POST /api/v1/generate-shorts`

**Request:**
```json
{
  "script": "Welcome to today's market update. Tech stocks are rallying — pause — Apple reported strong earnings today — pause — Looking ahead to next quarter's outlook",
  "voice": "nova",
  "speed": 1.2
}
```

**Response:**
```json
{
  "success": true,
  "session_id": "api_581cfa84-dfc4-4a40-9448-4ed6971c07bc",
  "status": "processing",
  "message": "YouTube Shorts generation started successfully",
  "estimated_segments": 3,
  "status_url": "/api/v1/shorts-status/api_581cfa84-dfc4-4a40-9448-4ed6971c07bc",
  "created_at": "2025-09-14T13:53:41.284Z"
}
```

### 2. Check Generation Status

**Endpoint:** `GET /api/v1/shorts-status/{session_id}`

**Response (Processing):**
```json
{
  "session_id": "api_581cfa84-dfc4-4a40-9448-4ed6971c07bc",
  "status": "processing",
  "progress": 45,
  "message": "Generating video 2 of 3: Apple reported strong earnings...",
  "current_segment": 2,
  "total_segments": 3,
  "created_at": "2025-09-14T13:53:41.284Z",
  "updated_at": "2025-09-14T13:54:15.123Z"
}
```

**Response (Completed):**
```json
{
  "session_id": "api_581cfa84-dfc4-4a40-9448-4ed6971c07bc",
  "status": "completed",
  "progress": 100,
  "message": "Successfully generated 3 YouTube Shorts videos!",
  "current_segment": 3,
  "total_segments": 3,
  "zip_url": "https://your-domain.com/download-voiceover/api_shorts_581cfa84_ab12cd34.zip",
  "count": 3,
  "videos": [
    {
      "index": 1,
      "file_url": "https://your-domain.com/download-voiceover/api_Welcome_Todays_Market_Update.mp4",
      "duration": 8.5,
      "format": "mp4",
      "download_name": "api_Welcome_Todays_Market_Update.mp4"
    },
    {
      "index": 2,
      "file_url": "https://your-domain.com/download-voiceover/api_Apple_Reported_Strong.mp4",
      "duration": 6.2,
      "format": "mp4",
      "download_name": "api_Apple_Reported_Strong.mp4"
    },
    {
      "index": 3,
      "file_url": "https://your-domain.com/download-voiceover/api_Looking_Ahead_Next.mp4",
      "duration": 7.8,
      "format": "mp4",
      "download_name": "api_Looking_Ahead_Next.mp4"
    }
  ],
  "created_at": "2025-09-14T13:53:41.284Z",
  "updated_at": "2025-09-14T13:55:22.456Z"
}
```

**Response (Failed):**
```json
{
  "session_id": "api_581cfa84-dfc4-4a40-9448-4ed6971c07bc",
  "status": "failed",
  "progress": 25,
  "message": "Generation failed: Invalid voice parameter",
  "error": "Voice 'invalid_voice' not found. Available voices: nova, alloy, echo, fable, onyx, shimmer",
  "created_at": "2025-09-14T13:53:41.284Z",
  "updated_at": "2025-09-14T13:54:02.789Z"
}
```

### 3. Generate Regular Format Voiceover

**Endpoint:** `POST /api/v1/voiceover/generate`

**Request:**
```json
{
  "script": "Welcome to our quarterly business review. Today we'll discuss market performance, key achievements, and strategic initiatives for the upcoming quarter.",
  "voice": "nova",
  "speed": 1.0,
  "format": "mp4",
  "background_image_url": "https://example.com/background.jpg",
  "webhook_url": "https://your-domain.com/webhook/voiceover-complete"
}
```

**Parameters:**
- `script` (required): Text content to convert to voiceover (no pause markers needed)
- `voice` (optional): Voice type - nova, alloy, echo, fable, onyx, shimmer (default: "nova")
- `speed` (optional): Speech speed 0.25-4.0 (default: 1.0)
- `format` (optional): Output format - mp3, wav, mp4 (default: "mp4")
- `background_image_url` (optional): URL to background image for video
- `webhook_url` (optional): URL for completion notification

**Response:**
```json
{
  "success": true,
  "session_id": "api_voiceover_7f3b2a18-4c9d-4e8a-b5f6-1a2b3c4d5e6f",
  "message": "Voiceover generation started",
  "status_url": "/api/v1/voiceover/status/api_voiceover_7f3b2a18-4c9d-4e8a-b5f6-1a2b3c4d5e6f"
}
```

### 4. Check Voiceover Status

**Endpoint:** `GET /api/v1/voiceover/status/{session_id}`

**Response (Processing):**
```json
{
  "session_id": "api_voiceover_7f3b2a18-4c9d-4e8a-b5f6-1a2b3c4d5e6f",
  "status": "processing",
  "progress": 65,
  "message": "Generating video with audio waveform...",
  "script": "Welcome to our quarterly business review...",
  "voice": "nova",
  "speed": 1.0,
  "format": "mp4",
  "created_at": "2025-09-15T14:30:15.234Z"
}
```

**Response (Completed):**
```json
{
  "session_id": "api_voiceover_7f3b2a18-4c9d-4e8a-b5f6-1a2b3c4d5e6f",
  "status": "completed",
  "progress": 100,
  "message": "Voiceover generation completed successfully!",
  "download_url": "https://your-domain.com/api/v1/voiceover/download/api_voiceover_7f3b2a18-4c9d-4e8a-b5f6-1a2b3c4d5e6f",
  "result": {
    "file_url": "https://your-domain.com/download-voiceover/quarterly_review_7f3b2a18.mp4",
    "download_url": "https://your-domain.com/api/v1/voiceover/download/api_voiceover_7f3b2a18-4c9d-4e8a-b5f6-1a2b3c4d5e6f",
    "filename": "quarterly_review_7f3b2a18.mp4",
    "duration": 45.6,
    "format": "mp4"
  },
  "script": "Welcome to our quarterly business review...",
  "voice": "nova",
  "speed": 1.0,
  "format": "mp4",
  "created_at": "2025-09-15T14:30:15.234Z"
}
```

**Response (Failed):**
```json
{
  "session_id": "api_voiceover_7f3b2a18-4c9d-4e8a-b5f6-1a2b3c4d5e6f",
  "status": "failed",
  "progress": 30,
  "message": "Generation failed: Unsupported format",
  "error": "Format 'avi' not supported. Use: mp3, wav, mp4",
  "created_at": "2025-09-15T14:30:15.234Z"
}
```

### 5. Direct Download

**Endpoint:** `GET /api/v1/voiceover/download/{session_id}`

**Response:** Direct file download (MP4/MP3/WAV)
- Returns the generated file directly with proper MIME type headers
- No ZIP compression for single files
- Original filename preserved in download headers
- Enhanced error handling with detailed logging for troubleshooting

**Success Response:**
- Status: `200 OK`
- Content-Type: `video/mp4`, `audio/mpeg`, or `audio/wav` based on format
- Content-Disposition: `attachment; filename="original_filename.ext"`
- Body: Binary file data

**Error Responses:**
```json
// Session not found
{
  "error": "Session not found"
}
// Status: 404

// Generation not completed
{
  "error": "Generation not completed yet"
}
// Status: 400

// File not available
{
  "error": "No file URL available"
}
// Status: 404

// File missing from disk
{
  "error": "Generated file not found"
}
// Status: 404

// Server error with details
{
  "error": "Download failed: [specific error message]"
}
// Status: 500
```

**Enhanced Error Handling:**
The download endpoint now includes comprehensive error logging and debugging information:
- Validates session existence before processing
- Checks generation completion status
- Verifies file URL availability in session data
- Handles multiple URL formats (direct paths, API endpoints)
- Confirms file existence on disk before serving
- Provides detailed server-side logging for troubleshooting
- Lists available files when target file is missing (for debugging)

**URL Format Handling:**
The endpoint now properly handles various stored URL formats:
- `/download-voiceover/filename.mp4` (standard format)
- `/api/v1/voiceover/download/session_id` (recursive references)
- Direct filenames without path prefixes
- Malformed URLs with graceful fallback parsing

## ⚠️ CRITICAL: External Project Integration Notes

### Common Issue: Videos Generated But Not Fetchable

**Problem:** Your external project successfully creates videos but cannot fetch them.

**Root Causes & Solutions:**

1. **Incorrect Download URL Usage**
   ```python
   # ❌ WRONG - Using relative file_url
   download_response = requests.get(f"{base_url}{result['result']['file_url']}")
   
   # ✅ CORRECT - Using dedicated download_url
   download_response = requests.get(result['result']['download_url'])
   # OR
   download_response = requests.get(result['download_url'])
   ```

2. **URL Path Issues**
   ```python
   # ❌ WRONG - Double slashes or missing base URL
   url = f"{base_url}//download-voiceover/file.mp4"
   
   # ✅ CORRECT - Clean URL construction
   base_url = "https://your-domain.com"
   download_url = result.get('download_url') or result['result']['download_url']
   # download_url already includes full path
   ```

3. **Session Timing Issues**
   ```python
   # ❌ WRONG - Trying to download immediately
   result = api.generate_voiceover(script)
   download_file(result['session_id'])  # May fail if not completed
   
   # ✅ CORRECT - Wait for completion first
   result = api.generate_voiceover(script)
   if result['status'] == 'completed':
       download_file(result['session_id'])
   ```

### Updated Client Integration Pattern

**For Regular Voiceover API:**
```python
import requests
import time

class VoiceoverClient:
    def __init__(self, base_url):
        self.base_url = base_url.rstrip('/')
    
    def generate_and_download(self, script, output_path, **kwargs):
        """Complete workflow: generate -> wait -> download"""
        try:
            # Step 1: Start generation
            response = requests.post(f"{self.base_url}/api/v1/voiceover/generate", 
                                   json={"script": script, **kwargs})
            result = response.json()
            
            if not result.get('success'):
                raise Exception(f"Generation failed: {result.get('error')}")
            
            session_id = result['session_id']
            print(f"Generation started: {session_id}")
            
            # Step 2: Poll until completed
            while True:
                status_response = requests.get(f"{self.base_url}/api/v1/voiceover/status/{session_id}")
                status_data = status_response.json()
                
                print(f"Status: {status_data['status']} - {status_data.get('progress', 0)}%")
                
                if status_data['status'] == 'completed':
                    break
                elif status_data['status'] == 'failed':
                    raise Exception(f"Generation failed: {status_data.get('error')}")
                
                time.sleep(3)
            
            # Step 3: Download using the correct endpoint
            # ✅ Use the dedicated download endpoint
            download_url = f"{self.base_url}/api/v1/voiceover/download/{session_id}"
            
            print(f"Downloading from: {download_url}")
            download_response = requests.get(download_url, stream=True)
            download_response.raise_for_status()
            
            # Save file
            with open(output_path, 'wb') as f:
                for chunk in download_response.iter_content(chunk_size=8192):
                    f.write(chunk)
            
            print(f"Downloaded successfully: {output_path}")
            return output_path
            
        except Exception as e:
            print(f"Error in generate_and_download: {e}")
            raise

# Usage
client = VoiceoverClient("https://your-domain.com")
client.generate_and_download(
    script="Your newspaper summary text here...",
    output_path="output_video.mp4",
    voice="nova",
    speed=1.2,
    format="mp4"
)
```

**For YouTube Shorts API:**
```python
class ShortsClient:
    def __init__(self, base_url):
        self.base_url = base_url.rstrip('/')
    
    def generate_and_download(self, script, output_zip_path, **kwargs):
        """Complete workflow: generate -> wait -> download ZIP"""
        try:
            # Step 1: Start generation
            response = requests.post(f"{self.base_url}/api/v1/generate-shorts", 
                                   json={"script": script, **kwargs})
            result = response.json()
            
            if not result.get('success'):
                raise Exception(f"Generation failed: {result.get('error')}")
            
            session_id = result['session_id']
            print(f"Shorts generation started: {session_id}")
            
            # Step 2: Poll until completed
            while True:
                status_response = requests.get(f"{self.base_url}/api/v1/shorts-status/{session_id}")
                status_data = status_response.json()
                
                print(f"Status: {status_data['status']} - {status_data.get('progress', 0)}%")
                
                if status_data['status'] == 'completed':
                    break
                elif status_data['status'] == 'failed':
                    raise Exception(f"Generation failed: {status_data.get('error')}")
                
                time.sleep(3)
            
            # Step 3: Download ZIP file
            # ✅ zip_url already contains full URL
            zip_url = status_data['zip_url']
            
            print(f"Downloading ZIP from: {zip_url}")
            download_response = requests.get(zip_url, stream=True)
            download_response.raise_for_status()
            
            # Save ZIP file
            with open(output_zip_path, 'wb') as f:
                for chunk in download_response.iter_content(chunk_size=8192):
                    f.write(chunk)
            
            print(f"ZIP downloaded successfully: {output_zip_path}")
            return {
                'zip_path': output_zip_path,
                'video_count': status_data['count'],
                'videos': status_data['videos']
            }
            
        except Exception as e:
            print(f"Error in generate_and_download: {e}")
            raise

# Usage
client = ShortsClient("https://your-domain.com")
result = client.generate_and_download(
    script="Breaking news — pause — Market update — pause — Final thoughts",
    output_zip_path="shorts_bundle.zip",
    voice="nova",
    speed=1.2
)
```

### Download URL Reference Guide

**YouTube Shorts API:**
- `zip_url`: Full URL to download ZIP file containing all videos
- `videos[].file_url`: Full URLs to individual video files
- Both URLs are ready to use directly

**Regular Voiceover API:**
- `download_url` (top-level): Direct download endpoint URL
- `result.download_url`: Same direct download endpoint URL  
- `result.file_url`: Alternative file access URL
- **Recommended**: Use `download_url` for external projects

### Testing Your Integration

```python
def test_download_urls():
    """Test script to verify download URLs work correctly"""
    
    # Test regular voiceover
    print("Testing Regular Voiceover...")
    voiceover_result = {
        "session_id": "test_session_123",
        "status": "completed",
        "download_url": "https://your-domain.com/api/v1/voiceover/download/test_session_123",
        "result": {
            "file_url": "https://your-domain.com/download-voiceover/test_file.mp4",
            "download_url": "https://your-domain.com/api/v1/voiceover/download/test_session_123"
        }
    }
    
    # Test the download URLs
    for url_type, url in [
        ("Top-level download_url", voiceover_result.get('download_url')),
        ("Result download_url", voiceover_result['result'].get('download_url')),
        ("Result file_url", voiceover_result['result'].get('file_url'))
    ]:
        print(f"Testing {url_type}: {url}")
        try:
            response = requests.head(url)  # HEAD request to check availability
            print(f"  ✅ Status: {response.status_code}")
        except Exception as e:
            print(f"  ❌ Error: {e}")
    
    # Test shorts
    print("\nTesting YouTube Shorts...")
    shorts_result = {
        "zip_url": "https://your-domain.com/download-voiceover/api_shorts_test.zip",
        "videos": [
            {"file_url": "https://your-domain.com/download-voiceover/video1.mp4"},
            {"file_url": "https://your-domain.com/download-voiceover/video2.mp4"}
        ]
    }
    
    # Test ZIP URL
    print(f"Testing ZIP URL: {shorts_result['zip_url']}")
    try:
        response = requests.head(shorts_result['zip_url'])
        print(f"  ✅ ZIP Status: {response.status_code}")
    except Exception as e:
        print(f"  ❌ ZIP Error: {e}")
    
    # Test individual video URLs
    for i, video in enumerate(shorts_result['videos']):
        print(f"Testing Video {i+1}: {video['file_url']}")
        try:
            response = requests.head(video['file_url'])
            print(f"  ✅ Video Status: {response.status_code}")
        except Exception as e:
            print(f"  ❌ Video Error: {e}")

# Run the test
test_download_urls()
```

## Troubleshooting

### Common Issues

1. **"Session not found"**
   - Session expired (sessions are temporary)
   - Invalid session ID format
   - Server restart cleared sessions

2. **Generation takes too long**
   - Script may be too long
   - Server may be under heavy load
   - Increase timeout values

3. **❌ Download URLs not working (MOST COMMON)**
   - **Check URL format**: Use `download_url` not `file_url`
   - **Verify completion**: Ensure status is 'completed' before downloading
   - **Full URL required**: Don't manually construct URLs, use provided ones
   - **Session timing**: Download immediately after completion
   - **Network issues**: Check firewall/proxy settings

4. **Files not found on server**
   - Files may have been cleaned up (temporary storage)
   - Download immediately after generation
   - Check server disk space

### Debug Tips for External Projects

1. **Log all URLs before attempting download**
   ```python
   print(f"Session ID: {session_id}")
   print(f"Status: {status_data['status']}")
   print(f"Download URL: {status_data.get('download_url')}")
   print(f"File URL: {status_data.get('result', {}).get('file_url')}")
   ```

2. **Test with curl first**
   ```bash
   # Test if URL is accessible
   curl -I "https://your-domain.com/api/v1/voiceover/download/your_session_id"
   ```

3. **Check HTTP status codes**
   ```python
   response = requests.get(download_url)
   print(f"Status Code: {response.status_code}")
   print(f"Headers: {dict(response.headers)}")
   if response.status_code != 200:
       print(f"Error Response: {response.text}")
   ```

4. **Verify file existence on server**
   ```python
   # Add this to your server-side debugging
   print(f"Files in voiceovers folder: {os.listdir('voiceovers/')}")
   ```

5. **Enable detailed logging** in your client
6. **Check server logs** for errors
7. **Validate script format** (ensure proper pause markers)
8. **Test with shorter scripts** first
9. **Monitor progress updates** for stuck generations

### Server-Side Debugging

Add to your server `.env` file for enhanced debugging:
```bash
FLASK_DEBUG=true
VOICEOVER_DEBUG_LOGGING=true
```

This will enable detailed logging of:
- File creation and paths
- Download request processing
- Session data validation
- Error stack traces

## Support

For issues or questions:
1. Check this integration guide
2. Review the troubleshooting section
3. Enable debug logging in your client
4. Test URLs with curl or browser first
5. Contact the API maintainer with session IDs and error messages

---

**Last Updated**: November 10, 2025  
**API Version**: v1  
**Project**: Newspaper Summary PDF Processing with Video Generation  
**Compatible with**: All major programming languages via HTTP/REST  
**Flask Application**: Supports WebSocket progress tracking and real-time updates