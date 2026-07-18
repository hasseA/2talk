import { FormEvent, KeyboardEvent, useCallback, useEffect, useMemo, useRef, useState } from "react"

import { usePolling } from "./hooks/usePolling"
import { api, ApiError } from "./services/api"
import { clearSession, loadSession, ParticipantSession, saveSession } from "./services/session"
import type { ConversationDetails, Guidance, Language, VisibleMessage } from "./types/api"

type EntryScreen = "landing" | "create" | "join" | "created" | "room"

function invitationTokenFromUrl(): string | null {
  const match = window.location.pathname.match(/^\/join\/([^/]+)\/?$/)
  return match ? decodeURIComponent(match[1]) : null
}

function invitationUrl(token: string): string {
  return new URL(`/join/${encodeURIComponent(token)}`, window.location.origin).toString()
}

function errorMessage(error: unknown): string {
  return error instanceof ApiError ? error.message : "Something went wrong. Please try again."
}

export default function App() {
  const [session, setSession] = useState<ParticipantSession | null>(() => loadSession())
  const [screen, setScreen] = useState<EntryScreen>(() => {
    if (loadSession()) return "room"
    return invitationTokenFromUrl() ? "join" : "landing"
  })
  const [notice, setNotice] = useState<string | null>(null)
  const inviteToken = invitationTokenFromUrl()

  useEffect(() => {
    const onPopState = () => {
      if (loadSession()) setScreen("room")
      else setScreen(invitationTokenFromUrl() ? "join" : "landing")
    }
    window.addEventListener("popstate", onPopState)
    return () => window.removeEventListener("popstate", onPopState)
  }, [])

  const enterRoom = (nextSession: ParticipantSession) => {
    saveSession(nextSession)
    setSession(nextSession)
    window.history.replaceState({}, "", "/")
    setScreen("room")
  }

  const invalidSession = useCallback(() => {
    clearSession()
    setSession(null)
    setNotice("Your participant session is no longer valid. Please start or join again.")
    window.history.replaceState({}, "", "/")
    setScreen("landing")
  }, [])

  return (
    <main className="app-shell">
      {screen === "landing" && (
        <Landing notice={notice} onStart={() => setScreen("create")} />
      )}
      {screen === "create" && (
        <ParticipantForm
          title="Start a private conversation"
          submitLabel="Create conversation"
          onCancel={() => setScreen("landing")}
          onSubmit={async (displayName, language) => {
            const result = await api.createConversation(displayName, language)
            const nextSession = {
              conversationId: result.conversation.id,
              participantId: result.participant.id,
              token: result.session_token,
              invitationUrl: invitationUrl(result.invitation.token),
            }
            saveSession(nextSession)
            setSession(nextSession)
            setScreen("created")
          }}
        />
      )}
      {screen === "join" && inviteToken && (
        <JoinScreen token={inviteToken} onJoined={enterRoom} />
      )}
      {screen === "created" && session && (
        <CreatedScreen session={session} onEnter={() => setScreen("room")} />
      )}
      {screen === "room" && session && (
        <ConversationRoom session={session} onInvalidSession={invalidSession} />
      )}
    </main>
  )
}

function Landing({ notice, onStart }: { notice: string | null; onStart: () => void }) {
  return (
    <section className="card entry-card stack">
      <h1 className="brand">2talk</h1>
      <p>A private conversation where AI helps two people communicate more clearly.</p>
      {notice && <p className="notice">{notice}</p>}
      <div><button onClick={onStart}>Start a conversation</button></div>
    </section>
  )
}

function useLanguages() {
  const [languages, setLanguages] = useState<Language[]>([])
  const [error, setError] = useState<string | null>(null)
  const load = useCallback(async () => {
    try {
      setLanguages(await api.listLanguages())
      setError(null)
    } catch (caught) {
      setError(errorMessage(caught))
    }
  }, [])
  useEffect(() => { void load() }, [load])
  return { languages, error, reload: load }
}

