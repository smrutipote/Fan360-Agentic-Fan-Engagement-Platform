import React, { useState, useEffect, useRef } from "react";
import { Radio, ChevronRight } from "lucide-react";

// ── Colour + agent config ────────────────────────────────────────────
const AGENTS = {
  Orchestrator:          { color: "#00D4FF", bg: "#001a2e", icon: "\ud83c\udfaf", role: "Parent \u2014 routes & decides" },
  ChurnAgent:            { color: "#FF4D6D", bg: "#1a0010", icon: "\ud83d\udd25", role: "Retention offers" },
  PersonalisationAgent:  { color: "#A855F7", bg: "#0d001a", icon: "\u2728", role: "Personalised engagement" },
  RecommendationAgent:   { color: "#F59E0B", bg: "#1a1000", icon: "\ud83d\udca1", role: "Re-activation offers" },
  SegmentationAgent:     { color: "#10B981", bg: "#001a0d", icon: "\ud83d\udd2c", role: "Fan classification" },
  SponsorMatchingAgent:  { color: "#3B82F6", bg: "#00051a", icon: "\ud83e\udd1d", role: "Commercial sponsor match" },
};

const EVENT_STYLES = {
  THINKING:  { color: "#00D4FF", label: "Thinking",   icon: "\ud83e\udde0" },
  ROUTING:   { color: "#A855F7", label: "Routing",    icon: "\ud83d\udd00" },
  A2A:       { color: "#F59E0B", label: "A2A Call",   icon: "\ud83d\udce1" },
  RESULT:    { color: "#10B981", label: "Result",     icon: "\u2705" },
  WRITEBACK: { color: "#3B82F6", label: "Write-back", icon: "\ud83d\udcbe" },
  ERROR:     { color: "#FF4D6D", label: "Error",      icon: "\u274c" },
};

// ── Scanline CSS ─────────────────────────────────────────────────────
const globalStyles = `
  @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@300;400;600;700&family=Orbitron:wght@400;700;900&display=swap');
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { background: #000; overflow-x: hidden; }
  ::-webkit-scrollbar { width: 4px; }
  ::-webkit-scrollbar-track { background: #0a0a0a; }
  ::-webkit-scrollbar-thumb { background: #00D4FF44; border-radius: 2px; }
  @keyframes pulse { 0%,100%{opacity:1} 50%{opacity:0.4} }
  @keyframes scanline {
    0% { transform: translateY(-100%); }
    100% { transform: translateY(100vh); }
  }
  @keyframes glow {
    0%,100% { box-shadow: 0 0 4px currentColor; }
    50% { box-shadow: 0 0 16px currentColor, 0 0 32px currentColor; }
  }
  @keyframes flowDot {
    0%   { left: 0%;   opacity: 0; }
    10%  { opacity: 1; }
    90%  { opacity: 1; }
    100% { left: 100%; opacity: 0; }
  }
  @keyframes fadeIn {
    from { opacity:0; transform: translateY(6px); }
    to   { opacity:1; transform: translateY(0); }
  }
  .log-entry { animation: fadeIn 0.3s ease forwards; }
`;

// ── Flow connector with animated dot ─────────────────────────────────
function FlowArrow({ active, color }) {
  return (
    <div style={{ position: "relative", width: 48, height: 2,
                  background: active ? color + "44" : "#ffffff11",
                  alignSelf: "center", flexShrink: 0, overflow: "visible" }}>
      {active && (
        <div style={{
          position: "absolute", top: -3, width: 8, height: 8,
          borderRadius: "50%", background: color,
          boxShadow: `0 0 8px ${color}`,
          animation: "flowDot 0.8s linear infinite"
        }}/>
      )}
      <div style={{
        position: "absolute", right: -5, top: -4,
        borderLeft: `8px solid ${active ? color : "#ffffff22"}`,
        borderTop: "4px solid transparent",
        borderBottom: "4px solid transparent"
      }}/>
    </div>
  );
}

