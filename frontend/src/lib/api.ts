const API_BASE = import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000/api/v1";

export type User = { id: string; email: string; full_name: string | null; is_active: boolean; is_verified: boolean };
export type Workspace = { id: string; name: string; slug: string; owner_id: string };
export type DocumentItem = { id: string; workspace_id: string; original_filename: string; content_type: string; file_size: number; status: string; error_message: string | null; page_count: number; chunk_count: number; created_at: string };
export type Citation = { document_id: string; filename: string; chunk_id: string; page_number: number | null; excerpt: string; score: number };
export type ChatResult = { conversation_id: string; answer: string; citations: Citation[] };
export type AgentStep = { step: number; tool: string; status: string };
export type AgentResult = { conversation_id: string; answer: string; steps: AgentStep[]; max_steps: number };
export type ConversationItem = { id: string; title: string; created_at: string };
export type MessageItem = { id: string; role: string; content: string; citations: Citation[]; created_at: string };
export type ExactCountResult = { document_id: string; filename: string; term: string; count: number; counting_mode: string; page_count: number; per_page: { page_number: number | null; count: number }[] };
type Tokens = { access_token: string; refresh_token: string; token_type: string; expires_in: number };

export const getAccessToken = () => localStorage.getItem("access_token");
export const getRefreshToken = () => localStorage.getItem("refresh_token");
export function saveTokens(tokens: Tokens) { localStorage.setItem("access_token", tokens.access_token); localStorage.setItem("refresh_token", tokens.refresh_token); }
export function clearTokens() { localStorage.removeItem("access_token"); localStorage.removeItem("refresh_token"); }
let refreshPromise: Promise<boolean> | null = null;
async function refreshSession(): Promise<boolean> {
  const token = getRefreshToken(); if (!token) return false;
  try {
    const response = await fetch(`${API_BASE}/auth/refresh`, { method: "POST", headers: {"Content-Type":"application/json"}, body: JSON.stringify({refresh_token:token}) });
    if (!response.ok) { clearTokens(); return false; }
    saveTokens(await response.json()); return true;
  } catch { return false; }
}
async function request<T>(path: string, options: RequestInit = {}, retry = true): Promise<T> {
  const headers = new Headers(options.headers);
  const token = getAccessToken(); if (token) headers.set("Authorization", `Bearer ${token}`);
  if (!(options.body instanceof FormData)) headers.set("Content-Type", "application/json");
  const response = await fetch(`${API_BASE}${path}`, {...options, headers});
  if (response.status === 401 && retry && getRefreshToken()) {
    if (!refreshPromise) refreshPromise = refreshSession().finally(() => { refreshPromise = null; });
    if (await refreshPromise) return request<T>(path, options, false);
  }
  if (!response.ok) { const error = await response.json().catch(() => ({})); throw new Error(error.detail || `Request failed (${response.status})`); }
  if (response.status === 204) return undefined as T;
  return response.json();
}
export const api = {
  register: (data: {email:string;password:string;full_name:string}) => request<User>("/auth/register",{method:"POST",body:JSON.stringify(data)}),
  login: (data:{email:string;password:string}) => request<Tokens>("/auth/login",{method:"POST",body:JSON.stringify(data)}),
  me: () => request<User>("/users/me"),
  workspaces: () => request<Workspace[]>("/workspaces"),
  createWorkspace: (name:string) => request<Workspace>("/workspaces",{method:"POST",body:JSON.stringify({name})}),
  logout: (refreshToken:string) => request<{message:string}>("/auth/logout",{method:"POST",body:JSON.stringify({refresh_token:refreshToken})}),
  documents: (workspaceId:string) => request<DocumentItem[]>(`/workspaces/${workspaceId}/documents`),
  uploadDocument: (workspaceId:string,file:File) => { const data=new FormData(); data.append("file",file); return request<DocumentItem>(`/workspaces/${workspaceId}/documents`,{method:"POST",body:data}); },
  deleteDocument: (workspaceId:string,documentId:string) => request<void>(`/workspaces/${workspaceId}/documents/${documentId}`,{method:"DELETE"}),
  reindexDocument: (workspaceId:string,documentId:string) => request<DocumentItem>(`/workspaces/${workspaceId}/documents/${documentId}/reindex`,{method:"POST"}),
  exactCount: (workspaceId:string,documentId:string,term:string) => request<ExactCountResult>(`/workspaces/${workspaceId}/documents/${documentId}/exact-count?term=${encodeURIComponent(term)}`),
  chat: (workspaceId:string,question:string,conversationId?:string) => request<ChatResult>(`/workspaces/${workspaceId}/chat`,{method:"POST",body:JSON.stringify({question,conversation_id:conversationId})}),
  conversations: (workspaceId:string) => request<ConversationItem[]>(`/workspaces/${workspaceId}/conversations`),
  messages: (workspaceId:string,conversationId:string) => request<MessageItem[]>(`/workspaces/${workspaceId}/conversations/${conversationId}/messages`),
  agent: (workspaceId:string,task:string,conversationId?:string) => request<AgentResult>(`/workspaces/${workspaceId}/agent`,{method:"POST",body:JSON.stringify({task,conversation_id:conversationId})})
};
