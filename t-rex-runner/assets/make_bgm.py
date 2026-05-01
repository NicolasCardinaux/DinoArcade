import wave
import math
import struct

def make_bgm(filename, duration=4.0, sample_rate=44100):
    with wave.open(filename, 'w') as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sample_rate)
        
        # Simple upbeat chiptune melody loop (C major arpeggios)
        notes = [261.63, 329.63, 392.00, 523.25, 392.00, 329.63, 261.63, 196.00]
        note_dur = 0.25 # 4 notes per second => 16 notes total
        
        sequence = notes * 2 # 4 seconds
        
        for n in sequence:
            for i in range(int(sample_rate * note_dur)):
                t = i / float(sample_rate)
                # Square wave for retro 8-bit feel
                v = 1.0 if math.sin(2.0 * math.pi * n * t) > 0 else -1.0
                
                # Staccato envelope
                env = 1.0 - (t / note_dur)
                env = max(0, env - 0.2)
                
                # Very low volume (user requested "despacito, muy leve")
                sample = int(v * env * 32767.0 * 0.05)
                sample = max(-32768, min(32767, sample))
                w.writeframesraw(struct.pack('<h', sample))

make_bgm('bg_music.wav')
