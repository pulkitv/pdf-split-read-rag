# YouTube Shorts API Integration Guide

This guide provides complete instructions for integrating with the YouTube Shorts Generation API to create automated video content from text scripts.

## Overview

The YouTube Shorts API allows you to:
- Generate multiple short videos from a single script
- Split content using pause markers (`— pause —`)
- Customize voice and speech speed
- Download individual videos or bulk ZIP files
- Track generation progress in real-time

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