import { expect, Page, test } from "@playwright/test"

const session = {
  conversationId: "11111111-1111-4111-8111-111111111111",
  participantId: "22222222-2222-4222-8222-222222222222",
  token: "tab-a-secret-token",
  invitationUrl: "http://127.0.0.1:5173/join/invite-token",
}

const participant = {
  id: session.participantId,
  display_name: "Anna",
  preferred_language: "sv",
}

async function installSession(page: Page, value = session) {
  await page.addInitScript((stored) => {
    sessionStorage.setItem("2talk.participant-session", JSON.stringify(stored))
  }, value)
}

async function mockLanguages(page: Page) {
  await page.route("**/api/v1/languages", (route) =>
    route.fulfill({
      json: {
        success: true,
        data: { languages: [{ code: "sv", name: "Swedish" }, { code: "en", name: "English" }] },
      },
    }),
  )
}

async function mockRoom(
  page: Page,
  options: {
    status?: "waiting" | "active" | "ended"
    messages?: Record<string, unknown>[]
    guidance?: Record<string, unknown>[]
    onMessages?: () => void
  } = {},
) {
  const status = options.status ?? "active"
  await page.route(`**/api/v1/conversations/${session.conversationId}`, (route) =>
    route.fulfill({
      json: {
        success: true,
        data: {
          conversation: { id: session.conversationId, title: null, status, created_at: "2026-07-18T10:00:00Z", ended_at: status === "ended" ? "2026-07-18T11:00:00Z" : null },
          current_participant: participant,
          other_participant: status === "waiting" ? null : { id: "33333333-3333-4333-8333-333333333333", display_name: "John", preferred_language: "en" },
        },
      },
    }),
  )
  await page.route(`**/api/v1/conversations/${session.conversationId}/messages?limit=100`, (route) => {
    options.onMessages?.()
    return route.fulfill({ json: { success: true, data: { messages: options.messages ?? [], has_more: false, next_cursor: null } } })
  })
  await page.route(`**/api/v1/conversations/${session.conversationId}/guidance?limit=100`, (route) =>
    route.fulfill({ json: { success: true, data: { guidance: options.guidance ?? [] } } }),
  )
}

test("invitation URL opens the join flow", async ({ page }) => {
  await mockLanguages(page)
  await page.route("**/api/v1/invitations/invite-token", (route) =>
    route.fulfill({ json: { success: true, data: { valid: true, conversation: { title: null, status: "waiting" } } } }),
  )
  await page.goto("/join/invite-token")
  await expect(page.getByRole("heading", { name: "Join the conversation" })).toBeVisible()
  await expect(page.getByLabel("Display name")).toBeVisible()
})

test("participant credentials stay in sessionStorage and authenticate by header", async ({ page }) => {
  await installSession(page)
  let authorization = ""
  let requestedUrl = ""
  await mockRoom(page)
  await page.route(`**/api/v1/conversations/${session.conversationId}`, async (route) => {
    authorization = route.request().headers().authorization ?? ""
    requestedUrl = route.request().url()
    await route.fulfill({
      json: {
        success: true,
        data: { conversation: { id: session.conversationId, title: null, status: "active", created_at: "2026-07-18T10:00:00Z", ended_at: null }, current_participant: participant, other_participant: null },
      },
    })
  })
  await page.goto("/")
  await expect(page.getByText("Anna")).toBeVisible()
  expect(authorization).toBe(`Bearer ${session.token}`)
  expect(requestedUrl).not.toContain(session.token)
  const stored = await page.evaluate(() => sessionStorage.getItem("2talk.participant-session"))
  expect(stored).toContain(session.token)
})

test("two tabs retain separate participant sessions", async ({ context }) => {
  const first = await context.newPage()
  const second = await context.newPage()
  await first.goto("/")
  await second.goto("/")
  await first.evaluate(() => sessionStorage.setItem("participant", "A"))
  await second.evaluate(() => sessionStorage.setItem("participant", "B"))
  expect(await first.evaluate(() => sessionStorage.getItem("participant"))).toBe("A")
  expect(await second.evaluate(() => sessionStorage.getItem("participant"))).toBe("B")
})

test("blank message cannot be submitted", async ({ page }) => {
  await installSession(page)
  await mockRoom(page)
  let sends = 0
  await page.route(`**/api/v1/conversations/${session.conversationId}/messages`, (route) => {
    if (route.request().method() === "POST") sends += 1
    return route.fulfill({ json: { success: true, data: { message: { id: "message", status: "processing" } } } })
  })
  await page.goto("/")
  await page.getByLabel("Message").fill("   ")
  await expect(page.getByRole("button", { name: "Send" })).toBeDisabled()
  expect(sends).toBe(0)
})

