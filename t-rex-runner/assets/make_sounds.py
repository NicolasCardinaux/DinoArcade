import wave
import math
import struct
import random

def make_wav(filename, freq_func, duration, sample_rate=44100):
    with wave.open(filename, 'w') as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sample_rate)
        
        for i in range(int(sample_rate * duration)):
            t = i / float(sample_rate)
            v = freq_func(t)
            env = 1.0 - (t / duration)
            sample = int(v * env * 32767.0 * 0.8)
            sample = max(-32768, min(32767, sample))
            w.writeframesraw(struct.pack('<h', sample))

# jump (boing) - frequency sweeps up
def jump_freq(t):
    freq = 300 + 800 * t
    return math.sin(2.0 * math.pi * freq * t)

# hit (bonk) - low frequency and noise
def hit_freq(t):
    freq = 100 - 150 * t
    if freq < 20: freq = 20
    return math.sin(2.0 * math.pi * freq * t) + random.uniform(-0.2, 0.2)

# score (coin) - two quick high tones
def score_freq(t):
    freq = 987.77 if t < 0.1 else 1318.51
    return math.sin(2.0 * math.pi * freq * t)

make_wav('jump.wav', jump_freq, 0.35)
make_wav('hit.wav', hit_freq, 0.4)
make_wav('score.wav', score_freq, 0.5)
