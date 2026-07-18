import type {
  ApiEnvelope,
  ConversationDetails,
  CreateConversationData,
  Guidance,
  JoinConversationData,
  Language,
  VisibleMessage,
} from "../types/api"

const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL ?? "").replace(/\/$/, "")

type ErrorKind = "authentication" | "authorization" | "validation" | "network" | "server"

export class ApiError extends Error {
  constructor(
    message: string,
    readonly kind: ErrorKind,
    readonly code?: string,
    readonly status?: number,
  ) {
    super(message)
  }
}

async function request<T>(
  path: string,
  options: RequestInit = {},
  token?: string,
): Promise<T> {
  const headers = new Headers(options.headers)
  if (options.body) headers.set("Content-Type", "application/json")
  if (token) headers.set("Authorization", `Bearer ${token}`)

  let response: Response
  try {
    response = await fetch(`${API_BASE_URL}${path}`, { ...options, headers })
  } catch {
    throw new ApiError("Unable to reach 2talk. Please try again.", "network")
  }

  const payload = (await response.json().catch(() => null)) as
    | ApiEnvelope<T>
    | { success: false; error: { code?: string; message?: string } }
    | null
  if (!response.ok || !payload || payload.success === false) {
    const code = payload && payload.success === false ? payload.error.code : undefined
    const message =
      payload && payload.success === false
        ? payload.error.message ?? "The request could not be completed."
        : "The request could not be completed."
    const kind: ErrorKind =
      response.status === 401
        ? "authentication"
        : response.status === 403
          ? "authorization"
          : response.status === 400 || response.status === 409 || response.status === 422
            ? "validation"
            : "server"
    throw new ApiError(message, kind, code, response.status)
  }
  return payload.data
}

export const api = {
  listLanguages: () =>
    request<{ languages: Language[] }>("/api/v1/languages").then((data) => data.languages),

  createConversation: (displayName: string, preferredLanguage: string) =>
    request<CreateConversationData>("/api/v1/conversations", {
      method: "POST",
      body: JSON.stringify({
        title: null,
        description: null,
        display_name: displayName,
        preferred_language: preferredLanguage,
      }),
    }),

  validateInvitation: (token: string) =>
    request<{ valid: true; conversation: { title: string | null; status: string } }>(
      `/api/v1/invitations/${encodeURIComponent(token)}`,
    ),

  joinConversation: (invitationToken: string, displayName: string, language: string) =>
    request<JoinConversationData>(
      `/api/v1/invitations/${encodeURIComponent(invitationToken)}/join`,
      {
        method: "POST",
        body: JSON.stringify({ display_name: displayName, preferred_language: language }),
      },
    ),

  getConversation: (conversationId: string, token: string) =>
    request<ConversationDetails>(`/api/v1/conversations/${conversationId}`, {}, token),

  listMessages: (conversationId: string, token: string) =>
    request<{ messages: VisibleMessage[]; has_more: boolean; next_cursor: string | null }>(
      `/api/v1/conversations/${conversationId}/messages?limit=100`,
      {},
      token,
    ).then((data) => data.messages),

  listGuidance: (conversationId: string, token: string) =>
    request<{ guidance: Guidance[] }>(
      `/api/v1/conversations/${conversationId}/guidance?limit=100`,
      {},
      token,
    ).then((data) => data.guidance),

  sendMessage: (conversationId: string, token: string, message: string) =>
    request<{ message: { id: string; status: string } }>(
      `/api/v1/conversations/${conversationId}/messages`,
      {
        method: "POST",
        body: JSON.stringify({ client_message_id: crypto.randomUUID(), message }),
      },
      token,
    ),

  retryMessage: (conversationId: string, messageId: string, token: string) =>
    request<{ message: { id: string; status: string } }>(
      `/api/v1/conversations/${conversationId}/messages/${messageId}/retry`,
      { method: "POST" },
      token,
    ),

  endConversation: (conversationId: string, token: string) =>
    request<{ conversation: { id: string; status: string; ended_at: string } }>(
      `/api/v1/conversations/${conversationId}/end`,
      { method: "POST", body: JSON.stringify({ generate_summary: false }) },
      token,
    ),
}
