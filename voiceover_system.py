import os
import tempfile
from openai import OpenAI
import subprocess
import uuid
from pathlib import Path
import json
import shutil

# Removed unused Flask app and request imports to keep this module framework-agnostic

class VoiceoverSystem:
    def __init__(self):
        # Initialize OpenAI client for Text-to-Speech
        api_key = os.getenv('OPENAI_API_KEY')
        if (api_key):
            self.openai_client = OpenAI(api_key=api_key)
        else:
            self.openai_client = None
        
        # Configure paths
        self.output_folder = os.getenv('VOICEOVER_FOLDER', 'voiceovers')
        os.makedirs(self.output_folder, exist_ok=True)
        
        # Voice settings
        self.available_voices = ['alloy', 'echo', 'fable', 'onyx', 'nova', 'shimmer']
        self.supported_formats = ['mp3', 'wav', 'mp4']
        
        # Video generation settings
        self.video_width = int(os.getenv('VIDEO_WIDTH', 1920))
        self.video_height = int(os.getenv('VIDEO_HEIGHT', 1080))
        self.video_fps = int(os.getenv('VIDEO_FPS', 30))
        # New: Optional text overlay on waveform videos
        self.text_overlay_enabled = os.getenv('VOICEOVER_TEXT_OVERLAY', 'true').lower() == 'true'
        self.text_overlay_font_path = os.getenv('VOICEOVER_FONT_PATH', '')
        self.text_overlay_max_chars = int(os.getenv('VOICEOVER_TEXT_OVERLAY_MAX_CHARS', 120))
        
        # TTS request constraints
        self.max_input_chars = int(os.getenv('VOICEOVER_MAX_INPUT_CHARS', 3900))  # keep under API 4096
        self.pause_marker_primary = '— pause —'  # em-dash separators from UI
        self.pause_marker_fallback = '-- pause --'
        self.pause_silence_seconds = float(os.getenv('VOICEOVER_PAUSE_SECONDS', 0.6))
        
    def generate_speech(self, text, voice='nova', speed=1.0, format='mp3', session_id=None, background_image_path=None):
        """Generate speech from text using OpenAI TTS. If format is mp4 and background_image_path is provided, create a video using the image.
        Now supports auto-chunking for long scripts and concatenation.
        """
        if not self.openai_client:
            raise Exception("OpenAI client not configured. Please set OPENAI_API_KEY environment variable.")
        
        if voice not in self.available_voices:
            raise Exception(f"Voice '{voice}' not supported. Available voices: {', '.join(self.available_voices)}")
        
        if format not in self.supported_formats:
            raise Exception(f"Format '{format}' not supported. Available formats: {', '.join(self.supported_formats)}")
        
        try:
            # Generate unique file base
            file_id = str(uuid.uuid4())
            if session_id:
                file_id = f"{session_id}_{file_id}"
            
            # Ensure work dir for temp artifacts
            work_dir = tempfile.mkdtemp(prefix="voiceover_")
            
            # Split text into API-safe segments, preserving pauses
            segments = self._split_text_for_tts(text, self.max_input_chars)
            
            # Helper: ensure output in MP3 first, then convert if needed
            def finalize_output_from_mp3(source_mp3_path: str):
                if format == 'mp4':
                    video_path = self._create_video_with_audio(source_mp3_path, file_id, text, background_image_path=background_image_path)
                    final_path = os.path.join(self.output_folder, os.path.basename(video_path))
                    if video_path != final_path:
                        os.replace(video_path, final_path)
                    return final_path, 'mp4'
                elif format == 'wav':
                    final_wav = os.path.join(self.output_folder, f"{file_id}.wav")
                    self._convert_audio_format(source_mp3_path, final_wav, 'wav')
                    return final_wav, 'wav'
                else:
                    final_mp3 = os.path.join(self.output_folder, f"{file_id}.mp3")
                    if os.path.abspath(source_mp3_path) != os.path.abspath(final_mp3):
                        os.replace(source_mp3_path, final_mp3)
                    return final_mp3, 'mp3'
            
            # If only a single text segment, synthesize once
            if len(segments) == 1 and segments[0]['type'] == 'text':
                temp_mp3 = os.path.join(work_dir, f"{file_id}.mp3")
                self._tts_request_to_file(segments[0]['content'], voice=voice, speed=speed, out_path=temp_mp3)
                final_path, final_fmt = finalize_output_from_mp3(temp_mp3)
                self._safe_rmtree(work_dir)
                return {
                    'success': True,
                    'file_path': final_path,
                    'file_url': f"/download-voiceover/{os.path.basename(final_path)}",
                    'format': final_fmt,
                    'duration': self._get_audio_duration(final_path)
                }
            
            # Multi-segment synthesis -> produce MP3 segments including silence as MP3
            part_paths = []
            for seg in segments:
                if seg['type'] == 'pause':
                    silence_mp3 = os.path.join(work_dir, f"silence_{len(part_paths)}.mp3")
                    self._generate_silence(silence_mp3, self.pause_silence_seconds, target_format='mp3')
                    part_paths.append(silence_mp3)
                else:
                    seg_mp3 = os.path.join(work_dir, f"seg_{len(part_paths)}.mp3")
                    self._tts_request_to_file(seg['content'], voice=voice, speed=speed, out_path=seg_mp3)
                    part_paths.append(seg_mp3)
            
            # Concatenate MP3 parts
            joined_mp3 = os.path.join(work_dir, f"{file_id}_joined.mp3")
            self._concat_audio_files(part_paths, joined_mp3, target_format='mp3')
            
            final_path, final_fmt = finalize_output_from_mp3(joined_mp3)
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
            raise Exception(f"Failed to generate voiceover: {str(e)}")
    
    def _tts_request_to_file(self, text, voice, speed, out_path):
        """Issue a single streaming TTS request to OpenAI and write the MP3 to out_path."""
        client = self.openai_client
        if client is None:
            raise Exception("OpenAI client not configured. Please set OPENAI_API_KEY environment variable.")
        # Use streaming response to write directly to file
        with client.audio.speech.with_streaming_response.create(
            model="tts-1-hd",
            voice=voice,
            input=text,
            speed=speed,
        ) as response:
            response.stream_to_file(out_path)
    
    def _split_text_for_tts(self, text: str, max_chars: int):
        """Split text into a list of segments under max_chars.
        Returns a list of dicts with {'type': 'text'|'pause', 'content'?: str}.
        Respects explicit pause markers and prefers paragraph/sentence boundaries.
        """
        if not text:
            return [{'type': 'text', 'content': ''}]
        
        # Normalize line endings and trim
        t = text.replace('\r\n', '\n').strip()
        
        # Split on explicit pause markers, preserving them
        parts = []
        idx = 0
        while idx < len(t):
            # Find next marker
            next_primary = t.find(self.pause_marker_primary, idx)
            next_fallback = t.find(self.pause_marker_fallback, idx)
            candidates = [i for i in [next_primary, next_fallback] if i != -1]
            next_idx = min(candidates) if candidates else -1
            if next_idx == -1:
                parts.append({'type': 'text', 'content': t[idx:]})
                break
            # Leading text
            if next_idx > idx:
                parts.append({'type': 'text', 'content': t[idx:next_idx]})
            # Add a pause token
            parts.append({'type': 'pause'})
            # Advance past the marker
            if next_idx == next_primary:
                idx = next_idx + len(self.pause_marker_primary)
            else:
                idx = next_idx + len(self.pause_marker_fallback)
        
        # Now ensure each text chunk is <= max_chars using paragraph and sentence splits
        def split_chunk(chunk_text: str):
            chunk_text = (chunk_text or '').strip()
            if not chunk_text:
                return []
            if len(chunk_text) <= max_chars:
                return [chunk_text]
            # Prefer paragraph boundaries
            paras = [p.strip() for p in chunk_text.split('\n\n') if p.strip()]
            current = ''
            chunks = []
            for p in paras:
                if len(p) > max_chars:
                    # Split paragraph by sentences
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
                            # Hard wrap long sentence
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
        
        # Collapse leading/trailing/multiple pauses
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
    
    def _create_video_with_audio(self, audio_path, file_id, text, background_image_path=None):
        """Create video from audio. If background_image_path is provided, create a static-image video; otherwise, create a waveform visualization."""
        try:
            video_filename = f"{file_id}.mp4"
            video_path = os.path.join(self.output_folder, video_filename)
            
            # Get audio duration for video length
            duration = self._get_audio_duration(audio_path)
            
            if background_image_path and os.path.exists(background_image_path):
                # Create a video using a static background image, scaled and padded to target size
                vf_filters = (
                    f"scale={self.video_width}:{self.video_height}:force_original_aspect_ratio=decrease,"
                    f"pad={self.video_width}:{self.video_height}:(ow-iw)/2:(oh-ih)/2"
                )
                ffmpeg_cmd = [
                    'ffmpeg', '-y',
                    '-loop', '1',
                    '-i', background_image_path,
                    '-i', audio_path,
                    '-vf', vf_filters,
                    '-t', str(duration),
                    '-r', str(self.video_fps),
                    '-c:v', 'libx264',
                    '-pix_fmt', 'yuv420p',
                    '-c:a', 'aac',
                    '-shortest',
                    video_path
                ]
                result = subprocess.run(ffmpeg_cmd, capture_output=True, text=True)
                if result.returncode != 0:
                    print(f"Static image video generation failed, falling back. stderr: {result.stderr}")
                    # Fallback to waveform method (use temp path then move)
                    temp_video = os.path.join(tempfile.gettempdir(), f"{uuid.uuid4()}.mp4")
                    temp_path = self._create_waveform_video(audio_path, temp_video, duration, text)
                    os.replace(temp_path, video_path)
            else:
                # No background image; create waveform visualization (to final path)
                self._create_waveform_video(audio_path, video_path, duration, text)
            
            if not os.path.exists(video_path):
                raise Exception("Video file was not created")
            
            return video_path
            
        except Exception as e:
            print(f"Error creating video: {str(e)}")
            # Fallback: simple solid color video
            return self._create_simple_video(audio_path, os.path.join(self.output_folder, f"{file_id}.mp4"), duration)
    
    def _create_waveform_video(self, audio_path, video_path, duration, text):
        """Create a video with waveform visualization and optional text overlay using ffmpeg."""
        try:
            # Prepare optional drawtext overlay if enabled and text is provided
            overlay_label_in = 'bg'
            filter_complex = (
                f"[1:a]showwaves=s={self.video_width}x{int(self.video_height*0.3)}:mode=line:colors=white@0.8[waveform];"
                f"[0:v][waveform]overlay=(W-w)/2:(H-h)/2[bg]"
            )

            apply_text = self.text_overlay_enabled and isinstance(text, str) and text.strip()
            if apply_text:
                short_text = text.strip().replace('\n', ' ')
                if len(short_text) > self.text_overlay_max_chars:
                    short_text = short_text[:self.text_overlay_max_chars].rstrip() + '…'
                short_text = self._escape_text_for_ffmpeg(short_text)
                # Choose font option
                font_part = ''
                if self.text_overlay_font_path:
                    font_part = f":fontfile={self.text_overlay_font_path}"
                # Draw text near top center with boxed background
                filter_complex = (
                    filter_complex +
                    f";[bg]drawtext=text='{short_text}'{font_part}:fontcolor=white:fontsize={int(self.video_height*0.035)}:"
                    f"x=(w-text_w)/2:y=H*0.08:box=1:boxcolor=0x000000@0.5:boxborderw=12[out]"
                )
                overlay_label_out = 'out'
            else:
                overlay_label_out = 'bg'

            ffmpeg_cmd = [
                'ffmpeg', '-y',
                '-f', 'lavfi',
                '-i', f'color=c=0x1e3c72:size={self.video_width}x{self.video_height}:duration={duration}',
                '-i', audio_path,
                '-filter_complex', filter_complex,
                '-map', f'[{overlay_label_out}]',
                '-map', '1:a',
                '-c:v', 'libx264',
                '-c:a', 'aac',
                '-shortest',
                video_path
            ]
            result = subprocess.run(ffmpeg_cmd, capture_output=True, text=True)
            if result.returncode != 0:
                print(f"Waveform video generation failed, using simple video. stderr: {result.stderr}")
                return self._create_simple_video(audio_path, video_path, duration)
            return video_path
        except Exception as e:
            print(f"Waveform video creation error: {str(e)}")
            return self._create_simple_video(audio_path, video_path, duration)
    
    def _create_simple_video(self, audio_path, video_path, duration):
        """Create a simple video with static background and audio"""
        try:
            ffmpeg_cmd = [
                'ffmpeg', '-y',
                '-f', 'lavfi',
                '-i', f'color=c=0x1e3c72:size={self.video_width}x{self.video_height}:duration={duration}',
                '-i', audio_path,
                '-c:v', 'libx264',
                '-c:a', 'aac',
                '-shortest',
                video_path
            ]
            
            subprocess.run(ffmpeg_cmd, check=True, capture_output=True)
            return video_path
            
        except Exception as e:
            print(f"Simple video creation also failed: {str(e)}")
            raise Exception("Failed to create video file")
    
    def _convert_audio_format(self, input_path, output_path, target_format):
        """Convert audio file to different format using ffmpeg"""
        try:
            ffmpeg_cmd = [
                'ffmpeg', '-y',
                '-i', input_path,
                '-c:a', 'pcm_s16le' if target_format == 'wav' else 'libmp3lame',
                output_path
            ]
            
            subprocess.run(ffmpeg_cmd, check=True, capture_output=True)
            
        except Exception as e:
            raise Exception(f"Failed to convert audio format: {str(e)}")
    
    def _concat_audio_files(self, input_paths, output_path, target_format='mp3'):
        """Concatenate multiple audio files and re-encode to target format for robustness."""
        if not input_paths:
            raise Exception("No audio segments to concatenate")
        # Build concat list file
        with tempfile.NamedTemporaryFile('w', delete=False, suffix='.txt') as list_file:
            list_path = list_file.name
            for p in input_paths:
                # ffmpeg concat demuxer requires file paths quoted
                list_file.write(f"file '{os.path.abspath(p)}'\n")
        try:
            codec = 'libmp3lame' if target_format == 'mp3' else 'pcm_s16le'
            ffmpeg_cmd = [
                'ffmpeg', '-y',
                '-f', 'concat', '-safe', '0', '-i', list_path,
                '-c:a', codec,
                output_path
            ]
            result = subprocess.run(ffmpeg_cmd, capture_output=True, text=True)
            if result.returncode != 0:
                # Fallback: decode pipeline concat
                joined_tmp = os.path.join(tempfile.gettempdir(), f"joined_{uuid.uuid4()}.{target_format}")
                alt_cmd = ['ffmpeg', '-y']
                for p in input_paths:
                    alt_cmd.extend(['-i', p])
                alt_cmd.extend(['-filter_complex', f"concat=n={len(input_paths)}:v=0:a=1", '-c:a', codec, joined_tmp])
                result2 = subprocess.run(alt_cmd, capture_output=True, text=True)
                if result2.returncode != 0:
                    raise Exception(f"Audio concat failed: {result.stderr}\n{result2.stderr}")
                os.replace(joined_tmp, output_path)
        finally:
            try:
                os.remove(list_path)
            except Exception:
                pass
    
    def _generate_silence(self, output_path, seconds: float, target_format: str = 'mp3'):
        """Generate a silent audio clip of the given duration in the desired format."""
        try:
            codec = 'libmp3lame' if target_format == 'mp3' else 'pcm_s16le'
            ext = 'mp3' if target_format == 'mp3' else 'wav'
            if not output_path.endswith(f'.{ext}'):
                output_path = f"{output_path}.{ext}"
            ffmpeg_cmd = [
                'ffmpeg', '-y',
                '-f', 'lavfi',
                '-i', f"anullsrc=r=44100:cl=mono", '-t', str(max(0.1, seconds)),
                '-c:a', codec,
                output_path
            ]
            subprocess.run(ffmpeg_cmd, check=True, capture_output=True)
        except Exception as e:
            # If silence generation fails, create a minimal 0.1s clip
            try:
                fallback_codec = 'libmp3lame' if target_format == 'mp3' else 'pcm_s16le'
                fallback_cmd = [
                    'ffmpeg', '-y',
                    '-f', 'lavfi',
                    '-i', f"anullsrc=r=44100:cl=mono", '-t', '0.1',
                    '-c:a', fallback_codec,
                    output_path
                ]
                subprocess.run(fallback_cmd, check=True, capture_output=True)
            except Exception:
                # As last resort, skip silence
                pass
    
    def _get_audio_duration(self, audio_path):
        """Get duration of audio or video file in seconds"""
        try:
            ffprobe_cmd = [
                'ffprobe', '-v', 'quiet',
                '-print_format', 'json',
                '-show_entries', 'format=duration',
                audio_path
            ]
            
            result = subprocess.run(ffprobe_cmd, capture_output=True, text=True)
            
            if result.returncode == 0:
                data = json.loads(result.stdout)
                return float(data['format']['duration'])
            else:
                return 30.0  # Default duration if detection fails
                
        except Exception as e:
            print(f"Error getting audio duration: {str(e)}")
            return 30.0  # Default duration
    
    def _escape_text_for_ffmpeg(self, text):
        """Escape text for safe use in ffmpeg drawtext filter"""
        # Replace problematic characters for ffmpeg drawtext when using single-quoted text value.
        if text is None:
            return ''
        s = str(text)
        # Normalize whitespace
        s = s.replace('\r\n', ' ').replace('\n', ' ').strip()
        # Escape backslash first
        s = s.replace('\\', r'\\')
        # Escape special characters per drawtext: ':', "'", '%', '[', ']' and comma occasionally
        s = s.replace(':', r'\:')
        s = s.replace("'", r"\'")
        s = s.replace('%', r'\%')
        s = s.replace('[', r'\[').replace(']', r'\]')
        s = s.replace(',', r'\,')
        return s

    def _safe_rmtree(self, path: str):
        """Safely remove a directory tree, ignoring errors."""
        try:
            if path and os.path.isdir(path):
                shutil.rmtree(path, ignore_errors=True)
        except Exception:
            pass

    def get_file_info(self, filename: str):
        """Return basic info for a generated voiceover file used by the download route."""
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