# FFmpeg Quality Optimization Guide

## Overview

The voiceover system now uses optimized FFmpeg parameters for professional-quality video output. These settings provide a balance between file size, encoding speed, and visual/audio quality.

## Quality Settings Explained

### Video Encoding

#### 1. **VIDEO_PRESET** (Default: `slow`)
Controls encoding speed vs. compression efficiency.

| Preset | Speed | Quality | Use Case |
|--------|-------|---------|----------|
| `ultrafast` | Fastest | Lowest | Real-time streaming, testing |
| `superfast` | Very Fast | Low | Quick previews |
| `veryfast` | Fast | Medium-Low | Live encoding |
| `faster` | Fast | Medium | Fast turnaround needed |
| `fast` | Moderate | Medium-High | Good balance for speed |
| `medium` | Moderate | High | Default FFmpeg setting |
| **`slow`** | **Slow** | **Very High** | **Recommended (current)** |
| `slower` | Very Slow | Excellent | Archival quality |
| `veryslow` | Slowest | Maximum | Professional archival |

**Current Setting:** `slow` provides excellent quality with reasonable encoding time.

#### 2. **VIDEO_CRF** (Default: `18`)
Constant Rate Factor - controls video quality (0-51 scale).

| CRF Value | Quality Level | File Size | Use Case |
|-----------|---------------|-----------|----------|
| 0 | Lossless | Very Large | Editing/archival |
| **18** | **Visually Lossless** | **Large** | **High-quality output (current)** |
| 23 | High Quality | Medium | YouTube recommended |
| 28 | Acceptable Quality | Small | Web streaming |
| 35 | Low Quality | Very Small | Low bandwidth |
| 51 | Worst Quality | Smallest | Thumbnails only |

**Current Setting:** `18` provides visually lossless quality - virtually indistinguishable from the source.

**Recommendation:**
- **CRF 18**: For professional content, presentations, archival
- **CRF 23**: For general YouTube uploads (good quality, smaller files)
- **CRF 28**: For social media where quality is less critical

#### 3. **VIDEO_PROFILE** (Default: `high`)
H.264 encoding profile.

| Profile | Features | Compatibility | Use Case |
|---------|----------|---------------|----------|
| `baseline` | Basic | Universal | Old devices, web browsers |
| `main` | Standard | Most devices | General compatibility |
| **`high`** | **Advanced** | **Modern devices** | **Best quality (current)** |

**Current Setting:** `high` enables all H.264 features for maximum quality.

#### 4. **VIDEO_LEVEL** (Default: `4.2`)
H.264 level - defines video capabilities.

| Level | Max Resolution | Max Bitrate | Use Case |
|-------|----------------|-------------|----------|
| 3.0 | 720p | 10 Mbps | Mobile devices |
| 3.1 | 720p | 14 Mbps | Enhanced mobile |
| 4.0 | 1080p | 20 Mbps | HD content |
| 4.1 | 1080p | 50 Mbps | High-quality HD |
| **4.2** | **1080p** | **50 Mbps** | **Professional HD (current)** |
| 5.0 | 4K | 135 Mbps | 4K content |

**Current Setting:** `4.2` supports full 1080p HD at professional bitrates.

#### 5. **VIDEO_TUNE** (Default: `animation`)
Optimizes encoder for specific content types.

| Tune | Optimized For | Use Case |
|------|---------------|----------|
| **`animation`** | **Text, graphics, cartoons** | **Voiceovers with text (current)** |
| `film` | Natural video, movies | Live-action footage |
| `grain` | Grainy/noisy footage | Film scans |
| `stillimage` | Slideshows | Photo presentations |
| `fastdecode` | Playback speed | Low-power devices |
| `zerolatency` | Real-time | Live streaming |

**Current Setting:** `animation` is perfect for voiceover videos with text overlays and static backgrounds.

**Recommendation:**
- **animation**: For voiceovers, text-heavy content (current use case)
- **film**: If using real background video footage

### Audio Encoding

#### 6. **AUDIO_BITRATE** (Default: `256k`)
Controls audio quality.

| Bitrate | Quality | File Size | Use Case |
|---------|---------|-----------|----------|
| 128k | Good | Small | Podcasts, voice-only |
| 192k | High | Medium | Music, voice |
| **256k** | **Very High** | **Large** | **Professional (current)** |
| 320k | Maximum | Largest | Studio quality |

**Current Setting:** `256k` provides excellent audio quality for voiceovers.

#### 7. **AUDIO_SAMPLE_RATE** (Default: `48000`)
Audio sampling frequency.

| Sample Rate | Quality | Use Case |
|-------------|---------|----------|
| 44100 Hz | CD Quality | Music, consumer audio |
| **48000 Hz** | **Professional** | **Video production (current)** |

**Current Setting:** `48000 Hz` (48 kHz) is the professional standard for video.

## Performance Impact

### Encoding Time Comparison

For a 60-second video:

| Preset | Approximate Time | Quality Gain |
|--------|-----------------|--------------|
| `ultrafast` | 5-10 seconds | Baseline |
| `fast` | 15-20 seconds | +15% |
| `medium` | 30-40 seconds | +25% |
| **`slow`** | **60-90 seconds** | **+40% (current)** |
| `veryslow` | 120-180 seconds | +45% |

**Current Setting:** 60-90 seconds encoding time for excellent quality.

### File Size Comparison

For a 60-second 1080p video with voice:

