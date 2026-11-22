const API_BASE = "/api";

export async function fetchAgents() {
  const res = await fetch(`${API_BASE}/agents`);
  if (!res.ok) throw new Error("Failed to fetch agents");
  return res.json();
}

export async function fetchCalendar() {
  const res = await fetch(`${API_BASE}/business-calendar`);
  if (!res.ok) throw new Error("Failed to fetch business calendar");
  return res.json();
}

export async function fetchMetrics() {
  const res = await fetch(`${API_BASE}/agent/tickets/metrics`);
  if (!res.ok) throw new Error("Failed to fetch metrics");
  return res.json();
}

export async function fetchTickets(params = {}) {
  const query = new URLSearchParams();
  if (params.view) query.append("view", params.view);
  if (params.status) query.append("status", params.status);
  if (params.severity) query.append("severity", params.severity);
  if (params.search) query.append("search", params.search);
  if (params.assigned_to) query.append("assigned_to", params.assigned_to);
  if (params.current_agent_id) query.append("current_agent_id", params.current_agent_id);

  const res = await fetch(`${API_BASE}/agent/tickets?${query.toString()}`);
  if (!res.ok) throw new Error("Failed to fetch tickets");
  return res.json();
}

export async function fetchTicketDetail(ticketId) {
  const res = await fetch(`${API_BASE}/agent/tickets/${ticketId}`);
  if (!res.ok) throw new Error("Failed to fetch ticket detail");
  return res.json();
}

export async function claimTicket(ticketId, agentId, currentVersion) {
  const res = await fetch(`${API_BASE}/agent/tickets/${ticketId}/claim`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ agent_id: agentId, current_version: currentVersion }),
  });
  const data = await res.json();
  if (!res.ok) {
    throw new Error(data.detail || "Failed to claim ticket");
  }
  return data;
}

export async function postTicketMessage(ticketId, agentId, content, isInternal) {
  const res = await fetch(`${API_BASE}/agent/tickets/${ticketId}/messages?agent_id=${agentId}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ content, is_internal: isInternal }),
  });
  const data = await res.json();
  if (!res.ok) throw new Error(data.detail || "Failed to post message");
  return data;
}

export async function updateTicketStatus(ticketId, agentId, status, note = null) {
  const res = await fetch(`${API_BASE}/agent/tickets/${ticketId}/status`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ status, agent_id: agentId, note }),
  });
  const data = await res.json();
  if (!res.ok) throw new Error(data.detail || "Failed to update status");
  return data;
}

export async function updateTicketSeverity(ticketId, agentId, severity, reason = null) {
  const res = await fetch(`${API_BASE}/agent/tickets/${ticketId}/severity`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ severity, agent_id: agentId, reason }),
  });
  const data = await res.json();
  if (!res.ok) throw new Error(data.detail || "Failed to update severity");
  return data;
}

export async function triggerAutoClose() {
  const res = await fetch(`${API_BASE}/agent/tickets/auto-close-stale`, {
    method: "POST",
  });
  return res.json();
}

// Customer Portal API (Guaranteed Zero Leakage)
export async function customerCreateTicket(ticketData) {
  const res = await fetch(`${API_BASE}/customer/tickets`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(ticketData),
  });
  const data = await res.json();
  if (!res.ok) throw new Error(data.detail || "Failed to create ticket");
  return data;
}

export async function customerGetTicket(ticketNumber) {
  const res = await fetch(`${API_BASE}/customer/tickets/${ticketNumber}`);
  const data = await res.json();
  if (!res.ok) throw new Error(data.detail || "Ticket not found");
  return data;
}

export async function customerReply(ticketNumber, replyData) {
  const res = await fetch(`${API_BASE}/customer/tickets/${ticketNumber}/reply`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(replyData),
  });
  const data = await res.json();
  if (!res.ok) throw new Error(data.detail || "Failed to send customer reply");
  return data;
}

export async function customerReopen(ticketNumber) {
  const res = await fetch(`${API_BASE}/customer/tickets/${ticketNumber}/reopen`, {
    method: "POST",
  });
  const data = await res.json();
  if (!res.ok) throw new Error(data.detail || "Failed to reopen ticket");
  return data;
}
