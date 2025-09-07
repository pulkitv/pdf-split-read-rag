"""
TTS Providers Module - Support for multiple Text-to-Speech backends
Including OpenAI, Coqui TTS, Microsoft SpeechT5, and Festival
"""
import os
import tempfile
import subprocess
import shutil
import numpy as np
from abc import ABC, abstractmethod
from typing import List, Dict, Optional
from openai import OpenAI


class TTSProvider(ABC):
    """Abstract base class for TTS providers"""
    
    @abstractmethod
    def is_available(self) -> bool:
        """Check if this TTS provider is available"""
        pass
    
    @abstractmethod
    def get_voices(self) -> List[Dict[str, str]]:
        """Get list of available voices"""
        pass
    
    @abstractmethod
    def synthesize(self, text: str, voice: str, speed: float, output_path: str) -> bool:
        """Synthesize text to audio file"""
        pass
    
    @abstractmethod
    def get_provider_name(self) -> str:
        """Get provider name"""
        pass


class OpenAITTSProvider(TTSProvider):
    """OpenAI TTS Provider"""
    
    def __init__(self):
        api_key = os.getenv('OPENAI_API_KEY')
        self.client = OpenAI(api_key=api_key) if api_key else None
        self.voices = [
            {'id': 'alloy', 'name': 'Alloy (Neutral)', 'language': 'en-US'},
            {'id': 'echo', 'name': 'Echo (Deep)', 'language': 'en-US'},
            {'id': 'fable', 'name': 'Fable (Expressive)', 'language': 'en-US'},
            {'id': 'onyx', 'name': 'Onyx (Professional)', 'language': 'en-US'},
            {'id': 'nova', 'name': 'Nova (Clear)', 'language': 'en-US'},
            {'id': 'shimmer', 'name': 'Shimmer (Warm)', 'language': 'en-US'}
        ]
    
    def is_available(self) -> bool:
        return self.client is not None
    
    def get_voices(self) -> List[Dict[str, str]]:
        return self.voices
    
    def get_provider_name(self) -> str:
        return "OpenAI TTS"
    
    def synthesize(self, text: str, voice: str, speed: float, output_path: str) -> bool:
        if not self.client:
            return False
        
        try:
            # Use streaming if available
            try:
                with self.client.audio.speech.with_streaming_response.create(
                    model="tts-1-hd",
                    voice=voice,
                    input=text,
                    speed=speed,
                ) as response:
                    response.stream_to_file(output_path)
                    return True
            except AttributeError:
                # Fallback to non-streaming
                resp = self.client.audio.speech.create(
                    model="tts-1-hd",
                    voice=voice,
                    input=text,
                    speed=speed,
                )
                with open(output_path, 'wb') as f:
                    if hasattr(resp, 'content'):
                        f.write(resp.content)
                    else:
                        f.write(resp.read())
                return True
        except Exception as e:
            print(f"OpenAI TTS error: {e}")
            return False


class CoquiTTSProvider(TTSProvider):
    """Coqui TTS Provider - High quality open-source TTS"""
    
    def __init__(self):
        self.voices = [
            {'id': 'tts_models/en/vctk/vits', 'name': 'VCTK Multi-Speaker (Indian: p225, p226)', 'language': 'en-IN'},
            {'id': 'tts_models/en/ljspeech/tacotron2-DDC', 'name': 'LJSpeech Tacotron2', 'language': 'en-US'},
            {'id': 'tts_models/en/ljspeech/glow-tts', 'name': 'LJSpeech Glow-TTS', 'language': 'en-US'},
            {'id': 'tts_models/multilingual/multi-dataset/your_tts', 'name': 'YourTTS Multilingual', 'language': 'multi'},
        ]
        self._check_installation()
    
    def _check_installation(self):
        """Check if Coqui TTS is installed"""
        try:
            import TTS  # type: ignore
            self.available = True
        except ImportError:
            self.available = False
            print("Coqui TTS not installed. Run: pip install TTS")
    
    def is_available(self) -> bool:
        return self.available
    
    def get_voices(self) -> List[Dict[str, str]]:
        return self.voices
    
    def get_provider_name(self) -> str:
        return "Coqui TTS (Open Source)"
    
    def synthesize(self, text: str, voice: str, speed: float, output_path: str) -> bool:
        if not self.available:
            return False
        
        try:
            from TTS.api import TTS  # type: ignore
            
            # Initialize TTS with the selected model
            tts = TTS(model_name=voice)
            
            # Generate speech
            if 'vctk' in voice:
                # For VCTK models, use Indian speakers
                speaker = "p225"  # Indian female speaker
                tts.tts_to_file(text=text, file_path=output_path, speaker=speaker)
            else:
                tts.tts_to_file(text=text, file_path=output_path)
            
            # Apply speed adjustment if needed (using FFmpeg)
            if speed != 1.0:
                self._adjust_speed(output_path, speed)
            
            return True
        except Exception as e:
            print(f"Coqui TTS error: {e}")
            return False
    
    def _adjust_speed(self, audio_path: str, speed: float):
        """Adjust audio speed using FFmpeg"""
        try:
            temp_path = audio_path + ".temp.wav"
            cmd = [
                'ffmpeg', '-y', '-i', audio_path,
                '-filter:a', f'atempo={speed}',
                temp_path
            ]
            subprocess.run(cmd, check=True, capture_output=True)
            shutil.move(temp_path, audio_path)
        except Exception as e:
            print(f"Speed adjustment failed: {e}")