test("successful send refreshes and shows processing", async ({ page }) => {
  await installSession(page)
  let sent = false
  await mockRoom(page, {
    messages: [],
  })
  await page.unroute(`**/api/v1/conversations/${session.conversationId}/messages?limit=100`)
  await page.route(`**/api/v1/conversations/${session.conversationId}/messages?limit=100`, (route) =>
    route.fulfill({
      json: {
        success: true,
        data: {
          messages: sent ? [{ id: "message-1", sender_id: participant.id, sender_display_name: "Anna", direction: "outgoing", original_message: "Hello", mediated_message: null, status: "processing", created_at: "2026-07-18T10:00:00Z", delivered_at: null }] : [],
          has_more: false,
          next_cursor: null,
        },
      },
    }),
  )
  await page.route(`**/api/v1/conversations/${session.conversationId}/messages`, (route) => {
    sent = true
    return route.fulfill({ status: 202, json: { success: true, data: { message: { id: "message-1", status: "processing" } } } })
  })
  await page.goto("/")
  await page.getByLabel("Message").fill("Hello")
  await page.getByRole("button", { name: "Send" }).click()
  await expect(page.getByText("processing", { exact: true })).toBeVisible()
  await expect(page.getByLabel("Message")).toHaveValue("")
})

test("incoming rendering ignores original_message and shows returned private guidance", async ({ page }) => {
  await installSession(page)
  const messageId = "message-incoming"
  await mockRoom(page, {
    messages: [{ id: messageId, sender_id: "other", sender_display_name: "John", direction: "incoming", original_message: "RAW SECRET", mediated_message: "Mediated hello", status: "delivered", created_at: "2026-07-18T10:00:00Z", delivered_at: "2026-07-18T10:00:02Z" }],
    guidance: [{ id: "guidance-1", message_id: messageId, audience: "recipient", text: "Take a moment before replying.", type: "pause_suggestion", created_at: "2026-07-18T10:00:02Z" }],
  })
  await page.goto("/")
  await expect(page.getByText("Mediated hello")).toBeVisible()
  await expect(page.getByText("RAW SECRET")).toHaveCount(0)
  await expect(page.getByText("Private guidance for you")).toBeVisible()
  await expect(page.getByText("Take a moment before replying.")).toBeVisible()
})

test("Retry is offered only for a failed outgoing message", async ({ page }) => {
  await installSession(page)
  await mockRoom(page, {
    messages: [
      { id: "out", sender_id: participant.id, sender_display_name: "Anna", direction: "outgoing", original_message: "Mine", mediated_message: null, status: "failed", created_at: "2026-07-18T10:00:00Z", delivered_at: null },
      { id: "in", sender_id: "other", sender_display_name: "John", direction: "incoming", mediated_message: "Incoming", status: "failed", created_at: "2026-07-18T10:01:00Z", delivered_at: null },
    ],
  })
  await page.goto("/")
  await expect(page.getByRole("button", { name: "Retry" })).toHaveCount(1)
})

test("polling does not overlap requests", async ({ page }) => {
  await installSession(page)
  let active = 0
  let maximum = 0
  await mockRoom(page)
  await page.unroute(`**/api/v1/conversations/${session.conversationId}`)
  await page.route(`**/api/v1/conversations/${session.conversationId}`, async (route) => {
    active += 1
    maximum = Math.max(maximum, active)
    await new Promise((resolve) => setTimeout(resolve, 2300))
    active -= 1
    await route.fulfill({ json: { success: true, data: { conversation: { id: session.conversationId, title: null, status: "active", created_at: "2026-07-18T10:00:00Z", ended_at: null }, current_participant: participant, other_participant: null } } })
  })
  await page.goto("/")
  await page.waitForTimeout(5000)
  expect(maximum).toBe(1)
})

test("polling stops for an ended conversation", async ({ page }) => {
  await installSession(page)
  let messageRequests = 0
  await mockRoom(page, {
    status: "ended",
    messages: [
      { id: "failed-outgoing", sender_id: participant.id, sender_display_name: "Anna", direction: "outgoing", original_message: "Mine", mediated_message: null, status: "failed", created_at: "2026-07-18T10:00:00Z", delivered_at: null },
    ],
    onMessages: () => { messageRequests += 1 },
  })
  await page.goto("/")
  await expect(page.getByText("ended", { exact: true })).toBeVisible()
  const initial = messageRequests
  await page.waitForTimeout(2500)
  expect(messageRequests).toBe(initial)
  await expect(page.getByLabel("Message")).toBeDisabled()
  await expect(page.getByRole("button", { name: "Retry" })).toHaveCount(0)
})

test("invalid session clears tab state and returns to a safe entry screen", async ({ page }) => {
  await installSession(page)
  await page.route("**/api/v1/conversations/**", (route) =>
    route.fulfill({ status: 401, json: { success: false, error: { code: "UNAUTHORIZED", message: "Invalid session token." } } }),
  )
  await page.goto("/")
  await expect(page.getByRole("button", { name: "Start a conversation" })).toBeVisible()
  await expect(page.getByText(/session is no longer valid/i)).toBeVisible()
  expect(await page.evaluate(() => sessionStorage.getItem("2talk.participant-session"))).toBeNull()
})
