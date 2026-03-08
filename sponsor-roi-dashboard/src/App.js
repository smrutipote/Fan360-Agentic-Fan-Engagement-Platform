import React, { useState } from "react";
import {
  BarChart, Bar, LineChart, Line, PieChart, Pie, Cell,
  XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer
} from "recharts";
import { TrendingUp, Users, Mail, Target, Award, ChevronDown } from "lucide-react";

// ── Mock data shaped like gold_sponsor_audiences ──────────────────────
const SPONSORS = [
  { id: "heineken",  name: "Heineken",   segment: "Match Day Diehards",    color: "#00A651" },
  { id: "bdo",       name: "BDO",        segment: "Business Executives",   color: "#E63946" },
  { id: "energia",   name: "Energia",    segment: "Sustainability Fans",   color: "#F4A261" },
  { id: "aib",       name: "AIB",        segment: "Season Ticket Holders", color: "#003087" },
];

const SPONSOR_DATA = {
  heineken: {
    audience_size:    12400,
    offers_sent:      8200,
    offers_opened:    5330,
    offers_redeemed:  1890,
    avg_spend_uplift: 34,
    roi_percent:      287,
    trend: [
      { month: "Oct", redeemed: 210, opened: 580 },
      { month: "Nov", redeemed: 340, opened: 820 },
      { month: "Dec", redeemed: 290, opened: 750 },
      { month: "Jan", redeemed: 410, opened: 910 },
      { month: "Feb", redeemed: 390, opened: 870 },
      { month: "Mar", redeemed: 250, opened: 400 },
    ],
    top_offers: [
      { name: "Matchday Pint Offer",      redeemed: 780 },
      { name: "Half-time Promotion",      redeemed: 620 },
      { name: "Season Ticket Bundle",     redeemed: 490 },
    ],
    segment_breakdown: [
      { name: "VIP Diehard",    value: 38 },
      { name: "Loyal Regular",  value: 41 },
      { name: "Casual Fan",     value: 21 },
    ],
  },
  bdo: {
    audience_size:    3100,
    offers_sent:      2800,
    offers_opened:    1960,
    offers_redeemed:  640,
    avg_spend_uplift: 52,
    roi_percent:      341,
    trend: [
      { month: "Oct", redeemed: 60,  opened: 180 },
      { month: "Nov", redeemed: 95,  opened: 290 },
      { month: "Dec", redeemed: 110, opened: 340 },
      { month: "Jan", redeemed: 130, opened: 420 },
      { month: "Feb", redeemed: 145, opened: 480 },
      { month: "Mar", redeemed: 100, opened: 250 },
    ],
    top_offers: [
      { name: "Corporate Box Experience", redeemed: 280 },
      { name: "Networking Match Night",   redeemed: 210 },
      { name: "Brand Visibility Package", redeemed: 150 },
    ],
    segment_breakdown: [
      { name: "VIP Diehard",   value: 55 },
      { name: "Loyal Regular", value: 35 },
      { name: "New Fan",       value: 10 },
    ],
  },
  energia: {
    audience_size:    5800,
    offers_sent:      4100,
    offers_opened:    2870,
    offers_redeemed:  980,
    avg_spend_uplift: 28,
    roi_percent:      214,
    trend: [
      { month: "Oct", redeemed: 90,  opened: 310 },
      { month: "Nov", redeemed: 145, opened: 420 },
      { month: "Dec", redeemed: 160, opened: 480 },
      { month: "Jan", redeemed: 200, opened: 590 },
      { month: "Feb", redeemed: 230, opened: 680 },
      { month: "Mar", redeemed: 155, opened: 390 },
    ],
    top_offers: [
      { name: "Green Match Initiative",   redeemed: 410 },
      { name: "Sustainability Pledge",    redeemed: 320 },
      { name: "Eco Fan Pack",             redeemed: 250 },
    ],
    segment_breakdown: [
      { name: "Casual Fan",    value: 44 },
      { name: "Loyal Regular", value: 36 },
      { name: "New Fan",       value: 20 },
    ],
  },
  aib: {
    audience_size:    9200,
    offers_sent:      7600,
    offers_opened:    5320,
    offers_redeemed:  2100,
    avg_spend_uplift: 41,
    roi_percent:      312,
    trend: [
      { month: "Oct", redeemed: 280, opened: 640 },
      { month: "Nov", redeemed: 330, opened: 780 },
      { month: "Dec", redeemed: 310, opened: 820 },
      { month: "Jan", redeemed: 420, opened: 990 },
      { month: "Feb", redeemed: 480, opened: 1100 },
      { month: "Mar", redeemed: 280, opened: 590 },
    ],
    top_offers: [
      { name: "Season Pass Finance",     redeemed: 890 },
      { name: "Away Trip Loan Offer",    redeemed: 720 },
      { name: "Fan Cashback Reward",     redeemed: 490 },
    ],
    segment_breakdown: [
      { name: "VIP Diehard",   value: 42 },
      { name: "Loyal Regular", value: 38 },
      { name: "Casual Fan",    value: 20 },
    ],
  },
};