// ── Agent Node Card ───────────────────────────────────────────────────
function AgentNode({ name, active, result, pulsing }) {
  const cfg = AGENTS[name];
  return (
    <div style={{
      background: active ? cfg.bg : "#0a0a0a",
      border: `1px solid ${active ? cfg.color : "#ffffff15"}`,
      borderRadius: 10, padding: "12px 16px", minWidth: 130,
      boxShadow: active ? `0 0 20px ${cfg.color}44, inset 0 0 20px ${cfg.color}11` : "none",
      transition: "all 0.4s ease", flexShrink: 0
    }}>
      <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 6 }}>
        <span style={{ fontSize: 18 }}>{cfg.icon}</span>
        <div style={{
          width: 8, height: 8, borderRadius: "50%",
          background: active ? cfg.color : "#333",
          animation: pulsing ? "pulse 1s infinite" : "none",
          boxShadow: active ? `0 0 8px ${cfg.color}` : "none"
        }}/>
      </div>
      <div style={{
        fontFamily: "Orbitron", fontSize: 9, fontWeight: 700,
        color: active ? cfg.color : "#666",
        letterSpacing: 1, marginBottom: 4
      }}>{name.replace("Agent","").replace("Matching","Match")}</div>
      <div style={{ fontFamily: "JetBrains Mono", fontSize: 9, color: "#444" }}>
        {cfg.role}
      </div>
      {result && (
        <div style={{
          marginTop: 8, padding: "4px 6px",
          background: cfg.color + "22", borderRadius: 4,
          fontFamily: "JetBrains Mono", fontSize: 9, color: cfg.color
        }}>
          {result.offer_type || result.assigned_segment || "\u2713"}
        </div>
      )}
    </div>
  );
}

// ── Log Entry ─────────────────────────────────────────────────────────
function LogEntry({ event }) {
  const style = EVENT_STYLES[event.type] || EVENT_STYLES.THINKING;
  return (
    <div className="log-entry" style={{
      display: "flex", gap: 10, padding: "8px 12px",
      borderLeft: `2px solid ${style.color}`,
      background: style.color + "08",
      marginBottom: 6, borderRadius: "0 6px 6px 0"
    }}>
      <span style={{ fontSize: 14, flexShrink: 0 }}>{style.icon}</span>
      <div style={{ flex: 1 }}>
        <div style={{ display: "flex", gap: 8, alignItems: "center", marginBottom: 2 }}>
          <span style={{
            fontFamily: "Orbitron", fontSize: 8, color: style.color,
            background: style.color + "22", padding: "1px 6px", borderRadius: 3
          }}>{style.label}</span>
          {event.agent && (
            <span style={{
              fontFamily: "Orbitron", fontSize: 8,
              color: AGENTS[event.agent]?.color || "#666"
            }}>{event.agent}</span>
          )}
          <span style={{ fontFamily: "JetBrains Mono", fontSize: 9, color: "#444", marginLeft: "auto" }}>
            {event.timestamp}
          </span>
        </div>
        <div style={{ fontFamily: "JetBrains Mono", fontSize: 11, color: "#ccc", lineHeight: 1.5 }}>
          {event.message}
        </div>
        {event.data?.reasoning && (
          <div style={{
            marginTop: 4, fontFamily: "JetBrains Mono", fontSize: 10,
            color: "#888", fontStyle: "italic"
          }}>
            \ud83d\udcad {event.data.reasoning}
          </div>
        )}
      </div>
    </div>
  );
}

