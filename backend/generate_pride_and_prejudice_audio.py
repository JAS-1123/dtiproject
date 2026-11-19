"""Generate a synthetic narration of Chapter I of Pride and Prejudice.

The source text is the public-domain 1813 novel, Chapter I. The audio is an
original eSpeak rendering for this prototype, not a commercial audiobook.
"""
from __future__ import annotations

import json
import subprocess
import wave
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AUDIO_DIR = ROOT / "frontend" / "public" / "audio"
DATA_DIR = ROOT / "backend" / "data"
AUDIO_DIR.mkdir(parents=True, exist_ok=True)
DATA_DIR.mkdir(parents=True, exist_ok=True)

segments = [
    {
        "id": "pp1",
        "title": "A universally acknowledged truth",
        "text": (
            "It is a truth universally acknowledged, that a single man in possession "
            "of a good fortune must be in want of a wife. However little known the feelings "
            "or views of such a man may be on his first entering a neighbourhood, this truth "
            "is so well fixed in the minds of the surrounding families, that he is considered "
            "as the rightful property of some one or other of their daughters."
        ),
    },
    {
        "id": "pp2",
        "title": "A visitor at Netherfield",
        "text": (
            "My dear Mr. Bennet, said his lady to him one day, have you heard that "
            "Netherfield Park is let at last? Mr. Bennet replied that he had not. "
            "But it is, returned she; for Mrs. Long has just been here, and she told me "
            "all about it. Mr. Bennet made no answer. Do not you want to know who has "
            "taken it? cried his wife impatiently. You want to tell me, and I have no "
            "objection to hearing it. This was invitation enough."
        ),
    },
    {
        "id": "pp3",
        "title": "The new tenant is named",
        "text": (
            "Why, my dear, you must know, Mrs. Long says that Netherfield is taken by a "
            "young man of large fortune from the north of England; that he came down on "
            "Monday in a chaise and four to see the place, and was so much delighted with "
            "it that he agreed with Mr. Morris immediately; that he is to take possession "
            "before Michaelmas, and some of his servants are to be in the house by the end "
            "of next week. What is his name? Bingley."
        ),
    },
    {
        "id": "pp4",
        "title": "A wealthy bachelor",
        "text": (
            "Is he married or single? Oh, single, my dear, to be sure! A single man of "
            "large fortune; four or five thousand a-year. What a fine thing for our girls! "
            "How so? how can it affect them? My dear Mr. Bennet, replied his wife, how can "
            "you be so tiresome! You must know that I am thinking of his marrying one of them."
        ),
    },
    {
        "id": "pp5",
        "title": "Mr. Bennet teases his wife",
        "text": (
            "Is that his design in settling here? Design! nonsense, how can you talk so! "
            "But it is very likely that he may fall in love with one of them, and therefore "
            "you must visit him as soon as he comes. I see no occasion for that. You and "
            "the girls may go, or you may send them by themselves, which perhaps will be "
            "still better, for as you are as handsome as any of them, Mr. Bingley might "
            "like you the best of the party."
        ),
    },
    {
        "id": "pp6",
        "title": "The Bennet daughters",
        "text": (
            "My dear, you flatter me. I certainly have had my share of beauty, but I do "
            "not pretend to be any thing extraordinary now. When a woman has five grown "
            "up daughters, she ought to give over thinking of her own beauty. In such cases, "
            "a woman has not often much beauty to think of. But, my dear, you must indeed "
            "go and see Mr. Bingley when he comes into the neighbourhood. It is more than "
            "I engage for, I assure you."
        ),
    },
    {
        "id": "pp7",
        "title": "Lizzy and her sisters",
        "text": (
            "You are over scrupulous surely. I dare say Mr. Bingley will be very glad to "
            "see you; and I will send a few lines by you to assure him of my hearty consent "
            "to his marrying which ever he chooses of the girls; though I must throw in a "
            "good word for my little Lizzy. I desire you will do no such thing. Lizzy is not "
            "a bit better than the others; and I am sure she is not half so handsome as Jane, "
            "nor half so good humoured as Lydia. But you are always giving her the preference."
        ),
    },
    {
        "id": "pp8",
        "title": "A portrait of Mr. and Mrs. Bennet",
        "text": (
            "They have none of them much to recommend them, replied he; they are all silly "
            "and ignorant like other girls; but Lizzy has something more of quickness than "
            "her sisters. Mr. Bennet, how can you abuse your own children in such a way? "
            "You take delight in vexing me. You have no compassion on my poor nerves. "
            "You mistake me, my dear. I have a high respect for your nerves. They are my old "
            "friends. I have heard you mention them with consideration these twenty years "
            "at least. Ah! you do not know what I suffer. But I hope you will get over it, and "
            "live to see many young men of four thousand a-year come into the neighbourhood. "
            "It will be no use to us, if twenty such should come, since you will not visit them. "
            "Depend upon it, my dear, that when there are twenty, I will visit them all. "
            "Mr. Bennet was so odd a mixture of quick parts, sarcastic humour, reserve, and "
            "caprice, that the experience of three and twenty years had been insufficient to "
            "make his wife understand his character. Her mind was less difficult to develope. "
            "She was a woman of mean understanding, little information, and uncertain temper. "
            "When she was discontented she fancied herself nervous. The business of her life "
            "was to get her daughters married; its solace was visiting and news."
        ),
    },
]

