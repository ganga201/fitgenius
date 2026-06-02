'use client'
import { useState, useRef, useEffect } from 'react'
import { useUser, UserButton } from '@clerk/nextjs'
import axios from 'axios'

interface Message {
  role: 'user' | 'assistant'
  content: string
  sources?: string[]
  intents?: string[]
}

const SUGGESTIONS = [
  "What's the target heart rate during cardio?",
  "How many days per week should I train?",
  "I have a knee injury — what's safe?",
  "How does alcohol affect my fitness?",
]

const INTENT_CONFIG: Record<string, { label: string; color: string; bg: string }> = {
  injury:    { label: '🩹 Injury',    color: '#ef4444', bg: 'rgba(239,68,68,0.08)'  },
  nutrition: { label: '🥗 Nutrition', color: '#22c55e', bg: 'rgba(34,197,94,0.08)'  },
  fitness:   { label: '💪 Fitness',   color: '#3b82f6', bg: 'rgba(59,130,246,0.08)' },
}

export default function Home() {
  const { user, isLoaded } = useUser()
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [quota, setQuota] = useState<number | null>(null)
  const [quotaMax, setQuotaMax] = useState(30)
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, loading])

  // Fetch current quota when user loads
  useEffect(() => {
    if (user?.id) {
      fetchQuota()
    }
  }, [user?.id])

  async function fetchQuota() {
    try {
      const res = await axios.get(
        `${process.env.NEXT_PUBLIC_API_URL}/quota/${user?.id}`
      )
      setQuota(res.data.remaining)
      setQuotaMax(res.data.limit)
    } catch {
      setQuota(30) // fallback
    }
  }

  async function sendMessage(text?: string) {
    const userMessage = (text || input).trim()
    if (!userMessage || loading || quota === 0 || !user?.id) return

    setInput('')
    setLoading(true)

    const newMessages: Message[] = [...messages, {
      role: 'user', content: userMessage
    }]
    setMessages(newMessages)

    const history = messages.slice(1).slice(-6).map(m => ({
      role: m.role, content: m.content
    }))

    try {
      const res = await axios.post(
        `${process.env.NEXT_PUBLIC_API_URL}/chat`,
        {
          message: userMessage,
          user_id: user.id,        // ← real Clerk user ID
          session_id: user.id,     // ← same for quota tracking
          history
        }
      )

      setMessages(prev => [...prev, {
        role: 'assistant',
        content: res.data.response,
        sources: res.data.sources || [],
        intents: res.data.intents || []
      }])

      // Update quota from backend response
      if (res.data.quota_remaining !== undefined) {
        setQuota(res.data.quota_remaining)
      }

    } catch (e: any) {
      if (e.response?.status === 429) {
        setMessages(prev => [...prev, {
          role: 'assistant',
          content: 'You have used all your questions for this period. Please contact your gym to continue.',
          sources: [], intents: []
        }])
        setQuota(0)
      } else {
        setMessages(prev => [...prev, {
          role: 'assistant',
          content: 'Something went wrong. Please try again.',
          sources: [], intents: []
        }])
      }
    }
    setLoading(false)
  }

  function handleKey(e: React.KeyboardEvent) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      sendMessage()
    }
  }

  const quotaNum = quota ?? 30
  const quotaPct = (quotaNum / quotaMax) * 100
  const quotaHue = Math.round((quotaPct / 100) * 120)

  // Show loading while Clerk initializes
  if (!isLoaded) {
    return (
      <div style={{
        height: '100vh', background: '#0a0a0f',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        color: 'rgba(255,255,255,0.4)', fontFamily: 'sans-serif'
      }}>
        Loading...
      </div>
    )
  }

  return (
    <>
      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=Syne:wght@400;600;700;800&family=DM+Sans:wght@300;400;500&display=swap');
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body { font-family: 'DM Sans', sans-serif; background: #0a0a0f; color: #e8e8f0; height: 100vh; overflow: hidden; }
        .app { display: flex; flex-direction: column; height: 100vh; max-width: 860px; margin: 0 auto; position: relative; }
        .app::before { content: ''; position: fixed; top: -200px; left: 50%; transform: translateX(-50%); width: 600px; height: 600px; background: radial-gradient(circle, rgba(99,102,241,0.12) 0%, transparent 70%); pointer-events: none; z-index: 0; }
        .header { display: flex; align-items: center; justify-content: space-between; padding: 20px 28px 16px; border-bottom: 1px solid rgba(255,255,255,0.06); backdrop-filter: blur(20px); background: rgba(10,10,15,0.8); position: relative; z-index: 10; flex-shrink: 0; }
        .logo-area { display: flex; align-items: center; gap: 12px; }
        .logo-icon { width: 40px; height: 40px; border-radius: 12px; background: linear-gradient(135deg, #6366f1, #8b5cf6); display: flex; align-items: center; justify-content: center; font-size: 20px; box-shadow: 0 0 20px rgba(99,102,241,0.4); }
        .logo-text { font-family: 'Syne', sans-serif; font-weight: 800; font-size: 20px; letter-spacing: -0.5px; background: linear-gradient(135deg, #fff 40%, #a5b4fc); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }
        .logo-sub { font-size: 11px; color: rgba(255,255,255,0.35); letter-spacing: 0.5px; font-weight: 300; }
        .header-right { display: flex; align-items: center; gap: 16px; }
        .quota-area { display: flex; flex-direction: column; align-items: flex-end; gap: 6px; }
        .quota-label { font-size: 11px; color: rgba(255,255,255,0.4); font-weight: 300; }
        .quota-bar-wrap { width: 100px; height: 4px; background: rgba(255,255,255,0.08); border-radius: 2px; overflow: hidden; }
        .quota-bar-fill { height: 100%; border-radius: 2px; transition: width 0.5s ease, background 0.5s ease; }
        .messages { flex: 1; overflow-y: auto; padding: 24px 28px; display: flex; flex-direction: column; gap: 20px; position: relative; z-index: 1; scrollbar-width: thin; scrollbar-color: rgba(255,255,255,0.08) transparent; }
        .hero { display: flex; flex-direction: column; align-items: center; justify-content: center; flex: 1; gap: 16px; text-align: center; padding: 40px 20px; animation: fadeUp 0.6s ease both; }
        @keyframes fadeUp { from { opacity: 0; transform: translateY(20px); } to { opacity: 1; transform: translateY(0); } }
        .hero-icon { width: 72px; height: 72px; border-radius: 20px; background: linear-gradient(135deg, #6366f1, #8b5cf6); display: flex; align-items: center; justify-content: center; font-size: 36px; box-shadow: 0 0 40px rgba(99,102,241,0.35); margin-bottom: 8px; }
        .hero-title { font-family: 'Syne', sans-serif; font-weight: 800; font-size: 32px; letter-spacing: -1px; background: linear-gradient(135deg, #fff 40%, #a5b4fc); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }
        .hero-sub { font-size: 15px; color: rgba(255,255,255,0.4); max-width: 380px; line-height: 1.6; font-weight: 300; }
        .hero-user { font-size: 14px; color: rgba(255,255,255,0.5); }
        .hero-user span { color: #a5b4fc; font-weight: 500; }
        .suggestions-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; width: 100%; max-width: 560px; margin-top: 16px; }
        .suggestion-btn { background: rgba(255,255,255,0.04); border: 1px solid rgba(255,255,255,0.08); border-radius: 12px; padding: 12px 16px; font-size: 13px; color: rgba(255,255,255,0.6); cursor: pointer; text-align: left; transition: all 0.2s ease; font-family: 'DM Sans', sans-serif; line-height: 1.4; }
        .suggestion-btn:hover { background: rgba(99,102,241,0.12); border-color: rgba(99,102,241,0.3); color: rgba(255,255,255,0.9); transform: translateY(-1px); }
        .msg-row { display: flex; gap: 12px; animation: fadeUp 0.3s ease both; }
        .msg-row.user { flex-direction: row-reverse; }
        .avatar { width: 32px; height: 32px; border-radius: 10px; display: flex; align-items: center; justify-content: center; font-size: 15px; flex-shrink: 0; margin-top: 2px; }
        .avatar.bot { background: linear-gradient(135deg, #6366f1, #8b5cf6); box-shadow: 0 0 12px rgba(99,102,241,0.3); }
        .avatar.user { background: rgba(255,255,255,0.08); border: 1px solid rgba(255,255,255,0.1); }
        .bubble-wrap { max-width: 75%; display: flex; flex-direction: column; gap: 8px; }
        .msg-row.user .bubble-wrap { align-items: flex-end; }
        .bubble { padding: 14px 18px; border-radius: 18px; font-size: 14px; line-height: 1.65; white-space: pre-wrap; }
        .bubble.user { background: linear-gradient(135deg, #6366f1, #7c3aed); color: #fff; border-bottom-right-radius: 4px; }
        .bubble.bot { background: rgba(255,255,255,0.05); border: 1px solid rgba(255,255,255,0.08); color: rgba(255,255,255,0.88); border-bottom-left-radius: 4px; }
        .sources-area { padding: 10px 14px; background: rgba(255,255,255,0.03); border: 1px solid rgba(255,255,255,0.06); border-radius: 10px; font-size: 12px; }
        .sources-label { color: rgba(255,255,255,0.3); font-weight: 500; margin-bottom: 6px; letter-spacing: 0.3px; }
        .sources-chips { display: flex; flex-wrap: wrap; gap: 6px; }
        .source-chip { padding: 3px 10px; background: rgba(99,102,241,0.1); border: 1px solid rgba(99,102,241,0.2); border-radius: 20px; color: #a5b4fc; font-size: 11px; }
        .intent-chips { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 4px; }
        .intent-chip { padding: 3px 10px; border-radius: 20px; font-size: 11px; font-weight: 500; border: 1px solid; }
        .typing { display: flex; gap: 12px; align-items: flex-start; animation: fadeUp 0.3s ease both; }
        .typing-dots { display: flex; gap: 5px; padding: 16px 18px; background: rgba(255,255,255,0.05); border: 1px solid rgba(255,255,255,0.08); border-radius: 18px; border-bottom-left-radius: 4px; }
        .dot { width: 7px; height: 7px; background: rgba(255,255,255,0.3); border-radius: 50%; animation: bounce 1.2s ease infinite; }
        .dot:nth-child(2) { animation-delay: 0.2s; }
        .dot:nth-child(3) { animation-delay: 0.4s; }
        @keyframes bounce { 0%, 60%, 100% { transform: translateY(0); opacity: 0.4; } 30% { transform: translateY(-6px); opacity: 1; } }
        .input-area { padding: 16px 28px 24px; border-top: 1px solid rgba(255,255,255,0.06); background: rgba(10,10,15,0.9); backdrop-filter: blur(20px); position: relative; z-index: 10; flex-shrink: 0; }
        .input-row { display: flex; gap: 10px; align-items: flex-end; background: rgba(255,255,255,0.05); border: 1px solid rgba(255,255,255,0.1); border-radius: 16px; padding: 10px 12px 10px 18px; transition: border-color 0.2s; }
        .input-row:focus-within { border-color: rgba(99,102,241,0.5); background: rgba(255,255,255,0.07); }
        .input-field { flex: 1; background: transparent; border: none; outline: none; font-family: 'DM Sans', sans-serif; font-size: 14px; color: rgba(255,255,255,0.88); resize: none; line-height: 1.5; max-height: 120px; overflow-y: auto; }
        .input-field::placeholder { color: rgba(255,255,255,0.25); }
        .send-btn { width: 38px; height: 38px; border-radius: 10px; background: linear-gradient(135deg, #6366f1, #7c3aed); border: none; cursor: pointer; display: flex; align-items: center; justify-content: center; flex-shrink: 0; transition: all 0.2s ease; box-shadow: 0 0 16px rgba(99,102,241,0.35); }
        .send-btn:hover:not(:disabled) { transform: scale(1.05); box-shadow: 0 0 24px rgba(99,102,241,0.5); }
        .send-btn:disabled { opacity: 0.3; cursor: not-allowed; box-shadow: none; }
        .input-footer { text-align: center; font-size: 11px; color: rgba(255,255,255,0.18); margin-top: 10px; letter-spacing: 0.3px; }
        .quota-banner { padding: 12px 28px; background: rgba(239,68,68,0.08); border-top: 1px solid rgba(239,68,68,0.2); text-align: center; font-size: 13px; color: #f87171; }
      `}</style>

      <div className="app">
        <header className="header">
          <div className="logo-area">
            <div className="logo-icon">🏋️</div>
            <div>
              <div className="logo-text">FitGenius</div>
              <div className="logo-sub">IFA CERTIFIED ADVISOR</div>
            </div>
          </div>
          <div className="header-right">
            <div className="quota-area">
              <div className="quota-label">{quotaNum}/{quotaMax} questions</div>
              <div className="quota-bar-wrap">
                <div className="quota-bar-fill"
                  style={{ width: `${quotaPct}%`, background: `hsl(${quotaHue}, 80%, 55%)` }} />
              </div>
            </div>
            {/* Clerk UserButton — shows avatar, sign out, profile */}
            <UserButton />
          </div>
        </header>

        <div className="messages">
          {messages.length === 0 && !loading && (
            <div className="hero">
              <div className="hero-icon">🏋️</div>
              <div className="hero-title">FitGenius</div>
              <div className="hero-sub">
                Your certified fitness advisor — powered by IFA guidelines.
              </div>
              {user && (
                <div className="hero-user">
                  Welcome back, <span>{user.firstName || user.emailAddresses[0]?.emailAddress}</span>
                </div>
              )}
              <div className="suggestions-grid">
                {SUGGESTIONS.map((s, i) => (
                  <button key={i} className="suggestion-btn"
                    onClick={() => sendMessage(s)}>{s}</button>
                ))}
              </div>
            </div>
          )}

          {messages.map((msg, i) => (
            <div key={i} className={`msg-row ${msg.role}`}>
              <div className={`avatar ${msg.role === 'user' ? 'user' : 'bot'}`}>
                {msg.role === 'user' ? '👤' : '🤖'}
              </div>
              <div className="bubble-wrap">
                <div className={`bubble ${msg.role === 'user' ? 'user' : 'bot'}`}>
                  {msg.content}
                </div>
                {msg.sources && msg.sources.length > 0 && (
                  <div className="sources-area">
                    <div className="sources-label">📖 Sources</div>
                    <div className="sources-chips">
                      {msg.sources.map((src, j) => (
                        <span key={j} className="source-chip">{src}</span>
                      ))}
                    </div>
                  </div>
                )}
                {msg.intents && msg.intents.length > 0 && (
                  <div className="intent-chips">
                    {msg.intents.map((intent, k) => {
                      const cfg = INTENT_CONFIG[intent] || INTENT_CONFIG.fitness
                      return (
                        <span key={k} className="intent-chip" style={{
                          color: cfg.color, background: cfg.bg,
                          borderColor: cfg.color + '33'
                        }}>{cfg.label}</span>
                      )
                    })}
                  </div>
                )}
              </div>
            </div>
          ))}

          {loading && (
            <div className="typing">
              <div className="avatar bot">🤖</div>
              <div className="typing-dots">
                <div className="dot" /><div className="dot" /><div className="dot" />
              </div>
            </div>
          )}
          <div ref={bottomRef} />
        </div>

        {quota === 0 && (
          <div className="quota-banner">
            ⚠️ You've used all {quotaMax} questions for this period.
            Contact your gym to continue.
          </div>
        )}

        <div className="input-area">
          <div className="input-row">
            <textarea
              className="input-field"
              value={input}
              onChange={e => setInput(e.target.value)}
              onKeyDown={handleKey}
              placeholder={
                quota === 0
                  ? 'Quota exhausted — contact your gym'
                  : 'Ask about fitness, nutrition, or injuries...'
              }
              disabled={loading || quota === 0}
              rows={1}
            />
            <button className="send-btn"
              onClick={() => sendMessage()}
              disabled={loading || !input.trim() || quota === 0}>
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none">
                <path d="M22 2L11 13M22 2L15 22L11 13M11 13L2 9L22 2"
                  stroke="white" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
              </svg>
            </button>
          </div>
          <div className="input-footer">
            Answers grounded in IFA Fitness ABCs certified guidelines only
          </div>
        </div>
      </div>
    </>
  )
}
