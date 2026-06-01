'use client'
import { useState, useRef, useEffect } from 'react'
import axios from 'axios'

interface Message {
  role: 'user' | 'assistant'
  content: string
  sources?: string[]
  intents?: string[]
}

export default function Home() {
  const [messages, setMessages] = useState<Message[]>([
    {
      role: 'assistant',
      content: 'Hi! I am FitGenius, your certified fitness advisor. Ask me anything about fitness, nutrition, or exercise. My answers are based on IFA certified fitness guidelines only.',
      sources: [],
      intents: []
    }
  ])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [quota, setQuota] = useState(30)
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  async function sendMessage() {
    if (!input.trim() || loading || quota === 0) return

    const userMessage = input.trim()
    setInput('')
    setLoading(true)

    setMessages(prev => [...prev, {
      role: 'user',
      content: userMessage
    }])

    try {
      const res = await axios.post(
        `${process.env.NEXT_PUBLIC_API_URL}/chat`,
        { message: userMessage }
      )

      setMessages(prev => [...prev, {
        role: 'assistant',
        content: res.data.response,
        sources: res.data.sources || [],
        intents: res.data.intents || []
      }])

      setQuota(prev => prev - 1)

    } catch (e) {
      setMessages(prev => [...prev, {
        role: 'assistant',
        content: 'Sorry, I encountered an error. Please try again.',
        sources: [],
        intents: []
      }])
    }

    setLoading(false)
  }

  function handleKeyDown(e: React.KeyboardEvent) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      sendMessage()
    }
  }

  const intentColor = (intent: string) => {
    if (intent === 'injury') return 'bg-red-100 text-red-600'
    if (intent === 'nutrition') return 'bg-green-100 text-green-600'
    return 'bg-blue-100 text-blue-600'
  }

  const quotaPercent = (quota / 30) * 100
  const quotaColor = quota > 20 ? 'bg-green-400' :
                     quota > 10 ? 'bg-yellow-400' : 'bg-red-400'

  return (
    <div className="flex flex-col h-screen bg-gray-50">

      {/* Header */}
      <div className="bg-blue-700 text-white px-4 py-3 flex items-center justify-between shadow-lg">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 bg-blue-500 rounded-full flex items-center justify-center text-xl">
            🏋️
          </div>
          <div>
            <h1 className="text-lg font-bold leading-tight">FitGenius</h1>
            <p className="text-blue-200 text-xs">
              IFA Certified Fitness Advisor
            </p>
          </div>
        </div>

        {/* Quota */}
        <div className="text-right">
          <div className="text-xs text-blue-200 mb-1">
            {quota}/30 questions
          </div>
          <div className="w-28 bg-blue-900 rounded-full h-2">
            <div
              className={`${quotaColor} rounded-full h-2 transition-all duration-500`}
              style={{ width: `${quotaPercent}%` }}
            />
          </div>
        </div>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-4 py-4 space-y-4">

        {messages.map((msg, i) => (
          <div
            key={i}
            className={`flex items-end gap-2 ${
              msg.role === 'user' ? 'flex-row-reverse' : 'flex-row'
            }`}
          >
            {/* Avatar */}
            <div className={`w-8 h-8 rounded-full flex items-center 
              justify-center text-sm flex-shrink-0 shadow ${
              msg.role === 'user'
                ? 'bg-blue-600 text-white'
                : 'bg-green-600 text-white'
            }`}>
              {msg.role === 'user' ? '👤' : '🤖'}
            </div>

            {/* Bubble */}
            <div className={`max-w-[78%] rounded-2xl px-4 py-3 shadow-sm ${
              msg.role === 'user'
                ? 'bg-blue-600 text-white rounded-br-none'
                : 'bg-white text-gray-800 border border-gray-100 rounded-bl-none'
            }`}>

              {/* Message text */}
              <p className="text-sm leading-relaxed whitespace-pre-wrap">
                {msg.content}
              </p>

              {/* Sources */}
              {msg.sources && msg.sources.length > 0 && (
                <div className="mt-3 pt-2 border-t border-gray-100">
                  <p className="text-xs text-gray-400 font-semibold mb-1">
                    📖 Sources:
                  </p>
                  <div className="flex flex-wrap gap-1">
                    {msg.sources.map((src, j) => (
                      <span
                        key={j}
                        className="text-xs bg-blue-50 text-blue-700 
                          border border-blue-100 rounded-md px-2 py-0.5"
                      >
                        {src}
                      </span>
                    ))}
                  </div>
                </div>
              )}

              {/* Intent badges */}
              {msg.intents && msg.intents.length > 0 && (
                <div className="mt-2 flex flex-wrap gap-1">
                  {msg.intents.map((intent, k) => (
                    <span
                      key={k}
                      className={`text-xs px-2 py-0.5 rounded-full 
                        font-medium ${intentColor(intent)}`}
                    >
                      {intent}
                    </span>
                  ))}
                </div>
              )}
            </div>
          </div>
        ))}

        {/* Loading indicator */}
        {loading && (
          <div className="flex items-end gap-2">
            <div className="w-8 h-8 rounded-full bg-green-600 text-white 
              flex items-center justify-center text-sm shadow">
              🤖
            </div>
            <div className="bg-white rounded-2xl rounded-bl-none px-4 py-3 
              shadow-sm border border-gray-100">
              <div className="flex gap-1 items-center">
                <div className="w-2 h-2 bg-gray-300 rounded-full animate-bounce"
                  style={{ animationDelay: '0ms' }} />
                <div className="w-2 h-2 bg-gray-300 rounded-full animate-bounce"
                  style={{ animationDelay: '150ms' }} />
                <div className="w-2 h-2 bg-gray-300 rounded-full animate-bounce"
                  style={{ animationDelay: '300ms' }} />
              </div>
            </div>
          </div>
        )}

        <div ref={bottomRef} />
      </div>

      {/* Quota exhausted banner */}
      {quota === 0 && (
        <div className="px-4 py-2 bg-red-50 border-t border-red-200 
          text-center text-sm text-red-600 font-medium">
          ⚠️ You have used all 30 questions for this period.
          Please contact your gym for assistance.
        </div>
      )}

      {/* Suggested questions */}
      {messages.length === 1 && (
        <div className="px-4 py-2 border-t border-gray-100 bg-white">
          <p className="text-xs text-gray-400 mb-2">Try asking:</p>
          <div className="flex flex-wrap gap-2">
            {[
              "What is the target heart rate during cardio?",
              "How many days per week should I train?",
              "I have a knee injury, what exercises are safe?",
              "How does alcohol affect fitness progress?"
            ].map((q, i) => (
              <button
                key={i}
                onClick={() => setInput(q)}
                className="text-xs bg-blue-50 text-blue-700 border 
                  border-blue-100 rounded-full px-3 py-1 hover:bg-blue-100 
                  transition-colors"
              >
                {q}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Input area */}
      <div className="border-t bg-white px-4 py-3 shadow-lg">
        <div className="flex gap-2 max-w-4xl mx-auto">
          <textarea
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={
              quota === 0
                ? 'Quota exhausted — contact your gym'
                : 'Ask a fitness question... (Enter to send)'
            }
            disabled={loading || quota === 0}
            rows={1}
            className="flex-1 resize-none border border-gray-200 rounded-xl 
              px-4 py-2.5 text-sm focus:outline-none focus:ring-2 
              focus:ring-blue-400 focus:border-transparent
              disabled:bg-gray-50 disabled:text-gray-400 
              placeholder-gray-400"
          />
          <button
            onClick={sendMessage}
            disabled={loading || !input.trim() || quota === 0}
            className="bg-blue-600 text-white px-5 py-2.5 rounded-xl 
              text-sm font-semibold hover:bg-blue-700 
              disabled:opacity-40 disabled:cursor-not-allowed 
              transition-colors shadow-sm"
          >
            {loading ? '...' : 'Send'}
          </button>
        </div>
        <p className="text-center text-xs text-gray-300 mt-2">
          Answers based on IFA Fitness ABCs certified guidelines only
        </p>
      </div>

    </div>
  )
}
