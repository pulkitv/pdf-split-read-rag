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
        
        # Background Video Configuration
        self.background_video_enabled = os.getenv('BACKGROUND_VIDEO_ENABLED', 'false').lower() == 'true'
        
        # Support both folder-based (multiple videos) and single file configurations
        self.shorts_background_folder = os.getenv('SHORTS_BACKGROUND_FOLDER', 'backgrounds/shorts')
        self.regular_background_folder = os.getenv('REGULAR_BACKGROUND_FOLDER', 'backgrounds/regular')
        
        # Legacy single file support (fallback)
        self.shorts_background_video = os.getenv('SHORTS_BACKGROUND_VIDEO', 'shorts_background.mp4')
        self.regular_background_video = os.getenv('REGULAR_BACKGROUND_VIDEO', 'regular_background.mp4')
        
        self.background_video_fallback = os.getenv('BACKGROUND_VIDEO_FALLBACK', 'waveform')
        
        # Validate background video files/folders exist if enabled
        if self.background_video_enabled:
            self._validate_background_videos()
        
        # FFmpeg Quality Settings (Optimized for High Quality)
        self.video_preset = os.getenv('VIDEO_PRESET', 'slow')  # slow = better quality, slower encoding
        self.video_crf = int(os.getenv('VIDEO_CRF', '18'))  # 18 = visually lossless (0-51, lower=better)
        self.audio_bitrate = os.getenv('AUDIO_BITRATE', '256k')  # High quality audio
        self.audio_sample_rate = int(os.getenv('AUDIO_SAMPLE_RATE', 48000))  # 48kHz for professional quality
        
        # Video encoding profile settings
        self.video_profile = os.getenv('VIDEO_PROFILE', 'high')  # high, main, baseline
        self.video_level = os.getenv('VIDEO_LEVEL', '4.2')  # H.264 level
        self.video_tune = os.getenv('VIDEO_TUNE', 'animation')  # animation for text/graphics, film for video
        
        # Text overlay settings
        self.text_overlay_enabled = os.getenv('VOICEOVER_TEXT_OVERLAY', 'true').lower() == 'true'
        self.text_overlay_font_path = os.getenv('VOICEOVER_FONT_PATH', '')
        self.text_overlay_max_chars = int(os.getenv('VOICEOVER_TEXT_OVERLAY_MAX_CHARS', 120))
        self.text_overlay_fontsize_px = int(os.getenv('VOICEOVER_OVERLAY_FONTSIZE', 50))
        self.text_overlay_side_margin_px = int(os.getenv('VOICEOVER_TEXT_MARGIN', 20))
        
        # TTS request constraints
        self.max_input_chars = int(os.getenv('VOICEOVER_MAX_INPUT_CHARS', 3900))
        self.pause_marker_primary = '— pause —'
        self.pause_marker_fallback = '-- pause --'
        self.pause_silence_seconds = float(os.getenv('VOICEOVER_PAUSE_DURATION', 1.5))
        self.pause_enabled = os.getenv('VOICEOVER_ENABLE_PAUSES', 'true').lower() == 'true'

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
    
    def _validate_background_videos(self):
        """Validate that background video files/folders exist and are accessible."""
        validation_errors = []
        validation_warnings = []
        
        # Check shorts background (folder or file)
        shorts_videos = self._get_background_videos_from_folder(self.shorts_background_folder)
        if not shorts_videos:
            # Try legacy single file
            if os.path.exists(self.shorts_background_video):
                validation_warnings.append(f"Using legacy single shorts background: {self.shorts_background_video}")
            else:
                validation_errors.append(f"Shorts background not found. Checked folder: {self.shorts_background_folder} and file: {self.shorts_background_video}")
        else:
            print(f"✓ Found {len(shorts_videos)} shorts background videos in: {self.shorts_background_folder}")
        
        # Check regular background (folder or file)
        regular_videos = self._get_background_videos_from_folder(self.regular_background_folder)
        if not regular_videos:
            # Try legacy single file
            if os.path.exists(self.regular_background_video):
                validation_warnings.append(f"Using legacy single regular background: {self.regular_background_video}")
            else:
                validation_errors.append(f"Regular background not found. Checked folder: {self.regular_background_folder} and file: {self.regular_background_video}")
        else:
            print(f"✓ Found {len(regular_videos)} regular background videos in: {self.regular_background_folder}")
        
        # Display warnings
        if validation_warnings:
            for warning in validation_warnings:
                print(f"⚠️  WARNING: {warning}")
        
        # Handle errors
        if validation_errors:
            error_message = "Background video validation failed:\n" + "\n".join(f"  - {error}" for error in validation_errors)
            print(f"WARNING: {error_message}")
            print(f"Falling back to {self.background_video_fallback} mode")
            # Disable background video if files are missing
            self.background_video_enabled = False
        else:
            print(f"✓ Background videos validated successfully")
    
    def _get_background_videos_from_folder(self, folder_path):
        """
        Get list of video files from a folder.
        
        Args:
            folder_path: Path to folder containing background videos
        
        Returns:
            list: List of full paths to video files, empty list if folder doesn't exist
        """
        if not os.path.exists(folder_path) or not os.path.isdir(folder_path):
            return []
        
        # Supported video extensions
        video_extensions = {'.mp4', '.mov', '.avi', '.mkv', '.webm', '.flv'}
        
        video_files = []
        try:
            for filename in os.listdir(folder_path):
                file_path = os.path.join(folder_path, filename)
                # Check if it's a file and has a video extension
                if os.path.isfile(file_path):
                    _, ext = os.path.splitext(filename)
                    if ext.lower() in video_extensions:
                        video_files.append(file_path)
        except Exception as e:
            print(f"Error reading folder {folder_path}: {str(e)}")
            return []
        
        return sorted(video_files)  # Sort for consistency
    
    def get_background_video_path(self, generation_type='youtube_shorts'):
        """
        Get a random background video path based on generation type.
        
        Args:
            generation_type: 'regular' or 'standalone' for landscape,
                           'shorts' or 'youtube_shorts' for portrait
        
        Returns:
            str: Path to randomly selected background video file, or None if disabled/not found
        """
        if not self.background_video_enabled:
            return None
        
        import random
        
        # Determine which folder/file to use based on generation type
        if generation_type in ['shorts', 'youtube_shorts']:
            folder_path = self.shorts_background_folder
            fallback_file = self.shorts_background_video
            video_type = "Shorts"
        else:  # 'regular' or 'standalone'
            folder_path = self.regular_background_folder
            fallback_file = self.regular_background_video
            video_type = "Regular"
        
        # Try to get videos from folder first
        available_videos = self._get_background_videos_from_folder(folder_path)
        
        if available_videos:
            # Randomly select a video from the folder
            selected_video = random.choice(available_videos)
            print(f"📹 Randomly selected {video_type} background: {os.path.basename(selected_video)} (from {len(available_videos)} available)")
            return selected_video
        
        # Fallback to legacy single file
        if os.path.exists(fallback_file):
            print(f"📹 Using legacy {video_type} background: {fallback_file}")
            return fallback_file
        
        # No background video found
        print(f"WARNING: No {video_type} background video found")
        return None
        
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
    
    def _preprocess_text_for_tts(self, text):
        """Preprocess text to make it more TTS-friendly by converting symbols to words."""
        if not text:
            return text
        
        # Convert % symbol to "percent" for better TTS pronunciation and display
        processed_text = text.replace('%', ' percent')
        
        # Clean up any double spaces that might have been created
        processed_text = ' '.join(processed_text.split())
        
        return processed_text
    
    def _split_text_into_timed_sections(self, text, duration, max_chars_per_section=120):
        """
        Split text into timed sections that sync with voiceover speed.
        Each section will be displayed proportionally based on word count.
        
        Args:
            text: Full text to split
            duration: Total audio duration in seconds
            max_chars_per_section: Maximum characters per section
        
        Returns:
            list: List of dicts with 'text', 'start', 'end', and 'word_count' times
        """
        if not text or duration <= 0:
            return []
        
        # Clean up the text
        clean_text = text.strip()
        if not clean_text:
            return []
        
        # Split text into sentences first (better for natural breaks)
        sentences = re.split(r'[.!?]+', clean_text)
        sentences = [s.strip() for s in sentences if s.strip()]
        
        if not sentences:
            return []
        
        # Group sentences into sections based on character limit
        sections = []
        current_section = ""
        
        for sentence in sentences:
            # Test if adding this sentence would exceed the limit
            test_section = f"{current_section} {sentence}".strip()
            
            if len(test_section) <= max_chars_per_section:
                current_section = test_section
            else:
                # Save current section if it has content
                if current_section:
                    sections.append(current_section)
                    current_section = sentence
                else:
                    # Single sentence is too long, force add it
                    sections.append(sentence)
                    current_section = ""
        
        # Add the last section if it has content
        if current_section:
            sections.append(current_section)
        
        # If we have no sections, create one from the original text
        if not sections:
            sections = [clean_text[:max_chars_per_section]]
        
        # Count words in each section
        section_word_counts = []
        for section_text in sections:
            word_count = len(section_text.split())
            section_word_counts.append(word_count)
        
        # Calculate total words across all sections
        total_words = sum(section_word_counts)
        
        print(f"📊 Text analysis: {len(sections)} sections, {total_words} total words")
        
        # Calculate timing for each section based on word count proportion
        timed_sections = []
        current_time = 0.0
        
        for i, (section_text, word_count) in enumerate(zip(sections, section_word_counts)):
            # Calculate proportional duration based on word count
            word_ratio = word_count / total_words
            section_duration = duration * word_ratio
            
            start_time = current_time
            end_time = current_time + section_duration
            
            timed_sections.append({
                'text': section_text,
                'start': start_time,
                'end': end_time,
                'word_count': word_count,
                'duration': section_duration
            })
            
            current_time = end_time
        
        # Log the timing breakdown
        print(f"⏱️  Proportional timing breakdown:")
        for i, section in enumerate(timed_sections):
            words_per_second = section['word_count'] / section['duration'] if section['duration'] > 0 else 0
            print(f"  Section {i+1}: {section['start']:.1f}s-{section['end']:.1f}s | "
                  f"{section['word_count']} words | {section['duration']:.1f}s | "
                  f"{words_per_second:.1f} words/sec")
        
        return timed_sections

    def _build_timed_drawtext_chain(self, input_label, captions):
        """Build FFmpeg drawtext filter chain with timed captions and proper text wrapping."""
        if not captions:
            return "", input_label
        
        # Wrap text to fit video width
        def wrap_text_for_video(text, max_chars_per_line):
            """
            Wrap text to fit within video width with better word breaking.
            """
            if len(text) <= max_chars_per_line:
                return [text]
            
            words = text.split()
            lines = []
            current_line = ""
            
            for word in words:
                # Test if adding this word would exceed the limit
                test_line = f"{current_line} {word}".strip()
                
                if len(test_line) <= max_chars_per_line:
                    current_line = test_line
                else:
                    # If current_line has content, save it and start new line
                    if current_line:
                        lines.append(current_line)
                        current_line = word
                    else:
                        # Word itself is too long, force break it
                        current_line = word
            
            # Add the last line if it has content
            if current_line:
                lines.append(current_line)
            
            return lines
        
        # Escape text for FFmpeg drawtext (but NOT newlines)
        def escape_drawtext(s):
            # Escape special characters for FFmpeg drawtext but preserve newlines
            s = s.replace('\\', '\\\\')
            s = s.replace("'", "\\'") 
            s = s.replace(':', '\\:')
            s = s.replace('%', '\\%')
            s = s.replace('[', '\\[')
            s = s.replace(']', '\\]')
            # Don't escape newlines - FFmpeg handles \n directly
            return s
        
        # Font settings
        fontfile = self.text_overlay_font_path if self.text_overlay_font_path else ''
        fontsize = self.text_overlay_fontsize_px
        margin = self.text_overlay_side_margin_px
        
        # Calculate max characters per line based on video dimensions
        # INCREASED: Use less conservative character width estimate for wider text
        char_width_estimate = fontsize * 0.5  # Less conservative (was 0.6)
        available_width = self.video_width - (2 * margin)
        max_chars = max(15, int(available_width / char_width_estimate))
        
        # INCREASED: Allow more characters per line for wider text boxes
        if self.video_width <= 1080:  # Portrait (YouTube Shorts)
            max_chars = min(max_chars, 22)  # INCREASED from 16 to 22
        else:  # Landscape (Regular videos)
            max_chars = min(max_chars, 35)  # INCREASED from 25 to 35
        
        print(f"Text overlay settings: fontsize={fontsize}, max_chars={max_chars}, video={self.video_width}x{self.video_height}")
        
        # Build drawtext filters for each caption
        drawtext_filters = []
        for i, cap in enumerate(captions):
            # Wrap text into multiple lines
            text_lines = wrap_text_for_video(cap['text'], max_chars)
            
            start = cap['start']
            end = cap['end']
            
            # Join lines with actual newline characters (not escaped)
            display_text = '\n'.join([escape_drawtext(line) for line in text_lines])
            
            # Enable expression: show between start and end times
            enable_expr = f"between(t,{start},{end})"
            
            # Build drawtext filter with proper text positioning
            dt_parts = [
                f"text='{display_text}'",
                f"fontsize={fontsize}",
                "fontcolor=white",
                "bordercolor=black", 
                "borderw=3",
                "box=1",
                "boxcolor=black@0.5",
                "boxborderw=15",  # REDUCED padding for more text space (was 20)
                "line_spacing=8",  # REDUCED line spacing for more compact text (was 10)
                f"x=(w-text_w)/2",  # Center horizontally
                f"y=h*0.85-text_h",   # Position near bottom with more margin
                f"enable='{enable_expr}'"
            ]
            
            if fontfile and os.path.exists(fontfile):
                dt_parts.insert(1, f"fontfile='{fontfile}'")
            
            # Build the complete filter
            filter_params = ':'.join(dt_parts)
            full_filter = filter_params
            
            drawtext_filters.append(full_filter)
        
        # Chain all drawtext filters
        current_label = input_label.strip('[]')  # Remove any existing brackets
        filter_chain_parts = []
        
        for i, dt_filter in enumerate(drawtext_filters):
            next_label = f"txt{i}"
            filter_chain_parts.append(f"[{current_label}]drawtext={dt_filter}[{next_label}]")
            current_label = next_label
        
        return ';'.join(filter_chain_parts), f"[{current_label}]"

    def _chunk_text_for_tts(self, text, max_chars=3800):
        """
        Split long text into chunks suitable for TTS API while preserving sentence boundaries.
        
        Args:
            text: Text to split
            max_chars: Maximum characters per chunk (slightly less than API limit for safety)
        
        Returns:
            list: List of text chunks
        """
        if len(text) <= max_chars:
            return [text]
        
        # Split text into sentences for natural boundaries
        sentences = re.split(r'(?<=[.!?])\s+', text)
        
        chunks = []
        current_chunk = ""
        
        for sentence in sentences:
            # Test if adding this sentence would exceed the limit
            test_chunk = f"{current_chunk} {sentence}".strip()
            
            if len(test_chunk) <= max_chars:
                current_chunk = test_chunk
            else:
                # Save current chunk if it has content
                if current_chunk:
                    chunks.append(current_chunk)
                
                # If single sentence is too long, force split it
                if len(sentence) > max_chars:
                    # Split long sentence by words
                    words = sentence.split()
                    word_chunk = ""
                    
                    for word in words:
                        test_word_chunk = f"{word_chunk} {word}".strip()
                        if len(test_word_chunk) <= max_chars:
                            word_chunk = test_word_chunk
                        else:
                            if word_chunk:
                                chunks.append(word_chunk)
                            word_chunk = word
                    
                    if word_chunk:
                        current_chunk = word_chunk
                    else:
                        current_chunk = ""
                else:
                    current_chunk = sentence
        
        # Add the last chunk if it has content
        if current_chunk:
            chunks.append(current_chunk)
        
        return chunks

    def _generate_multiple_audio_chunks(self, text_chunks, voice, speed, session_id):
        """
        Generate multiple audio files from text chunks and combine them.
        
        Args:
            text_chunks: List of text strings to convert
            voice: Voice to use
            speed: Speech speed
            session_id: Session ID for file naming
        
        Returns:
            tuple: (success: bool, combined_audio_path: str, total_duration: float, error_msg: str)
        """
        try:
            print(f"🔊 Generating {len(text_chunks)} audio chunks...")
            
            temp_audio_files = []
            total_duration = 0
            
            # Generate audio for each chunk
            for i, chunk in enumerate(text_chunks):
                print(f"   Generating chunk {i+1}/{len(text_chunks)} ({len(chunk)} chars)...")
                
                chunk_filename = f"{session_id}_chunk_{i+1}.mp3"
                chunk_path = os.path.join(tempfile.gettempdir(), chunk_filename)
                
                try:
                    # Generate TTS for this chunk
                    response = self.openai_client.audio.speech.create(
                        model="tts-1",
                        voice=voice,
                        input=chunk,
                        speed=speed,
                        response_format="mp3"
                    )
                    
                    # Save chunk audio
                    with open(chunk_path, 'wb') as f:
                        f.write(response.content)
                    
                    # Verify file was created
                    if not os.path.exists(chunk_path) or os.path.getsize(chunk_path) == 0:
                        raise Exception(f"Failed to create audio chunk {i+1}")
                    
                    # Get duration of this chunk
                    chunk_duration = self._get_audio_duration(chunk_path)
                    total_duration += chunk_duration
                    
                    temp_audio_files.append(chunk_path)
                    print(f"   ✅ Chunk {i+1} generated: {chunk_duration:.1f}s")
                    
                except Exception as chunk_error:
                    # Cleanup any files created so far
                    for temp_file in temp_audio_files:
                        if os.path.exists(temp_file):
                            os.remove(temp_file)
                    return False, None, 0, f"Failed to generate audio chunk {i+1}: {str(chunk_error)}"
            
            print(f"🔗 Combining {len(temp_audio_files)} audio chunks...")
            
            # Combine audio files using FFmpeg
            combined_filename = f"{session_id}_combined.mp3"
            combined_path = os.path.join(tempfile.gettempdir(), combined_filename)
            
            # Create FFmpeg concat file
            concat_filename = f"{session_id}_concat.txt"
            concat_path = os.path.join(tempfile.gettempdir(), concat_filename)
            
            with open(concat_path, 'w') as f:
                for audio_file in temp_audio_files:
                    # Escape the file path for FFmpeg
                    escaped_path = audio_file.replace('\\', '\\\\').replace("'", "\\'")
                    f.write(f"file '{escaped_path}'\n")
            
            # Combine audio files
            ffmpeg_cmd = [
                'ffmpeg', '-y',
                '-f', 'concat',
                '-safe', '0',
                '-i', concat_path,
                '-c', 'copy',
                combined_path
            ]
            
            result = subprocess.run(ffmpeg_cmd, capture_output=True, text=True)
            
            # Cleanup individual chunk files and concat file
            for temp_file in temp_audio_files:
                if os.path.exists(temp_file):
                    os.remove(temp_file)
            if os.path.exists(concat_path):
                os.remove(concat_path)
            
            if result.returncode == 0:
                # Verify combined file was created
                if os.path.exists(combined_path) and os.path.getsize(combined_path) > 0:
                    print(f"✅ Audio chunks combined successfully: {total_duration:.1f}s total")
                    return True, combined_path, total_duration, None
                else:
                    return False, None, 0, "Combined audio file was not created properly"
            else:
                return False, None, 0, f"FFmpeg error combining audio: {result.stderr}"
                
        except Exception as e:
            # Cleanup on error
            for temp_file in temp_audio_files:
                if os.path.exists(temp_file):
                    os.remove(temp_file)
            if 'concat_path' in locals() and os.path.exists(concat_path):
                os.remove(concat_path)
            if 'combined_path' in locals() and os.path.exists(combined_path):
                os.remove(combined_path)
            
            return False, None, 0, f"Error in audio chunk generation: {str(e)}"

    def _process_script_with_pauses(self, script, voice, speed, session_id):
        """
        Process a script with pause markers by generating separate audio segments
        and combining them with silence gaps.
        
        Args:
            script: Text with pause markers (— pause — or -- pause --)
            voice: TTS voice
            speed: Speech speed
            session_id: Session ID for file naming
        
        Returns:
            tuple: (success, combined_audio_path, total_duration, error_msg)
        """
        try:
            # Check if pause handling is enabled
            if not self.pause_enabled:
                return None  # Signal to use regular processing
            
            # Split script by pause markers
            pause_pattern = r'(?:—\s*pause\s*—|--\s*pause\s*--)'
            segments = re.split(pause_pattern, script, flags=re.IGNORECASE)
            segments = [seg.strip() for seg in segments if seg.strip()]
            
            if len(segments) <= 1:
                # No pauses found, return None to use regular processing
                return None
            
            print(f"⏸️  Found {len(segments)-1} pause markers in script")
            print(f"🔄 Processing script with {len(segments)} segments and pauses...")
            
            temp_audio_files = []
            temp_silence_file = None
            total_duration = 0
            
            # Generate silence audio file if needed
            if self.pause_silence_seconds > 0:
                silence_filename = f"{session_id}_silence.mp3"
                temp_silence_file = os.path.join(tempfile.gettempdir(), silence_filename)
                
                # Generate silence using FFmpeg
                silence_cmd = [
                    'ffmpeg', '-y',
                    '-f', 'lavfi',
                    '-i', f'anullsrc=channel_layout=stereo:sample_rate={self.audio_sample_rate}',
                    '-t', str(self.pause_silence_seconds),
                    '-c:a', 'libmp3lame',
                    '-b:a', self.audio_bitrate,
                    temp_silence_file
                ]
                
                result = subprocess.run(silence_cmd, capture_output=True, text=True)
                if result.returncode != 0:
                    print(f"⚠️  Failed to generate silence audio: {result.stderr}")
                    temp_silence_file = None
                else:
                    print(f"✅ Generated {self.pause_silence_seconds}s silence audio")
            
            # Generate audio for each segment
            for i, segment in enumerate(segments):
                print(f"   Generating segment {i+1}/{len(segments)} ({len(segment)} chars)...")
                
                segment_filename = f"{session_id}_segment_{i+1}.mp3"
                segment_path = os.path.join(tempfile.gettempdir(), segment_filename)
                
                try:
                    # Generate TTS for this segment
                    response = self.openai_client.audio.speech.create(
                        model="tts-1",
                        voice=voice,
                        input=segment,
                        speed=speed,
                        response_format="mp3"
                    )
                    
                    # Save segment audio
                    with open(segment_path, 'wb') as f:
                        f.write(response.content)
                    
                    if not os.path.exists(segment_path) or os.path.getsize(segment_path) == 0:
                        raise Exception(f"Failed to create audio segment {i+1}")
                    
                    # Get duration
                    segment_duration = self._get_audio_duration(segment_path)
                    total_duration += segment_duration
                    
                    temp_audio_files.append(segment_path)
                    print(f"   ✅ Segment {i+1} generated: {segment_duration:.1f}s")
                    
                    # Add pause/silence after this segment (except for last segment)
                    if i < len(segments) - 1 and temp_silence_file and os.path.exists(temp_silence_file):
                        temp_audio_files.append(temp_silence_file)
                        total_duration += self.pause_silence_seconds
                        print(f"   ⏸️  Added {self.pause_silence_seconds}s pause")
                    
                except Exception as segment_error:
                    # Cleanup
                    for temp_file in temp_audio_files:
                        if temp_file != temp_silence_file and os.path.exists(temp_file):
                            os.remove(temp_file)
                    if temp_silence_file and os.path.exists(temp_silence_file):
                        os.remove(temp_silence_file)
                    return False, None, 0, f"Failed to generate segment {i+1}: {str(segment_error)}"
            
            print(f"🔗 Combining {len(segments)} segments with {len(segments)-1} pauses...")
            
            # Create FFmpeg concat file
            combined_filename = f"{session_id}_with_pauses.mp3"
            combined_path = os.path.join(tempfile.gettempdir(), combined_filename)
            
            concat_filename = f"{session_id}_pause_concat.txt"
            concat_path = os.path.join(tempfile.gettempdir(), concat_filename)
            
            with open(concat_path, 'w') as f:
                for audio_file in temp_audio_files:
                    escaped_path = audio_file.replace('\\', '\\\\').replace("'", "\\'")
                    f.write(f"file '{escaped_path}'\n")
            
            # Combine audio files with pauses
            ffmpeg_cmd = [
                'ffmpeg', '-y',
                '-f', 'concat',
                '-safe', '0',
                '-i', concat_path,
                '-c', 'copy',
                combined_path
            ]
            
            result = subprocess.run(ffmpeg_cmd, capture_output=True, text=True)
            
            # Cleanup individual segment files, silence file, and concat file
            for temp_file in temp_audio_files:
                if temp_file != temp_silence_file and os.path.exists(temp_file):
                    os.remove(temp_file)
            if temp_silence_file and os.path.exists(temp_silence_file):
                os.remove(temp_silence_file)
            if os.path.exists(concat_path):
                os.remove(concat_path)
            
            if result.returncode == 0:
                if os.path.exists(combined_path) and os.path.getsize(combined_path) > 0:
                    print(f"✅ Audio with pauses combined successfully: {total_duration:.1f}s total")
                    return True, combined_path, total_duration, None
                else:
                    return False, None, 0, "Combined audio file was not created properly"
            else:
                return False, None, 0, f"FFmpeg error combining audio with pauses: {result.stderr}"
                
        except Exception as e:
            # Cleanup on error
            if 'temp_audio_files' in locals():
                for temp_file in temp_audio_files:
                    if temp_file != temp_silence_file and os.path.exists(temp_file):
                        os.remove(temp_file)
            if 'temp_silence_file' in locals() and temp_silence_file and os.path.exists(temp_silence_file):
                os.remove(temp_silence_file)
            if 'concat_path' in locals() and os.path.exists(concat_path):
                os.remove(concat_path)
            if 'combined_path' in locals() and os.path.exists(combined_path):
                os.remove(combined_path)
            
            return False, None, 0, f"Error processing script with pauses: {str(e)}"

    def generate_speech(self, text, voice='onyx', speed=1.2, format='mp3', 
                       session_id=None, background_image_path=None, 
                       generation_type='regular', custom_filename=None):
        """
        Generate speech from text using OpenAI TTS and optionally create video.
        
        Args:
            text: Text to convert to speech
            voice: Voice to use (alloy, echo, fable, onyx, nova, shimmer)
            speed: Speech speed (0.25 to 4.0)
            format: Output format (mp3, wav, mp4)
            session_id: Session ID for file naming
            background_image_path: Path to background image for video
            generation_type: 'regular', 'youtube_shorts', 'shorts', or 'standalone'
            custom_filename: Custom filename base (without extension)
        
        Returns:
            dict: Result with success status, file paths, and metadata
        """
        try:
            print(f"🎤 === GENERATE SPEECH START ===")
            print(f"Session ID: {session_id}")
            print(f"Text length: {len(text)} chars")
            print(f"Voice: {voice}")
            print(f"Speed: {speed}")
            print(f"Format: {format}")
            print(f"Generation type: {generation_type}")
            print(f"Background image: {background_image_path}")
            
            # Check OpenAI client
            if not self.openai_client:
                error_msg = 'OpenAI API key not configured'
                print(f"❌ ERROR: {error_msg}")
                return {
                    'success': False,
                    'error': error_msg
                }
            print(f"✅ OpenAI client initialized")
            
            # Validate inputs
            if not text or not text.strip():
                error_msg = 'Text is required'
                print(f"❌ ERROR: {error_msg}")
                return {
                    'success': False,
                    'error': error_msg
                }
            
            if voice not in self.available_voices:
                error_msg = f'Invalid voice. Use: {", ".join(self.available_voices)}'
                print(f"❌ ERROR: {error_msg}")
                return {
                    'success': False,
                    'error': error_msg
                }
            
            if not (0.25 <= speed <= 4.0):
                error_msg = 'Speed must be between 0.25 and 4.0'
                print(f"❌ ERROR: {error_msg}")
                return {
                    'success': False,
                    'error': error_msg
                }
            
            if format not in self.supported_formats:
                error_msg = f'Unsupported format. Use: {", ".join(self.supported_formats)}'
                print(f"❌ ERROR: {error_msg}")
                return {
                    'success': False,
                    'error': error_msg
                }
            print(f"✅ Input validation passed")
            
            # Preprocess text for better TTS
            print(f"📝 Preprocessing text...")
            processed_text = self._preprocess_text_for_tts(text)
            print(f"✅ Text preprocessed: {len(processed_text)} chars")
            
            # Generate filename first (needed for pause processing)
            print(f"📁 Generating filename...")
            if custom_filename:
                filename_base = custom_filename
                print(f"Using custom filename: {filename_base}")
            elif session_id:
                filename_base = f"voiceover_{session_id}"
                print(f"Using session-based filename: {filename_base}")
            else:
                filename_from_text = self._generate_filename_from_text(processed_text)
                if filename_from_text:
                    filename_base = f"voiceover_{filename_from_text}"
                    print(f"Using text-based filename: {filename_base}")
                else:
                    filename_base = f"voiceover_{str(uuid.uuid4())[:8]}"
                    print(f"Using UUID-based filename: {filename_base}")
            
            # NEW: Check for pause markers and process accordingly (only for regular videos, not shorts)
            temp_audio_path = None
            duration = None
            
            if generation_type in ['regular', 'standalone'] and self.pause_enabled:
                print(f"🔍 Checking for pause markers in script...")
                pause_result = self._process_script_with_pauses(processed_text, voice, speed, filename_base)
                
                if pause_result is not None:
                    # Pause processing was attempted
                    success, temp_audio_path, duration, error_msg = pause_result
                    
                    if not success:
                        print(f"❌ PAUSE PROCESSING ERROR: {error_msg}")
                        return {
                            'success': False,
                            'error': error_msg
                        }
                    
                    print(f"✅ Script with pauses processed: {duration:.1f}s total")
            
            # If no pause processing or pause processing returned None, continue with regular processing
            if temp_audio_path is None:
                # Handle long text by chunking if needed
                if len(processed_text) > self.max_input_chars:
                    print(f"📄 Text exceeds {self.max_input_chars} chars, splitting into chunks...")
                    text_chunks = self._chunk_text_for_tts(processed_text, self.max_input_chars - 100)
                    print(f"📄 Split into {len(text_chunks)} chunks")
                    for i, chunk in enumerate(text_chunks):
                        print(f"   Chunk {i+1}: {len(chunk)} chars")
                else:
                    print(f"📄 Text fits in single chunk")
                    text_chunks = [processed_text]
                
                # Set video dimensions based on generation type
                print(f"🎬 Setting video dimensions...")
                if generation_type in ['shorts', 'youtube_shorts']:
                    self.video_width = self.shorts_video_width
                    self.video_height = self.shorts_video_height
                else:
                    self.video_width = self.regular_video_width
                    self.video_height = self.regular_video_height
                
                print(f"✅ Video dimensions set to: {self.video_width}x{self.video_height} for type: {generation_type}")
                
                # Generate TTS audio
                if len(text_chunks) == 1:
                    print(f"🔊 Generating single TTS audio...")
                    temp_audio_path = os.path.join(tempfile.gettempdir(), f"{filename_base}.mp3")
                    
                    try:
                        response = self.openai_client.audio.speech.create(
                            model="tts-1",
                            voice=voice,
                            input=text_chunks[0],
                            speed=speed,
                            response_format="mp3"
                        )
                        print(f"✅ OpenAI TTS response received")
                        
                        with open(temp_audio_path, 'wb') as f:
                            f.write(response.content)
                        print(f"✅ TTS audio saved: {temp_audio_path}")
                        
                        if os.path.exists(temp_audio_path):
                            file_size = os.path.getsize(temp_audio_path)
                            print(f"📊 Audio file size: {file_size} bytes")
                            if file_size == 0:
                                raise Exception("Generated audio file is empty")
                        else:
                            raise Exception("Audio file was not created")
                        
                        duration = self._get_audio_duration(temp_audio_path)
                        print(f"✅ Audio duration: {duration} seconds")
                        
                    except Exception as tts_error:
                        error_msg = f"OpenAI TTS API error: {str(tts_error)}"
                        print(f"❌ TTS ERROR: {error_msg}")
                        import traceback
                        traceback.print_exc()
                        return {
                            'success': False,
                            'error': error_msg
                        }
                else:
                    print(f"🔊 Generating multiple TTS audio chunks...")
                    success, temp_audio_path, duration, error_msg = self._generate_multiple_audio_chunks(
                        text_chunks, voice, speed, filename_base
                    )
                    
                    if not success:
                        print(f"❌ CHUNKED TTS ERROR: {error_msg}")
                        return {
                            'success': False,
                            'error': error_msg
                        }
                    
                    print(f"✅ Combined audio duration: {duration} seconds")
            
            # At this point, temp_audio_path and duration are set (either from pause processing or regular processing)
            
            # Set video dimensions if not already set (for pause processing path)
            if generation_type in ['shorts', 'youtube_shorts']:
                self.video_width = self.shorts_video_width
                self.video_height = self.shorts_video_height
            else:
                self.video_width = self.regular_video_width
                self.video_height = self.regular_video_height
            
            # Determine final output path and format
            print(f"🎯 Determining output format and path...")
            if format == 'mp4':
                print(f"🎬 Creating video...")
                final_filename = f"{filename_base}.mp4"
                final_path = os.path.join(self.output_folder, final_filename)
                print(f"   Output path: {final_path}")
                
                try:
                    success = self._create_video_with_audio(
                        temp_audio_path, 
                        final_path, 
                        processed_text, 
                        background_image_path, 
                        generation_type,
                        duration
                    )
                    
                    if not success:
                        if os.path.exists(temp_audio_path):
                            os.remove(temp_audio_path)
                        error_msg = 'Failed to create video - FFmpeg error'
                        print(f"❌ VIDEO ERROR: {error_msg}")
                        return {
                            'success': False,
                            'error': error_msg
                        }
                    print(f"✅ Video created successfully")
                    
                except Exception as video_error:
                    if os.path.exists(temp_audio_path):
                        os.remove(temp_audio_path)
                    error_msg = f'Video creation failed: {str(video_error)}'
                    print(f"❌ VIDEO ERROR: {error_msg}")
                    import traceback
                    traceback.print_exc()
                    return {
                        'success': False,
                        'error': error_msg
                    }
                
            else:
                print(f"🎵 Processing audio only...")
                final_filename = f"{filename_base}.{format}"
                final_path = os.path.join(self.output_folder, final_filename)
                print(f"   Output path: {final_path}")
                
                if format == 'wav':
                    print(f"🔄 Converting MP3 to WAV...")
                    ffmpeg_cmd = [
                        'ffmpeg', '-y',
                        '-i', temp_audio_path,
                        '-acodec', 'pcm_s16le',
                        '-ar', str(self.audio_sample_rate),
                        final_path
                    ]
                    
                    try:
                        result = subprocess.run(ffmpeg_cmd, capture_output=True, text=True)
                        if result.returncode != 0:
                            print(f"❌ FFmpeg WAV conversion error: {result.stderr}")
                            if os.path.exists(temp_audio_path):
                                os.remove(temp_audio_path)
                            return {
                                'success': False,
                                'error': 'Failed to convert to WAV format'
                            }
                        print(f"✅ WAV conversion successful")
                    except Exception as wav_error:
                        error_msg = f'WAV conversion failed: {str(wav_error)}'
                        print(f"❌ WAV ERROR: {error_msg}")
                        if os.path.exists(temp_audio_path):
                            os.remove(temp_audio_path)
                        return {
                            'success': False,
                            'error': error_msg
                        }
                else:
                    print(f"📁 Moving MP3 file...")
                    try:
                        shutil.move(temp_audio_path, final_path)
                        print(f"✅ MP3 file moved successfully")
                    except Exception as move_error:
                        error_msg = f'Failed to move MP3 file: {str(move_error)}'
                        print(f"❌ MOVE ERROR: {error_msg}")
                        return {
                            'success': False,
                            'error': error_msg
                        }
            
            # Cleanup temporary audio file if it still exists
            if os.path.exists(temp_audio_path):
                try:
                    os.remove(temp_audio_path)
                    print(f"🧹 Cleaned up temp file: {temp_audio_path}")
                except Exception as cleanup_error:
                    print(f"⚠️ Could not cleanup temp file: {cleanup_error}")
            
            # Verify final file was created
            if not os.path.exists(final_path):
                error_msg = f'Final output file was not created: {final_path}'
                print(f"❌ FINAL ERROR: {error_msg}")
                return {
                    'success': False,
                    'error': error_msg
                }
            
            final_file_size = os.path.getsize(final_path)
            print(f"📊 Final file size: {final_file_size} bytes")
            
            file_url = f"/download-voiceover/{final_filename}"
            print(f"🔗 File URL: {file_url}")
            
            print(f"✅ === GENERATE SPEECH SUCCESS ===")
            print(f"Final path: {final_path}")
            
            return {
                'success': True,
                'file_path': final_path,
                'file_url': file_url,
                'filename': final_filename,
                'duration': duration,
                'format': format,
                'voice': voice,
                'speed': speed,
                'text_length': len(processed_text)
            }
            
        except Exception as e:
            error_msg = f"Unexpected error in generate_speech: {str(e)}"
            print(f"❌ === GENERATE SPEECH FAILED ===")
            print(f"ERROR: {error_msg}")
            import traceback
            traceback.print_exc()
            
            # Cleanup on error
            if 'temp_audio_path' in locals() and temp_audio_path and os.path.exists(temp_audio_path):
                try:
                    os.remove(temp_audio_path)
                    print(f"🧹 Cleaned up temp file on error")
                except:
                    pass
            
            return {
                'success': False,
                'error': error_msg
            }

    def _get_audio_duration(self, audio_path):
        """Get duration of audio file using FFmpeg."""
        try:
            cmd = [
                'ffprobe', '-v', 'quiet', '-print_format', 'json', 
                '-show_format', audio_path
            ]
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode == 0:
                import json
                data = json.loads(result.stdout)
                duration = float(data['format']['duration'])
                return duration
            else:
                print(f"FFprobe error: {result.stderr}")
                return 10.0  # Default fallback duration
                
        except Exception as e:
            print(f"Error getting audio duration: {e}")
            return 10.0  # Default fallback duration

    def _create_video_with_audio(self, audio_path, output_path, text, 
                                background_image_path=None, generation_type='regular', 
                                duration=None):
        """Create video with audio, background, and text overlay."""
        try:
            print(f"Creating video: {output_path}")
            print(f"Audio: {audio_path}")
            print(f"Background image: {background_image_path}")
            print(f"Generation type: {generation_type}")
            print(f"Video dimensions: {self.video_width}x{self.video_height}")
            print(f"Target duration: {duration} seconds")
            
            # Get background video path
            background_video_path = self.get_background_video_path(generation_type)
            
            # Build FFmpeg command
            ffmpeg_cmd = ['ffmpeg', '-y']
            
            # Input sources and track audio input index
            audio_input_index = 0
            
            if (background_video_path and os.path.exists(background_video_path)):
                print(f"Using background video: {background_video_path}")
                # NEW: Add stream_loop to loop the video indefinitely and set duration
                ffmpeg_cmd.extend([
                    '-stream_loop', '-1',  # Loop video indefinitely
                    '-i', background_video_path,
                    '-i', audio_path
                ])
                video_input = '[0:v]'
                audio_input_index = 1
            elif (background_image_path and os.path.exists(background_image_path)):
                print(f"Using background image: {background_image_path}")
                ffmpeg_cmd.extend([
                    '-loop', '1', '-i', background_image_path,
                    '-i', audio_path
                ])
                video_input = '[0:v]'
                audio_input_index = 1
            else:
                print("Using solid color background")
                ffmpeg_cmd.extend(['-i', audio_path])
                # Create solid color background with specified duration
                color_input = f'color=c=black:s={self.video_width}x{self.video_height}:d={duration or 30}'
                ffmpeg_cmd.extend(['-f', 'lavfi', '-i', color_input])
                video_input = '[1:v]'
                audio_input_index = 0
            
            # Build filter chain
            filter_parts = []
            current_label = video_input
            
            # Scale and crop video/image to fit dimensions
            if (background_video_path or background_image_path):
                filter_parts.append(f"{current_label}scale={self.video_width}:{self.video_height}:force_original_aspect_ratio=increase[scaled]")
                filter_parts.append(f"[scaled]crop={self.video_width}:{self.video_height}[cropped]")
                current_label = '[cropped]'
            
            # Add text overlay if enabled - Use timed sections instead of full text
            if (self.text_overlay_enabled and text):
                # Split text into timed sections that sync with voiceover
                max_chars_per_section = 120 if generation_type in ['shorts', 'youtube_shorts'] else 200
                timed_sections = self._split_text_into_timed_sections(text, duration or 30, max_chars_per_section)
                
                if (timed_sections):
                    text_chain, final_label = self._build_timed_drawtext_chain(current_label, timed_sections)
                    if (text_chain):
                        filter_parts.append(text_chain)
                        current_label = final_label
            
            # Add filter complex if we have filters
            if (filter_parts):
                ffmpeg_cmd.extend(['-filter_complex', ';'.join(filter_parts)])
                # Properly map the final video output
                final_video_label = current_label.strip('[]')
                ffmpeg_cmd.extend(['-map', f'[{final_video_label}]'])
            else:
                ffmpeg_cmd.extend(['-map', '0:v'])
            
            # Map audio using the correct input index
            ffmpeg_cmd.extend(['-map', f'{audio_input_index}:a'])
            
            # Video encoding settings
            ffmpeg_cmd.extend([
                '-c:v', 'libx264',
                '-preset', self.video_preset,
                '-crf', str(self.video_crf),
                '-profile:v', self.video_profile,
                '-level', self.video_level,
                '-tune', self.video_tune,
                '-pix_fmt', 'yuv420p',
                '-r', str(self.video_fps)
            ])
            
            # Audio encoding settings
            ffmpeg_cmd.extend([
                '-c:a', 'aac',
                '-b:a', self.audio_bitrate,
                '-ar', str(self.audio_sample_rate)
            ])
            
            # NEW: Always set duration to match audio duration to ensure complete video
            if (duration):
                ffmpeg_cmd.extend(['-t', str(duration)])
                print(f"Setting video duration to match audio: {duration} seconds")
            
            # NEW: Add shortest option to ensure video doesn't end before audio
            ffmpeg_cmd.extend(['-shortest'])
            
            ffmpeg_cmd.append(output_path)
            
            print(f"FFmpeg command: {' '.join(ffmpeg_cmd)}")
            
            # Execute FFmpeg
            result = subprocess.run(ffmpeg_cmd, capture_output=True, text=True)
            
            if (result.returncode == 0):
                print(f"Video created successfully: {output_path}")
                return True
            else:
                print(f"FFmpeg error: {result.stderr}")
                return False
                
        except Exception as e:
            print(f"Error creating video: {e}")
            import traceback
            traceback.print_exc()
            return False