const PIE_COLORS = ["#003087", "#0057B8", "#90CAF9", "#CFE2FF"];

const fmt = (n) => n >= 1000 ? `${(n / 1000).toFixed(1)}k` : n;

function StatCard({ icon: Icon, label, value, sub, color }) {
  return (
    <div style={{
      background: "white", borderRadius: 12, padding: "20px 24px",
      boxShadow: "0 2px 12px rgba(0,0,0,0.08)", flex: 1, minWidth: 160
    }}>
      <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 8 }}>
        <div style={{
          background: color + "22", borderRadius: 8,
          padding: 8, display: "flex"
        }}>
          <Icon size={18} color={color} />
        </div>
        <span style={{ fontSize: 13, color: "#666" }}>{label}</span>
      </div>
      <div style={{ fontSize: 28, fontWeight: 700, color: "#111" }}>{value}</div>
      {sub && <div style={{ fontSize: 12, color: "#999", marginTop: 4 }}>{sub}</div>}
    </div>
  );
}

export default function App() {
  const [selected, setSelected] = useState("heineken");
  const sponsor = SPONSORS.find(s => s.id === selected);
  const data    = SPONSOR_DATA[selected];
  const openRate    = Math.round((data.offers_opened   / data.offers_sent)    * 100);
  const redeemRate  = Math.round((data.offers_redeemed / data.offers_opened)  * 100);

  return (
    <div style={{ background: "#F4F6FB", minHeight: "100vh", fontFamily: "Inter, Arial, sans-serif" }}>

      {/* Header */}
      <div style={{
        background: "#003087", padding: "18px 32px",
        display: "flex", alignItems: "center", justifyContent: "space-between"
      }}>
        <div>
          <div style={{ color: "white", fontSize: 20, fontWeight: 700 }}>
            Fan360 · Sponsor ROI Dashboard
          </div>
          <div style={{ color: "#90CAF9", fontSize: 13 }}>
            Powered by gold_sponsor_audiences · GDPR-safe · Real-time
          </div>
        </div>
        <div style={{ color: "#90CAF9", fontSize: 13 }}>
          Leinster Rugby · Season 2025–26
        </div>
      </div>

      <div style={{ padding: "28px 32px" }}>

        {/* Sponsor Selector */}
        <div style={{ display: "flex", gap: 12, marginBottom: 28, flexWrap: "wrap" }}>
          {SPONSORS.map(s => (
            <button key={s.id} onClick={() => setSelected(s.id)} style={{
              padding: "10px 20px", borderRadius: 24,
              border: `2px solid ${selected === s.id ? s.color : "#ddd"}`,
              background: selected === s.id ? s.color : "white",
              color: selected === s.id ? "white" : "#333",
              fontWeight: 600, cursor: "pointer", fontSize: 14,
              transition: "all 0.2s"
            }}>
              {s.name}
              <span style={{
                marginLeft: 8, fontSize: 11,
                opacity: 0.8
              }}>· {s.segment}</span>
            </button>
          ))}
        </div>

        {/* KPI Cards */}
        <div style={{ display: "flex", gap: 16, marginBottom: 24, flexWrap: "wrap" }}>
          <StatCard icon={Users}     label="Audience Size"     value={fmt(data.audience_size)}  sub="GDPR-safe segment"   color="#003087" />
          <StatCard icon={Mail}      label="Offers Sent"       value={fmt(data.offers_sent)}    sub={`${openRate}% open rate`}  color="#0057B8" />
          <StatCard icon={Target}    label="Redeemed"          value={fmt(data.offers_redeemed)} sub={`${redeemRate}% of opens`} color="#F4A261" />
          <StatCard icon={TrendingUp} label="Spend Uplift"     value={`+${data.avg_spend_uplift}%`} sub="vs control group"  color="#2ECC71" />
          <StatCard icon={Award}     label="ROI"               value={`${data.roi_percent}%`}   sub="campaign return"     color="#E63946" />
        </div>

        {/* Charts Row */}
        <div style={{ display: "grid", gridTemplateColumns: "2fr 1fr", gap: 20, marginBottom: 20 }}>

          {/* Trend Line */}
          <div style={{ background: "white", borderRadius: 12, padding: 24, boxShadow: "0 2px 12px rgba(0,0,0,0.06)" }}>
            <div style={{ fontWeight: 700, marginBottom: 16, color: "#111" }}>
              Offer Performance Trend
            </div>
            <ResponsiveContainer width="100%" height={220}>
              <LineChart data={data.trend}>
                <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                <XAxis dataKey="month" tick={{ fontSize: 12 }} />
                <YAxis tick={{ fontSize: 12 }} />
                <Tooltip />
                <Legend />
                <Line type="monotone" dataKey="opened"   stroke="#003087" strokeWidth={2} dot={{ r: 4 }} name="Opened" />
                <Line type="monotone" dataKey="redeemed" stroke={sponsor.color} strokeWidth={2} dot={{ r: 4 }} name="Redeemed" />
              </LineChart>
            </ResponsiveContainer>
          </div>

          {/* Segment Pie */}
          <div style={{ background: "white", borderRadius: 12, padding: 24, boxShadow: "0 2px 12px rgba(0,0,0,0.06)" }}>
            <div style={{ fontWeight: 700, marginBottom: 16, color: "#111" }}>
              Audience Breakdown
            </div>
            <ResponsiveContainer width="100%" height={220}>
              <PieChart>
                <Pie data={data.segment_breakdown} cx="50%" cy="50%"
                  innerRadius={55} outerRadius={85}
                  dataKey="value" label={({ name, value }) => `${value}%`}
                  labelLine={false}>
                  {data.segment_breakdown.map((_, i) => (
                    <Cell key={i} fill={PIE_COLORS[i % PIE_COLORS.length]} />
                  ))}
                </Pie>
                <Tooltip formatter={(v) => `${v}%`} />
                <Legend />
              </PieChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Top Offers Bar */}
        <div style={{ background: "white", borderRadius: 12, padding: 24, boxShadow: "0 2px 12px rgba(0,0,0,0.06)" }}>
          <div style={{ fontWeight: 700, marginBottom: 16, color: "#111" }}>
            Top Performing Offers
          </div>
          <ResponsiveContainer width="100%" height={180}>
            <BarChart data={data.top_offers} layout="vertical">
              <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
              <XAxis type="number" tick={{ fontSize: 12 }} />
              <YAxis type="category" dataKey="name" tick={{ fontSize: 12 }} width={200} />
              <Tooltip />
              <Bar dataKey="redeemed" fill={sponsor.color} radius={[0, 6, 6, 0]} name="Redeemed" />
            </BarChart>
          </ResponsiveContainer>
        </div>

        {/* GDPR Footer */}
        <div style={{
          marginTop: 20, padding: "12px 20px",
          background: "#EEF2FF", borderRadius: 8,
          fontSize: 12, color: "#555",
          display: "flex", alignItems: "center", gap: 8
        }}>
          <span role="img" aria-label="lock">🔒</span> <strong>GDPR Compliant:</strong> Sponsors receive aggregated segment data only.
          No individual fan PII is shared. Data sourced from <code>gold_sponsor_audiences</code> via Fan360 MCP layer.
        </div>

      </div>
    </div>
  );
}
