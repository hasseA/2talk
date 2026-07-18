export type Language = { code: string; name: string }

export type Participant = {
  id: string
  display_name: string
  preferred_language: string
  role?: string
}

export type Conversation = {
  id: string
  title: string | null
  description?: string | null
  status: "waiting" | "active" | "ended"
  created_at?: string
  ended_at?: string | null
}

export type ConversationDetails = {
  conversation: Conversation
  current_participant: Participant
  other_participant: Participant | null
}

export type VisibleMessage = {
  id: string
  sender_id: string
  sender_display_name: string
  direction: "outgoing" | "incoming"
  original_message?: string
  mediated_message: string | null
  status: "processing" | "delivered" | "blocked" | "failed"
  created_at: string
  delivered_at: string | null
}

export type Guidance = {
  id: string
  message_id: string
  audience: "sender" | "recipient"
  text: string
  type: string
  created_at: string
}

export type ApiEnvelope<T> = { success: true; data: T }

export type CreateConversationData = {
  conversation: Conversation
  participant: Participant
  invitation: { token: string; url: string }
  session_token: string
}

export type JoinConversationData = {
  conversation: Conversation
  participant: Participant
  session_token: string
}
