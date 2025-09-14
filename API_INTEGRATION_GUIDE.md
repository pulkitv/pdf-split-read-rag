# API Integration Guide

This guide provides complete instructions for integrating with both the YouTube Shorts Generation API and the Regular Format Voiceover API to create automated video content from text scripts.

## Overview

The APIs allow you to:

### YouTube Shorts API
- Generate multiple short videos from a single script
- Split content using pause markers (`— pause —`)
- Create portrait 1080x1920 videos optimized for social media
- Download individual videos or bulk ZIP files

### Regular Format Voiceover API (NEW!)
- Generate single landscape 1920x1080 videos from scripts
- Perfect for presentations, tutorials, and general content
- Direct MP4/MP3/WAV file downloads
- No script splitting - treats entire text as one video
- Supports multiple output formats

Both APIs support:
- Voice customization and speech speed control
- Real-time progress tracking
- Background image integration
- Webhook notifications (optional)

## Quick Start

### Base URL
```
https://your-domain.com/api/v1/
```

### Authentication
Currently no authentication required (add API keys if needed in production).

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
  "zip_url": "/download-voiceover/api_shorts_581cfa84_ab12cd34.zip",
  "count": 3,
  "videos": [
    {
      "index": 1,
      "file_url": "/download-voiceover/api_Welcome_Todays_Market_Update.mp4",
      "duration": 8.5,
      "format": "mp4",
      "download_name": "api_Welcome_Todays_Market_Update.mp4"
    },
    {
      "index": 2,
      "file_url": "/download-voiceover/api_Apple_Reported_Strong.mp4",
      "duration": 6.2,
      "format": "mp4",
      "download_name": "api_Apple_Reported_Strong.mp4"
    },
    {
      "index": 3,
      "file_url": "/download-voiceover/api_Looking_Ahead_Next.mp4",
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
  "result": {
    "file_url": "https://your-domain.com/download-voiceover/quarterly_review_7f3b2a18.mp4",
    "filename": "quarterly_review_7f3b2a18.mp4",
    "duration": 45.6,
    "format": "mp4",
    "file_size": "12.8 MB"
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

## Request Parameters

### Script Format
- Use `— pause —` to split content into separate videos
- Each segment becomes one YouTube Short (9:16 portrait format)
- Optimal length: 30-60 seconds per segment
- Maximum script length: ~4000 characters

### Voice Options
Available voices:
- `nova` (recommended) - Clear, professional
- `alloy` - Neutral, versatile
- `echo` - Deep, authoritative  
- `fable` - Warm, friendly
- `onyx` - Deep, serious
- `shimmer` - Bright, energetic

### Speed Options
- Range: `0.25` to `4.0`
- Recommended: `1.0` to `1.5`
- `1.0` = Normal speed
- `1.2` = Slightly faster (good for news)
- `1.5` = Fast (good for summaries)

## Integration Examples

### Python Client Example

```python
import requests
import time
import logging

class YouTubeShortsAPI:
    def __init__(self, base_url):
        self.base_url = base_url.rstrip('/')
        self.logger = logging.getLogger(__name__)
    
    def generate_shorts(self, script, voice="nova", speed=1.0, timeout=300):
        """
        Generate YouTube Shorts from script with polling for completion.
        
        Args:
            script (str): Text script with — pause — markers
            voice (str): Voice to use (nova, alloy, echo, fable, onyx, shimmer)
            speed (float): Speech speed (0.25 to 4.0)
            timeout (int): Maximum wait time in seconds
            
        Returns:
            dict: Final result with videos and download URLs
        """
        try:
            # Step 1: Start generation
            self.logger.info(f"Starting YouTube Shorts generation for script: {script[:50]}...")
            
            response = requests.post(
                f"{self.base_url}/api/v1/generate-shorts",
                json={
                    "script": script,
                    "voice": voice,
                    "speed": speed
                },
                headers={"Content-Type": "application/json"},
                timeout=30
            )
            
            if response.status_code != 200:
                raise Exception(f"API request failed: {response.status_code} - {response.text}")
            
            data = response.json()
            if not data.get('success'):
                raise Exception(f"API error: {data.get('error', 'Unknown error')}")
            
            session_id = data['session_id']
            self.logger.info(f"Generation started. Session ID: {session_id}")
            self.logger.info(f"Estimated segments: {data.get('estimated_segments', 'unknown')}")
            
            # Step 2: Poll for completion
            start_time = time.time()
            last_progress = -1
            
            while time.time() - start_time < timeout:
                try:
                    status_response = requests.get(
                        f"{self.base_url}/api/v1/shorts-status/{session_id}",
                        timeout=10
                    )
                    
                    if status_response.status_code != 200:
                        self.logger.warning(f"Status check failed: {status_response.status_code}")
                        time.sleep(5)
                        continue
                    
                    status_data = status_response.json()
                    current_status = status_data.get('status')
                    progress = status_data.get('progress', 0)
                    message = status_data.get('message', '')
                    
                    # Log progress updates
                    if progress != last_progress:
                        self.logger.info(f"Progress: {progress}% - {message}")
                        last_progress = progress
                    
                    if current_status == 'completed':
                        self.logger.info(f"Generation completed! {status_data.get('count', 0)} videos created")
                        return status_data
                    
                    elif current_status == 'failed':
                        error_msg = status_data.get('error', 'Unknown error')
                        raise Exception(f"Generation failed: {error_msg}")
                    
                    # Wait before next poll
                    time.sleep(3)
                    
                except requests.RequestException as e:
                    self.logger.warning(f"Status check request failed: {e}")
                    time.sleep(5)
            
            raise TimeoutError(f"Generation timed out after {timeout} seconds")
            
        except Exception as e:
            self.logger.error(f"YouTube Shorts generation failed: {e}")
            raise
    
    def download_zip(self, zip_url, output_path):
        """Download the ZIP file containing all generated videos."""
        try:
            self.logger.info(f"Downloading ZIP from: {zip_url}")
            
            response = requests.get(f"{self.base_url}{zip_url}", stream=True, timeout=60)
            response.raise_for_status()
            
            with open(output_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            
            self.logger.info(f"ZIP downloaded successfully: {output_path}")
            return output_path
            
        except Exception as e:
            self.logger.error(f"ZIP download failed: {e}")
            raise

# Usage Example
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    api = YouTubeShortsAPI("https://your-domain.com")
    
    script = """
    ABB India reported strong quarterly results today.
    — pause —
    The company's revenue grew by 15% year-over-year.
    — pause —
    Management expects continued growth in the next quarter.
    """
    
    try:
        result = api.generate_shorts(
            script=script,
            voice="nova",
            speed=1.2,
            timeout=300
        )
        
        print(f"✅ Generated {result['count']} videos successfully!")
        print(f"📦 ZIP Download: {result['zip_url']}")
        
        # Download the ZIP file
        api.download_zip(result['zip_url'], "youtube_shorts.zip")
        
        # Print individual video details
        for video in result.get('videos', []):
            print(f"🎥 Video {video['index']}: {video['download_name']} ({video['duration']}s)")
            
    except Exception as e:
        print(f"❌ Error: {e}")
```

### Python Client for Regular Voiceover

```python
import requests
import time
import logging

class RegularVoiceoverAPI:
    def __init__(self, base_url):
        self.base_url = base_url.rstrip('/')
        self.logger = logging.getLogger(__name__)
    
    def generate_voiceover(self, script, voice="nova", speed=1.0, format_type="mp4", 
                          background_image_url=None, webhook_url=None, timeout=300):
        """
        Generate regular format voiceover from script.
        
        Args:
            script (str): Text content to convert to voiceover
            voice (str): Voice to use (nova, alloy, echo, fable, onyx, shimmer)
            speed (float): Speech speed (0.25 to 4.0)
            format_type (str): Output format (mp3, wav, mp4)
            background_image_url (str): Optional background image URL
            webhook_url (str): Optional webhook for completion notification
            timeout (int): Maximum wait time in seconds
            
        Returns:
            dict: Final result with file URL and details
        """
        try:
            # Step 1: Start generation
            self.logger.info(f"Starting voiceover generation for script: {script[:50]}...")
            
            payload = {
                "script": script,
                "voice": voice,
                "speed": speed,
                "format": format_type
            }
            
            if background_image_url:
                payload["background_image_url"] = background_image_url
            if webhook_url:
                payload["webhook_url"] = webhook_url
            
            response = requests.post(
                f"{self.base_url}/api/v1/voiceover/generate",
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=30
            )
            
            if response.status_code != 202:
                raise Exception(f"API request failed: {response.status_code} - {response.text}")
            
            data = response.json()
            if not data.get('success'):
                raise Exception(f"API error: {data.get('error', 'Unknown error')}")
            
            session_id = data['session_id']
            self.logger.info(f"Generation started. Session ID: {session_id}")
            
            # Step 2: Poll for completion
            start_time = time.time()
            last_progress = -1
            
            while time.time() - start_time < timeout:
                try:
                    status_response = requests.get(
                        f"{self.base_url}/api/v1/voiceover/status/{session_id}",
                        timeout=10
                    )
                    
                    if status_response.status_code != 200:
                        self.logger.warning(f"Status check failed: {status_response.status_code}")
                        time.sleep(5)
                        continue
                    
                    status_data = status_response.json()
                    current_status = status_data.get('status')
                    progress = status_data.get('progress', 0)
                    message = status_data.get('message', '')
                    
                    # Log progress updates
                    if progress != last_progress:
                        self.logger.info(f"Progress: {progress}% - {message}")
                        last_progress = progress
                    
                    if current_status == 'completed':
                        self.logger.info("Voiceover generation completed!")
                        return status_data
                    
                    elif current_status == 'failed':
                        error_msg = status_data.get('error', 'Unknown error')
                        raise Exception(f"Generation failed: {error_msg}")
                    
                    # Wait before next poll
                    time.sleep(3)
                    
                except requests.RequestException as e:
                    self.logger.warning(f"Status check request failed: {e}")
                    time.sleep(5)
            
            raise TimeoutError(f"Generation timed out after {timeout} seconds")
            
        except Exception as e:
            self.logger.error(f"Voiceover generation failed: {e}")
            raise
    
    def download_file(self, session_id, output_path):
        """Download the generated voiceover file directly."""
        try:
            self.logger.info(f"Downloading file for session: {session_id}")
            
            response = requests.get(
                f"{self.base_url}/api/v1/voiceover/download/{session_id}", 
                stream=True, 
                timeout=60
            )
            response.raise_for_status()
            
            with open(output_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            
            self.logger.info(f"File downloaded successfully: {output_path}")
            return output_path
            
        except Exception as e:
            self.logger.error(f"File download failed: {e}")
            raise

# Usage Example
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    api = RegularVoiceoverAPI("https://your-domain.com")
    
    script = """
    Welcome to our quarterly business review. In this presentation, we'll cover 
    our market performance, key achievements, and strategic initiatives for Q4. 
    Our revenue growth this quarter exceeded expectations, with a 12% increase 
    compared to the same period last year. We've successfully launched three 
    new products and expanded into two additional markets.
    """
    
    try:
        result = api.generate_voiceover(
            script=script,
            voice="nova",
            speed=1.1,
            format_type="mp4",
            background_image_url="https://example.com/corporate-bg.jpg",
            timeout=300
        )
        
        print(f"✅ Voiceover generated successfully!")
        print(f"📄 File: {result['result']['filename']}")
        print(f"⏱️ Duration: {result['result']['duration']}s")
        print(f"📦 Size: {result['result']['file_size']}")
        print(f"🔗 URL: {result['result']['file_url']}")
        
        # Download the file
        api.download_file(result['session_id'], f"output.{result['result']['format']}")
        
    except Exception as e:
        print(f"❌ Error: {e}")
```

### JavaScript/Node.js Client Example

```javascript
const axios = require('axios');

class YouTubeShortsAPI {
    constructor(baseUrl) {
        this.baseUrl = baseUrl.replace(/\/$/, '');
    }
    
    async generateShorts(script, voice = 'nova', speed = 1.0, timeout = 300000) {
        try {
            console.log(`🎬 Starting YouTube Shorts generation...`);
            
            // Step 1: Start generation
            const startResponse = await axios.post(`${this.baseUrl}/api/v1/generate-shorts`, {
                script,
                voice,
                speed
            }, {
                headers: { 'Content-Type': 'application/json' },
                timeout: 30000
            });
            
            if (!startResponse.data.success) {
                throw new Error(`API error: ${startResponse.data.error}`);
            }
            
            const sessionId = startResponse.data.session_id;
            console.log(`📋 Session ID: ${sessionId}`);
            console.log(`📊 Estimated segments: ${startResponse.data.estimated_segments}`);
            
            // Step 2: Poll for completion
            const startTime = Date.now();
            let lastProgress = -1;
            
            while (Date.now() - startTime < timeout) {
                try {
                    const statusResponse = await axios.get(
                        `${this.baseUrl}/api/v1/shorts-status/${sessionId}`,
                        { timeout: 10000 }
                    );
                    
                    const statusData = statusResponse.data;
                    const { status, progress, message } = statusData;
                    
                    // Log progress updates
                    if (progress !== lastProgress) {
                        console.log(`📈 Progress: ${progress}% - ${message}`);
                        lastProgress = progress;
                    }
                    
                    if (status === 'completed') {
                        console.log(`✅ Generation completed! ${statusData.count} videos created`);
                        return statusData;
                    }
                    
                    if (status === 'failed') {
                        throw new Error(`Generation failed: ${statusData.error}`);
                    }
                    
                    // Wait before next poll
                    await new Promise(resolve => setTimeout(resolve, 3000));
                    
                } catch (error) {
                    if (error.code === 'ECONNABORTED') {
                        console.warn('⚠️ Status check timeout, retrying...');
                        await new Promise(resolve => setTimeout(resolve, 5000));
                        continue;
                    }
                    throw error;
                }
            }
            
            throw new Error(`Generation timed out after ${timeout}ms`);
            
        } catch (error) {
            console.error(`❌ YouTube Shorts generation failed:`, error.message);
            throw error;
        }
    }
    
    async downloadZip(zipUrl, outputPath) {
        const fs = require('fs');
        
        try {
            console.log(`📦 Downloading ZIP from: ${zipUrl}`);
            
            const response = await axios.get(`${this.baseUrl}${zipUrl}`, {
                responseType: 'stream',
                timeout: 60000
            });
            
            const writer = fs.createWriteStream(outputPath);
            response.data.pipe(writer);
            
            return new Promise((resolve, reject) => {
                writer.on('finish', () => {
                    console.log(`✅ ZIP downloaded: ${outputPath}`);
                    resolve(outputPath);
                });
                writer.on('error', reject);
            });
            
        } catch (error) {
            console.error(`❌ ZIP download failed:`, error.message);
            throw error;
        }
    }
}

// Usage Example
async function main() {
    const api = new YouTubeShortsAPI('https://your-domain.com');
    
    const script = `
        Breaking: Tech stocks surge in early trading today.
        — pause —
        Apple and Microsoft lead the rally with gains over 3%.
        — pause —
        Analysts remain optimistic about the sector's outlook.
    `;
    
    try {
        const result = await api.generateShorts(script, 'nova', 1.2);
        
        console.log(`🎉 Success! Generated ${result.count} videos`);
        console.log(`📦 ZIP URL: ${result.zip_url}`);
        
        // Download the ZIP
        await api.downloadZip(result.zip_url, 'youtube_shorts.zip');
        
        // Log video details
        result.videos.forEach(video => {
            console.log(`🎥 Video ${video.index}: ${video.download_name} (${video.duration}s)`);
        });
        
    } catch (error) {
        console.error('❌ Error:', error.message);
    }
}

main();
```

### JavaScript/Node.js Client for Regular Voiceover

```javascript
const axios = require('axios');
const fs = require('fs');

class RegularVoiceoverAPI {
    constructor(baseUrl) {
        this.baseUrl = baseUrl.replace(/\/$/, '');
    }
    
    async generateVoiceover(script, options = {}) {
        const {
            voice = 'nova',
            speed = 1.0,
            format = 'mp4',
            backgroundImageUrl = null,
            webhookUrl = null,
            timeout = 300000
        } = options;
        
        try {
            console.log(`🎙️ Starting voiceover generation...`);
            
            // Step 1: Start generation
            const payload = {
                script,
                voice,
                speed,
                format
            };
            
            if (backgroundImageUrl) payload.background_image_url = backgroundImageUrl;
            if (webhookUrl) payload.webhook_url = webhookUrl;
            
            const startResponse = await axios.post(
                `${this.baseUrl}/api/v1/voiceover/generate`,
                payload,
                {
                    headers: { 'Content-Type': 'application/json' },
                    timeout: 30000
                }
            );
            
            if (!startResponse.data.success) {
                throw new Error(`API error: ${startResponse.data.error}`);
            }
            
            const sessionId = startResponse.data.session_id;
            console.log(`📋 Session ID: ${sessionId}`);
            
            // Step 2: Poll for completion
            const startTime = Date.now();
            let lastProgress = -1;
            
            while (Date.now() - startTime < timeout) {
                try {
                    const statusResponse = await axios.get(
                        `${this.baseUrl}/api/v1/voiceover/status/${sessionId}`,
                        { timeout: 10000 }
                    );
                    
                    const statusData = statusResponse.data;
                    const { status, progress, message } = statusData;
                    
                    // Log progress updates
                    if (progress !== lastProgress) {
                        console.log(`📈 Progress: ${progress}% - ${message}`);
                        lastProgress = progress;
                    }
                    
                    if (status === 'completed') {
                        console.log(`✅ Voiceover generation completed!`);
                        return statusData;
                    }
                    
                    if (status === 'failed') {
                        throw new Error(`Generation failed: ${statusData.error}`);
                    }
                    
                    // Wait before next poll
                    await new Promise(resolve => setTimeout(resolve, 3000));
                    
                } catch (error) {
                    if (error.code === 'ECONNABORTED') {
                        console.warn('⚠️ Status check timeout, retrying...');
                        await new Promise(resolve => setTimeout(resolve, 5000));
                        continue;
                    }
                    throw error;
                }
            }
            
            throw new Error(`Generation timed out after ${timeout}ms`);
            
        } catch (error) {
            console.error(`❌ Voiceover generation failed:`, error.message);
            throw error;
        }
    }
    
    async downloadFile(sessionId, outputPath) {
        try {
            console.log(`📥 Downloading file for session: ${sessionId}`);
            
            const response = await axios.get(
                `${this.baseUrl}/api/v1/voiceover/download/${sessionId}`,
                {
                    responseType: 'stream',
                    timeout: 60000
                }
            );
            
            const writer = fs.createWriteStream(outputPath);
            response.data.pipe(writer);
            
            return new Promise((resolve, reject) => {
                writer.on('finish', () => {
                    console.log(`✅ File downloaded: ${outputPath}`);
                    resolve(outputPath);
                });
                writer.on('error', reject);
            });
            
        } catch (error) {
            console.error(`❌ File download failed:`, error.message);
            throw error;
        }
    }
}

// Usage Example
async function main() {
    const api = new RegularVoiceoverAPI('https://your-domain.com');
    
    const script = `
        Good morning everyone and welcome to our quarterly business review.
        Today's agenda includes market analysis, product updates, and our
        strategic roadmap for the next quarter. We're excited to share
        our achievements and outline our vision for continued growth.
    `;
    
    try {
        const result = await api.generateVoiceover(script, {
            voice: 'nova',
            speed: 1.1,
            format: 'mp4',
            backgroundImageUrl: 'https://example.com/presentation-bg.jpg'
        });
        
        console.log(`🎉 Success! Generated voiceover`);
        console.log(`📄 Filename: ${result.result.filename}`);
        console.log(`⏱️ Duration: ${result.result.duration}s`);
        console.log(`📦 File Size: ${result.result.file_size}`);
        console.log(`🔗 Download URL: ${result.result.file_url}`);
        
        // Download the file
        await api.downloadFile(result.session_id, `output.${result.result.format}`);
        
    } catch (error) {
        console.error('❌ Error:', error.message);
    }
}

main();
```

## Error Handling

### Common Error Responses

```json
{
  "success": false,
  "error": "Script is required"
}
```

```json
{
  "success": false,
  "error": "Invalid voice. Available voices: nova, alloy, echo, fable, onyx, shimmer"
}
```

```json
{
  "success": false,
  "error": "Speed must be between 0.25 and 4.0"
}
```

### Status Codes
- `200` - Success
- `400` - Bad Request (invalid parameters)
- `404` - Session not found
- `500` - Internal Server Error

### Best Practices

1. **Always check the `success` field** in responses
2. **Implement exponential backoff** for status polling
3. **Set reasonable timeouts** (5-10 minutes for large scripts)
4. **Handle network errors gracefully** with retries
5. **Log progress updates** for debugging
6. **Validate inputs** before sending requests

## Rate Limiting & Performance

- **Concurrent requests**: Limit to 3-5 simultaneous generations
- **Script length**: Keep under 4000 characters for best performance
- **Polling frequency**: Check status every 3-5 seconds
- **Timeout recommendations**: 
  - Small scripts (1-3 segments): 2 minutes
  - Medium scripts (4-8 segments): 5 minutes
  - Large scripts (9+ segments): 10 minutes

## Video Specifications

### Generated Video Format
- **Resolution**: 1080x1920 (9:16 portrait)
- **Format**: MP4 with H.264 encoding
- **Audio**: AAC encoding, 44.1kHz
- **Optimized for**: YouTube Shorts, Instagram Reels, TikTok

### File Naming
- Individual videos: `api_Meaningful_Content_Keywords.mp4`
- ZIP files: `api_shorts_{session_id}_{random}.zip`

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

3. **Download URLs not working**
   - Files may have been cleaned up
   - Check the full URL path
   - Try downloading immediately after generation

### Debug Tips

1. **Enable detailed logging** in your client
2. **Check server logs** for errors
3. **Validate script format** (ensure proper pause markers)
4. **Test with shorter scripts** first
5. **Monitor progress updates** for stuck generations

## Support

For issues or questions:
1. Check this integration guide
2. Review the troubleshooting section
3. Enable debug logging in your client
4. Contact the API maintainer with session IDs and error messages

---

**Last Updated**: September 14, 2025  
**API Version**: v1  
**Compatible with**: All major programming languages via HTTP/REST