class SpeechT5Provider(TTSProvider):
    """Microsoft SpeechT5 Provider via Hugging Face"""
    
    def __init__(self):
        self.voices = [
            {'id': 'microsoft/speecht5_tts', 'name': 'SpeechT5 (General English)', 'language': 'en-US'},
        ]
        self._check_installation()
    
    def _check_installation(self):
        """Check if required packages are installed"""
        try:
            import torch  # type: ignore
            from transformers import SpeechT5Processor, SpeechT5ForTextToSpeech  # type: ignore
            from datasets import load_dataset  # type: ignore
            self.available = True
        except ImportError:
            self.available = False
            print("SpeechT5 dependencies not installed. Run: pip install torch transformers datasets soundfile")
    
    def is_available(self) -> bool:
        return self.available
    
    def get_voices(self) -> List[Dict[str, str]]:
        return self.voices
    
    def get_provider_name(self) -> str:
        return "Microsoft SpeechT5 (Open Source)"
    
    def synthesize(self, text: str, voice: str, speed: float, output_path: str) -> bool:
        if not self.available:
            return False
        
        try:
            try:
                import torch  # type: ignore
                from transformers import SpeechT5Processor, SpeechT5ForTextToSpeech, SpeechT5HifiGan  # type: ignore
                from datasets import load_dataset  # type: ignore
                import soundfile as sf  # type: ignore
                import numpy as np
            except ImportError as import_error:
                print(f"Required dependencies not available: {import_error}")
                return False
            
            # Load model and processor
            processor = SpeechT5Processor.from_pretrained("microsoft/speecht5_tts")
            model = SpeechT5ForTextToSpeech.from_pretrained("microsoft/speecht5_tts")
            vocoder = SpeechT5HifiGan.from_pretrained("microsoft/speecht5_hifigan")
            
            # Load speaker embeddings
            embeddings_dataset = load_dataset("Matthijs/cmu-arctic-xvectors", split="validation")
            speaker_embeddings = torch.tensor(embeddings_dataset[7306]["xvector"]).unsqueeze(0)
            
            # Process text
            inputs = processor(text=text, return_tensors="pt")
            
            # Generate speech
            speech = model.generate_speech(inputs["input_ids"], speaker_embeddings, vocoder=vocoder)
            
            # Ensure we have a NumPy array
            if hasattr(speech, "detach"):  # torch.Tensor
                speech_np = speech.detach().cpu().numpy()
            elif isinstance(speech, np.ndarray):
                speech_np = speech
            else:
                speech_np = np.array(speech)
            
            # Apply speed adjustment
            if speed != 1.0:
                # Simple speed adjustment by resampling
                speech_np = self._adjust_speech_speed(speech_np, speed)
            
            # Save to file
            sf.write(output_path, speech_np, samplerate=16000)
            return True
            
        except Exception as e:
            print(f"SpeechT5 TTS error: {e}")
            return False
    
    def _adjust_speech_speed(self, audio: np.ndarray, speed: float) -> np.ndarray:
        """Adjust speech speed by resampling"""
        try:
            import librosa  # type: ignore
            return librosa.effects.time_stretch(audio, rate=speed)
        except ImportError:
            # Fallback: simple decimation/interpolation
            if speed > 1.0:
                # Speed up: take every nth sample
                step = int(speed)
                return audio[::step]
            elif speed < 1.0:
                # Slow down: interpolate
                import numpy as np
                new_length = int(len(audio) / speed)
                return np.interp(np.linspace(0, len(audio)-1, new_length), 
                               np.arange(len(audio)), audio)
            return audio