function ParticipantForm({
  title,
  submitLabel,
  onSubmit,
  onCancel,
  intro,
}: {
  title: string
  submitLabel: string
  onSubmit: (name: string, language: string) => Promise<void>
  onCancel?: () => void
  intro?: string
}) {
  const { languages, error: languageError, reload } = useLanguages()
  const [displayName, setDisplayName] = useState("")
  const [language, setLanguage] = useState("")
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!language && languages.length) setLanguage(languages[0].code)
  }, [language, languages])

  const submit = async (event: FormEvent) => {
    event.preventDefault()
    if (!displayName.trim() || !language || submitting) return
    setSubmitting(true)
    setError(null)
    try {
      await onSubmit(displayName.trim(), language)
    } catch (caught) {
      setError(errorMessage(caught))
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <section className="card entry-card stack">
      <h1 className="brand">2talk</h1>
      <h2>{title}</h2>
      {intro && <p className="muted">{intro}</p>}
      <form className="stack" onSubmit={submit}>
        <label className="field">Display name
          <input value={displayName} maxLength={80} required onChange={(e) => setDisplayName(e.target.value)} />
        </label>
        <label className="field">Preferred language
          <select value={language} required disabled={!languages.length} onChange={(e) => setLanguage(e.target.value)}>
            {!languages.length && <option value="">Loading languages…</option>}
            {languages.map((item) => <option key={item.code} value={item.code}>{item.name}</option>)}
          </select>
        </label>
        {languageError && <div className="error">{languageError} <button type="button" className="secondary" onClick={() => void reload()}>Try again</button></div>}
        {error && <p className="error">{error}</p>}
        <div className="actions">
          <button disabled={submitting || !displayName.trim() || !language}>{submitting ? "Please wait…" : submitLabel}</button>
          {onCancel && <button type="button" className="secondary" onClick={onCancel}>Back</button>}
        </div>
      </form>
    </section>
  )
}

function JoinScreen({ token, onJoined }: { token: string; onJoined: (session: ParticipantSession) => void }) {
  const [invitation, setInvitation] = useState<{ title: string | null; status: string } | null>(null)
  const [error, setError] = useState<string | null>(null)
  useEffect(() => {
    let active = true
    api.validateInvitation(token)
      .then((result) => { if (active) setInvitation(result.conversation) })
      .catch((caught) => { if (active) setError(errorMessage(caught)) })
    return () => { active = false }
  }, [token])

  if (error) return <section className="card entry-card stack"><h1 className="brand">2talk</h1><h2>Invitation unavailable</h2><p className="error">{error}</p><a href="/">Return to 2talk</a></section>
  if (!invitation) return <section className="card entry-card"><p>Checking invitation…</p></section>
  return (
    <ParticipantForm
      title="Join the conversation"
      intro={invitation.title ? `You were invited to “${invitation.title}”.` : "You were invited to a private conversation."}
      submitLabel="Join conversation"
      onSubmit={async (name, language) => {
        const result = await api.joinConversation(token, name, language)
        onJoined({ conversationId: result.conversation.id, participantId: result.participant.id, token: result.session_token })
      }}
    />
  )
}

function CreatedScreen({ session, onEnter }: { session: ParticipantSession; onEnter: () => void }) {
  const [copied, setCopied] = useState(false)
  const copy = async () => {
    if (!session.invitationUrl) return
    await navigator.clipboard.writeText(session.invitationUrl)
    setCopied(true)
  }
  return (
    <section className="card entry-card stack">
      <h1 className="brand">2talk</h1>
      <h2>Conversation created</h2>
      <p>Share this private invitation with the other participant.</p>
      <div className="invite-box" data-testid="invitation-url">{session.invitationUrl}</div>
      <div className="actions">
        <button onClick={() => void copy()}>{copied ? "Copied" : "Copy invitation link"}</button>
        <button className="secondary" onClick={onEnter}>Enter conversation</button>
      </div>
    </section>
  )
}

