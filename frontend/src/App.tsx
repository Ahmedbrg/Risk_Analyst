import React, { useState } from 'react';
import './App.css';
import { ChatMessage, RiskAnalysisResponse } from './types/risk';

// Keep the standalone React client aligned with the FastAPI default in app/config.py.
const API_BASE = process.env.REACT_APP_API_BASE ?? "http://localhost:8001/api/v1";

export const App: React.FC = () => {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [conversationId, setConversationId] = useState<string | null>(null);

  const handleSend = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim() || loading) return;

    const userText = input;
    setInput('');
    setLoading(true);

    const userMsg: ChatMessage = {
      role: 'user',
      content: userText,
      timestamp: new Date().toISOString()
    };

    setMessages((prev) => [...prev, userMsg]);

    try {
      const response = await fetch(`${API_BASE}/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          conversation_id: conversationId,
          message: userText,
          use_crew_ai: false,
          include_rag: false
        })
      });

      const data: ChatMessage = await response.json();
      if (data.risk_analysis?.conversation_id) {
        setConversationId(data.risk_analysis.conversation_id);
      }
      setMessages((prev) => [...prev, data]);
    } catch (err) {
      console.error(err);
      const errorMsg: ChatMessage = {
        role: 'assistant',
          content: 'Error connecting to AI Risk Analyst Backend. Please ensure FastAPI server is running on http://localhost:8001.',
        timestamp: new Date().toISOString()
      };
      setMessages((prev) => [...prev, errorMsg]);
    } finally {
      setLoading(false);
    }
  };

  const handleDownloadPDF = async (analysis: RiskAnalysisResponse) => {
    if (!analysis.report_validation?.valid_for_distribution) {
      alert('This report failed final QC and cannot be exported. Please re-analyze it.');
      return;
    }
    try {
      const response = await fetch(`${API_BASE}/reports/pdf`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(analysis)
      });

      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `Risk_Report_${analysis.analysis_id.slice(0, 8)}.pdf`;
      document.body.appendChild(a);
      a.click();
      a.remove();
    } catch (err) {
      alert("Failed to download PDF report.");
    }
  };

  return (
    <div className="app-container">
      {/* Sidebar */}
      <div className="sidebar">
        <div className="brand">
          <span>🛡️ AI Risk Analyst</span>
        </div>
        <button className="new-chat-btn" onClick={() => { setMessages([]); setConversationId(null); }}>
          + New Risk Audit
        </button>
        <div className="history-section">
          <div className="history-title">Recent Sessions</div>
          {conversationId && (
            <div className="history-item active">
              Session #{conversationId.slice(0, 8)}
            </div>
          )}
        </div>
      </div>

      {/* Main Content */}
      <div className="main-content">
        <div className="header">
          <h2>Decision-Support Risk Intelligence Platform</h2>
          <span style={{ color: '#38bdf8', fontSize: '0.85rem' }}>Engine: Grounded RAG + Multi-Factor Scoring</span>
        </div>

        {/* Chat Thread */}
        <div className="chat-thread">
          {messages.length === 0 && (
            <div style={{ textAlign: 'center', marginTop: '100px', color: '#94a3b8' }}>
              <h3>Describe a Business Situation</h3>
              <p style={{ marginTop: '8px' }}>Example: "Revenue dropped 30%, two suppliers are consistently late, and our main client contract expires next month."</p>
            </div>
          )}

          {messages.map((msg, idx) => (
            <div key={idx} className="message-wrapper">
              {msg.role === 'user' ? (
                <div className="user-bubble">{msg.content}</div>
              ) : (
                <div className="assistant-bubble">
                  {msg.risk_analysis ? (
                    <div>
                      <div className={`overall-badge badge-${msg.risk_analysis.overall_risk}`}>
                        OVERALL RISK: {msg.risk_analysis.overall_risk}
                      </div>

                      <div className="exec-summary">
                        <strong>Executive Summary:</strong><br />
                        {msg.risk_analysis.executive_summary}
                      </div>

                      {/* Download PDF Button */}
                      <button
                        onClick={() => handleDownloadPDF(msg.risk_analysis!)}
                        disabled={!msg.risk_analysis.report_validation?.valid_for_distribution}
                        style={{
                          backgroundColor: '#2563eb', color: 'white', border: 'none',
                          padding: '8px 16px', borderRadius: '6px', cursor: 'pointer', marginBottom: '16px'
                        }}
                      >
                        {msg.risk_analysis.report_validation?.valid_for_distribution
                          ? '📄 Download PDF Executive Report'
                          : '⚠️ Re-analysis required before export'}
                      </button>

                      {/* Identified Risks */}
                      <h4 style={{ marginBottom: '12px', color: '#38bdf8' }}>Identified Risk Vectors</h4>
                      <div className="risk-grid">
                        {msg.risk_analysis.identified_risks.map((risk, rIdx) => (
                          <div key={rIdx} className="risk-card">
                            <div className="risk-card-header">
                              <span className="risk-title">{risk.title}</span>
                              <span className={`overall-badge badge-${risk.severity}`} style={{ fontSize: '0.7rem', padding: '2px 8px' }}>
                                {risk.severity}
                              </span>
                            </div>
                            <p style={{ fontSize: '0.85rem', color: '#cbd5e1' }}>{risk.description}</p>
                            <div style={{ fontSize: '0.8rem', color: '#94a3b8' }}>
                              <strong>Impact:</strong> {risk.potential_impact}
                            </div>
                            <div style={{ fontSize: '0.8rem', color: '#38bdf8' }}>
                              <strong>Evidence:</strong> {risk.evidence.join('; ')}
                            </div>
                          </div>
                        ))}
                      </div>

                      {/* Priority Actions */}
                      <h4 style={{ marginTop: '20px', marginBottom: '10px', color: '#38bdf8' }}>Priority Actions</h4>
                      <ol style={{ paddingLeft: '20px', fontSize: '0.9rem', lineHeight: '1.6' }}>
                        {msg.risk_analysis.priority_actions.map((act, aIdx) => (
                          <li key={aIdx}><strong>[{act.priority}]</strong> {act.action}</li>
                        ))}
                      </ol>

                      {/* Missing Information */}
                      <h4 style={{ marginTop: '20px', marginBottom: '10px', color: '#fbbf24' }}>Missing Information Needed</h4>
                      <ul style={{ paddingLeft: '20px', fontSize: '0.85rem', color: '#cbd5e1' }}>
                        {msg.risk_analysis.missing_information.map((info, iIdx) => (
                          <li key={iIdx}>{info}</li>
                        ))}
                      </ul>
                    </div>
                  ) : (
                    <div>{msg.content}</div>
                  )}
                </div>
              )}
            </div>
          ))}

          {loading && (
            <div className="message-wrapper">
              <div className="assistant-bubble" style={{ color: '#38bdf8' }}>
                Analyzing business situation and evaluating risk metrics...
              </div>
            </div>
          )}
        </div>

        {/* Input Area */}
        <div className="input-area">
          <form className="input-form" onSubmit={handleSend}>
            <input
              type="text"
              className="chat-input"
              placeholder="Describe a business situation (e.g. revenue dropped 30%, key supplier delayed...)"
              value={input}
              onChange={(e) => setInput(e.target.value)}
            />
            <button type="submit" className="send-btn" disabled={loading}>
              Analyze Risks
            </button>
          </form>
        </div>
      </div>
    </div>
  );
};

export default App;
