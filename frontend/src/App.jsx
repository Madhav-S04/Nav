import React, { useState, useEffect } from "react";
import {
  ShieldAlert,
  Clock,
  User,
  Users,
  CheckCircle,
  AlertTriangle,
  Lock,
  Send,
  Search,
  MessageSquare,
  FileText,
  RotateCcw,
  Sparkles,
  Building,
  Mail,
  HelpCircle,
  Briefcase,
  ChevronRight
} from "lucide-react";
import * as api from "./api";

export default function App() {
  const [mode, setMode] = useState("AGENT"); // "AGENT" or "CUSTOMER"
  const [agents, setAgents] = useState([]);
  const [currentAgent, setCurrentAgent] = useState(null);
  const [calendar, setCalendar] = useState(null);
  const [metrics, setMetrics] = useState(null);
  
  // Agent view state
  const [tickets, setTickets] = useState([]);
  const [selectedTicketId, setSelectedTicketId] = useState(null);
  const [selectedTicket, setSelectedTicket] = useState(null);
  const [activeTab, setActiveTab] = useState("conversation"); // "conversation" or "audit"
  const [viewFilter, setViewFilter] = useState("all"); // "all", "mine", "late", "waiting", "unassigned", "resolved"
  const [searchTerm, setSearchTerm] = useState("");
  const [severityFilter, setSeverityFilter] = useState("");

  // Composer state
  const [replyMode, setReplyMode] = useState("public"); // "public" or "internal"
  const [messageContent, setMessageContent] = useState("");
  const [composerSubmitting, setComposerSubmitting] = useState(false);
  const [notification, setNotification] = useState(null);

  // Customer Portal State
  const [customerTicketNum, setCustomerTicketNum] = useState("INC-0304");
  const [customerTicketData, setCustomerTicketData] = useState(null);
  const [customerReplyText, setCustomerReplyText] = useState("");
  const [customerReplyName, setCustomerReplyName] = useState("");
  const [newTicketForm, setNewTicketForm] = useState({
    title: "",
    description: "",
    severity: "MEDIUM",
    customer_name: "",
    customer_email: "",
    customer_company: "",
  });
  const [customerTab, setCustomerTab] = useState("track"); // "track" or "new"

  // Load initial data
  useEffect(() => {
    loadAgentsAndCalendar();
  }, []);

  useEffect(() => {
    if (mode === "AGENT") {
      loadTickets();
      loadMetrics();
    }
  }, [mode, viewFilter, severityFilter, currentAgent]);

  useEffect(() => {
    if (selectedTicketId) {
      loadTicketDetail(selectedTicketId);
    }
  }, [selectedTicketId]);

  const showNotification = (msg, type = "success") => {
    setNotification({ msg, type });
    setTimeout(() => setNotification(null), 4500);
  };

  const loadAgentsAndCalendar = async () => {
    try {
      const [agList, cal] = await Promise.all([
        api.fetchAgents(),
        api.fetchCalendar(),
      ]);
      setAgents(agList);
      if (agList.length > 0 && !currentAgent) {
        // Default to Alex Chen or Meera Raman
        setCurrentAgent(agList[1] || agList[0]);
      }
      setCalendar(cal);
    } catch (err) {
      console.error(err);
    }
  };

  const loadMetrics = async () => {
    try {
      const m = await api.fetchMetrics();
      setMetrics(m);
    } catch (err) {
      console.error(err);
    }
  };

  const loadTickets = async () => {
    try {
      const params = {};
      if (viewFilter === "mine" && currentAgent) {
        params.assigned_to = currentAgent.id;
      } else if (viewFilter !== "all" && viewFilter !== "resolved") {
        params.view = viewFilter;
      } else if (viewFilter === "resolved") {
        params.status = "RESOLVED";
      }

      if (severityFilter) params.severity = severityFilter;
      if (searchTerm) params.search = searchTerm;
      if (currentAgent) params.current_agent_id = currentAgent.id;

      const data = await api.fetchTickets(params);
      setTickets(data);
      if (data.length > 0 && !selectedTicketId) {
        setSelectedTicketId(data[0].id);
      }
    } catch (err) {
      console.error(err);
    }
  };

  const loadTicketDetail = async (id) => {
    try {
      const detail = await api.fetchTicketDetail(id);
      setSelectedTicket(detail);
    } catch (err) {
      console.error(err);
    }
  };

  // Claim Ticket Handler (Collision Prevention - Incident 4.1)
  const handleClaimTicket = async () => {
    if (!selectedTicket || !currentAgent) return;
    try {
      await api.claimTicket(selectedTicket.id, currentAgent.id, selectedTicket.version);
      showNotification(`Ticket successfully claimed by ${currentAgent.name}`);
      loadTicketDetail(selectedTicket.id);
      loadTickets();
      loadMetrics();
    } catch (err) {
      showNotification(err.message, "error");
    }
  };

  // Send Message / Internal Note Handler
  const handleSendMessage = async (e) => {
    e.preventDefault();
    if (!messageContent.trim() || !selectedTicket || !currentAgent) return;

    setComposerSubmitting(true);
    const isInternal = replyMode === "internal";
    try {
      await api.postTicketMessage(selectedTicket.id, currentAgent.id, messageContent, isInternal);
      setMessageContent("");
      showNotification(isInternal ? "Private team note saved" : "Public reply sent to customer");
      loadTicketDetail(selectedTicket.id);
      loadTickets();
      loadMetrics();
    } catch (err) {
      showNotification(err.message, "error");
    } finally {
      setComposerSubmitting(false);
    }
  };

  // Change Status
  const handleStatusChange = async (newStatus) => {
    if (!selectedTicket || !currentAgent) return;
    try {
      await api.updateTicketStatus(selectedTicket.id, currentAgent.id, newStatus);
      showNotification(`Status updated to ${newStatus}`);
      loadTicketDetail(selectedTicket.id);
      loadTickets();
      loadMetrics();
    } catch (err) {
      showNotification(err.message, "error");
    }
  };

  // Change Severity
  const handleSeverityChange = async (newSev) => {
    if (!selectedTicket || !currentAgent) return;
    try {
      await api.updateTicketSeverity(selectedTicket.id, currentAgent.id, newSev, "Changed via agent console");
      showNotification(`Severity updated to ${newSev}. SLA targets recalculated.`);
      loadTicketDetail(selectedTicket.id);
      loadTickets();
      loadMetrics();
    } catch (err) {
      showNotification(err.message, "error");
    }
  };

  // Customer Portal Handlers
  const handleCustomerSearch = async () => {
    if (!customerTicketNum.trim()) return;
    try {
      const data = await api.customerGetTicket(customerTicketNum.trim());
      setCustomerTicketData(data);
      setCustomerReplyName(data.customer_name);
    } catch (err) {
      setCustomerTicketData(null);
      showNotification(err.message, "error");
    }
  };

  const handleCustomerReply = async (e) => {
    e.preventDefault();
    if (!customerReplyText.trim() || !customerTicketData) return;
    try {
      const updated = await api.customerReply(customerTicketData.ticket_number, {
        customer_name: customerReplyName || customerTicketData.customer_name,
        customer_email: customerTicketData.customer_email,
        content: customerReplyText,
      });
      setCustomerTicketData(updated);
      setCustomerReplyText("");
      showNotification("Reply sent! SLA timer resumed and ticket is in progress.");
    } catch (err) {
      showNotification(err.message, "error");
    }
  };

  const handleCustomerReopen = async () => {
    if (!customerTicketData) return;
    try {
      const updated = await api.customerReopen(customerTicketData.ticket_number);
      setCustomerTicketData(updated);
      showNotification("Ticket reopened successfully within the 7-day window!");
    } catch (err) {
      showNotification(err.message, "error");
    }
  };

  const handleCustomerCreateTicket = async (e) => {
    e.preventDefault();
    try {
      const res = await api.customerCreateTicket(newTicketForm);
      showNotification(`Ticket created: ${res.ticket_number}`);
      setCustomerTicketData(res);
      setCustomerTicketNum(res.ticket_number);
      setCustomerTab("track");
      setNewTicketForm({
        title: "",
        description: "",
        severity: "MEDIUM",
        customer_name: "",
        customer_email: "",
        customer_company: "",
      });
    } catch (err) {
      showNotification(err.message, "error");
    }
  };

  const formatRemaining = (seconds) => {
    if (seconds == null) return "--";
    const abs = Math.abs(seconds);
    const hrs = Math.floor(abs / 3600);
    const mins = Math.floor((abs % 3600) / 60);
    const str = `${hrs}h ${mins}m`;
    return seconds < 0 ? `Late by ${str}` : `${str} left`;
  };

  return (
    <div className="app-container">
      {/* Notification Toast */}
      {notification && (
        <div style={{ position: "fixed", top: "16px", right: "24px", zIndex: 999 }}>
          <div className={`alert-banner ${notification.type}`}>
            {notification.type === "error" ? <AlertTriangle size={16} /> : <CheckCircle size={16} />}
            <span>{notification.msg}</span>
          </div>
        </div>
      )}

      {/* Top Navbar */}
      <header className="top-nav">
        <div className="brand-section">
          <div className="brand-logo">FD</div>
          <div>
            <div className="brand-title">Frontdesk</div>
            <div className="brand-subtitle">Arvo Systems Support Operations</div>
          </div>
        </div>

        <div className="nav-controls">
          {/* Business Hours Indicator */}
          {calendar && (
            <div className={`biz-hours-pill ${calendar.is_currently_working_hours ? "open" : "closed"}`}>
              <Clock size={13} />
              <span>
                {calendar.is_currently_working_hours
                  ? "Arvo Business Hours (9:30 - 18:30)"
                  : "Outside Business Hours (SLA Paused)"}
              </span>
            </div>
          )}

          {/* Mode Switcher */}
          <div className="mode-toggle">
            <button
              className={`mode-btn ${mode === "AGENT" ? "active" : ""}`}
              onClick={() => setMode("AGENT")}
            >
              <Briefcase size={14} /> Agent Screen
            </button>
            <button
              className={`mode-btn ${mode === "CUSTOMER" ? "active" : ""}`}
              onClick={() => {
                setMode("CUSTOMER");
                handleCustomerSearch();
              }}
            >
              <User size={14} /> Customer Portal
            </button>
          </div>

          {/* Agent Switcher (9 Support Agents) */}
          {mode === "AGENT" && agents.length > 0 && currentAgent && (
            <div className="agent-selector-wrap">
              <div
                style={{
                  width: "22px",
                  height: "22px",
                  borderRadius: "50%",
                  background: currentAgent.avatar_color,
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  color: "white",
                  fontSize: "11px",
                  fontWeight: 700,
                }}
              >
                {currentAgent.name[0]}
              </div>
              <select
                className="agent-select"
                value={currentAgent.id}
                onChange={(e) => {
                  const ag = agents.find((a) => a.id === parseInt(e.target.value));
                  if (ag) setCurrentAgent(ag);
                }}
              >
                {agents.map((ag) => (
                  <option key={ag.id} value={ag.id}>
                    {ag.name} ({ag.role})
                  </option>
                ))}
              </select>
            </div>
          )}
        </div>
      </header>

      {/* AGENT SCREEN */}
      {mode === "AGENT" && (
        <>
          {/* KPI Metrics Bar */}
          {metrics && (
            <div className="metrics-bar">
              <div className="metric-card">
                <span className="metric-label">All Problems</span>
                <span className="metric-value">{metrics.total_tickets}</span>
              </div>
              <div className="metric-card">
                <span className="metric-label">Active Work</span>
                <span className="metric-value">{metrics.active_tickets}</span>
              </div>
              <div className="metric-card warning">
                <span className="metric-label">Waiting on Customer</span>
                <span className="metric-value">
                  <Clock size={16} /> {metrics.waiting_on_customer}
                </span>
              </div>
              <div className="metric-card danger">
                <span className="metric-label">Breached / Late</span>
                <span className="metric-value">
                  <AlertTriangle size={16} /> {metrics.late_tickets}
                </span>
              </div>
              <div className="metric-card danger">
                <span className="metric-label">Urgent Severity</span>
                <span className="metric-value">{metrics.urgent_tickets}</span>
              </div>
              <div className="metric-card">
                <span className="metric-label">Resolved</span>
                <span className="metric-value">{metrics.resolved_tickets}</span>
              </div>
            </div>
          )}

          {/* Main 2-Panel Support Screen */}
          <div className="main-content">
            {/* Left Panel: Ticket List & Filters */}
            <div className="tickets-panel">
              <div className="filter-bar">
                <div className="search-box">
                  <Search size={15} color="#94a3b8" />
                  <input
                    type="text"
                    className="search-input"
                    placeholder="Search by INC#, subject, customer..."
                    value={searchTerm}
                    onChange={(e) => setSearchTerm(e.target.value)}
                    onKeyDown={(e) => e.key === "Enter" && loadTickets()}
                  />
                </div>

                <div className="view-tabs">
                  <button
                    className={`view-tab ${viewFilter === "all" ? "active" : ""}`}
                    onClick={() => setViewFilter("all")}
                  >
                    All
                  </button>
                  <button
                    className={`view-tab ${viewFilter === "mine" ? "active" : ""}`}
                    onClick={() => setViewFilter("mine")}
                  >
                    My Queue
                  </button>
                  <button
                    className={`view-tab ${viewFilter === "late" ? "active" : ""}`}
                    onClick={() => setViewFilter("late")}
                  >
                    ⚠️ Late
                  </button>
                  <button
                    className={`view-tab ${viewFilter === "waiting" ? "active" : ""}`}
                    onClick={() => setViewFilter("waiting")}
                  >
                    ⏳ Waiting
                  </button>
                  <button
                    className={`view-tab ${viewFilter === "unassigned" ? "active" : ""}`}
                    onClick={() => setViewFilter("unassigned")}
                  >
                    Unassigned
                  </button>
                  <button
                    className={`view-tab ${viewFilter === "resolved" ? "active" : ""}`}
                    onClick={() => setViewFilter("resolved")}
                  >
                    Resolved
                  </button>
                </div>
              </div>

              {/* Tickets List */}
              <ul className="ticket-list">
                {tickets.map((t) => {
                  const isLate = t.sla_info?.reply_late || t.sla_info?.resolve_late;
                  const isPaused = t.status === "WAITING_ON_CUSTOMER";
                  return (
                    <li
                      key={t.id}
                      className={`ticket-item ${selectedTicketId === t.id ? "selected" : ""}`}
                      onClick={() => setSelectedTicketId(t.id)}
                    >
                      <div className="ticket-header-row">
                        <span className="ticket-num">{t.ticket_number}</span>
                        <div className="tag-row">
                          <span className={`badge badge-${t.severity.toLowerCase()}`}>
                            {t.severity}
                          </span>
                          {isLate ? (
                            <span className="badge badge-sla-breached">LATE</span>
                          ) : isPaused ? (
                            <span className="badge badge-sla-paused">PAUSED</span>
                          ) : (
                            <span className="badge badge-sla-ontrack">ON TRACK</span>
                          )}
                        </div>
                      </div>

                      <div className="ticket-title">{t.title}</div>

                      <div className="ticket-meta-row">
                        <span>{t.customer_company || t.customer_name}</span>
                        <span>
                          {t.assigned_agent ? (
                            <span style={{ fontWeight: 600 }}>{t.assigned_agent.name}</span>
                          ) : (
                            <span style={{ color: "#d97706", fontWeight: 600 }}>Unassigned</span>
                          )}
                        </span>
                      </div>
                    </li>
                  );
                })}
              </ul>
            </div>

            {/* Right Panel: Detail View */}
            {selectedTicket ? (
              <div className="detail-panel">
                {/* Detail Header */}
                <div className="detail-header">
                  <div className="detail-title-area">
                    <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                      <span className="ticket-num" style={{ fontSize: "14px" }}>
                        {selectedTicket.ticket_number}
                      </span>
                      <span className={`badge badge-${selectedTicket.severity.toLowerCase()}`}>
                        {selectedTicket.severity}
                      </span>
                      <span
                        className="badge"
                        style={{ background: "#f1f5f9", color: "#334155" }}
                      >
                        {selectedTicket.status}
                      </span>
                    </div>
                    <h2 className="detail-title">{selectedTicket.title}</h2>
                    <div style={{ fontSize: "12px", color: "#64748b", display: "flex", gap: "16px" }}>
                      <span>👤 {selectedTicket.customer_name} ({selectedTicket.customer_email})</span>
                      <span>🏢 {selectedTicket.customer_company}</span>
                    </div>
                  </div>

                  <div className="detail-actions">
                    {/* Claim Button */}
                    {selectedTicket.assigned_agent_id !== currentAgent?.id && (
                      <button className="btn btn-claim" onClick={handleClaimTicket}>
                        <User size={14} /> Take Ticket
                      </button>
                    )}

                    {/* Change Status */}
                    <select
                      className="btn btn-outline"
                      value={selectedTicket.status}
                      onChange={(e) => handleStatusChange(e.target.value)}
                    >
                      <option value="OPEN">Open</option>
                      <option value="IN_PROGRESS">In Progress</option>
                      <option value="WAITING_ON_CUSTOMER">Waiting on Customer</option>
                      <option value="RESOLVED">Resolved</option>
                      <option value="CLOSED">Closed</option>
                    </select>

                    {/* Change Severity */}
                    <select
                      className="btn btn-outline"
                      value={selectedTicket.severity}
                      onChange={(e) => handleSeverityChange(e.target.value)}
                    >
                      <option value="URGENT">Urgent (2h reply, same day fix)</option>
                      <option value="MEDIUM">Medium (4.5h reply, 3d fix)</option>
                      <option value="SMALL">Small (1d reply, 1w fix)</option>
                    </select>
                  </div>
                </div>

                {/* SLA Status Card */}
                {selectedTicket.sla_info && (
                  <div className="sla-banner">
                    <div className="sla-block">
                      <Clock size={18} color="#2563eb" />
                      <div className="sla-details">
                        <div className="sla-item">
                          <span className="sla-item-title">First Reply SLA</span>
                          <span className="sla-item-val">
                            {selectedTicket.first_replied_at ? (
                              <span style={{ color: "#059669" }}>✓ Fulfilled</span>
                            ) : (
                              formatRemaining(selectedTicket.sla_info.reply_remaining_seconds)
                            )}
                          </span>
                        </div>

                        <div className="sla-item">
                          <span className="sla-item-title">Resolution SLA</span>
                          <span className="sla-item-val">
                            {selectedTicket.resolved_at ? (
                              <span style={{ color: "#059669" }}>✓ Resolved</span>
                            ) : (
                              formatRemaining(selectedTicket.sla_info.resolve_remaining_seconds)
                            )}
                          </span>
                        </div>

                        {selectedTicket.total_paused_seconds > 0 && (
                          <div className="sla-item">
                            <span className="sla-item-title">Paused Working Time</span>
                            <span className="sla-item-val">
                              {Math.round(selectedTicket.total_paused_seconds / 3600)}h (Customer wait)
                            </span>
                          </div>
                        )}
                      </div>
                    </div>

                    <div>
                      {selectedTicket.status === "WAITING_ON_CUSTOMER" ? (
                        <span className="badge badge-sla-paused">SLA Clock Paused</span>
                      ) : selectedTicket.sla_info.overall_sla_badge === "BREACHED" ? (
                        <span className="badge badge-sla-breached">SLA BREACHED</span>
                      ) : (
                        <span className="badge badge-sla-ontrack">SLA Compliant</span>
                      )}
                    </div>
                  </div>
                )}

                {/* Tab Navigation */}
                <div className="detail-tab-nav">
                  <button
                    className={`detail-tab-btn ${activeTab === "conversation" ? "active" : ""}`}
                    onClick={() => setActiveTab("conversation")}
                  >
                    <MessageSquare size={14} style={{ display: "inline", marginRight: "6px" }} />
                    Conversation & Notes ({selectedTicket.messages?.length || 0})
                  </button>
                  <button
                    className={`detail-tab-btn ${activeTab === "audit" ? "active" : ""}`}
                    onClick={() => setActiveTab("audit")}
                  >
                    <FileText size={14} style={{ display: "inline", marginRight: "6px" }} />
                    Immutable Audit Trail ({selectedTicket.audit_logs?.length || 0})
                  </button>
                </div>

                {/* Tab Content */}
                {activeTab === "conversation" ? (
                  <>
                    <div className="conversation-body">
                      {selectedTicket.messages?.map((msg) => {
                        const isInternal = msg.is_internal;
                        const isCustomer = msg.sender_type === "CUSTOMER";
                        return (
                          <div
                            key={msg.id}
                            className={`message-card ${
                              isInternal
                                ? "internal-note"
                                : isCustomer
                                ? "customer"
                                : "agent-public"
                            }`}
                          >
                            <div className="message-header">
                              <span className="sender-name">
                                {isInternal && <Lock size={14} color="#d97706" />}
                                {isInternal
                                  ? `🔒 PRIVATE TEAM NOTE (${msg.sender_name})`
                                  : msg.sender_name}
                              </span>
                              <span className="message-time">
                                {new Date(msg.created_at).toLocaleTimeString([], {
                                  hour: "2-digit",
                                  minute: "2-digit",
                                  day: "numeric",
                                  month: "short",
                                })}
                              </span>
                            </div>
                            <div className="message-text">{msg.content}</div>
                          </div>
                        );
                      })}
                    </div>

                    {/* Composer with Clear Public vs Private Distinction */}
                    <form className="composer-area" onSubmit={handleSendMessage}>
                      <div className="composer-tabs">
                        <button
                          type="button"
                          className={`composer-tab ${replyMode === "public" ? "active-reply" : ""}`}
                          onClick={() => setReplyMode("public")}
                        >
                          <Send size={13} /> Public Reply to Customer
                        </button>
                        <button
                          type="button"
                          className={`composer-tab ${replyMode === "internal" ? "active-note" : ""}`}
                          onClick={() => setReplyMode("internal")}
                        >
                          <Lock size={13} /> 🔒 Private Team Note
                        </button>
                      </div>

                      <textarea
                        className={`composer-textarea ${replyMode === "internal" ? "note-mode" : ""}`}
                        placeholder={
                          replyMode === "internal"
                            ? "🔒 Write a private note for the Arvo team. NEVER shown or sent to the customer."
                            : "Reply to customer..."
                        }
                        value={messageContent}
                        onChange={(e) => setMessageContent(e.target.value)}
                      />

                      <div className="composer-footer">
                        <span style={{ fontSize: "12px", color: replyMode === "internal" ? "#d97706" : "#64748b" }}>
                          {replyMode === "internal"
                            ? "⚠️ Private notes are excluded from all customer screens, lists, APIs, and exports (Incident 4.2)."
                            : "Customer will receive this response via email and portal."}
                        </span>

                        <button
                          type="submit"
                          disabled={composerSubmitting || !messageContent.trim()}
                          className={`btn ${replyMode === "internal" ? "btn-outline" : "btn-primary"}`}
                          style={
                            replyMode === "internal"
                              ? { background: "#f59e0b", color: "#78350f", borderColor: "#d97706" }
                              : {}
                          }
                        >
                          {replyMode === "internal" ? "Add Private Note" : "Send Reply"}
                        </button>
                      </div>
                    </form>
                  </>
                ) : (
                  /* Audit Trail Tab */
                  <div className="audit-list">
                    {selectedTicket.audit_logs?.map((log) => (
                      <div key={log.id} className="audit-entry">
                        <div className="audit-bullet" />
                        <div className="audit-content">
                          <div className="audit-action-row">
                            <span className="audit-action-tag">{log.action}</span>
                            <span className="audit-actor">{log.actor_name}</span>
                            <span className="audit-time">
                              {new Date(log.timestamp).toLocaleString()}
                            </span>
                          </div>
                          <div className="audit-detail-text">{log.details}</div>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            ) : (
              <div
                style={{
                  flex: 1,
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  color: "#94a3b8",
                }}
              >
                Select a problem ticket to view details and take action
              </div>
            )}
          </div>
        </>
      )}

      {/* CUSTOMER PORTAL SCREEN */}
      {mode === "CUSTOMER" && (
        <div className="customer-portal">
          <div style={{ marginBottom: "24px" }}>
            <h1 style={{ fontSize: "24px", fontWeight: 700 }}>Arvo Customer Support Portal</h1>
            <p style={{ color: "#64748b", fontSize: "14px" }}>
              Submit tickets or review your support interactions. Notice: Private team notes are
              strictly blocked from this portal!
            </p>
          </div>

          <div style={{ display: "flex", gap: "12px", marginBottom: "20px" }}>
            <button
              className={`btn ${customerTab === "track" ? "btn-primary" : "btn-outline"}`}
              onClick={() => setCustomerTab("track")}
            >
              <Search size={14} /> Track Existing Ticket
            </button>
            <button
              className={`btn ${customerTab === "new" ? "btn-primary" : "btn-outline"}`}
              onClick={() => setCustomerTab("new")}
            >
              <MessageSquare size={14} /> Submit New Problem
            </button>
          </div>

          {customerTab === "track" && (
            <>
              {/* Ticket Search Bar */}
              <div className="customer-card">
                <div style={{ display: "flex", gap: "10px" }}>
                  <input
                    type="text"
                    className="composer-textarea"
                    style={{ minHeight: "42px", padding: "8px 12px" }}
                    placeholder="Enter Ticket Number (e.g. INC-0304, INC-0318)"
                    value={customerTicketNum}
                    onChange={(e) => setCustomerTicketNum(e.target.value)}
                  />
                  <button className="btn btn-primary" onClick={handleCustomerSearch}>
                    Search Ticket
                  </button>
                </div>
                <span style={{ fontSize: "12px", color: "#64748b", marginTop: "6px", display: "block" }}>
                  Tip: Check <strong>INC-0304</strong> to verify that the private team note about the customer is completely invisible!
                </span>
              </div>

              {/* Display Customer View of Ticket */}
              {customerTicketData && (
                <div className="customer-card">
                  <div
                    style={{
                      display: "flex",
                      justifyContent: "space-between",
                      borderBottom: "1px solid #e2e8f0",
                      paddingBottom: "14px",
                      marginBottom: "16px",
                    }}
                  >
                    <div>
                      <span className="ticket-num">{customerTicketData.ticket_number}</span>
                      <h2 style={{ fontSize: "18px", fontWeight: 700 }}>{customerTicketData.title}</h2>
                      <span style={{ fontSize: "12px", color: "#64748b" }}>
                        Submitted on {new Date(customerTicketData.created_at).toLocaleDateString()}
                      </span>
                    </div>

                    <div style={{ display: "flex", flexDirection: "column", alignItems: "flex-end", gap: "6px" }}>
                      <span
                        className="badge"
                        style={{ background: "#dbeafe", color: "#1e40af", fontSize: "13px" }}
                      >
                        Status: {customerTicketData.status}
                      </span>
                      {customerTicketData.status === "RESOLVED" && customerTicketData.can_reopen && (
                        <button className="btn btn-outline" onClick={handleCustomerReopen}>
                          <RotateCcw size={14} /> Reopen Ticket (Within 7 Days)
                        </button>
                      )}
                    </div>
                  </div>

                  {/* Public Conversation History */}
                  <div style={{ display: "flex", flexDirection: "column", gap: "12px", marginBottom: "20px" }}>
                    <h3 style={{ fontSize: "14px", fontWeight: 700, color: "#475569" }}>
                      Message History
                    </h3>

                    {customerTicketData.messages.map((m) => (
                      <div
                        key={m.id}
                        style={{
                          background: m.sender_type === "CUSTOMER" ? "#f8fafc" : "#eff6ff",
                          border: "1px solid",
                          borderColor: m.sender_type === "CUSTOMER" ? "#e2e8f0" : "#bfdbfe",
                          padding: "12px 16px",
                          borderRadius: "8px",
                        }}
                      >
                        <div
                          style={{
                            display: "flex",
                            justifyContent: "space-between",
                            fontSize: "12px",
                            fontWeight: 600,
                            marginBottom: "4px",
                          }}
                        >
                          <span>{m.sender_name}</span>
                          <span style={{ color: "#94a3b8" }}>
                            {new Date(m.created_at).toLocaleTimeString([], {
                              hour: "2-digit",
                              minute: "2-digit",
                            })}
                          </span>
                        </div>
                        <div style={{ fontSize: "13.5px", color: "#0f172a" }}>{m.content}</div>
                      </div>
                    ))}
                  </div>

                  {/* Customer Reply Box (Unpauses SLA) */}
                  {customerTicketData.status !== "CLOSED" && (
                    <form onSubmit={handleCustomerReply}>
                      <textarea
                        className="composer-textarea"
                        placeholder="Reply to support agents... (Replying will resume the SLA clock and set ticket to In Progress)"
                        value={customerReplyText}
                        onChange={(e) => setCustomerReplyText(e.target.value)}
                        style={{ marginBottom: "10px" }}
                      />
                      <button
                        type="submit"
                        className="btn btn-primary"
                        disabled={!customerReplyText.trim()}
                      >
                        <Send size={14} /> Send Reply
                      </button>
                    </form>
                  )}
                </div>
              )}
            </>
          )}

          {customerTab === "new" && (
            <div className="customer-card">
              <h2 style={{ fontSize: "18px", fontWeight: 700, marginBottom: "16px" }}>
                Submit a Support Problem
              </h2>
              <form onSubmit={handleCustomerCreateTicket} style={{ display: "flex", flexDirection: "column", gap: "14px" }}>
                <div>
                  <label style={{ fontSize: "13px", fontWeight: 600 }}>Your Name</label>
                  <input
                    type="text"
                    required
                    className="composer-textarea"
                    style={{ minHeight: "38px" }}
                    value={newTicketForm.customer_name}
                    onChange={(e) => setNewTicketForm({ ...newTicketForm, customer_name: e.target.value })}
                  />
                </div>

                <div>
                  <label style={{ fontSize: "13px", fontWeight: 600 }}>Email Address</label>
                  <input
                    type="email"
                    required
                    className="composer-textarea"
                    style={{ minHeight: "38px" }}
                    value={newTicketForm.customer_email}
                    onChange={(e) => setNewTicketForm({ ...newTicketForm, customer_email: e.target.value })}
                  />
                </div>

                <div>
                  <label style={{ fontSize: "13px", fontWeight: 600 }}>Company Name</label>
                  <input
                    type="text"
                    className="composer-textarea"
                    style={{ minHeight: "38px" }}
                    value={newTicketForm.customer_company}
                    onChange={(e) => setNewTicketForm({ ...newTicketForm, customer_company: e.target.value })}
                  />
                </div>

                <div>
                  <label style={{ fontSize: "13px", fontWeight: 600 }}>Severity</label>
                  <select
                    className="composer-textarea"
                    style={{ minHeight: "38px" }}
                    value={newTicketForm.severity}
                    onChange={(e) => setNewTicketForm({ ...newTicketForm, severity: e.target.value })}
                  >
                    <option value="URGENT">Urgent - Cannot work at all (2h reply, same day fix)</option>
                    <option value="MEDIUM">Medium problem (half day reply, 3d fix)</option>
                    <option value="SMALL">Small question or request (1d reply, 1w fix)</option>
                  </select>
                </div>

                <div>
                  <label style={{ fontSize: "13px", fontWeight: 600 }}>Subject / Title</label>
                  <input
                    type="text"
                    required
                    className="composer-textarea"
                    style={{ minHeight: "38px" }}
                    value={newTicketForm.title}
                    onChange={(e) => setNewTicketForm({ ...newTicketForm, title: e.target.value })}
                  />
                </div>

                <div>
                  <label style={{ fontSize: "13px", fontWeight: 600 }}>Problem Description</label>
                  <textarea
                    required
                    className="composer-textarea"
                    rows={4}
                    value={newTicketForm.description}
                    onChange={(e) => setNewTicketForm({ ...newTicketForm, description: e.target.value })}
                  />
                </div>

                <button type="submit" className="btn btn-primary" style={{ alignSelf: "flex-start" }}>
                  Submit Problem Ticket
                </button>
              </form>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
