import type { Activity, Cash, Ticket } from "./types";

export const API = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

async function call<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json" },
  });
  const body = await res.json().catch(() => ({}));
  if (!res.ok) {
    const d = (body as { detail?: unknown }).detail;
    throw new Error(typeof d === "string" ? d : `Request failed (${res.status})`);
  }
  return body as T;
}

export const getTickets = () => call<Ticket[]>("/tickets");
export const runTicket = (id: number) => call<{ run_status: string }>(`/tickets/${id}/run`, { method: "POST" });
export const getActivity = (id: number, since = 0) => call<Activity>(`/tickets/${id}/activity?since=${since}`);
export const getCash = () => call<Cash>("/cash");
export const approvePayment = (id: number, name: string) =>
  call<{ new_balance: number }>(`/payments/${id}/approve`, { method: "POST", body: JSON.stringify({ approved_by: name }) });
export const rejectPayment = (id: number, name: string) =>
  call<{ ok: boolean }>(`/payments/${id}/reject`, { method: "POST", body: JSON.stringify({ approved_by: name }) });
export const resetRealm = () => call<{ balance: number }>("/reset", { method: "POST" });
export const approvePrice = (id: number, name: string) =>
  call<{ ok: boolean }>(`/price-proposals/${id}/approve`, { method: "POST", body: JSON.stringify({ approved_by: name }) });
export const rejectPrice = (id: number, name: string) =>
  call<{ ok: boolean }>(`/price-proposals/${id}/reject`, { method: "POST", body: JSON.stringify({ approved_by: name }) });
