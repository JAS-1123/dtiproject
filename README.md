# LoreFlow — कथा वाचक

An audiobook companion that answers questions using only the passages that have finished playing. This presentation-ready prototype includes two selectable titles: an original short fantasy story and a synthetic narration of Chapter I of Jane Austen's *Pride and Prejudice*.

## What is included

- **React + Vite frontend** with a library selector, player, transcript passage map, free-form question composer, source timestamps, voice input and browser text-to-speech.
- **FastAPI backend** serving the frontend, book metadata and question-answering endpoints.
- **Python AI/ML module** for timestamp-restricted passage selection, retrieval, future-only question checks and Grok-powered answers.
- **xAI Grok Responses API** integration. The secret key stays on the server.
- **Two demo books:**
  - *Pride and Prejudice* by Jane Austen — Chapter I excerpt, synthetic eSpeak narration, eight timestamped passages. This is the default title.
  - *The Glass Citadel* — original LoreFlow sample story.
- **Tests** for spoiler boundaries and Grok prompt contents.

## Famous-book excerpt and attribution

The prototype includes Chapter I of *Pride and Prejudice* by Jane Austen (first published in 1813). The text is based on the Wikisource transcription of [Pride and Prejudice (1817), Chapter 1](https://en.wikisource.org/wiki/Pride_and_Prejudice_(1817)/Chapter_1), which attributes the transcription to a CC BY-SA-licensed Wikisource page. Project Gutenberg also lists the original novel as public domain in the United States: [eBook 1342](https://www.gutenberg.org/ebooks/1342). Please check the law that applies in your jurisdiction before reusing source material outside this educational prototype.

The bundled WAV is **new synthetic narration generated for this project using eSpeak**. It is not copied from a commercial audiobook or an existing performance. The text is separated into eight timestamped segments so the demo can block questions about Mr. Bingley before his name is heard, then answer once the relevant passage has played.

## Quick presentation flow

1. The app opens on *Pride and Prejudice*, just after the opening paragraph has played.
2. Ask: `Who is Mr. Bingley?` — the companion should say that the story has not introduced him in the passages heard so far.
3. Ask: `What does the opening suggest about a wealthy unmarried man?` — it can answer from the opening paragraph.
4. Click **Jump to the reveal**. The audio position moves to the passage where Mr. Bingley's name is introduced.
5. Ask `Who is Mr. Bingley?` again — it can now answer with the source passage and timestamp.
6. Switch to *The Glass Citadel* from the book selector to show the original fantasy sample too.

## Requirements

- Python 3.10 or newer
- Node.js 20 or newer
- An xAI API key for live Grok-generated responses (optional for local fallback; required for the Grok-powered experience)

## Run locally

From the project root:

### 1. Configure the Grok API key

Copy `.env.example` to `.env` for reference. The application does not automatically load `.env`, so export the variables in your shell before starting the backend:

```bash
export XAI_API_KEY="your_xai_api_key"
export XAI_MODEL="grok-4.7"
```

Never commit a real API key, place it in React code, or use a `VITE_` variable for it.

### 2. Start FastAPI

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn backend.main:app --reload --port 8000
```

### 3. Start React in a second terminal

```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173`. Vite proxies `/api` and `/audio` to FastAPI at `http://localhost:8000`.

## Deploy on Render with Grok

The repository includes a `Dockerfile` and `render.yaml`. Deploy it as a Render Blueprint so Render builds the frontend and Python API into one web service.

1. Create a new GitHub repository named **`dtiproject`**.
2. Extract this project ZIP. Upload/push the **contents of the `dtiproject/` folder** to the root of the GitHub repository. Confirm that `Dockerfile`, `render.yaml`, `backend/`, `frontend/`, and `requirements.txt` are visible at the repository's top level.
3. Go to [Render Dashboard](https://dashboard.render.com/) and choose **New → Blueprint**.
4. Connect GitHub if asked, then select the `dtiproject` repository and its `main` branch.
5. Render should detect the root-level `render.yaml`. It requests a value for the secret `XAI_API_KEY` because the YAML marks it `sync: false`. Paste the key created in the [xAI Console](https://console.x.ai/) into Render's secret field; never put the real key in GitHub. If you skip that prompt, add `XAI_API_KEY` later under the service's **Environment** settings.
6. The Blueprint sets `XAI_MODEL=grok-4.7` and `DEFAULT_BOOK_ID=pride-and-prejudice`. Review the proposed service and click **Apply** / **Deploy Blueprint**.
7. Wait for the deployment to show **Live**.
8. Open the Render service URL. Visit `/api/health`; the JSON should report `"answer_engine": "xAI Grok"` when the key is configured.
9. Test the free-form Q&A with the presentation flow above.

If Render does not detect the Dockerfile, check that **Root Directory** is blank (the Dockerfile is at repository root), **Dockerfile Path** is `./Dockerfile`, and **Docker Context Directory** is `.`.

### Verify Grok configuration

- `XAI_API_KEY`: required for live Grok answers; add it in Render Environment settings.
- `XAI_MODEL`: defaults to `grok-4.7` in `render.yaml`.
- The backend calls the official xAI [Responses API](https://docs.x.ai/developers/rest-api-reference/inference/responses) from Python. The default `grok-4.7` model is listed in the [xAI model documentation](https://docs.x.ai/developers/models/grok-4.7). The key is never sent to the frontend.
- xAI API usage is billed separately by xAI. Make sure the API account has billing/credits enabled.
- If the API call fails, LoreFlow logs a server-side warning and falls back to local timestamped retrieval so the prototype remains usable. The `/api/health` endpoint reports whether an API key is configured; it does not prove the key has remaining credits or that a live request will succeed.

## Run tests

From the project root, with the virtual environment active:

```bash
python -m unittest discover -s tests -v
```

To regenerate the bundled *Pride and Prejudice* synthetic narration (requires the `espeak` command-line program):

```bash
python backend/generate_pride_and_prejudice_audio.py
```

## API endpoints

| Method | Endpoint | Purpose |
|---|---|---|
| `GET` | `/api/health` | Health and configured answer engine |
| `GET` | `/api/books` | List available titles and default book ID |
| `GET` | `/api/book?book_id=pride-and-prejudice` | Book metadata and passage timings; passage text remains server-side |
| `POST` | `/api/ask` | Free-form, spoiler-aware question answering for a selected book |
| `POST` | `/api/recap` | Recap of completed passages for a selected book |

Example request:

```json
{
  "book_id": "pride-and-prejudice",
  "question": "Who is Mr. Bingley?",
  "position_sec": 22.3,
  "context_questions": []
}
```

## Project structure

```text
dtiproject/
├── backend/
│   ├── data/
│   │   ├── book.json                         # The Glass Citadel
│   │   └── pride_and_prejudice.json          # Chapter I excerpt and timings
│   ├── aiml.py                               # retrieval, future boundary and Grok call
│   ├── main.py                               # FastAPI multi-book API
│   └── generate_pride_and_prejudice_audio.py # reproducible synthetic narration generator
├── frontend/
│   ├── public/audio/
│   │   ├── loreflow_sample.wav
│   │   └── pride_and_prejudice_chapter1.wav
│   └── src/                                  # React UI and styling
├── tests/
├── Dockerfile
├── render.yaml
├── requirements.txt
└── README.md
```

## Prototype limitations

- Only Chapter I excerpt is bundled for *Pride and Prejudice*, not the entire novel.
- The audio is synthetic narration. It is not an official audiobook or a professional human reading.
- Transcript-to-audio alignment is precomputed for these sample assets; general-purpose automatic alignment is not included.
- Browser voice input and spoken answers use Web Speech APIs. Chrome or Edge generally has the broadest support, but available voices depend on the visitor's device.
- Spoiler detection is a prototype heuristic over the server-side passage index. For a production release, validate paraphrases and progress claims, add user accounts and licensed content ingestion, and strengthen retrieval/reranking.
# dtiproject
