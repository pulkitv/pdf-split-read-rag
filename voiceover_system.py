import os
import tempfile
from openai import OpenAI
import subprocess
import uuid
from pathlib import Path
import json
import shutil
import re

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
        # New: explicit font size and side margin for on-video captions
        self.text_overlay_fontsize_px = int(os.getenv('VOICEOVER_OVERLAY_FONTSIZE', 24))
        self.text_overlay_side_margin_px = int(os.getenv('VOICEOVER_TEXT_MARGIN', max(40, int(self.video_width * 0.05))))
        
        # TTS request constraints
        self.max_input_chars = int(os.getenv('VOICEOVER_MAX_INPUT_CHARS', 3900))  # keep under API 4096
        self.pause_marker_primary = '— pause —'  # em-dash separators from UI
        self.pause_marker_fallback = '-- pause --'
        self.pause_silence_seconds = float(os.getenv('VOICEOVER_PAUSE_SECONDS', 0.6))
        
    def generate_speech(self, text, voice='nova', speed=1.0, format='mp3', session_id=None, background_image_path=None):
        """Generate speech from text using OpenAI TTS. If format is mp4 and background_image_path is provided, create a video using the image.
        Now supports auto-chunking for long scripts and concatenation.
        Adds dynamic on-video captions that sync to speech segments.
        """
        # Generate unique file base
        file_id = str(uuid.uuid4())
        if session_id:
            file_id = f"{session_id}_{file_id}"
        work_dir = tempfile.mkdtemp(prefix="voiceover_")
        segments = self._split_text_for_tts(text, self.max_input_chars)

        # Helper: finalize to desired output from an MP3 and optional captions
        def finalize_output_from_mp3(source_mp3_path: str, captions=None):
            if format == 'mp4':
                video_path = self._create_video_with_audio(
                    source_mp3_path,
                    file_id,
                    text,
                    background_image_path=background_image_path,
                    captions=captions,
                )
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

        try:
            # Single segment -> synthesize once and build captions by sentence
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

            # Multi-segment synthesis -> produce MP3 segments including silence; capture timings per segment
            parts = []  # list of {type: 'text'|'pause', 'path': str, 'text'?: str, 'duration': float}
            for seg in segments:
                if seg['type'] == 'pause':
                    silence_mp3 = os.path.join(work_dir, f"silence_{len(parts)}.mp3")
                    self._generate_silence(silence_mp3, self.pause_silence_seconds, target_format='mp3')
                    parts.append({'type': 'pause', 'path': silence_mp3, 'duration': None})
                else:
                    seg_mp3 = os.path.join(work_dir, f"seg_{len(parts)}.mp3")
                    self._tts_request_to_file(seg['content'], voice=voice, speed=speed, out_path=seg_mp3)
                    parts.append({'type': 'text', 'path': seg_mp3, 'text': seg['content'], 'duration': None})

            # Compute durations and captions
            for p in parts:
                p['duration'] = self._get_audio_duration(p['path'])
            captions = []
            t = 0.0
            for p in parts:
                if p['type'] == 'pause':
                    t += p['duration']
                else:
                    start = t
                    end = t + p['duration']
                    captions.append({'text': p['text'], 'start': start, 'end': end})
                    t = end

            # Concatenate MP3 parts
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

    def _tts_request_to_file(self, text, voice, speed, out_path):
        """Issue a TTS request to OpenAI and write MP3 bytes to out_path.
        Supports both newer clients with streaming API and older clients without it.
        """
        client = self.openai_client
        if client is None:
            raise Exception("OpenAI client not configured. Please set OPENAI_API_KEY environment variable.")

        # Prefer streaming API if available
        try:
            ws = getattr(getattr(client, 'audio').speech, 'with_streaming_response', None)
            if ws is not None:
                try:
                    with client.audio.speech.with_streaming_response.create(
                        model="tts-1-hd",
                        voice=voice,
                        input=text,
                        speed=speed,
                    ) as response:
                        response.stream_to_file(out_path)
                        return
                except AttributeError:
                    # Older client without streaming support
                    pass
                except Exception as e:
                    # Fallback to non-streaming on any runtime streaming failure
                    print(f"TTS streaming failed, falling back to non-streaming: {e}")
        except Exception:
            # If feature detection above fails, fall back to non-streaming path
            pass

        # Non-streaming fallback compatible with older SDKs
        resp = client.audio.speech.create(
            model="tts-1-hd",
            voice=voice,
            input=text,
            speed=speed,
        )

        # Try common response shapes
        # 1) Object exposes stream_to_file
        if hasattr(resp, 'stream_to_file') and callable(getattr(resp, 'stream_to_file')):
            resp.stream_to_file(out_path)
            return

        # 2) Bytes content attribute
        content = None
        try:
            content = getattr(resp, 'content', None)
        except Exception:
            content = None

        # 3) Raw bytes-like or file-like
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

        # 4) body/data fallback
        if content is None:
            body = getattr(resp, 'body', None) or getattr(resp, 'data', None)
            if isinstance(body, (bytes, bytearray)):
                content = body

        if content is None:
            raise Exception("Unsupported OpenAI TTS response shape for installed 'openai' package. Consider upgrading the 'openai' dependency.")

        with open(out_path, 'wb') as f:
            f.write(content)
    
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
    
    def _create_video_with_audio(self, audio_path, file_id, text, background_image_path=None, captions=None):
        """Create video from audio. If background_image_path is provided, create a static-image video; otherwise, create a waveform visualization.
        If captions are provided, burn timed subtitles that change with speech.
        captions: list of dicts with keys {text, start, end} in seconds.
        """
        try:
            video_filename = f"{file_id}.mp4"
            video_path = os.path.join(self.output_folder, video_filename)
            duration = self._get_audio_duration(audio_path)

            # Normalize captions time range within total duration
            cap_list = []
            if captions:
                for c in captions:
                    s = max(0.0, float(c.get('start', 0.0)))
                    e = min(float(duration), float(c.get('end', duration)))
                    if e > s and isinstance(c.get('text'), str) and c.get('text').strip():
                        cap_list.append({'text': c['text'].strip(), 'start': s, 'end': e})

            if background_image_path and os.path.exists(background_image_path):
                # Build filter graph: [img] scale/pad -> [bg] -> optional timed drawtext chain -> [vout]
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
                    '-loop', '1',
                    '-i', background_image_path,  # 0:v
                    '-i', audio_path,            # 1:a
                    '-filter_complex', filter_complex,
                    '-map', f'[{last_label}]',
                    '-map', '1:a',
                    '-r', str(self.video_fps),
                    '-t', str(duration),
                    '-c:v', 'libx264',
                    '-pix_fmt', 'yuv420p',
                    '-c:a', 'aac',
                    '-shortest',
                    video_path
                ]
                result = subprocess.run(ffmpeg_cmd, capture_output=True, text=True)
                if result.returncode != 0:
                    print(f"Static image video generation failed, stderr: {result.stderr}")
                    # Fallback to waveform
                    temp_video = os.path.join(tempfile.gettempdir(), f"{uuid.uuid4()}.mp4")
                    temp_path = self._create_waveform_video(audio_path, temp_video, duration, text, captions=cap_list)
                    os.replace(temp_path, video_path)
            else:
                # Waveform visualization to final path
                self._create_waveform_video(audio_path, video_path, duration, text, captions=cap_list)

            if not os.path.exists(video_path):
                raise Exception("Video file was not created")
            return video_path
        except Exception as e:
            print(f"Error creating video: {str(e)}")
            return self._create_simple_video(audio_path, os.path.join(self.output_folder, f"{file_id}.mp4"), duration)
    
    def _create_waveform_video(self, audio_path, video_path, duration, text, captions=None):
        """Create a video with waveform visualization and optional dynamic captions using ffmpeg."""
        try:
            # Base: colored background + waveform overlay
            filter_parts = [
                f"[1:a]showwaves=s={self.video_width}x{int(self.video_height*0.3)}:mode=line:colors=white@0.8[waveform]",
                f"[0:v][waveform]overlay=(W-w)/2:(H-h)/2[bg]"
            ]
            last_label = 'bg'

            # Add timed captions if provided
            if captions:
                timed_chain, last_label = self._build_timed_drawtext_chain(last_label, captions)
                filter_parts.append(timed_chain)

            filter_complex = ';'.join(filter_parts)
            ffmpeg_cmd = [
                'ffmpeg', '-y',
                '-f', 'lavfi',
                '-i', f'color=c=0x1e3c72:size={self.video_width}x{self.video_height}:duration={duration}',  # 0:v
                '-i', audio_path,  # 1:a
                '-filter_complex', filter_complex,
                '-map', f'[{last_label}]',
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
        """Escape text for safe use in ffmpeg drawtext while preserving newlines for wrapping"""
        if text is None:
            return ''
        s = str(text)
        # Preserve newlines for drawtext (used to wrap text), normalize CRLF
        s = s.replace('\r\n', '\n').strip()
        # Escape backslash first
        s = s.replace('\\', r'\\')
        # Escape characters significant to drawtext parsing
        s = s.replace(':', r'\:')
        s = s.replace("'", r"\'")
        s = s.replace('%', r'\%')
        s = s.replace('[', r'\[').replace(']', r'\]')
        # Do NOT replace '\n'
        return s

    def _escape_path_for_ffmpeg(self, path: str):
        """Escape a filesystem path for use in drawtext fontfile option."""
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
        """Naive word-wrap to ensure text width <= video_width - 2*margin using approx avg char width."""
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
        """Return (filter_str, final_label) that overlays timed drawtext captions on base_label.
        captions: list of {text, start, end}
        """
        label_in = base_label
        chain_parts = []
        for idx, cap in enumerate(captions):
            # Wrap text to fit within margins, then escape
            wrapped = self._wrap_text_for_width(cap.get('text', ''), self.text_overlay_fontsize_px, self.text_overlay_side_margin_px)
            txt = self._escape_text_for_ffmpeg(wrapped)
            start = float(cap.get('start', 0.0))
            end = float(cap.get('end', start + 1.0))
            label_out = f"cap{idx}"
            font_part = ''
            if self.text_overlay_font_path:
                font_part = f":fontfile={self._escape_path_for_ffmpeg(self.text_overlay_font_path)}"
            chain_parts.append(
                f"[{label_in}]drawtext=text='{txt}'{font_part}:fontcolor=white:fontsize={self.text_overlay_fontsize_px}:"
                f"x=(w-text_w)/2:y=(h-text_h)/2:box=1:boxcolor=0x000000@0.5:boxborderw=12:"
                f"line_spacing={int(self.text_overlay_fontsize_px*0.35)}:shadowcolor=0x000000@0.6:shadowx=2:shadowy=2:fix_bounds=1:"
                f"enable='between(t,{start:.3f},{end:.3f})'[{label_out}]"
            )
            label_in = label_out
        return (';'.join(chain_parts) if chain_parts else '', label_in)

    def _make_captions_from_text(self, text: str, total_duration: float):
        """Split text into readable chunks and distribute total_duration proportionally.
        Returns list of {text, start, end}.
        """
        s = (text or '').strip()
        if not s:
            return []
        # Sentence split; if only one, try commas; fallback to fixed-size chunks
        sentences = [t.strip() for t in re.split(r'(?<=[\.\?!])\s+', s) if t.strip()]
        if len(sentences) == 1:
            sentences = [t.strip() for t in re.split(r',\s+', s) if t.strip()]
        if len(sentences) == 1 and len(s) > 120:
            # Hard wrap every ~100 chars
            sentences = [s[i:i+100].strip() for i in range(0, len(s), 100)]
        # Compute weights
        lengths = [max(1, len(t)) for t in sentences]
        total_len = sum(lengths)
        # Initial proportional durations with a minimum
        min_d = 0.6
        raw = [total_duration * (L/total_len) for L in lengths]
        adj = [max(min_d, r) for r in raw]
        # Normalize to total_duration
        scale = total_duration / max(1e-6, sum(adj))
        adj = [a*scale for a in adj]
        # Build timeline
        t = 0.0
        caps = []
        for i, sent in enumerate(sentences):
            start = t
            end = t + adj[i]
            caps.append({'text': sent, 'start': start, 'end': end})
            t = end
        # Clip to total_duration
        for c in caps:
            c['start'] = max(0.0, min(c['start'], total_duration))
            c['end'] = max(c['start'] + 0.1, min(c['end'], total_duration))
        return caps

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

    def _safe_rmtree(self, path: str):
        """Best-effort recursive directory removal without raising."""
        try:
            if path and os.path.exists(path):
                shutil.rmtree(path, ignore_errors=True)
        except Exception:
            pass