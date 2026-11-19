"""Generate the small, original demonstration audiobook used by LoreFlow."""

import json
import subprocess
import wave
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AUDIO_DIR = ROOT / "frontend" / "public" / "audio"
DATA_DIR = ROOT / "backend" / "data"
AUDIO_DIR.mkdir(parents=True, exist_ok=True)
DATA_DIR.mkdir(parents=True, exist_ok=True)

# Each paragraph is rendered separately so its real audio boundaries can be
# stored alongside the transcript. This is demo material, not a commercial book.
segments = [
    {
        "id": "p1",
        "title": "The city at dusk",
        "text": "At the edge of the Amber Sea stood the city of Veyra. Every evening, its glass towers caught the last light, while the old northern wall disappeared into blue mist. Tonight, the bells rang thirteen times. No one in Veyra could remember hearing the thirteenth bell before.",
    },
    {
        "id": "p2",
        "title": "Captain Mira",
        "text": "Captain Mira stood above the western gate, watching the streets below. She commanded the city's western guard and had protected Veyra for twelve years. Calm, observant, and difficult to surprise, Mira trusted preparation more than promises. The guards followed her because she never asked them to take a risk she would not take herself.",
    },
    {
        "id": "p3",
        "title": "The archivist's key",
        "text": "A thin man hurried up the steps. His name was Ilya, the royal archivist, keeper of the city's oldest records. In his hand was a brass key marked with a small crescent. He told Mira that the key had been missing from the archive for a hundred years, and that someone had returned it without leaving a name.",
    },
    {
        "id": "p4",
        "title": "A sealed map",
        "text": "Mira unfolded a map sealed with blue wax. It showed the northern gate, a passage that had been closed since the founding of Veyra. Ilya wanted to open it immediately. Mira refused. The map was incomplete, and the old records warned that the gate should never be opened by a single person.",
    },
    {
        "id": "p5",
        "title": "The hidden observatory",
        "text": "At the first light of dawn, Mira fitted the brass key into a hidden lock beneath the northern arch. The stone doors moved apart, revealing a staircase descending beneath the city. Beyond the north gate lay an underground observatory, built by Veyra's founders to watch a star that appeared only once every hundred years.",
    },
    {
        "id": "p6",
        "title": "The star compass",
        "text": "At the bottom of the stairs, a silver instrument hovered above a circular table. Ilya called it the star compass. Its needle pointed not north, but toward the dark sea. Mira understood why the old warning had survived: the observatory was not a weapon or a treasure room. It was a signal, waiting for the star to return.",
    },
]

# Use the same sample rate and channel count for every clip, then concatenate.
clips = []
with wave.open(str(AUDIO_DIR / "_combined.wav"), "wb") as out:
    out.setnchannels(1)
    out.setsampwidth(2)
    out.setframerate(22050)

    cursor = 0.0
    chunks = []
    for seg in segments:
        clip_path = AUDIO_DIR / f"_{seg['id']}.wav"
        subprocess.run(
            ["espeak", "-v", "en-us", "-s", "142", "-p", "42", "-a", "175", "-w", str(clip_path), seg["text"]],
            check=True,
            capture_output=True,
        )
        with wave.open(str(clip_path), "rb") as clip:
            params = clip.getparams()
            frames = clip.readframes(clip.getnframes())
        if params.nchannels != 1 or params.sampwidth != 2 or params.framerate != 22050:
            raise RuntimeError(f"Unexpected audio format in {clip_path}: {params}")
        duration = len(frames) / (params.framerate * params.nchannels * params.sampwidth)
        seg["start_sec"] = round(cursor, 2)
        seg["end_sec"] = round(cursor + duration, 2)
        seg["duration_sec"] = round(duration, 2)
        chunks.append(frames)
        # Add a short pause between paragraphs to make the chapter boundaries audible.
        silence_frames = int(0.35 * 22050)
        silence = b"\x00\x00" * silence_frames
        chunks.append(silence)
        cursor += duration + 0.35
        clip_path.unlink(missing_ok=True)

    for frames in chunks:
        out.writeframes(frames)

combined = AUDIO_DIR / "loreflow_sample.wav"
# Rename the assembled WAV to the public sample filename.
(AUDIO_DIR / "_combined.wav").replace(combined)

book = {
    "id": "the-glass-citadel",
    "title": "The Glass Citadel",
    "author": "LoreFlow Demo Studio",
    "genre": "Fantasy · Short story",
    "description": "A city of glass, a missing key, and a gate that should never be opened.",
    "audio_url": "/audio/loreflow_sample.wav",
    "duration_sec": round(cursor - 0.35, 2),
    "chapters": [
        {"id": "ch1", "title": "The Thirteenth Bell", "start_sec": segments[0]["start_sec"], "end_sec": segments[2]["end_sec"]},
        {"id": "ch2", "title": "The Northern Gate", "start_sec": segments[3]["start_sec"], "end_sec": segments[5]["end_sec"]},
    ],
    "chunks": segments,

}
(DATA_DIR / "book.json").write_text(json.dumps(book, indent=2), encoding="utf-8")
print(json.dumps({"duration_sec": book["duration_sec"], "chunks": [{k: s[k] for k in ("id", "start_sec", "end_sec", "duration_sec")} for s in segments]}, indent=2))