// ── Agent Flow Diagram ────────────────────────────────────────────────
function FlowDiagram({ activeAgents, results }) {
  const flow = ["Orchestrator","SegmentationAgent","RecommendationAgent",
                "PersonalisationAgent","ChurnAgent","SponsorMatchingAgent"];

  // Find last two active for arrow highlighting
  const actives = flow.filter(a => activeAgents.has(a));

  return (
    <div style={{ padding: "20px 24px" }}>
      <div style={{
        fontFamily: "Orbitron", fontSize: 10, color: "#00D4FF",
        letterSpacing: 2, marginBottom: 16
      }}>AGENT FLOW</div>

      {/* Main orchestrator row */}
      <div style={{ display: "flex", alignItems: "center", gap: 0, marginBottom: 20 }}>
        <AgentNode name="Orchestrator"
          active={activeAgents.has("Orchestrator")}
          pulsing={activeAgents.has("Orchestrator")}
          result={null}
        />
        <FlowArrow active={actives.length > 0}
          color={AGENTS["Orchestrator"].color} />
        <div style={{
          display: "grid", gridTemplateColumns: "1fr 1fr",
          gap: 8, flex: 1
        }}>
          {["ChurnAgent","PersonalisationAgent","RecommendationAgent",
            "SegmentationAgent","SponsorMatchingAgent"].map(name => (
            <AgentNode key={name} name={name}
              active={activeAgents.has(name)}
              pulsing={activeAgents.has(name)}
              result={results[name]}
            />
          ))}
        </div>
      </div>

      {/* Active chain text */}
      {actives.length > 1 && (
        <div style={{
          fontFamily: "JetBrains Mono", fontSize: 11,
          color: "#00D4FF", display: "flex", alignItems: "center", gap: 6,
          flexWrap: "wrap"
        }}>
          {actives.map((a, i) => (
            <React.Fragment key={a}>
              <span style={{ color: AGENTS[a]?.color }}>{a.replace("Agent","")}</span>
              {i < actives.length - 1 && <ChevronRight size={12} color="#444"/>}
            </React.Fragment>
          ))}
        </div>
      )}
    </div>
  );
}