class FestivalTTSProvider(TTSProvider):
    """Festival TTS Provider - Classic open-source TTS"""
    
    def __init__(self):
        self.voices = [
            {'id': 'cmu_indic_hin_ab', 'name': 'Hindi-English (Indian)', 'language': 'en-IN'},
            {'id': 'kal_diphone', 'name': 'Kal (American English)', 'language': 'en-US'},
            {'id': 'cmu_us_awb_arctic_hts', 'name': 'AWB (American English)', 'language': 'en-US'},
        ]
        self._check_installation()
    
    def _check_installation(self):
        """Check if Festival is installed"""
        try:
            result = subprocess.run(['festival', '--version'], 
                                  capture_output=True, text=True)
            self.available = result.returncode == 0
        except FileNotFoundError:
            self.available = False
    
    def is_available(self) -> bool:
        return self.available
    
    def get_voices(self) -> List[Dict[str, str]]:
        return self.voices
    
    def get_provider_name(self) -> str:
        return "Festival TTS (Open Source)"
    
    def synthesize(self, text: str, voice: str, speed: float, output_path: str) -> bool:
        if not self.available:
            return False
        
        try:
            # Create temporary script file for Festival
            with tempfile.NamedTemporaryFile(mode='w', suffix='.scm', delete=False) as f:
                script_content = f'''
(voice_{voice})
(set! utt1 (SayText "{text}"))
(utt.save.wave utt1 "{output_path}")
'''
                f.write(script_content)
                script_path = f.name
            
            # Run Festival
            cmd = ['festival', '-b', script_path]
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            # Clean up
            os.unlink(script_path)
            
            # Apply speed adjustment if needed
            if speed != 1.0 and os.path.exists(output_path):
                self._adjust_speed(output_path, speed)
            
            return result.returncode == 0 and os.path.exists(output_path)
            
        except Exception as e:
            print(f"Festival TTS error: {e}")
            return False
    
    def _adjust_speed(self, audio_path: str, speed: float):
        """Adjust audio speed using FFmpeg"""
        try:
            temp_path = audio_path + ".temp.wav"
            cmd = [
                'ffmpeg', '-y', '-i', audio_path,
                '-filter:a', f'atempo={speed}',
                temp_path
            ]
            subprocess.run(cmd, check=True, capture_output=True)
            shutil.move(temp_path, audio_path)
        except Exception as e:
            print(f"Speed adjustment failed: {e}")


class TTSManager:
    """Manages multiple TTS providers and automatically selects the best available one"""
    
    def __init__(self):
        self.providers = [
            CoquiTTSProvider(),      # Best quality for Indian English
            SpeechT5Provider(),      # Good alternative
            OpenAITTSProvider(),     # Fallback (requires API key)
            FestivalTTSProvider(),   # Last resort
        ]
        self.available_providers = [p for p in self.providers if p.is_available()]
        
        if not self.available_providers:
            print("Warning: No TTS providers available!")
        else:
            print(f"Available TTS providers: {[p.get_provider_name() for p in self.available_providers]}")
    
    def get_available_providers(self) -> List[TTSProvider]:
        """Get list of available TTS providers"""
        return self.available_providers
    
    def get_provider_by_name(self, name: str) -> Optional[TTSProvider]:
        """Get provider by name"""
        for provider in self.available_providers:
            if provider.get_provider_name() == name:
                return provider
        return None
    
    def get_default_provider(self) -> Optional[TTSProvider]:
        """Get the best available provider"""
        return self.available_providers[0] if self.available_providers else None
    
    def get_all_voices(self) -> Dict[str, List[Dict[str, str]]]:
        """Get all voices from all providers"""
        voices = {}
        for provider in self.available_providers:
            voices[provider.get_provider_name()] = provider.get_voices()
        return voices
    
    def synthesize_with_provider(self, provider_name: str, text: str, voice: str, 
                               speed: float, output_path: str) -> bool:
        """Synthesize using specific provider"""
        provider = self.get_provider_by_name(provider_name)
        if not provider:
            return False
        return provider.synthesize(text, voice, speed, output_path)
    
    def synthesize_with_best_provider(self, text: str, voice: str, speed: float, 
                                    output_path: str) -> bool:
        """Synthesize using the best available provider"""
        provider = self.get_default_provider()
        if not provider:
            return False
        return provider.synthesize(text, voice, speed, output_path)