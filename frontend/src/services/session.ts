const SESSION_KEY = "2talk.participant-session"

export type ParticipantSession = {
  conversationId: string
  participantId: string
  token: string
  invitationUrl?: string
}

export function loadSession(): ParticipantSession | null {
  const value = sessionStorage.getItem(SESSION_KEY)
  if (!value) return null
  try {
    const parsed = JSON.parse(value) as ParticipantSession
    if (!parsed.conversationId || !parsed.participantId || !parsed.token) return null
    return parsed
  } catch {
    return null
  }
}

export function saveSession(session: ParticipantSession): void {
  sessionStorage.setItem(SESSION_KEY, JSON.stringify(session))
}

export function clearSession(): void {
  sessionStorage.removeItem(SESSION_KEY)
}
