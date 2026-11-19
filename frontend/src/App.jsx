import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import {
  BookOpen, Bookmark, Check, ChevronRight, CircleHelp,
  Clock3, Headphones, LockKeyhole, Mic, Pause, Play, RotateCcw,
  Send, Settings2, ShieldCheck, Sparkles, Volume2, VolumeX,
} from 'lucide-react'

function fmtTime(value = 0) {
  const s = Math.max(0, Math.floor(value))
  return `${Math.floor(s / 60).toString().padStart(2, '0')}:${(s % 60).toString().padStart(2, '0')}`
}

function App() {
  const audioRef = useRef(null)
  const chatEndRef = useRef(null)
  const recognitionRef = useRef(null)
  const resumeAfterAssistantRef = useRef(false)
  const [book, setBook] = useState(null)
  const [books, setBooks] = useState([])
  const [position, setPosition] = useState(0)
  const [isPlaying, setIsPlaying] = useState(false)
  const [isMuted, setIsMuted] = useState(false)
  const [question, setQuestion] = useState('')
  const [busy, setBusy] = useState(false)
  const [listening, setListening] = useState(false)
  const [messages, setMessages] = useState([
    {
      role: 'assistant',
      kind: 'welcome',
      text: "I'm following along. Ask me about a character, a place, or anything you've heard so far. I'll keep future chapters out of the conversation.",
    },
  ])
  const [notice, setNotice] = useState('')
  const [speechSupported, setSpeechSupported] = useState(false)
  const [engineLabel, setEngineLabel] = useState('CONNECTING TO COMPANION')

  const duration = book?.duration_sec ?? 131
  const progress = Math.min(100, (position / duration) * 100)
  const heardChunks = useMemo(
    () => (book?.chunks ?? []).filter((chunk) => chunk.end_sec <= position),
    [book, position],
  )
  const heardIds = useMemo(() => new Set(heardChunks.map((chunk) => chunk.id)), [heardChunks])

  const loadBook = async (bookId) => {
    if (!bookId) return
    if (audioRef.current) audioRef.current.pause()
    if ('speechSynthesis' in window) window.speechSynthesis.cancel()
    setIsPlaying(false)
    setNotice('Loading book…')
    try {
      const response = await fetch(`/api/book?book_id=${encodeURIComponent(bookId)}`)
      if (!response.ok) throw new Error('Could not load this book')
      const data = await response.json()
      setBook(data)
      setPosition(Number(data.default_position_sec ?? 0))
      setMessages([{
        role: 'assistant',
        kind: 'welcome',
        text: `I'm following ${data.title}. Ask me about anything you've heard so far. I'll keep future passages out of the conversation.`,
      }])
      setNotice(`${data.title} is ready to play.`)
    } catch (error) {
      setNotice(error.message || 'Could not load the selected book.')
    }
  }

  useEffect(() => {
    fetch('/api/health')
      .then((response) => response.ok ? response.json() : null)
      .then((data) => {
        if (data?.answer_engine === 'xAI Grok') setEngineLabel('GROK + STORY RETRIEVAL')
        else if (data?.answer_engine) setEngineLabel('LOCAL STORY RETRIEVAL')
      })
      .catch(() => setEngineLabel('BACKEND UNAVAILABLE'))

    fetch('/api/books')
      .then((response) => {
        if (!response.ok) throw new Error('Could not load the book library')
        return response.json()
      })
      .then((data) => {
        setBooks(data.books ?? [])
        return loadBook(data.default_book_id || data.books?.[0]?.id)
      })
      .catch(() => setNotice('Start the backend server to load the book library. See the README for setup.'))

    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition
    setSpeechSupported(Boolean(SpeechRecognition))
  }, [])

  useEffect(() => {
    const audio = audioRef.current
    if (!audio) return undefined
    const sync = () => setPosition(audio.currentTime || 0)
    const onPlay = () => setIsPlaying(true)
    const onPause = () => setIsPlaying(false)
    audio.addEventListener('timeupdate', sync)
    audio.addEventListener('play', onPlay)
    audio.addEventListener('pause', onPause)
    audio.addEventListener('ended', onPause)
    return () => {
      audio.removeEventListener('timeupdate', sync)
      audio.removeEventListener('play', onPlay)
      audio.removeEventListener('pause', onPause)
      audio.removeEventListener('ended', onPause)
    }
  }, [book])

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' })
  }, [messages, busy])

  const seek = useCallback((nextPosition) => {
    const bounded = Math.max(0, Math.min(duration, Number(nextPosition)))
    setPosition(bounded)
    if (audioRef.current) audioRef.current.currentTime = bounded
  }, [duration])

  const togglePlayback = async () => {
    const audio = audioRef.current
    if (!audio) return
    if (audio.paused) {
      try {
        await audio.play()
      } catch {
        setNotice('Audio playback was blocked by the browser. Press play once more to start.')
      }
    } else {
      audio.pause()
    }
  }

  const speak = (text) => {
    if (!('speechSynthesis' in window)) {
      setNotice('Speech synthesis is not available in this browser. Try Chrome or Edge.')
      return
    }
    window.speechSynthesis.cancel()
    const audio = audioRef.current
    const shouldResume = resumeAfterAssistantRef.current || Boolean(audio && !audio.paused)
    resumeAfterAssistantRef.current = false
    if (audio && !audio.paused) audio.pause()
    const utterance = new SpeechSynthesisUtterance(text)
    utterance.rate = 0.96
    utterance.pitch = 0.92
    utterance.onend = () => {
      if (shouldResume && audio) audio.play().catch(() => {})
    }
    utterance.onerror = () => {
      if (shouldResume && audio) audio.play().catch(() => {})
    }
    window.speechSynthesis.speak(utterance)
  }

  const addMessage = (message) => setMessages((previous) => [...previous, message])

  const ask = async (rawQuestion) => {
    const text = (rawQuestion ?? question).trim()
    if (!text || busy) return
    setQuestion('')
    addMessage({ role: 'user', text })
    if (audioRef.current && !audioRef.current.paused) {
      resumeAfterAssistantRef.current = true
      audioRef.current.pause()
    }
    setBusy(true)
    setNotice('')
    try {
      const contextQuestions = messages
        .filter((message) => message.role === 'user')
        .map((message) => message.text)
        .slice(-4)
      const response = await fetch('/api/ask', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ book_id: book?.id, question: text, position_sec: position, context_questions: contextQuestions }),
      })
      if (!response.ok) throw new Error('The companion could not answer. Please try again.')
      const result = await response.json()
      addMessage({ role: 'assistant', text: result.answer, result })
    } catch (error) {
      addMessage({ role: 'assistant', text: error.message || 'Connection error. Check that the backend is running.' })
    } finally {
      setBusy(false)
    }
  }

  const startVoiceInput = () => {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition
    if (!SpeechRecognition) {
      setNotice('Voice input is not supported in this browser. You can type your question instead.')
      return
    }
    if (listening) {
      recognitionRef.current?.stop()
      setListening(false)
      return
    }
    const recognition = new SpeechRecognition()
    recognition.lang = 'en-IN'
    recognition.interimResults = false
    recognition.maxAlternatives = 1
    recognition.onresult = (event) => {
      const transcript = event.results?.[0]?.[0]?.transcript ?? ''
      setQuestion(transcript)
      setListening(false)
    }
    recognition.onerror = () => {
      setListening(false)
      setNotice('I could not hear that clearly. Try again or type your question.')
    }
    recognition.onend = () => setListening(false)
    recognitionRef.current = recognition
    recognition.start()
    setListening(true)
    setNotice('Listening for your question…')
  }

  const jumpToReveal = () => {
    const revealPosition = Number(book?.demo_reveal_sec ?? duration)
    seek(Math.min(duration, revealPosition))
    setNotice(book?.demo_reveal_message || 'Moved to the reveal passage.')
  }

  const jumpToStart = () => {
    seek(0)
    setMessages([{ role: 'assistant', kind: 'welcome', text: `We are back at the beginning of ${book?.title ?? 'the story'}. I will only use passages as they are heard.` }])
  }

  return (
    <div className="app-shell">
      <header className="topbar">
        <a className="brand" href="#top" aria-label="LoreFlow home">
          <span className="brand-mark">क</span>
          <span className="brand-copy"><strong>LoreFlow</strong><small>कथा वाचक</small></span>
        </a>
        <div className="topbar-center"><span className="live-dot" /> LISTENING COMPANION <span className="topbar-divider" /> <span className="prototype-pill">PRESENTATION PROTOTYPE</span></div>
        <button className="icon-button settings-button" title="Prototype settings" onClick={() => setNotice('Demo mode · local sample story · timestamp-filtered retrieval')}><Settings2 size={18} /></button>
      </header>

      <main id="top" className="main-wrap">
        <section className="intro-row">
          <div>
            <div className="eyebrow"><span>YOUR STORY, STILL IN REACH</span><span className="eyebrow-line" /></div>
            <h1>Stay inside the story.</h1>
            <p className="intro-copy">A little context, exactly when you need it. No searching. No spoilers.</p>
          </div>
          <div className="privacy-note"><ShieldCheck size={17} /><span>Answers are limited to<br /><strong>passages you've heard</strong></span></div>
        </section>

        <div className="workspace-grid">
          <section className="listen-column">
            <article className="player-card">
              <div className="player-topline">
                <span className="section-kicker"><Headphones size={14} /> NOW PLAYING</span>
                <div className="player-top-actions">
                  <span className="sample-tag">{book?.edition_note || 'LOREFLOW ORIGINAL'}</span>
                  <label className="book-select-wrap" aria-label="Choose a book">
                    <BookOpen size={13} />
                    <select className="book-select" value={book?.id ?? ''} onChange={(event) => loadBook(event.target.value)} disabled={!books.length}>
                      {books.map((item) => <option key={item.id} value={item.id}>{item.title}</option>)}
                    </select>
                  </label>
                </div>
              </div>
              <div className="book-layout">
                <div className={`book-cover ${book?.cover_style === 'classic' ? 'classic-cover' : ''}`} aria-label={`${book?.title ?? 'Book'} cover art`}>
                  <div className="cover-sun" /><div className="cover-arch" /><div className="cover-tower cover-tower-one" /><div className="cover-tower cover-tower-two" />
                  <div className="cover-title">{book?.short_title ?? 'THE GLASS\nCITADEL'}</div><div className="cover-author">{book?.cover_author ?? 'A LOREFLOW ORIGINAL'}</div>
                </div>
                <div className="book-info">
                  <div className="book-genre">{book?.genre ?? 'FANTASY · SHORT STORY'}</div>
                  <h2>{book?.title ?? 'Loading your book…'}</h2>
                  <p className="book-author">{book?.author ?? 'LoreFlow Demo Studio'}</p>
                  <p className="book-description">{book?.description ?? 'Choose a title from the library to begin.'}</p>
                  <div className="book-stats"><span><Clock3 size={14} /> {Math.ceil(duration / 60)} min</span><span><BookOpen size={14} /> {book?.chapters?.length ?? 0} chapter{book?.chapters?.length === 1 ? '' : 's'}</span></div>
                </div>
              </div>

              <audio
                ref={audioRef}
                src={book?.audio_url ?? '/audio/loreflow_sample.wav'}
                preload="metadata"
                onLoadedMetadata={() => {
                  if (audioRef.current && audioRef.current.currentTime === 0) {
                    audioRef.current.currentTime = Number(book?.default_position_sec ?? 0)
                    setPosition(Number(book?.default_position_sec ?? 0))
                  }
                }}
              />

              <div className="progress-section">
                <div className="progress-top"><span className="progress-label">YOUR LISTENING POSITION</span><span className="position-value">{fmtTime(position)} <span>/ {fmtTime(duration)}</span></span></div>
                <input className="timeline" aria-label="Audiobook position" type="range" min="0" max={duration} step="0.25" value={position} style={{ '--progress': `${progress}%` }} onChange={(event) => seek(event.target.value)} />
                <div className="timeline-labels"><span>Beginning</span><span>{Math.round(progress)}% heard</span><span>End</span></div>
              </div>

              <div className="player-controls">
                <button className="plain-control" onClick={jumpToStart} title="Restart story"><RotateCcw size={17} /><span>Restart</span></button>
                <button className="round-play" onClick={togglePlayback} aria-label={isPlaying ? 'Pause audiobook' : 'Play audiobook'}>{isPlaying ? <Pause size={21} fill="currentColor" /> : <Play size={21} fill="currentColor" />}</button>
                <button className="plain-control" onClick={() => seek(position + 10)} title="Skip forward 10 seconds"><span>+10 sec</span><ChevronRight size={17} /></button>
                <button className="volume-control" onClick={() => { if (audioRef.current) audioRef.current.muted = !isMuted; setIsMuted((v) => !v) }} title={isMuted ? 'Unmute' : 'Mute'}>{isMuted ? <VolumeX size={18} /> : <Volume2 size={18} />}</button>
              </div>
              <div className="demo-jump-row"><span>For the live demo</span><button onClick={jumpToReveal}>Jump to the reveal <ChevronRight size={14} /></button><button onClick={jumpToStart}>Start over</button></div>
            </article>

            <article className="transcript-card">
              <div className="card-heading"><div><span className="section-kicker">STORY MAP</span><h3>Where you are in the story</h3></div><span className="heard-count">{heardChunks.length} / {book?.chunks?.length ?? 6} passages heard</span></div>
              <div className="story-map">
                {(book?.chunks ?? []).map((chunk, index) => {
                  const heard = heardIds.has(chunk.id)
                  const current = !heard && position >= chunk.start_sec
                  const locked = !heard
                  return (
                    <button className={`story-row ${heard ? 'is-heard' : 'is-locked'} ${current ? 'is-current' : ''}`} key={chunk.id} onClick={() => seek(chunk.start_sec)}>
                      <span className="story-marker">{heard ? <Check size={13} /> : <LockKeyhole size={12} />}</span>
                      <span className="story-row-copy"><strong>{heard ? chunk.title : current ? 'Currently listening' : 'Future passage'}</strong><small>{heard ? 'Available to LoreFlow' : 'Not available yet'}</small></span>
                      <span className="story-time">{fmtTime(chunk.start_sec)}</span>
                    </button>
                  )
                })}
              </div>
              <div className="horizon-note"><ShieldCheck size={16} /><span><strong>Story boundary active.</strong> Future passages are excluded from answer retrieval.</span></div>
            </article>
          </section>

          <section className="assistant-card">
            <div className="assistant-header">
              <div className="assistant-avatar"><Sparkles size={19} /></div>
              <div className="assistant-heading"><h2>Your story companion</h2><span><span className="online-dot" /> Ready when you are</span></div>
              <button className="icon-button bookmark-button" title="Notebook preview" onClick={() => setNotice('Notebook is planned for the next prototype milestone.')}><Bookmark size={18} /></button>
            </div>
            <div className="assistant-boundary"><ShieldCheck size={16} /><span>Only using what you've heard up to <strong>{fmtTime(position)}</strong></span><span className="boundary-dot" /></div>

            <div className="conversation" aria-live="polite">
              {messages.map((message, index) => (
                <div className={`message-row ${message.role}`} key={`${index}-${message.role}`}>
                  {message.role === 'assistant' && <div className="message-avatar"><Sparkles size={14} /></div>}
                  <div className="message-content">
                    <div className={`message-bubble ${message.result?.spoiler_blocked ? 'spoiler-bubble' : ''}`}>
                      {message.result?.spoiler_blocked && <div className="spoiler-label"><LockKeyhole size={12} /> SPOILER PREVENTED</div>}
                      {message.text}
                    </div>
                    {message.result?.sources?.length > 0 && (
                      <div className="source-area">
                        <div className="source-heading"><span>GROUNDED IN HEARD PASSAGES</span><span>{message.result.mode}</span></div>
                        {message.result.sources.slice(0, 2).map((source) => (
                          <button className="source-chip" key={source.id} onClick={() => seek(source.start_sec)} title="Jump to source passage">
                            <span className="source-play"><Play size={9} fill="currentColor" /></span><span>{source.title}</span><time>{fmtTime(source.start_sec)}</time>
                          </button>
                        ))}
                      </div>
                    )}
                    {message.role === 'assistant' && message.result?.can_answer && <button className="speak-answer" onClick={() => speak(message.text)}><Volume2 size={13} /> Hear answer</button>}
                  </div>
                </div>
              ))}
              {busy && <div className="message-row assistant"><div className="message-avatar"><Sparkles size={14} /></div><div className="typing-bubble"><i /><i /><i /> <span>Checking the passages you've heard</span></div></div>}
              <div ref={chatEndRef} />
            </div>

            <form className="composer" onSubmit={(event) => { event.preventDefault(); ask() }}>
              <input value={question} onChange={(event) => setQuestion(event.target.value)} placeholder="Ask anything about the story you have heard…" aria-label="Ask LoreFlow a question" maxLength={1000} />
              <button type="button" className={`mic-button ${listening ? 'recording' : ''}`} onClick={startVoiceInput} title={speechSupported ? 'Ask by voice' : 'Voice input not supported'}><Mic size={17} /></button>
              <button type="submit" className="send-button" disabled={!question.trim() || busy} aria-label="Send question"><Send size={16} /></button>
            </form>
            <div className="composer-foot"><span><CircleHelp size={12} /> Ask freely. Answers use only completed passages.</span><span>{engineLabel}</span></div>
          </section>
        </div>

        <footer className="footer"><span>LOREFLOW <b>•</b> कथा वाचक</span><span>Context without breaking the story.</span><span className="footer-right">{book?.source_url ? <a href={book.source_url} target="_blank" rel="noreferrer">TEXT SOURCE</a> : null}<Headphones size={14} /> SPOILER-SAFE BY DESIGN</span></footer>
      </main>

      {notice && <div className="toast" role="status"><span>{notice}</span><button onClick={() => setNotice('')} aria-label="Dismiss notice">×</button></div>}
    </div>
  )
}

export default App
