#!/usr/bin/env python3
"""
Quick mic test - run this first to check if microphone permissions are working.
"""

import sounddevice as sd
import numpy as np
import time

def main():
    print("=" * 55)
    print("  🎤 MICROPHONE TEST")
    print("=" * 55)
    print()
    
    # List devices
    print("Available audio devices:")
    print(sd.query_devices())
    print()
    
    # Get default input
    default_input = sd.query_devices(kind='input')
    print(f"Default input device: {default_input['name']}")
    print(f"  Max channels: {default_input['max_input_channels']}")
    print(f"  Sample rate: {default_input['default_samplerate']} Hz")
    print()
    
    # Record test
    print("Recording 5 seconds of audio...")
    print("🎤 Speak now! Say 'Hey Veedatron' or anything else.")
    print()
    
    sample_rate = int(default_input['default_samplerate'])
    duration = 5
    
    # Visual level meter during recording
    levels = []
    
    def callback(indata, frames, time_info, status):
        rms = np.sqrt(np.mean(indata ** 2))
        levels.append(rms)
        # Print live level
        bar_len = int(rms * 500)  # Scale for visibility
        bar = "█" * min(bar_len, 50)
        print(f"\r  Level: [{bar:<50}] {rms:.4f}", end="", flush=True)
    
    stream = sd.InputStream(
        samplerate=sample_rate,
        channels=1,
        callback=callback,
        dtype='float32'
    )
    
    with stream:
        time.sleep(duration)
    
    print("\n")
    
    # Analyze
    if not levels:
        print("❌ No audio data received!")
        print()
        print("SOLUTION:")
        print("  1. Open System Settings → Privacy & Security → Microphone")
        print("  2. Enable microphone access for Terminal or Cursor")
        print("  3. You may need to restart Terminal/Cursor after enabling")
        return
    
    avg_level = np.mean(levels)
    max_level = np.max(levels)
    
    print(f"Average level: {avg_level:.4f}")
    print(f"Max level: {max_level:.4f}")
    print()
    
    if max_level < 0.001:
        print("❌ MICROPHONE NOT WORKING!")
        print()
        print("The microphone is not capturing any audio.")
        print()
        print("SOLUTIONS:")
        print("  1. Open System Settings → Privacy & Security → Microphone")
        print("  2. Make sure Terminal (or Cursor) has permission enabled")
        print("  3. If not listed, you may need to add it manually")
        print("  4. Try restarting Terminal/Cursor after granting permission")
        print()
        print("  If running from Cursor terminal, try running from regular Terminal.app")
        
    elif max_level < 0.01:
        print("⚠️  Audio level is very low!")
        print()
        print("The mic is working but the level is low.")
        print("Try:")
        print("  - Speaking louder")
        print("  - Moving closer to the microphone")
        print("  - Checking System Settings → Sound → Input level")
        
    elif max_level < 0.05:
        print("⚠️  Audio level is somewhat low but should work.")
        print("  Try speaking louder for wake word detection.")
        
    else:
        print("✅ MICROPHONE IS WORKING!")
        print()
        print("Audio levels look good. The wake word detector should work.")
        print("Run 'python test_ui.py' to test the full voice assistant.")


if __name__ == "__main__":
    main()
