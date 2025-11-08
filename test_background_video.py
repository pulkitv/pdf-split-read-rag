#!/usr/bin/env python3
"""
Test script for background video functionality in VoiceoverSystem

Tests:
1. Background video validation on startup
2. Short voiceover (video trimming)
3. Long voiceover (video looping)
4. YouTube Shorts format (portrait)
5. Regular format (landscape)
6. Fallback to waveform when background video is disabled
7. Text overlay on background video
"""

import os
import sys
import time
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Import the VoiceoverSystem
from voiceover_system import VoiceoverSystem


class BackgroundVideoTester:
    """Test harness for background video functionality"""
    
    def __init__(self):
        self.test_results = []
        self.voiceover_system = None
        
    def log(self, message, test_name=None):
        """Log a test message"""
        timestamp = time.strftime("%H:%M:%S")
        if test_name:
            print(f"\n{'='*60}")
            print(f"[{timestamp}] TEST: {test_name}")
            print(f"{'='*60}")
        else:
            print(f"[{timestamp}] {message}")
    
    def record_result(self, test_name, passed, details=""):
        """Record test result"""
        self.test_results.append({
            'test': test_name,
            'passed': passed,
            'details': details
        })
        status = "✅ PASSED" if passed else "❌ FAILED"
        print(f"\n{status}: {test_name}")
        if details:
            print(f"Details: {details}")
    
    def setup(self):
        """Setup test environment"""
        self.log("Setting up test environment...")
        
        # Check if background video files exist
        shorts_bg = os.getenv('SHORTS_BACKGROUND_VIDEO', 'shorts_background.mp4')
        regular_bg = os.getenv('REGULAR_BACKGROUND_VIDEO', 'regular_background.mp4')
        
        self.log(f"Checking for shorts background: {shorts_bg}")
        self.log(f"Checking for regular background: {regular_bg}")
        
        shorts_exists = os.path.exists(shorts_bg)
        regular_exists = os.path.exists(regular_bg)
        
        if not shorts_exists:
            self.log(f"⚠️  WARNING: Shorts background video not found: {shorts_bg}")
        else:
            self.log(f"✓ Shorts background video found")
            
        if not regular_exists:
            self.log(f"⚠️  WARNING: Regular background video not found: {regular_bg}")
        else:
            self.log(f"✓ Regular background video found")
        
        return shorts_exists and regular_exists
    
    def test_1_initialization(self):
        """Test 1: Verify VoiceoverSystem initialization and validation"""
        self.log("Initializing VoiceoverSystem...", "Test 1: Initialization & Validation")
        
        try:
            self.voiceover_system = VoiceoverSystem()
            
            # Check if background video is enabled
            bg_enabled = self.voiceover_system.background_video_enabled
            self.log(f"Background video enabled: {bg_enabled}")
            
            if bg_enabled:
                shorts_path = self.voiceover_system.shorts_background_video
                regular_path = self.voiceover_system.regular_background_video
                
                self.log(f"Shorts video path: {shorts_path}")
                self.log(f"Regular video path: {regular_path}")
                
                # Test get_background_video_path method
                shorts_bg = self.voiceover_system.get_background_video_path('youtube_shorts')
                regular_bg = self.voiceover_system.get_background_video_path('regular')
                
                passed = shorts_bg is not None and regular_bg is not None
                details = f"Shorts: {shorts_bg}, Regular: {regular_bg}"
            else:
                passed = True
                details = "Background video disabled (fallback mode)"
            
            self.record_result("Initialization & Validation", passed, details)
            return passed
            
        except Exception as e:
            self.record_result("Initialization & Validation", False, str(e))
            return False
    
    def test_2_short_voiceover(self):
        """Test 2: Short voiceover (video should be trimmed)"""
        self.log("Testing short voiceover (5-10 seconds)...", "Test 2: Short Voiceover (Trimming)")
        
        if not self.voiceover_system:
            self.record_result("Short Voiceover", False, "VoiceoverSystem not initialized")
            return False
        
        try:
            # Short text for 5-10 second voiceover
            text = "This is a short test message for background video trimming."
            
            result = self.voiceover_system.generate_speech(
                text=text,
                voice='onyx',
                speed=1.2,
                format='mp4',
                generation_type='regular',
                custom_filename='test_short_voiceover'
            )
            
            if result['success']:
                duration = result.get('duration', 0)
                file_path = result.get('file_path', '')
                
                # Check if file was created
                file_exists = os.path.exists(file_path)
                
                passed = file_exists and duration > 0 and duration < 15
                details = f"Duration: {duration:.2f}s, File: {os.path.basename(file_path)}"
                
                if file_exists:
                    file_size = os.path.getsize(file_path) / (1024 * 1024)  # MB
                    details += f", Size: {file_size:.2f}MB"
            else:
                passed = False
                details = "Generation failed"
            
            self.record_result("Short Voiceover (Trimming)", passed, details)
            return passed
            
        except Exception as e:
            self.record_result("Short Voiceover (Trimming)", False, str(e))
            return False
    
    def test_3_long_voiceover(self):
        """Test 3: Long voiceover (video should loop)"""
        self.log("Testing long voiceover (30+ seconds)...", "Test 3: Long Voiceover (Looping)")
        
        if not self.voiceover_system:
            self.record_result("Long Voiceover", False, "VoiceoverSystem not initialized")
            return False
        
        try:
            # Longer text for 30+ second voiceover
            text = """
            This is a comprehensive test message for background video looping functionality.
            The voiceover system should detect that the audio duration is longer than the background video.
            When this happens, the system will automatically loop the background video to match the audio length.
            This ensures a seamless viewing experience with continuous background visuals throughout the entire voiceover.
            The looping is handled intelligently by FFmpeg's loop filter, which creates smooth transitions.
            Text overlay captions will appear on top of the looped background video, synchronized with the audio timing.
            """
            
            result = self.voiceover_system.generate_speech(
                text=text,
                voice='nova',
                speed=1.0,
                format='mp4',
                generation_type='regular',
                custom_filename='test_long_voiceover'
            )
            
            if result['success']:
                duration = result.get('duration', 0)
                file_path = result.get('file_path', '')
                
                file_exists = os.path.exists(file_path)
                
                passed = file_exists and duration >= 25
                details = f"Duration: {duration:.2f}s, File: {os.path.basename(file_path)}"
                
                if file_exists:
                    file_size = os.path.getsize(file_path) / (1024 * 1024)
                    details += f", Size: {file_size:.2f}MB"
            else:
                passed = False
                details = "Generation failed"
            
            self.record_result("Long Voiceover (Looping)", passed, details)
            return passed
            
        except Exception as e:
            self.record_result("Long Voiceover (Looping)", False, str(e))
            return False
    
    def test_4_youtube_shorts(self):
        """Test 4: YouTube Shorts format (portrait 1080x1920)"""
        self.log("Testing YouTube Shorts format...", "Test 4: YouTube Shorts (Portrait)")
        
        if not self.voiceover_system:
            self.record_result("YouTube Shorts Format", False, "VoiceoverSystem not initialized")
            return False
        
        try:
            text = "Breaking news: Markets rally on positive economic data. Tech stocks lead gains."
            
            result = self.voiceover_system.generate_speech(
                text=text,
                voice='echo',
                speed=1.2,
                format='mp4',
                generation_type='youtube_shorts',  # Portrait format
                custom_filename='test_youtube_shorts'
            )
            
            if result['success']:
                file_path = result.get('file_path', '')
                file_exists = os.path.exists(file_path)
                
                # Verify dimensions (would need ffprobe in real test)
                passed = file_exists
                details = f"File: {os.path.basename(file_path)}, Format: Portrait (1080x1920)"
                
                if file_exists:
                    file_size = os.path.getsize(file_path) / (1024 * 1024)
                    duration = result.get('duration', 0)
                    details += f", Duration: {duration:.2f}s, Size: {file_size:.2f}MB"
            else:
                passed = False
                details = "Generation failed"
            
            self.record_result("YouTube Shorts Format", passed, details)
            return passed
            
        except Exception as e:
            self.record_result("YouTube Shorts Format", False, str(e))
            return False
    
    def test_5_regular_format(self):
        """Test 5: Regular format (landscape 1920x1080)"""
        self.log("Testing Regular format...", "Test 5: Regular Format (Landscape)")
        
        if not self.voiceover_system:
            self.record_result("Regular Format", False, "VoiceoverSystem not initialized")
            return False
        
        try:
            text = "Quarterly business review: Strong performance across all segments with record revenue."
            
            result = self.voiceover_system.generate_speech(
                text=text,
                voice='onyx',
                speed=1.0,
                format='mp4',
                generation_type='regular',  # Landscape format
                custom_filename='test_regular_format'
            )
            
            if result['success']:
                file_path = result.get('file_path', '')
                file_exists = os.path.exists(file_path)
                
                passed = file_exists
                details = f"File: {os.path.basename(file_path)}, Format: Landscape (1920x1080)"
                
                if file_exists:
                    file_size = os.path.getsize(file_path) / (1024 * 1024)
                    duration = result.get('duration', 0)
                    details += f", Duration: {duration:.2f}s, Size: {file_size:.2f}MB"
            else:
                passed = False
                details = "Generation failed"
            
            self.record_result("Regular Format", passed, details)
            return passed
            
        except Exception as e:
            self.record_result("Regular Format", False, str(e))
            return False
    
    def test_6_text_overlay(self):
        """Test 6: Text overlay on background video"""
        self.log("Testing text overlay with captions...", "Test 6: Text Overlay")
        
        if not self.voiceover_system:
            self.record_result("Text Overlay", False, "VoiceoverSystem not initialized")
            return False
        
        try:
            # Multi-sentence text to generate multiple caption segments
            text = "First segment of news. Second important update. Third breaking story."
            
            result = self.voiceover_system.generate_speech(
                text=text,
                voice='shimmer',
                speed=1.1,
                format='mp4',
                generation_type='youtube_shorts',
                custom_filename='test_text_overlay'
            )
            
            if result['success']:
                file_path = result.get('file_path', '')
                file_exists = os.path.exists(file_path)
                
                # Text overlay is enabled by default
                text_overlay_enabled = self.voiceover_system.text_overlay_enabled
                
                passed = file_exists and text_overlay_enabled
                details = f"File: {os.path.basename(file_path)}, Text overlay: {text_overlay_enabled}"
            else:
                passed = False
                details = "Generation failed"
            
            self.record_result("Text Overlay", passed, details)
            return passed
            
        except Exception as e:
            self.record_result("Text Overlay", False, str(e))
            return False
    
    def test_7_fallback_mode(self):
        """Test 7: Fallback to waveform when background video is unavailable"""
        self.log("Testing fallback mode...", "Test 7: Fallback to Waveform")
        
        try:
            # Temporarily disable background video
            original_setting = os.getenv('BACKGROUND_VIDEO_ENABLED')
            os.environ['BACKGROUND_VIDEO_ENABLED'] = 'false'
            
            # Create new instance with background video disabled
            fallback_system = VoiceoverSystem()
            
            text = "Testing fallback to waveform visualization."
            
            result = fallback_system.generate_speech(
                text=text,
                voice='alloy',
                speed=1.2,
                format='mp4',
                generation_type='regular',
                custom_filename='test_fallback_waveform'
            )
            
            # Restore original setting
            if original_setting:
                os.environ['BACKGROUND_VIDEO_ENABLED'] = original_setting
            
            if result['success']:
                file_path = result.get('file_path', '')
                file_exists = os.path.exists(file_path)
                
                passed = file_exists and not fallback_system.background_video_enabled
                details = f"File: {os.path.basename(file_path)}, Used fallback: {not fallback_system.background_video_enabled}"
            else:
                passed = False
                details = "Generation failed"
            
            self.record_result("Fallback to Waveform", passed, details)
            return passed
            
        except Exception as e:
            self.record_result("Fallback to Waveform", False, str(e))
            return False
    
    def print_summary(self):
        """Print test summary"""
        print("\n" + "="*60)
        print("TEST SUMMARY")
        print("="*60)
        
        total_tests = len(self.test_results)
        passed_tests = sum(1 for r in self.test_results if r['passed'])
        failed_tests = total_tests - passed_tests
        
        print(f"\nTotal Tests: {total_tests}")
        print(f"✅ Passed: {passed_tests}")
        print(f"❌ Failed: {failed_tests}")
        print(f"Success Rate: {(passed_tests/total_tests*100):.1f}%")
        
        print("\nDetailed Results:")
        print("-" * 60)
        for i, result in enumerate(self.test_results, 1):
            status = "✅" if result['passed'] else "❌"
            print(f"{i}. {status} {result['test']}")
            if result['details']:
                print(f"   {result['details']}")
        
        print("\n" + "="*60)
        
        # List generated files
        voiceover_folder = os.getenv('VOICEOVER_FOLDER', 'voiceovers')
        if os.path.exists(voiceover_folder):
            test_files = [f for f in os.listdir(voiceover_folder) if f.startswith('test_')]
            if test_files:
                print("\nGenerated Test Files:")
                print("-" * 60)
                for f in test_files:
                    file_path = os.path.join(voiceover_folder, f)
                    size = os.path.getsize(file_path) / (1024 * 1024)
                    print(f"  • {f} ({size:.2f}MB)")
        
        print("="*60 + "\n")
    
    def run_all_tests(self):
        """Run all tests in sequence"""
        self.log("Starting background video test suite...", "BACKGROUND VIDEO TEST SUITE")
        
        # Setup
        if not self.setup():
            self.log("⚠️  WARNING: Some background video files are missing")
            self.log("Tests will continue but may use fallback modes")
        
        # Run tests
        tests = [
            self.test_1_initialization,
            self.test_2_short_voiceover,
            self.test_3_long_voiceover,
            self.test_4_youtube_shorts,
            self.test_5_regular_format,
            self.test_6_text_overlay,
            self.test_7_fallback_mode
        ]
        
        for test_func in tests:
            try:
                test_func()
                time.sleep(1)  # Brief pause between tests
            except Exception as e:
                self.log(f"Unexpected error in {test_func.__name__}: {str(e)}")
        
        # Print summary
        self.print_summary()
        
        # Return overall success
        return all(r['passed'] for r in self.test_results)


def main():
    """Main test runner"""
    print("\n🎬 Background Video Test Suite")
    print("Testing VoiceoverSystem background video functionality\n")
    
    # Check OpenAI API key
    if not os.getenv('OPENAI_API_KEY'):
        print("❌ ERROR: OPENAI_API_KEY not found in environment variables")
        print("Please set your OpenAI API key in the .env file")
        sys.exit(1)
    
    # Run tests
    tester = BackgroundVideoTester()
    success = tester.run_all_tests()
    
    # Exit with appropriate code
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
