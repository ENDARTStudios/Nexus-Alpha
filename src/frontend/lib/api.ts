export interface ChatResponse {
  status?: string;
  reply: string;
  session_id: string;
  reasoning_steps: string[];
  sources: string[];
  provider: string;
  context_source?: string;
}

const API_BASE = process.env.NEXT_PUBLIC_NEXUS_API_URL ?? "";

export async function sendChatMessage(
  message: string,
  sessionId: string,
): Promise<ChatResponse> {
  const response = await fetch(`${API_BASE}/api/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message, session_id: sessionId }),
  });

  if (!response.ok) {
    throw new Error(`Falha na API da Nexus-Alpha (${response.status})`);
  }

  return (await response.json()) as ChatResponse;
}

export function newSessionId(): string {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    return crypto.randomUUID();
  }
  return `sess-${Date.now()}-${Math.random().toString(36).slice(2, 10)}`;
}
