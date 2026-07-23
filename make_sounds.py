"""Generate simple WAV sound effects for the pet (no external assets).
Uses stdlib wave + struct + math to synthesize cute sounds."""
import wave, struct, math, os

HERE = os.path.dirname(os.path.abspath(__file__))
SOUND_DIR = os.path.join(HERE, "poses", "sounds")
os.makedirs(SOUND_DIR, exist_ok=True)

SR = 22050  # sample rate

def write_wav(path, samples):
    with wave.open(path, "w") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(b"".join(struct.pack("<h", int(s * 32767)) for s in samples))

def bark():
    """A cute 'wang' sound — short bark with pitch sweep."""
    dur = 0.18
    n = int(SR * dur)
    out = []
    for i in range(n):
        t = i / SR
        env = math.exp(-t * 8) * (1 - math.exp(-t * 50))
        freq = 400 + 200 * math.exp(-t * 5)
        s = 0.5 * env * math.sin(2 * math.pi * freq * t)
        s += 0.2 * env * math.sin(2 * math.pi * freq * 2 * t)
        out.append(s)
    write_wav(os.path.join(SOUND_DIR, "bark.wav"), out)

def eat():
    """Chewing sound — two short low thumps."""
    out = []
    for beat in range(2):
        dur = 0.12
        n = int(SR * dur)
        for i in range(n):
            t = i / SR
            env = math.exp(-t * 15)
            freq = 120 + 40 * math.exp(-t * 10)
            s = 0.6 * env * math.sin(2 * math.pi * freq * t)
            out.append(s)
        # gap
        out.extend([0] * int(SR * 0.05))
    write_wav(os.path.join(SOUND_DIR, "eat.wav"), out)

def sleep():
    """Soft snore — low frequency wobble."""
    dur = 0.5
    n = int(SR * dur)
    out = []
    for i in range(n):
        t = i / SR
        env = 0.4 * (1 - math.exp(-t * 3)) * math.exp(-t * 2.5)
        wobble = 1 + 0.3 * math.sin(2 * math.pi * 3 * t)
        s = env * wobble * math.sin(2 * math.pi * 80 * t)
        out.append(s)
    write_wav(os.path.join(SOUND_DIR, "sleep.wav"), out)

def pet():
    """Happy squeak — short high chirp."""
    dur = 0.12
    n = int(SR * dur)
    out = []
    for i in range(n):
        t = i / SR
        env = math.exp(-t * 12)
        freq = 800 + 300 * t / dur
        s = 0.35 * env * math.sin(2 * math.pi * freq * t)
        out.append(s)
    write_wav(os.path.join(SOUND_DIR, "pet.wav"), out)

def bounce():
    """Boing — wall bounce."""
    dur = 0.15
    n = int(SR * dur)
    out = []
    for i in range(n):
        t = i / SR
        env = math.exp(-t * 8)
        freq = 300 - 100 * t / dur
        s = 0.4 * env * math.sin(2 * math.pi * freq * t)
        out.append(s)
    write_wav(os.path.join(SOUND_DIR, "bounce.wav"), out)

bark(); print("bark.wav")
eat();  print("eat.wav")
sleep();print("sleep.wav")
pet();  print("pet.wav")
bounce();print("bounce.wav")
print("done")
