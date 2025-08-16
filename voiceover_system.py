import os
import tempfile
from openai import OpenAI
import subprocess
import uuid
from pathlib import Path
import json

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
        
        # Video generation settings
        self.video_width = int(os.getenv('VIDEO_WIDTH', 1920))
        self.video_height = int(os.getenv('VIDEO_HEIGHT', 1080))
        self.video_fps = int(os.getenv('VIDEO_FPS', 30))
        
    def generate_speech(self, text, voice='nova', speed=1.0, format='mp3', session_id=None):
        """Generate speech from text using OpenAI TTS"""
        if not self.openai_client:
            raise Exception("OpenAI client not configured. Please set OPENAI_API_KEY environment variable.")
        
        if voice not in self.available_voices:
            raise Exception(f"Voice '{voice}' not supported. Available voices: {', '.join(self.available_voices)}")
        
        if format not in self.supported_formats:
            raise Exception(f"Format '{format}' not supported. Available formats: {', '.join(self.supported_formats)}")
        
        try:
            # Generate unique filename
            file_id = str(uuid.uuid4())
            if session_id:
                file_id = f"{session_id}_{file_id}"
            
            # Generate speech using OpenAI TTS
            print(f"Generating speech with voice: {voice}, speed: {speed}")
            
            from typing import cast, Literal
            response = self.openai_client.audio.speech.create(
                model="tts-1-hd",  # Use high-quality model
                voice=cast(Literal['alloy', 'echo', 'fable', 'onyx', 'nova', 'shimmer'], voice),
                input=text,
                speed=speed
            )
            
            # Save audio file
            if format == 'mp4':
                # For video format, first generate MP3 then convert to video
                audio_filename = f"{file_id}.mp3"
                audio_path = os.path.join(self.output_folder, audio_filename)
                
                response.stream_to_file(audio_path)
                
                # Generate video with audio
                video_path = self._create_video_with_audio(audio_path, file_id, text)
                
                # Clean up temporary audio file
                if os.path.exists(audio_path):
                    os.remove(audio_path)
                
                return {
                    'success': True,
                    'file_path': video_path,
                    'file_url': f"/download-voiceover/{os.path.basename(video_path)}",
                    'format': 'mp4',
                    'duration': self._get_audio_duration(video_path)
                }
            else:
                # For audio formats
                audio_filename = f"{file_id}.{format}"
                audio_path = os.path.join(self.output_folder, audio_filename)
                
                if format == 'mp3':
                    response.stream_to_file(audio_path)
                elif format == 'wav':
                    # Convert MP3 to WAV using ffmpeg
                    temp_mp3 = os.path.join(self.output_folder, f"{file_id}_temp.mp3")
                    response.stream_to_file(temp_mp3)
                    
                    # Convert to WAV
                    self._convert_audio_format(temp_mp3, audio_path, 'wav')
                    
                    # Clean up temporary MP3
                    if os.path.exists(temp_mp3):
                        os.remove(temp_mp3)
                
                return {
                    'success': True,
                    'file_path': audio_path,
                    'file_url': f"/download-voiceover/{os.path.basename(audio_path)}",
                    'format': format,
                    'duration': self._get_audio_duration(audio_path)
                }
                
        except Exception as e:
            print(f"Error generating speech: {str(e)}")
            raise Exception(f"Failed to generate voiceover: {str(e)}")
    
    def _create_video_with_audio(self, audio_path, file_id, text):
        """Create video with waveform visualization and text overlay"""
        try:
            video_filename = f"{file_id}.mp4"
            video_path = os.path.join(self.output_folder, video_filename)
            
            # Get audio duration for video length
            duration = self._get_audio_duration(audio_path)
            
            # Create video with waveform visualization using ffmpeg
            # This creates a professional-looking video with audio waveform and text
            ffmpeg_cmd = [
                'ffmpeg', '-y',  # Overwrite output file
                '-f', 'lavfi',
                '-i', f'color=c=0x1e3c72:size={self.video_width}x{self.video_height}:duration={duration}',  # Background
                '-i', audio_path,  # Audio input
                '-filter_complex', 
                f'''[1:a]showwaves=s={self.video_width}x{int(self.video_height*0.3)}:mode=line:colors=white@0.8[waveform];
                [0:v][waveform]overlay=(W-w)/2:(H-h)/2[bg];
                [bg]drawtext=text='{self._escape_text_for_ffmpeg(text[:100])}...':fontcolor=white:fontsize=24:x=(w-text_w)/2:y=50:fontfile=/System/Library/Fonts/Arial.ttf[video]''',
                '-map', '[video]',
                '-map', '1:a',
                '-c:v', 'libx264',
                '-c:a', 'aac',
                '-shortest',
                video_path
            ]
            
            # Execute ffmpeg command
            result = subprocess.run(ffmpeg_cmd, capture_output=True, text=True)
            
            if result.returncode != 0:
                # Fallback: create simple video without complex effects
                print(f"Complex video generation failed, using fallback method")
                self._create_simple_video(audio_path, video_path, duration)
            
            if not os.path.exists(video_path):
                raise Exception("Video file was not created")
            
            return video_path
            
        except Exception as e:
            print(f"Error creating video: {str(e)}")
            # Create a simple video as fallback
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
    
    def _get_audio_duration(self, audio_path):
        """Get duration of audio file in seconds"""
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
        # Replace problematic characters for ffmpeg
        text = text.replace("'", "\\'")
        text = text.replace(":", "\\:")
        text = text.replace(",", "\\,")
        text = text.replace("[", "\\[")
        text = text.replace("]", "\\]")
        return text
    
    def cleanup_old_files(self, max_age_hours=24):
        """Clean up old voiceover files"""
        try:
            import time
            current_time = time.time()
            max_age_seconds = max_age_hours * 3600
            
            for filename in os.listdir(self.output_folder):
                file_path = os.path.join(self.output_folder, filename)
                if os.path.isfile(file_path):
                    file_age = current_time - os.path.getctime(file_path)
                    if file_age > max_age_seconds:
                        os.remove(file_path)
                        print(f"Cleaned up old voiceover file: {filename}")
                        
        except Exception as e:
            print(f"Error during cleanup: {str(e)}")
    
    def get_file_info(self, filename):
        """Get information about a voiceover file"""
        try:
            file_path = os.path.join(self.output_folder, filename)
            
            if not os.path.exists(file_path):
                return None
            
            file_size = os.path.getsize(file_path)
            duration = self._get_audio_duration(file_path)
            
            return {
                'filename': filename,
                'size': file_size,
                'duration': duration,
                'format': filename.split('.')[-1]
            }
            
        except Exception as e:
            print(f"Error getting file info: {str(e)}")
            return None