function ConversationRoom({ session, onInvalidSession }: { session: ParticipantSession; onInvalidSession: () => void }) {
  const [details, setDetails] = useState<ConversationDetails | null>(null)
  const [messages, setMessages] = useState<VisibleMessage[]>([])
  const [guidance, setGuidance] = useState<Guidance[]>([])
  const [error, setError] = useState<string | null>(null)
  const activeRefresh = useRef<Promise<void> | null>(null)

  const refresh = useCallback((): Promise<void> => {
    if (activeRefresh.current) return activeRefresh.current
    const operation = Promise.all([
      api.getConversation(session.conversationId, session.token),
      api.listMessages(session.conversationId, session.token),
      api.listGuidance(session.conversationId, session.token),
    ]).then(([nextDetails, nextMessages, nextGuidance]) => {
      setDetails(nextDetails)
      setMessages(nextMessages)
      setGuidance(nextGuidance)
      setError(null)
    }).catch((caught) => {
      if (caught instanceof ApiError && caught.kind === "authentication") onInvalidSession()
      else setError(errorMessage(caught))
    }).finally(() => { activeRefresh.current = null })
    activeRefresh.current = operation
    return operation
  }, [onInvalidSession, session])

  usePolling(refresh, details?.conversation.status !== "ended")

  const guidanceByMessage = useMemo(() => {
    const grouped = new Map<string, Guidance[]>()
    for (const item of guidance) grouped.set(item.message_id, [...(grouped.get(item.message_id) ?? []), item])
    return grouped
  }, [guidance])

  return (
    <section className="room">
      <header className="room-header">
        <div><h1 className="brand">2talk</h1><p>{details ? `${details.current_participant.display_name}${details.other_participant ? ` and ${details.other_participant.display_name}` : ""}` : "Loading conversation…"}</p></div>
        <div className="actions">
          <span className="status">{statusLabel(details?.conversation.status)}</span>
          {details?.conversation.status !== "ended" && <button className="danger" onClick={async () => { try { await api.endConversation(session.conversationId, session.token); await refresh() } catch (caught) { setError(errorMessage(caught)) } }}>End conversation</button>}
        </div>
      </header>
      {details?.conversation.status === "waiting" && session.invitationUrl && <WaitingInvitation url={session.invitationUrl} />}
      {error && <p className="error">{error}</p>}
      <div className="timeline" aria-live="polite">
        {!messages.length && <p className="empty">{details?.conversation.status === "waiting" ? "Waiting for the other participant to join." : "No messages yet. Start when you are ready."}</p>}
        {messages.map((message) => <MessageItem key={message.id} message={message} guidance={guidanceByMessage.get(message.id) ?? []} canRetry={details?.conversation.status === "active"} onRetry={async () => { await api.retryMessage(session.conversationId, message.id, session.token); await refresh() }} />)}
      </div>
      <Composer disabled={details?.conversation.status !== "active"} onSend={async (text) => { await api.sendMessage(session.conversationId, session.token, text); await refresh() }} />
    </section>
  )
}

function statusLabel(status?: string) {
  if (status === "waiting") return "Waiting for participant"
  return status ?? "Loading"
}

function WaitingInvitation({ url }: { url: string }) {
  const [copied, setCopied] = useState(false)
  return <div className="notice stack"><strong>Waiting for the other participant</strong><div className="invite-box">{url}</div><div><button className="secondary" onClick={async () => { await navigator.clipboard.writeText(url); setCopied(true) }}>{copied ? "Copied" : "Copy invitation link"}</button></div></div>
}

function MessageItem({ message, guidance, canRetry, onRetry }: { message: VisibleMessage; guidance: Guidance[]; canRetry: boolean; onRetry: () => Promise<void> }) {
  const [retrying, setRetrying] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const text = message.status === "failed" ? "Message processing failed." : message.status === "blocked" ? "This message was blocked and was not delivered." : message.mediated_message ?? (message.direction === "outgoing" ? message.original_message : null)
  return (
    <article className={`message ${message.direction}`} data-direction={message.direction}>
      <div className="message-head"><strong>{message.direction === "outgoing" ? "You" : message.sender_display_name}</strong><time dateTime={message.created_at}>{new Date(message.created_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}</time></div>
      {text && <p className="message-text">{text}</p>}
      <div className="message-state">{message.status}</div>
      {guidance.map((item) => <aside className="guidance" key={item.id}><strong>Private guidance for you</strong>{item.text}</aside>)}
      {canRetry && message.direction === "outgoing" && message.status === "failed" && <button disabled={retrying} onClick={async () => { setRetrying(true); setError(null); try { await onRetry() } catch (caught) { setError(errorMessage(caught)) } finally { setRetrying(false) } }}>{retrying ? "Retrying…" : "Retry"}</button>}
      {error && <p className="error">{error}</p>}
    </article>
  )
}

function Composer({ disabled, onSend }: { disabled: boolean; onSend: (text: string) => Promise<void> }) {
  const [text, setText] = useState("")
  const [sending, setSending] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const send = async () => {
    const message = text.trim()
    if (!message || message.length > 5000 || disabled || sending) return
    setSending(true)
    setError(null)
    try { await onSend(message); setText("") } catch (caught) { setError(errorMessage(caught)) } finally { setSending(false) }
  }
  const keyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === "Enter" && (event.ctrlKey || event.metaKey)) { event.preventDefault(); void send() }
  }
  return (
    <div className="composer">
      <label className="field" htmlFor="message-composer">Message</label>
      <div className="composer-row"><textarea id="message-composer" maxLength={5000} value={text} disabled={disabled} placeholder={disabled ? "Messaging is unavailable." : "Write in your preferred language…"} onChange={(event) => setText(event.target.value)} onKeyDown={keyDown} /><button disabled={disabled || sending || !text.trim()} onClick={() => void send()}>{sending ? "Sending…" : "Send"}</button></div>
      <small>{text.length}/5000 · Ctrl+Enter or Cmd+Enter to send</small>
      {error && <p className="error">{error}</p>}
    </div>
  )
}
