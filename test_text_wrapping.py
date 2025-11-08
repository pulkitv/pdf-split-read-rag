#!/usr/bin/env python3
"""
Test script to verify text wrapping and newline handling in voiceover system
"""

import os
import tempfile
import subprocess
from voiceover_system import VoiceoverSystem

def test_text_wrapping():
    """Test the text wrapping functionality without generating actual TTS"""
    
    # Initialize voiceover system
    vs = VoiceoverSystem()
    vs.video_width = 1080  # Portrait mode
    vs.video_height = 1920
    vs.text_overlay_fontsize_px = 56
    vs.text_overlay_side_margin_px = 50
    
    # Test text that should wrap
    test_text = "This is a very long line of text that should definitely wrap to multiple lines when displayed on the video"
    
    print("=== Testing Text Wrapping Logic ===")
    print(f"Original text: {test_text}")
    print(f"Text length: {len(test_text)} characters")
    
    # Test the wrap_text_for_video function from the class
    # Calculate max characters per line (copied from the method)
    fontsize = vs.text_overlay_fontsize_px
    margin = vs.text_overlay_side_margin_px
    char_width_estimate = fontsize * 0.5
    available_width = vs.video_width - (2 * margin)
    max_chars = max(15, int(available_width / char_width_estimate))
    max_chars = min(max_chars, 20)  # Conservative for mobile
    
    print(f"Calculated max chars per line: {max_chars}")
    
    # Simulate the wrapping logic
    def wrap_text_for_video(text, max_chars_per_line):
        if len(text) <= max_chars_per_line:
            return [text]
        
        words = text.split()
        lines = []
        current_line = ""
        
        for word in words:
            test_line = f"{current_line} {word}".strip()
            
            if len(test_line) <= max_chars_per_line:
                current_line = test_line
            else:
                if current_line:
                    lines.append(current_line)
                    current_line = word
                else:
                    current_line = word
        
        if current_line:
            lines.append(current_line)
        
        return lines
    
    # Test wrapping
    wrapped_lines = wrap_text_for_video(test_text, max_chars)
    print(f"Wrapped into {len(wrapped_lines)} lines:")
    for i, line in enumerate(wrapped_lines):
        print(f"  Line {i+1}: '{line}' ({len(line)} chars)")
    
    # Test FFmpeg escaping
    def escape_drawtext(s):
        s = s.replace('\\', '\\\\')
        s = s.replace("'", "\\'") 
        s = s.replace(':', '\\:')
        s = s.replace('%', '\\%')
        s = s.replace('[', '\\[')
        s = s.replace(']', '\\]')
        return s
    
    # Create the display text as it would appear in FFmpeg
    display_text = '\\n'.join([escape_drawtext(line) for line in wrapped_lines])
    print(f"\nFFmpeg display text: '{display_text}'")
    
    # Test with a simple FFmpeg command to verify text rendering
    test_simple_ffmpeg_text(display_text, vs)

def test_simple_ffmpeg_text(display_text, vs):
    """Test FFmpeg text rendering with a simple command"""
    print("\n=== Testing FFmpeg Text Rendering ===")
    
    try:
        output_path = "/tmp/test_text_render.mp4"
        
        # Simple FFmpeg command to test text rendering
        ffmpeg_cmd = [
            'ffmpeg', '-y',
            '-f', 'lavfi', '-i', f'color=c=black:s={vs.video_width}x{vs.video_height}:d=3',
            '-vf', f"drawtext=text='{display_text}':fontsize={vs.text_overlay_fontsize_px}:fontcolor=white:x=(w-text_w)/2:y=(h-text_h)/2",
            '-c:v', 'libx264',
            '-t', '3',
            output_path
        ]
        
        print("Running FFmpeg command:")
        print(' '.join(ffmpeg_cmd))
        
        result = subprocess.run(ffmpeg_cmd, capture_output=True, text=True)
        
        if result.returncode == 0:
            print(f"✅ Test video created successfully: {output_path}")
            print("Check the video to see if text wrapping works correctly")
        else:
            print(f"❌ FFmpeg failed:")
            print(f"STDERR: {result.stderr}")
            
            # Try alternative newline syntax
            print("\nTrying alternative newline syntax...")
            alt_display_text = display_text.replace('\\n', '\n')
            
            ffmpeg_cmd[6] = f"drawtext=text='{alt_display_text}':fontsize={vs.text_overlay_fontsize_px}:fontcolor=white:x=(w-text_w)/2:y=(h-text_h)/2"
            
            result2 = subprocess.run(ffmpeg_cmd, capture_output=True, text=True)
            if result2.returncode == 0:
                print(f"✅ Alternative syntax worked: {output_path}")
            else:
                print(f"❌ Alternative syntax also failed: {result2.stderr}")
    
    except Exception as e:
        print(f"Error testing FFmpeg: {str(e)}")

if __name__ == "__main__":
    test_text_wrapping()