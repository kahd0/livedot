import os
import sys
import wave
import struct
import math
import subprocess
import logging
from constants import MUTE_SOUND_FILE, UNMUTE_SOUND_FILE

if sys.platform == "win32":
    import winsound

logger = logging.getLogger("livedot.sound")

def generate_tone(filepath, frequency, duration_sec, volume=0.7, decay=True):
    """
    Generates a sine wave audio tone with an optional exponential decay envelope
    and writes it to a 16-bit mono WAV file.
    """
    try:
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        
        sample_rate = 44100
        num_samples = int(duration_sec * sample_rate)
        
        with wave.open(filepath, 'wb') as wav_file:
            # Mono, 16-bit, 44100 Hz
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(sample_rate)
            
            for i in range(num_samples):
                t = i / sample_rate
                val = math.sin(2.0 * math.pi * frequency * t)
                
                if decay:
                    # Exponential decay from 1.0 to nearly 0.0 at duration_sec
                    envelope = math.exp(-6.0 * t / duration_sec)
                    val *= envelope
                
                # Convert float sample to 16-bit signed integer
                sample = int(val * volume * 32767)
                # Keep it bounded to prevent clipping
                sample = max(-32768, min(32767, sample))
                
                wav_file.writeframesraw(struct.pack('<h', sample))
                
        logger.info(f"Successfully generated tone at {filepath} ({frequency}Hz, {duration_sec}s)")
    except Exception as e:
        logger.error(f"Error generating tone at {filepath}: {e}")

def initialize_sounds():
    """
    Ensures that default mute and unmute audio feedback files are generated.
    """
    if not os.path.exists(MUTE_SOUND_FILE):
        logger.info("Mute sound not found. Generating...")
        generate_tone(MUTE_SOUND_FILE, frequency=180.0, duration_sec=0.15, volume=0.8)
        
    if not os.path.exists(UNMUTE_SOUND_FILE):
        logger.info("Unmute sound not found. Generating...")
        generate_tone(UNMUTE_SOUND_FILE, frequency=520.0, duration_sec=0.12, volume=0.8)

def play_sound(filepath):
    """
    Plays a WAV file asynchronously in the background.
    """
    if not os.path.exists(filepath):
        logger.warning(f"Audio file {filepath} does not exist.")
        return

    if sys.platform == "win32":
        try:
            # SND_ASYNC returns immediately; a new call cuts off the previous tone.
            winsound.PlaySound(filepath, winsound.SND_FILENAME | winsound.SND_ASYNC)
        except Exception as e:
            logger.error(f"Could not play audio via winsound: {e}")
        return

    # Attempt to use paplay (PulseAudio/Pipewire) first, fallback to aplay (ALSA)
    try:
        subprocess.Popen(["paplay", filepath], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except FileNotFoundError:
        try:
            subprocess.Popen(["aplay", filepath], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception as e:
            logger.error(f"Could not play audio using paplay or aplay: {e}")
            
def play_mute_sound():
    play_sound(MUTE_SOUND_FILE)

def play_unmute_sound():
    play_sound(UNMUTE_SOUND_FILE)