// ── Plain English Status ──────────────────────────────────────────────
function StatusPanel({ events, activeAgents }) {
  const latest = events[events.length - 1];
  if (!latest) return (
    <div style={{ padding: 24, fontFamily: "JetBrains Mono",
                  fontSize: 13, color: "#444" }}>
      Waiting for fan event...
    </div>
  );

  const summaries = {
    THINKING:  (e) => `The Orchestrator is reading ${e.agent === "Orchestrator" ? "fan data from Gold tables" : "context"} to understand this fan.`,
    ROUTING:   (e) => `The Orchestrator has decided: ${e.data?.target_child_agent ? `route to ${e.data.target_child_agent}` : "make a routing decision"}.`,
    A2A:       (e) => `The Orchestrator is calling ${e.agent} to generate the right offer for this fan.`,
    RESULT:    (e) => `${e.agent} has responded with a ${e.data?.offer_type || e.data?.assigned_segment || "decision"}${e.data?.offer_detail ? ` \u2014 "${e.data.offer_detail}"` : ""}.`,
    WRITEBACK: (e) => `The result is being saved back to the Gold table in Microsoft Fabric (OneLake).`,
    ERROR:     (e) => `Something went wrong: ${e.message}`,
  };

  const summary = summaries[latest.type]?.(latest) || latest.message;

  return (
    <div style={{ padding: "16px 24px" }}>
      <div style={{
        fontFamily: "Orbitron", fontSize: 10, color: "#00D4FF",
        letterSpacing: 2, marginBottom: 12
      }}>WHAT'S HAPPENING</div>
      <div style={{
        fontFamily: "JetBrains Mono", fontSize: 13, color: "#e0e0e0",
        lineHeight: 1.8, padding: "12px 16px",
        background: "#00D4FF08", borderRadius: 8,
        borderLeft: "3px solid #00D4FF"
      }}>
        {summary}
      </div>
      {activeAgents.size > 0 && (
        <div style={{ marginTop: 12, display: "flex", gap: 8, flexWrap: "wrap" }}>
          {[...activeAgents].map(a => (
            <div key={a} style={{
              fontFamily: "JetBrains Mono", fontSize: 10,
              color: AGENTS[a]?.color || "#fff",
              background: (AGENTS[a]?.color || "#fff") + "22",
              padding: "3px 10px", borderRadius: 12,
              animation: "pulse 1.5s infinite"
            }}>
              {AGENTS[a]?.icon} {a.replace("Agent","")} active
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ── Trigger Panel ─────────────────────────────────────────────────────
function TriggerPanel({ onTrigger, loading }) {
  const scenarios = [
    { label: "Churn Drop",     fan_id: "FAN-d65867e0", event_type: "ChurnDrop",            emoji: "\ud83d\udd25", color: "#FF4D6D" },
    { label: "Engagement",     fan_id: "FAN-5b86fccb", event_type: "EngagementOpportunity", emoji: "\u2728", color: "#A855F7" },
    { label: "Birthday",       fan_id: "FAN-d65867e0", event_type: "BirthdayEvent",         emoji: "\ud83c\udf82", color: "#F59E0B" },
    { label: "Gate Scan",      fan_id: "FAN-5b86fccb", event_type: "GateScan",              emoji: "\ud83d\udeaa", color: "#10B981" },
    { label: "Sponsor Match",  fan_id: "FAN-d65867e0", event_type: "SponsorOpportunity",    emoji: "\ud83e\udd1d", color: "#3B82F6" },
  ];

  return (
    <div style={{ padding: "16px 24px", borderTop: "1px solid #ffffff0a" }}>
      <div style={{
        fontFamily: "Orbitron", fontSize: 10, color: "#00D4FF",
        letterSpacing: 2, marginBottom: 12
      }}>FIRE TRIGGER</div>
      <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
        {scenarios.map(s => (
          <button key={s.label}
            onClick={() => onTrigger(s.fan_id, s.event_type)}
            disabled={loading}
            style={{
              fontFamily: "Orbitron", fontSize: 9, fontWeight: 700,
              color: s.color, background: s.color + "18",
              border: `1px solid ${s.color}44`,
              padding: "8px 14px", borderRadius: 6, cursor: "pointer",
              letterSpacing: 1, transition: "all 0.2s",
              opacity: loading ? 0.5 : 1
            }}>
            {s.emoji} {s.label.toUpperCase()}
          </button>
        ))}
      </div>
    </div>
  );
}

// ── Main App ──────────────────────────────────────────────────────────
export default function App() {
  const [events, setEvents]           = useState([]);
  const [activeAgents, setActiveAgents] = useState(new Set());
  const [results, setResults]         = useState({});
  const [loading, setLoading]         = useState(false);
  const [connected, setConnected]     = useState(false);
  const logRef                        = useRef(null);

  // ── Connect to SSE stream ─────────────────────────────────────────
  useEffect(() => {
    const es = new EventSource("http://localhost:8000/events");
    es.onopen    = () => setConnected(true);
    es.onerror   = () => setConnected(false);
    es.onmessage = (e) => {
      if (!e.data || e.data === "{}") return;
      try {
        const event = JSON.parse(e.data);
        setEvents(prev => [...prev.slice(-99), event]);

        // Track active agents
        if (event.agent) {
          setActiveAgents(prev => new Set([...prev, event.agent]));
          // Deactivate after 4s
          setTimeout(() => setActiveAgents(prev => {
            const n = new Set(prev); n.delete(event.agent); return n;
          }), 4000);
        }

        // Store results per agent
        if (event.type === "RESULT" && event.agent && event.data) {
          setResults(prev => ({ ...prev, [event.agent]: event.data }));
        }

        // Clear on new fan trigger
        if (event.type === "THINKING" && event.message?.includes("Reading fan")) {
          setResults({});
          setActiveAgents(new Set(["Orchestrator"]));
        }

      } catch {}
    };
    return () => es.close();
  }, []);

  // Auto-scroll log
  useEffect(() => {
    if (logRef.current)
      logRef.current.scrollTop = logRef.current.scrollHeight;
  }, [events]);

  // ── Fire trigger ──────────────────────────────────────────────────
  const handleTrigger = async (fan_id, event_type) => {
    setLoading(true);
    setEvents([]);
    setResults({});
    setActiveAgents(new Set(["Orchestrator"]));
    try {
      await fetch("http://localhost:8000/webhook/test", {
        method:  "POST",
        headers: { "Content-Type": "application/json" },
        body:    JSON.stringify({ fan_id, event_type })
      });
    } catch (e) {
      console.error(e);
    } finally {
      setTimeout(() => setLoading(false), 2000);
    }
  };

  return (
    <>
      <style>{globalStyles}</style>
      <div style={{ background: "#000", minHeight: "100vh", color: "#fff",
                    fontFamily: "JetBrains Mono" }}>

        {/* Scanline overlay */}
        <div style={{
          position: "fixed", top: 0, left: 0, right: 0, bottom: 0,
          pointerEvents: "none", zIndex: 9999,
          background: "repeating-linear-gradient(0deg, transparent, transparent 2px, rgba(0,212,255,0.015) 2px, rgba(0,212,255,0.015) 4px)"
        }}/>

        {/* Header */}
        <div style={{
          borderBottom: "1px solid #00D4FF22",
          padding: "16px 28px",
          display: "flex", alignItems: "center", justifyContent: "space-between",
          background: "linear-gradient(90deg, #00D4FF08, transparent)"
        }}>
          <div>
            <div style={{
              fontFamily: "Orbitron", fontSize: 18, fontWeight: 900,
              color: "#00D4FF", letterSpacing: 4,
              textShadow: "0 0 20px #00D4FF88"
            }}>FAN360</div>
            <div style={{
              fontFamily: "Orbitron", fontSize: 9, color: "#ffffff44",
              letterSpacing: 3, marginTop: 2
            }}>MULTI-AGENT CONTROL ROOM</div>
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <div style={{
              width: 8, height: 8, borderRadius: "50%",
              background: connected ? "#10B981" : "#FF4D6D",
              animation: connected ? "pulse 2s infinite" : "none",
              boxShadow: connected ? "0 0 8px #10B981" : "none"
            }}/>
            <span style={{
              fontFamily: "Orbitron", fontSize: 9, letterSpacing: 2,
              color: connected ? "#10B981" : "#FF4D6D"
            }}>
              {connected ? "LIVE" : "OFFLINE"}
            </span>
            <span style={{ color: "#444", fontSize: 9, marginLeft: 8 }}>
              Azure AI Foundry \u00b7 AutoGen A2A \u00b7 Semantic Kernel \u00b7 Microsoft Fabric
            </span>
          </div>
        </div>

        {/* Main Grid */}
        <div style={{
          display: "grid",
          gridTemplateColumns: "1fr 380px",
          gridTemplateRows:    "auto auto 1fr",
          height: "calc(100vh - 61px)"
        }}>

          {/* Left col */}
          <div style={{ display: "flex", flexDirection: "column",
                        borderRight: "1px solid #ffffff08", overflow: "hidden" }}>

            {/* Flow diagram */}
            <div style={{ borderBottom: "1px solid #ffffff08" }}>
              <FlowDiagram activeAgents={activeAgents} results={results} />
            </div>

            {/* Status */}
            <div style={{ borderBottom: "1px solid #ffffff08" }}>
              <StatusPanel events={events} activeAgents={activeAgents} />
            </div>

            {/* Trigger */}
            <TriggerPanel onTrigger={handleTrigger} loading={loading} />
          </div>

          {/* Right col — live log */}
          <div style={{ display: "flex", flexDirection: "column", overflow: "hidden" }}>
            <div style={{
              padding: "14px 20px", borderBottom: "1px solid #ffffff08",
              display: "flex", alignItems: "center", gap: 8
            }}>
              <Radio size={12} color="#00D4FF"
                style={{ animation: "pulse 1.5s infinite" }}/>
              <span style={{
                fontFamily: "Orbitron", fontSize: 10,
                color: "#00D4FF", letterSpacing: 2
              }}>LIVE EVENT LOG</span>
              <span style={{
                marginLeft: "auto", fontFamily: "JetBrains Mono",
                fontSize: 9, color: "#444"
              }}>{events.length} events</span>
            </div>
            <div ref={logRef} style={{
              flex: 1, overflowY: "auto", padding: "12px 16px"
            }}>
              {events.length === 0 ? (
                <div style={{
                  textAlign: "center", color: "#333",
                  fontFamily: "Orbitron", fontSize: 10,
                  letterSpacing: 2, marginTop: 40
                }}>
                  AWAITING TRIGGER
                </div>
              ) : (
                events.map((e, i) => <LogEntry key={i} event={e} />)
              )}
            </div>
          </div>

        </div>
      </div>
    </>
  );
}