| Settings | File Size | Quality |
|----------|-----------|---------|
| CRF 28, medium, 128k audio | ~8 MB | Acceptable |
| CRF 23, medium, 192k audio | ~15 MB | High |
| **CRF 18, slow, 256k audio** | **~25 MB** | **Visually Lossless (current)** |
| CRF 0, veryslow, 320k audio | ~100+ MB | True lossless |

**Current Setting:** ~25 MB for 60 seconds - excellent quality-to-size ratio.

## Customization Guide

### For Faster Encoding (Lower Quality)
```bash
VIDEO_PRESET=fast
VIDEO_CRF=23
AUDIO_BITRATE=192k
```
**Result:** 3x faster encoding, slightly lower quality, smaller files.

### For Maximum Quality (Slower Encoding)
```bash
VIDEO_PRESET=veryslow
VIDEO_CRF=15
AUDIO_BITRATE=320k
VIDEO_PROFILE=high
```
**Result:** Near-perfect quality, larger files, slower encoding.

### For Web/Social Media (Balanced)
```bash
VIDEO_PRESET=medium
VIDEO_CRF=23
AUDIO_BITRATE=192k
VIDEO_TUNE=film
```
**Result:** YouTube-quality output, faster encoding, smaller files.

### For Bandwidth-Constrained Delivery
```bash
VIDEO_PRESET=fast
VIDEO_CRF=28
AUDIO_BITRATE=128k
VIDEO_PROFILE=main
```
**Result:** Smaller files, faster encoding, acceptable quality.

## Quality Recommendations by Use Case

### 📱 YouTube Shorts / Social Media
```bash
VIDEO_PRESET=medium
VIDEO_CRF=23
AUDIO_BITRATE=192k
VIDEO_TUNE=animation  # If text-heavy
```

### 🎥 Professional Presentations
```bash
VIDEO_PRESET=slow      # Current
VIDEO_CRF=18          # Current
AUDIO_BITRATE=256k    # Current
VIDEO_PROFILE=high    # Current
```

### 📚 Educational Content / Tutorials
```bash
VIDEO_PRESET=medium
VIDEO_CRF=20
AUDIO_BITRATE=192k
VIDEO_TUNE=animation
```

### 🎬 Archival / Master Copy
```bash
VIDEO_PRESET=veryslow
VIDEO_CRF=15
AUDIO_BITRATE=320k
VIDEO_PROFILE=high
AUDIO_SAMPLE_RATE=48000
```

### ⚡ Quick Previews / Testing
```bash
VIDEO_PRESET=ultrafast
VIDEO_CRF=28
AUDIO_BITRATE=128k
```

## Current Optimized Settings Summary

The system is currently configured for **high-quality professional output**:

```bash
VIDEO_PRESET=slow              # Excellent compression efficiency
VIDEO_CRF=18                   # Visually lossless quality
VIDEO_PROFILE=high             # All H.264 features enabled
VIDEO_LEVEL=4.2                # Full 1080p HD support
VIDEO_TUNE=animation           # Optimized for text/graphics
AUDIO_BITRATE=256k             # Professional audio quality
AUDIO_SAMPLE_RATE=48000        # Video production standard
```

### Trade-offs:
- ✅ **Excellent visual quality** - Nearly indistinguishable from lossless
- ✅ **Professional audio** - Crystal clear voiceovers
- ✅ **Modern compatibility** - Works on all modern devices
- ⏱️ **Moderate encoding time** - 60-90 seconds per minute of video
- 💾 **Larger file sizes** - ~25 MB per minute

## Testing Quality Settings

Run the test script with different settings:

```bash
# Test current high-quality settings
python test_background_video.py

# Test faster settings (modify .env first)
VIDEO_PRESET=fast VIDEO_CRF=23 python test_background_video.py

# Compare output files in voiceovers/ folder
```

## Visual Quality Indicators

### How to identify quality levels:

**CRF 18 (Current):**
- Sharp text edges
- No visible compression artifacts
- Smooth gradients
- Clear background video

**CRF 23 (YouTube Standard):**
- Very good text clarity
- Minimal artifacts
- Good for most uses

**CRF 28 (Web Streaming):**
- Slight blurriness on text edges
- Some compression artifacts visible
- Acceptable for social media

## Audio Quality Indicators

### How to identify audio quality levels:

**256k (Current):**
- Crystal clear voice
- No audio artifacts
- Full frequency range

**192k:**
- Very clear voice
- Suitable for most uses

**128k:**
- Clear voice
- Some high-frequency loss
- Good for voice-only content

## Troubleshooting

### Encoding is too slow
- Reduce `VIDEO_PRESET` from `slow` to `medium` or `fast`
- Increase `VIDEO_CRF` from `18` to `23`

### File sizes are too large
- Increase `VIDEO_CRF` from `18` to `23` or `28`
- Reduce `AUDIO_BITRATE` from `256k` to `192k`

### Quality is not good enough
- Decrease `VIDEO_CRF` from `18` to `15` (caution: much larger files)
- Use `VIDEO_PRESET=slower` or `veryslow`
- Increase `AUDIO_BITRATE` to `320k`

### Compatibility issues
- Change `VIDEO_PROFILE` from `high` to `main`
- Reduce `VIDEO_LEVEL` from `4.2` to `4.0`

## Additional Resources

- [FFmpeg H.264 Encoding Guide](https://trac.ffmpeg.org/wiki/Encode/H.264)
- [FFmpeg AAC Encoding Guide](https://trac.ffmpeg.org/wiki/Encode/AAC)
- [CRF Guide](https://slhck.info/video/2017/02/24/crf-guide.html)

---

**Last Updated:** November 2025  
**Current Version:** Optimized for professional voiceover content