sample_rate = 22050
silence_duration = 0.42
parts: list[bytes] = []
chunks = []
cursor = 0.0
for segment_index, seg in enumerate(segments):
    clip_path = AUDIO_DIR / f"_{seg['id']}.wav"
    subprocess.run(
        ["espeak", "-v", "en-gb", "-s", "148", "-p", "48", "-a", "175", "-w", str(clip_path), seg["text"]],
        check=True,
        capture_output=True,
    )
    with wave.open(str(clip_path), "rb") as clip:
        params = clip.getparams()
        frames = clip.readframes(clip.getnframes())
    if params.nchannels != 1 or params.sampwidth != 2 or params.framerate != sample_rate:
        raise RuntimeError(f"Unexpected audio format: {params}")
    duration = len(frames) / (sample_rate * 2)
    seg["start_sec"] = round(cursor, 2)
    seg["end_sec"] = round(cursor + duration, 2)
    seg["duration_sec"] = round(duration, 2)
    chunks.append(seg)
    parts.append(frames)
    if segment_index < len(segments) - 1:
        silence_frames = int(silence_duration * sample_rate)
        parts.append(b"\x00\x00" * silence_frames)
        cursor += duration + silence_duration
    else:
        cursor += duration
    clip_path.unlink(missing_ok=True)

output_audio = AUDIO_DIR / "pride_and_prejudice_chapter1.wav"
with wave.open(str(output_audio), "wb") as out:
    out.setnchannels(1)
    out.setsampwidth(2)
    out.setframerate(sample_rate)
    for part in parts:
        out.writeframes(part)

book = {
    "id": "pride-and-prejudice",
    "title": "Pride and Prejudice",
    "author": "Jane Austen",
    "genre": "Classic fiction · Public-domain excerpt",
    "description": "Chapter I: the Bennets hear that Netherfield Park has been let to a wealthy new arrival.",
    "short_title": "PRIDE &\nPREJUDICE",
    "cover_author": "JANE AUSTEN",
    "cover_style": "classic",
    "audio_url": "/audio/pride_and_prejudice_chapter1.wav",
    "duration_sec": round(cursor, 2),
    "default_position_sec": chunks[0]["end_sec"] + 0.1,
    "demo_reveal_sec": chunks[2]["end_sec"] + 0.1,
    "demo_reveal_message": "Moved to the passage where Mrs. Bennet names the new tenant.",
    "edition_note": "SYNTHETIC NARRATION · CHAPTER I EXCERPT",
    "source_title": "Pride and Prejudice (1817), Chapter I",
    "source_url": "https://en.wikisource.org/wiki/Pride_and_Prejudice_(1817)/Chapter_1",
    "source_credit": "Jane Austen, Pride and Prejudice (1813), Chapter I. Text transcribed from Wikisource; synthetic narration generated for LoreFlow using eSpeak.",
    "license_note": "The original novel is public domain. The Wikisource page identifies its transcription as CC BY-SA; see the source page for its terms.",
    "chapters": [
        {"id": "pp-ch1", "title": "Chapter I · The Bennets", "start_sec": chunks[0]["start_sec"], "end_sec": chunks[-1]["end_sec"]}
    ],
    "chunks": chunks,
}
(DATA_DIR / "pride_and_prejudice.json").write_text(json.dumps(book, indent=2, ensure_ascii=False), encoding="utf-8")
print(json.dumps({"book": book["title"], "duration_sec": book["duration_sec"], "audio_bytes": output_audio.stat().st_size, "chunks": [{k: x[k] for k in ("id", "title", "start_sec", "end_sec")} for x in chunks]}, indent=2))
