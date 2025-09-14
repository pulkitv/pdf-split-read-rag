import os
import tempfile
from openai import OpenAI
import subprocess
import uuid
from pathlib import Path
import json
import shutil
import re
from werkzeug.utils import secure_filename

# Removed unused Flask app and request imports to keep this module framework-agnostic

class VoiceoverSystem:
    def __init__(self):
        # Initialize OpenAI client for Text-to-Speech
        api_key = os.getenv('OPENAI_API_KEY')
        if api_key:
            self.openai_client = OpenAI(api_key=api_key)
        else:
            self.openai_client = None
        
        # Configure paths
        self.output_folder = os.getenv('VOICEOVER_FOLDER', 'voiceovers')
        os.makedirs(self.output_folder, exist_ok=True)
        
        # Voice settings
        self.available_voices = ['alloy', 'echo', 'fable', 'onyx', 'nova', 'shimmer']
        self.supported_formats = ['mp3', 'wav', 'mp4']
        
        # Video generation settings - Support both formats
        # Regular format (landscape) - for Standalone AI Voiceover Generator
        self.regular_video_width = 1920
        self.regular_video_height = 1080
        
        # YouTube Shorts format (portrait) - for YouTube Shorts Generator
        self.shorts_video_width = 1080
        self.shorts_video_height = 1920
        
        # Default to regular format (will be overridden by generation_type parameter)
        self.video_width = self.regular_video_width
        self.video_height = self.regular_video_height
        self.video_fps = int(os.getenv('VIDEO_FPS', 30))
        
        # Text overlay settings
        self.text_overlay_enabled = os.getenv('VOICEOVER_TEXT_OVERLAY', 'true').lower() == 'true'
        self.text_overlay_font_path = os.getenv('VOICEOVER_FONT_PATH', '')
        self.text_overlay_max_chars = int(os.getenv('VOICEOVER_TEXT_OVERLAY_MAX_CHARS', 120))
        self.text_overlay_fontsize_px = int(os.getenv('VOICEOVER_OVERLAY_FONTSIZE', 64))
        self.text_overlay_side_margin_px = int(os.getenv('VOICEOVER_TEXT_MARGIN', 40))
        
        # TTS request constraints
        self.max_input_chars = int(os.getenv('VOICEOVER_MAX_INPUT_CHARS', 3900))
        self.pause_marker_primary = '— pause —'
        self.pause_marker_fallback = '-- pause --'
        self.pause_silence_seconds = float(os.getenv('VOICEOVER_PAUSE_SECONDS', 0))

        # Video format configurations
        self.video_formats = {
            'regular': {
                'width': 1920,
                'height': 1080,
                'description': 'Regular landscape format (1920x1080)'
            },
            'youtube_shorts': {
                'width': 1080,
                'height': 1920,
                'description': 'YouTube Shorts portrait format (1080x1920)'
            }
        }
        
    def _generate_filename_from_text(self, text):
        """Generate a safe filename from the first line of text."""
        if not text:
            return None
        
        # Get the first line and clean it up
        first_line = text.split('\n')[0].strip()
        if not first_line:
            return None
        
        # Remove common prefixes and clean up
        first_line = re.sub(r'^(chapter|part|section)\s*\d*[:\-\s]*', '', first_line, flags=re.IGNORECASE)
        
        # Limit length to avoid filesystem issues
        if len(first_line) > 50:
            # Try to find a good breaking point
            words = first_line.split()
            truncated = ""
            for word in words:
                if len(truncated + " " + word) <= 50:
                    truncated = (truncated + " " + word).strip()
                else:
                    break
            first_line = truncated if truncated else first_line[:50]
        
        # Make it filesystem-safe
        filename = secure_filename(first_line)
        
        # Fallback if secure_filename removes everything
        if not filename or len(filename) < 3:
            return None
            
        return filename
    
    def generate_speech(self, text, voice='nova', speed=1.0, format='mp3', session_id=None, 
                       background_image_path=None, generation_type='youtube_shorts', custom_filename=None):
        """
        Generate speech from text with optional video output
        
        Args:
            text: Text to convert to speech
            voice: Voice to use (nova, alloy, echo, fable, onyx, shimmer)
            speed: Speech speed (0.25 to 4.0)
            format: Output format (mp3, wav, mp4)
            session_id: Optional session ID for tracking
            background_image_path: Path to background image for video
            generation_type: 'regular' or 'standalone' for landscape (1920x1080), 
                           'shorts' or 'youtube_shorts' for portrait (1080x1920)
            custom_filename: Optional custom filename for the output file
        """
        try:
            # Generate base filename from first line of text if not provided
            if custom_filename is None:
                # Extract first line and clean it for filename
                first_line = text.split('\n')[0].strip()
                # Remove common separators and clean for filename
                first_line = first_line.replace('— pause —', '').strip()
                if first_line:
                    # Clean the text to make it filename-safe
                    import re
                    cleaned_text = re.sub(r'[^\w\s-]', '', first_line)
                    cleaned_text = re.sub(r'[-\s]+', '_', cleaned_text)
                    custom_filename = cleaned_text[:50]  # Limit to 50 characters
                else:
                    custom_filename = "voiceover"
            
            # Use custom filename as base, with UUID fallback for uniqueness
            base_filename = custom_filename or str(uuid.uuid4())
            
            # Set video dimensions based on generation type
            # Handle both 'shorts' and 'youtube_shorts' for backward compatibility
            if generation_type in ['shorts', 'youtube_shorts']:
                self.video_width = self.shorts_video_width
                self.video_height = self.shorts_video_height
                # Optimize text settings for mobile/portrait viewing
                self.text_overlay_fontsize_px = int(os.getenv('VOICEOVER_SHORTS_FONTSIZE', 56))  # Larger for mobile readability
                self.text_overlay_side_margin_px = int(max(50, int(self.video_width * 0.08)))  # More margin for mobile
                print(f"Using YouTube Shorts format: {self.video_width}x{self.video_height}")
            else:  # 'regular' or 'standalone'
                self.video_width = self.regular_video_width
                self.video_height = self.regular_video_height
                # Standard text settings for desktop/landscape viewing
                self.text_overlay_fontsize_px = int(os.getenv('VOICEOVER_REGULAR_FONTSIZE', 64))
                self.text_overlay_side_margin_px = int(max(80, int(self.video_width * 0.06)))  # Proportional margins
                print(f"Using Regular format: {self.video_width}x{self.video_height}")
            
            file_id = str(uuid.uuid4())
            if session_id:
                file_id = f"{session_id}_{file_id}"
            work_dir = tempfile.mkdtemp(prefix="voiceover_")
            segments = self._split_text_for_tts(text, self.max_input_chars)

            def finalize_output_from_mp3(source_mp3_path: str, captions=None):
                # Generate filename from text if custom_filename not provided
                if custom_filename:
                    base_filename = custom_filename
                else:
                    base_filename = self._generate_filename_from_text(text)
                    if not base_filename:
                        base_filename = file_id
                
                if format == 'mp4':
                    video_path = self._create_video_with_audio(
                        source_mp3_path, base_filename, text,
                        background_image_path=background_image_path,
                        captions=captions,
                    )
                    final_path = os.path.join(self.output_folder, os.path.basename(video_path))
                    if video_path != final_path:
                        os.replace(video_path, final_path)
                    return final_path, 'mp4'
                elif format == 'wav':
                    final_wav = os.path.join(self.output_folder, f"{base_filename}.wav")
                    self._convert_audio_format(source_mp3_path, final_wav, 'wav')
                    return final_wav, 'wav'
                else:
                    final_mp3 = os.path.join(self.output_folder, f"{base_filename}.mp3")
                    if os.path.abspath(source_mp3_path) != os.path.abspath(final_mp3):
                        os.replace(source_mp3_path, final_mp3)
                    return final_mp3, 'mp3'

            try:
                # Single segment processing
                if len(segments) == 1 and segments[0]['type'] == 'text':
                    temp_mp3 = os.path.join(work_dir, f"{file_id}.mp3")
                    self._tts_request_to_file(segments[0]['content'], voice=voice, speed=speed, out_path=temp_mp3)
                    total_dur = self._get_audio_duration(temp_mp3)
                    captions = self._make_captions_from_text(segments[0]['content'], total_dur)
                    final_path, final_fmt = finalize_output_from_mp3(temp_mp3, captions=captions if self.text_overlay_enabled else None)
                    self._safe_rmtree(work_dir)
                    return {
                        'success': True,
                        'file_path': final_path,
                        'file_url': f"/download-voiceover/{os.path.basename(final_path)}",
                        'format': final_fmt,
                        'duration': self._get_audio_duration(final_path)
                    }

                # Multi-segment processing
                parts = []
                for seg in segments:
                    if seg['type'] == 'pause':
                        silence_mp3 = os.path.join(work_dir, f"silence_{len(parts)}.mp3")
                        self._generate_silence(silence_mp3, self.pause_silence_seconds, target_format='mp3')
                        parts.append({'type': 'pause', 'path': silence_mp3, 'duration': None})
                    else:
                        seg_mp3 = os.path.join(work_dir, f"seg_{len(parts)}.mp3")
                        self._tts_request_to_file(seg['content'], voice=voice, speed=speed, out_path=seg_mp3)
                        parts.append({'type': 'text', 'path': seg_mp3, 'text': seg['content'], 'duration': None})

                # Compute durations and build captions
                for p in parts:
                    p['duration'] = self._get_audio_duration(p['path'])
                
                captions = []
                current_time = 0.0
                
                for p in parts:
                    if p['type'] == 'pause':
                        current_time += p['duration']
                    else:
                        segment_start = current_time
                        segment_end = current_time + p['duration']
                        segment_captions = self._make_captions_from_text(p['text'], p['duration'])
                        
                        for seg_cap in segment_captions:
                            captions.append({
                                'text': seg_cap['text'],
                                'start': segment_start + seg_cap['start'],
                                'end': segment_start + seg_cap['end']
                            })
                        
                        current_time = segment_end

                # Concatenate audio parts
                joined_mp3 = os.path.join(work_dir, f"{file_id}_joined.mp3")
                self._concat_audio_files([p['path'] for p in parts], joined_mp3, target_format='mp3')

                final_path, final_fmt = finalize_output_from_mp3(joined_mp3, captions=captions if self.text_overlay_enabled else None)
                self._safe_rmtree(work_dir)
                return {
                    'success': True,
                    'file_path': final_path,
                    'file_url': f"/download-voiceover/{os.path.basename(final_path)}",
                    'format': final_fmt,
                    'duration': self._get_audio_duration(final_path)
                }
            except Exception as e:
                print(f"Error generating speech: {str(e)}")
                self._safe_rmtree(work_dir)
                raise Exception(f"Failed to generate voiceover: {str(e)}")
        except Exception as e:
            print(f"Error generating speech: {str(e)}")
            self._safe_rmtree(work_dir)
            raise Exception(f"Failed to generate voiceover: {str(e)}")

    def _tts_request_to_file(self, text, voice, speed, out_path):
        """Issue a TTS request to OpenAI and write MP3 bytes to out_path."""
        client = self.openai_client
        if client is None:
            raise Exception("OpenAI client not configured. Please set OPENAI_API_KEY environment variable.")

        # Create TTS request
        resp = client.audio.speech.create(
            model="tts-1-hd",
            voice=voice,
            input=text,
            speed=speed,
        )

        # Check if response has stream_to_file method
        if hasattr(resp, 'stream_to_file') and callable(getattr(resp, 'stream_to_file')):
            resp.stream_to_file(out_path)
            return

        # Handle different response formats
        content = None
        try:
            content = getattr(resp, 'content', None)
        except Exception:
            content = None

        if content is None:
            try:
                if isinstance(resp, (bytes, bytearray)):
                    content = bytes(resp)
                elif hasattr(resp, 'read') and callable(getattr(resp, 'read')):
                    content = resp.read()
                elif hasattr(resp, 'iter_bytes') and callable(getattr(resp, 'iter_bytes')):
                    with open(out_path, 'wb') as f:
                        for chunk in resp.iter_bytes():
                            f.write(chunk)
                    return
            except Exception:
                pass

        if content is None:
            body = getattr(resp, 'body', None) or getattr(resp, 'data', None)
            if isinstance(body, (bytes, bytearray)):
                content = body

        if content is None:
            raise Exception("Unsupported OpenAI TTS response shape for installed 'openai' package.")

        with open(out_path, 'wb') as f:
            f.write(content)
    
    def _split_text_for_tts(self, text: str, max_chars: int):
        """Split text into segments under max_chars, respecting pause markers."""
        if not text:
            return [{'type': 'text', 'content': ''}]
        
        t = text.replace('\r\n', '\n').strip()
        
        # Split on pause markers
        parts = []
        idx = 0
        while idx < len(t):
            next_primary = t.find(self.pause_marker_primary, idx)
            next_fallback = t.find(self.pause_marker_fallback, idx)
            candidates = [i for i in [next_primary, next_fallback] if i != -1]
            next_idx = min(candidates) if candidates else -1
            if next_idx == -1:
                parts.append({'type': 'text', 'content': t[idx:]})
                break
            if next_idx > idx:
                parts.append({'type': 'text', 'content': t[idx:next_idx]})
            parts.append({'type': 'pause'})
            if next_idx == next_primary:
                idx = next_idx + len(self.pause_marker_primary)
            else:
                idx = next_idx + len(self.pause_marker_fallback)
        
        # Split large text chunks
        def split_chunk(chunk_text: str):
            chunk_text = (chunk_text or '').strip()
            if not chunk_text or len(chunk_text) <= max_chars:
                return [chunk_text] if chunk_text else []
            
            # Split by paragraphs first
            paras = [p.strip() for p in chunk_text.split('\n\n') if p.strip()]
            current = ''
            chunks = []
            for p in paras:
                if len(p) > max_chars:
                    # Split by sentences
                    sentences = []
                    buf = ''
                    for ch in p:
                        buf += ch
                        if ch in '.!?\n':
                            sentences.append(buf.strip())
                            buf = ''
                    if buf.strip():
                        sentences.append(buf.strip())
                    
                    for s in sentences:
                        if len(s) > max_chars:
                            # Hard wrap
                            start = 0
                            while start < len(s):
                                chunks.append(s[start:start+max_chars])
                                start += max_chars
                        else:
                            if len(current) + len(s) + 1 <= max_chars:
                                current = f"{current} {s}".strip()
                            else:
                                if current:
                                    chunks.append(current)
                                current = s
                else:
                    if len(current) + len(p) + 2 <= max_chars:
                        current = f"{current}\n\n{p}".strip()
                    else:
                        if current:
                            chunks.append(current)
                        current = p
            if current:
                chunks.append(current)
            return chunks
        
        final_segments = []
        for part in parts:
            if part['type'] == 'pause':
                final_segments.append({'type': 'pause'})
            else:
                for sub in split_chunk(part['content']):
                    final_segments.append({'type': 'text', 'content': sub})
        
        # Clean up consecutive pauses
        cleaned = []
        for seg in final_segments:
            if seg['type'] == 'pause':
                if not cleaned or cleaned[-1]['type'] == 'pause':
                    continue
                cleaned.append(seg)
            else:
                cleaned.append(seg)
        if cleaned and cleaned[-1]['type'] == 'pause':
            cleaned.pop()
        return cleaned or [{'type': 'text', 'content': ''}]
    
    def _create_video_with_audio(self, audio_path, file_id, text, background_image_path=None, captions=None):
        """Create video from audio with optional background image and captions."""
        try:
            video_filename = f"{file_id}.mp4"
            video_path = os.path.join(self.output_folder, video_filename)
            duration = self._get_audio_duration(audio_path)

            # Prepare captions
            cap_list = []
            if captions:
                for c in captions:
                    s = max(0.0, float(c.get('start', 0.0)))
                    e = min(float(duration), float(c.get('end', duration)))
                    if e > s and isinstance(c.get('text'), str) and c.get('text').strip():
                        cap_list.append({'text': c['text'].strip(), 'start': s, 'end': e})

            if background_image_path and os.path.exists(background_image_path):
                # Static image video with optional captions
                vf_scale_pad = (
                    f"[0:v]scale={self.video_width}:{self.video_height}:force_original_aspect_ratio=decrease,"
                    f"pad={self.video_width}:{self.video_height}:(ow-iw)/2:(oh-ih)/2:color=0x1e3c72[bg]"
                )
                filter_parts = [vf_scale_pad]
                last_label = 'bg'
                if cap_list:
                    timed_chain, last_label = self._build_timed_drawtext_chain(last_label, cap_list)
                    filter_parts.append(timed_chain)
                filter_complex = ';'.join(filter_parts)
                ffmpeg_cmd = [
                    'ffmpeg', '-y',
                    '-loop', '1', '-i', background_image_path,
                    '-i', audio_path,
                    '-filter_complex', filter_complex,
                    '-map', f'[{last_label}]', '-map', '1:a',
                    '-r', str(self.video_fps), '-t', str(duration),
                    '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-c:a', 'aac',
                    '-shortest', video_path
                ]
                result = subprocess.run(ffmpeg_cmd, capture_output=True, text=True)
                if result.returncode != 0:
                    print(f"Static image video failed: {result.stderr}")
                    temp_video = os.path.join(tempfile.gettempdir(), f"{uuid.uuid4()}.mp4")
                    temp_path = self._create_waveform_video(audio_path, temp_video, duration, text, captions=cap_list)
                    os.replace(temp_path, video_path)
            else:
                # Waveform video
                self._create_waveform_video(audio_path, video_path, duration, text, captions=cap_list)

            if not os.path.exists(video_path):
                raise Exception("Video file was not created")
            return video_path
        except Exception as e:
            print(f"Error creating video: {str(e)}")
            return self._create_simple_video(audio_path, os.path.join(self.output_folder, f"{file_id}.mp4"), duration)
    
    def _create_waveform_video(self, audio_path, video_path, duration, text, captions=None):
        """Create waveform visualization video with optional captions."""
        try:
            filter_parts = [
                f"[1:a]showwaves=s={self.video_width}x{int(self.video_height*0.3)}:mode=line:colors=white@0.8[waveform]",
                f"[0:v][waveform]overlay=(W-w)/2:(H-h)/2[bg]"
            ]
            last_label = 'bg'

            if captions:
                timed_chain, last_label = self._build_timed_drawtext_chain(last_label, captions)
                filter_parts.append(timed_chain)

            filter_complex = ';'.join(filter_parts)
            ffmpeg_cmd = [
                'ffmpeg', '-y',
                '-f', 'lavfi', '-i', f'color=c=0x1e3c72:size={self.video_width}x{self.video_height}:duration={duration}',
                '-i', audio_path,
                '-filter_complex', filter_complex,
                '-map', f'[{last_label}]', '-map', '1:a',
                '-c:v', 'libx264', '-c:a', 'aac', '-shortest', video_path
            ]
            result = subprocess.run(ffmpeg_cmd, capture_output=True, text=True)
            if result.returncode != 0:
                print(f"Waveform video failed: {result.stderr}")
                return self._create_simple_video(audio_path, video_path, duration)
            return video_path
        except Exception as e:
            print(f"Waveform video error: {str(e)}")
            return self._create_simple_video(audio_path, video_path, duration)
    
    def _create_simple_video(self, audio_path, video_path, duration):
        """Create simple static background video."""
        try:
            ffmpeg_cmd = [
                'ffmpeg', '-y',
                '-f', 'lavfi', '-i', f'color=c=0x1e3c72:size={self.video_width}x{self.video_height}:duration={duration}',
                '-i', audio_path,
                '-c:v', 'libx264', '-c:a', 'aac', '-shortest', video_path
            ]
            subprocess.run(ffmpeg_cmd, check=True, capture_output=True)
            return video_path
        except Exception as e:
            print(f"Simple video creation failed: {str(e)}")
            raise Exception("Failed to create video file")
    
    def _convert_audio_format(self, input_path, output_path, target_format):
        """Convert audio to different format."""
        try:
            ffmpeg_cmd = [
                'ffmpeg', '-y', '-i', input_path,
                '-c:a', 'pcm_s16le' if target_format == 'wav' else 'libmp3lame',
                output_path
            ]
            subprocess.run(ffmpeg_cmd, check=True, capture_output=True)
        except Exception as e:
            raise Exception(f"Failed to convert audio format: {str(e)}")
    
    def _concat_audio_files(self, input_paths, output_path, target_format='mp3'):
        """Concatenate multiple audio files."""
        if not input_paths:
            raise Exception("No audio segments to concatenate")
        
        with tempfile.NamedTemporaryFile('w', delete=False, suffix='.txt') as list_file:
            list_path = list_file.name
            for p in input_paths:
                list_file.write(f"file '{os.path.abspath(p)}'\n")
        
        try:
            codec = 'libmp3lame' if target_format == 'mp3' else 'pcm_s16le'
            ffmpeg_cmd = [
                'ffmpeg', '-y', '-f', 'concat', '-safe', '0', '-i', list_path,
                '-c:a', codec, output_path
            ]
            result = subprocess.run(ffmpeg_cmd, capture_output=True, text=True)
            if result.returncode != 0:
                # Fallback method
                alt_cmd = ['ffmpeg', '-y']
                for p in input_paths:
                    alt_cmd.extend(['-i', p])
                alt_cmd.extend(['-filter_complex', f"concat=n={len(input_paths)}:v=0:a=1", '-c:a', codec, output_path])
                result2 = subprocess.run(alt_cmd, capture_output=True, text=True)
                if result2.returncode != 0:
                    raise Exception(f"Audio concat failed: {result.stderr}\n{result2.stderr}")
        finally:
            try:
                os.remove(list_path)
            except Exception:
                pass
    
    def _generate_silence(self, output_path, seconds: float, target_format: str = 'mp3'):
        """Generate silent audio clip."""
        try:
            codec = 'libmp3lame' if target_format == 'mp3' else 'pcm_s16le'
            ffmpeg_cmd = [
                'ffmpeg', '-y', '-f', 'lavfi', '-i', f"anullsrc=r=44100:cl=mono",
                '-t', str(max(0.1, seconds)), '-c:a', codec, output_path
            ]
            subprocess.run(ffmpeg_cmd, check=True, capture_output=True)
        except Exception:
            # Fallback to minimal silence
            try:
                fallback_cmd = [
                    'ffmpeg', '-y', '-f', 'lavfi', '-i', f"anullsrc=r=44100:cl=mono",
                    '-t', '0.1', '-c:a', codec, output_path
                ]
                subprocess.run(fallback_cmd, check=True, capture_output=True)
            except Exception:
                pass
    
    def _get_audio_duration(self, audio_path):
        """Get audio/video duration in seconds."""
        try:
            ffprobe_cmd = [
                'ffprobe', '-v', 'quiet', '-print_format', 'json',
                '-show_entries', 'format=duration', audio_path
            ]
            result = subprocess.run(ffprobe_cmd, capture_output=True, text=True)
            if result.returncode == 0:
                data = json.loads(result.stdout)
                return float(data['format']['duration'])
            else:
                return 30.0
        except Exception:
            return 30.0
    
    def _escape_text_for_ffmpeg(self, text):
        """Escape text for ffmpeg drawtext filter - handles apostrophes by replacement."""
        if text is None:
            return ''
        s = str(text).replace('\r\n', '\n').strip()
        
        # Replace apostrophes with a safe alternative instead of escaping
        # This is the most reliable approach for FFmpeg drawtext
        s = s.replace("'", "")  # Simply remove apostrophes
        # Alternative: s = s.replace("'", "`")  # Replace with backtick
        
        # Escape other FFmpeg special characters
        s = s.replace('\\', r'\\')
        s = s.replace(':', r'\:')
        s = s.replace('%', r'\%')
        s = s.replace('[', r'\[').replace(']', r'\]')
        
        return s

    def _escape_path_for_ffmpeg(self, path: str):
        """Escape filesystem path for ffmpeg."""
        if not path:
            return ''
        p = str(path)
        p = p.replace('\\', r'\\')
        p = p.replace(':', r'\:')
        p = p.replace("'", r"\'")
        p = p.replace(' ', r'\ ')
        p = p.replace('[', r'\[').replace(']', r'\]')
        return p

    def _wrap_text_for_width(self, text: str, fontsize_px: int, margin_px: int):
        """Word-wrap text to fit video width."""
        s = (text or '').strip()
        if not s:
            return ''
        max_w = max(10, self.video_width - 2 * max(0, int(margin_px)))
        avg_char_w = max(6, int(fontsize_px * 0.6))
        max_chars = max(10, int(max_w / avg_char_w))
        words = s.split()
        lines = []
        cur = ''
        for w in words:
            candidate = f"{cur} {w}".strip() if cur else w
            if len(candidate) <= max_chars:
                cur = candidate
            else:
                if cur:
                    lines.append(cur)
                cur = w
        if cur:
            lines.append(cur)
        return '\n'.join(lines)

    def _build_timed_drawtext_chain(self, base_label: str, captions):
        """Build ffmpeg filter chain for timed captions - uses single quotes with proper apostrophe escaping."""
        label_in = base_label
        chain_parts = []
        for idx, cap in enumerate(captions):
            wrapped = self._wrap_text_for_width(cap.get('text', ''), self.text_overlay_fontsize_px, self.text_overlay_side_margin_px)
            txt = self._escape_text_for_ffmpeg(wrapped)
            start = float(cap.get('start', 0.0))
            end = float(cap.get('end', start + 1.0))
            label_out = f"cap{idx}"
            font_part = ''
            if self.text_overlay_font_path:
                font_part = f":fontfile={self._escape_path_for_ffmpeg(self.text_overlay_font_path)}"
            
            # Use single quotes to wrap text with properly escaped apostrophes
            chain_parts.append(
                f"[{label_in}]drawtext=text='{txt}'{font_part}:fontcolor=white:fontsize={self.text_overlay_fontsize_px}:"
                f"x=(w-text_w)/2:y=(h-text_h)/2:box=1:boxcolor=0x000000@0.5:boxborderw=12:"
                f"line_spacing={int(self.text_overlay_fontsize_px*0.35)}:shadowcolor=0x000000@0.6:shadowx=2:shadowy=2:fix_bounds=1:"
                f"enable='between(t,{start:.3f},{end:.3f})'[{label_out}]"
            )
            label_in = label_out
        return (';'.join(chain_parts) if chain_parts else '', label_in)

    def _make_captions_from_text(self, text: str, audio_duration: float):
        """Create caption data with accurate timing based on actual speech rate."""
        if not text or audio_duration <= 0:
            return []
        
        # Create optimized text chunks
        chunks = self._create_dynamic_caption_chunks(text)
        if not chunks:
            return []
        
        captions = []
        
        # Calculate timing based on actual speech characteristics
        total_words = sum(len(chunk.split()) for chunk in chunks)
        total_chars = sum(len(chunk) for chunk in chunks)
        
        if total_words == 0:
            return []
        
        # Estimate actual speech rate from the audio duration
        # Make changes here for configuring speech
        # This gives us the actual words per second from the TTS engine
        actual_wps = total_words / audio_duration
        
        # Add buffer time for natural pacing (10% buffer for pauses and emphasis)
        buffer_factor = 1.0 #Changing this from 1.1 to 1
        
        current_time = 0.0
        
        for i, chunk in enumerate(chunks):
            chunk_words = len(chunk.split())
            chunk_chars = len(chunk)
            
            # Calculate duration based on word count and actual speech rate
            base_duration = (chunk_words / actual_wps) * buffer_factor
            
            # Adjust for chunk characteristics
            duration_adjustments = 0.0
            
            # Longer chunks need slightly more time for comprehension
            if chunk_words > 15:
                duration_adjustments += 0 #Changing this from 0.3
            elif chunk_words < 5:
                duration_adjustments -= 0.1 #Changing this from 0.2
            
            # Sentences with punctuation need pause time
            punctuation_count = chunk.count('.') + chunk.count('!') + chunk.count('?') + chunk.count(';')
            duration_adjustments += punctuation_count * 0 #Changing this from 0.2
            
            # Complex sentences (with commas) need more time
            comma_count = chunk.count(',')
            duration_adjustments += comma_count * 0 #Changing this from 0.1
            
            # Apply adjustments
            final_duration = max(base_duration + duration_adjustments, 1.5)  # Minimum 1.5 seconds
            
            # Ensure we don't exceed the total audio duration
            if current_time + final_duration > audio_duration:
                final_duration = audio_duration - current_time
                if final_duration < 0.5:  # If less than 0.5 seconds left, merge with previous
                    if captions:
                        captions[-1]['text'] += ' ' + chunk
                        captions[-1]['end'] = audio_duration
                    break
            
            caption = {
                'start': current_time,
                'end': current_time + final_duration,
                'text': chunk.strip(),
                'words': chunk_words,
                'chars': chunk_chars
            }
            
            captions.append(caption)
            current_time += final_duration
        
        # Final adjustment: ensure last caption ends exactly at audio duration
        if captions and captions[-1]['end'] < audio_duration:
            time_remaining = audio_duration - captions[-1]['end']
            # Distribute remaining time proportionally among all captions
            for caption in captions:
                duration = caption['end'] - caption['start']
                proportion = duration / current_time if current_time > 0 else 0
                additional_time = time_remaining * proportion
                caption['end'] += additional_time
        
        return captions

    def _create_dynamic_caption_chunks(self, text: str):
        """Create caption chunks optimized for natural speech pacing and readability."""
        if not text:
            return []
        
        import re
        
        # First, split by major sentence boundaries
        sentences = re.split(r'[.!?]+', text)
        sentences = [s.strip() for s in sentences if s.strip()]
        
        if not sentences:
            return [text.strip()]
        
        chunks = []
        current_chunk = ""
        
        for i, sentence in enumerate(sentences):
            # Clean up the sentence
            sentence = sentence.strip()
            if not sentence:
                continue
            
            # Build the chunk
            if current_chunk:
                test_chunk = current_chunk + ". " + sentence
            else:
                test_chunk = sentence
            
            should_break = False
            
            # Break conditions based on natural speech pacing:
            
            # 1. Character limit for comfortable reading (120-180 chars is optimal)
            if len(test_chunk) > 150:
                should_break = True
            
            # 2. Word count limit (15-25 words per chunk for comfortable reading speed)
            word_count = len(test_chunk.split())
            if word_count > 20:
                should_break = True
            
            # 3. Natural pause points (commas, conjunctions, etc.)
            if len(test_chunk) > 80 and re.search(r',\s+(?:and|but|or|however|therefore|moreover)\s+', test_chunk):
                should_break = True
            
            # 4. End of sentences (natural breaking point)
            if i == len(sentences) - 1:
                should_break = True
            
            # 5. Multiple sentences in chunk (break after 1-2 complete sentences)
            sentence_markers = test_chunk.count('.') + test_chunk.count('!') + test_chunk.count('?')
            if sentence_markers >= 2 and len(test_chunk) > 100:
                should_break = True
            
            if should_break:
                if current_chunk:
                    # Add the current chunk before breaking
                    final_chunk = current_chunk + (". " + sentence if current_chunk else sentence)
                    chunks.append(final_chunk.strip())
                    current_chunk = ""
                else:
                    # Single sentence is too long, add it as is
                    chunks.append(sentence.strip())
            else:
                current_chunk = test_chunk
        
        # Add any remaining chunk
        if current_chunk and current_chunk.strip():
            chunks.append(current_chunk.strip())
        
        # Post-process chunks to handle very short ones
        final_chunks = []
        i = 0
        while i < len(chunks):
            chunk = chunks[i]
            
            # If chunk is very short (< 30 chars) and not the last one, try to merge with next
            if len(chunk) < 30 and i < len(chunks) - 1:
                next_chunk = chunks[i + 1]
                merged = chunk + ". " + next_chunk
                
                # Only merge if the result is still reasonable length
                if len(merged) <= 180 and len(merged.split()) <= 25:
                    final_chunks.append(merged)
                    i += 2  # Skip the next chunk since we merged it
                    continue
            
            final_chunks.append(chunk)
            i += 1
        
        return final_chunks if final_chunks else [text.strip()]

    def get_file_info(self, filename: str):
        """Get info for generated voiceover file."""
        try:
            file_path = os.path.join(self.output_folder, filename)
            if not os.path.exists(file_path):
                return None
            size = os.path.getsize(file_path)
            ext = os.path.splitext(filename)[1].lower().lstrip('.')
            info = {
                'filename': filename,
                'size_bytes': size,
                'format': ext,
                'duration': None
            }
            try:
                info['duration'] = self._get_audio_duration(file_path)
            except Exception:
                info['duration'] = None
            return info
        except Exception:
            return None

    def _safe_rmtree(self, path: str):
        """Safe recursive directory removal."""
        try:
            if path and os.path.exists(path):
                shutil.rmtree(path, ignore_errors=True)
        except Exception:
            pass