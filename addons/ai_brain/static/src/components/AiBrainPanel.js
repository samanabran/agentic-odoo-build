/** @odoo-module **/

import { Component, useState, markup } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { rpc } from "@web/core/network/rpc";
import { xml } from "@odoo/owl";

const ACTIONS = [
    { id: "summary",          label: "Financial Summary",    icon: "fa-bar-chart",        color: "primary",   prompt: "Give me a concise financial summary for today: total receivables outstanding, total payables due, and any overdue items requiring immediate attention." },
    { id: "invoices",         label: "Outstanding Invoices", icon: "fa-file-text-o",      color: "info",      prompt: "List outstanding unpaid customer invoices grouped by aging: 0-30 days, 31-60 days, 61-90 days, and 90+ days overdue. Show totals per bucket." },
    { id: "cash",             label: "Cash Position",        icon: "fa-money",            color: "success",   prompt: "What is the current cash position? List bank account balances and total liquid cash available." },
    { id: "reconcile",        label: "Reconciliation",       icon: "fa-refresh",          color: "warning",   prompt: "Are there any unreconciled bank statement lines? Summarise what is pending reconciliation and highlight any urgent items." },
    { id: "aml",              label: "AML Patterns",         icon: "fa-search",           color: "danger",    prompt: "Run an AML pattern scan for the last 30 days. Identify structuring, round-number, or high-frequency transaction patterns. List any high-severity alerts." },
    { id: "receivables",      label: "Aged Receivables",     icon: "fa-arrow-circle-up",  color: "info",      prompt: "Show the aged receivables report. Group amounts customers owe us by: current, 1-30 days, 31-60 days, 61-90 days, 90+ days. Include top 5 overdue customers." },
    { id: "payables",         label: "Aged Payables",        icon: "fa-arrow-circle-down",color: "warning",   prompt: "Show the aged payables report. Group amounts we owe vendors by due date. Highlight any overdue payables." },
    { id: "tax",              label: "VAT / Tax Summary",    icon: "fa-calculator",       color: "secondary", prompt: "Summarise tax obligations for the current period: VAT collected on sales, VAT paid on purchases, and net VAT payable or refundable." },
    { id: "pnl",              label: "P&L Snapshot",         icon: "fa-line-chart",       color: "success",   prompt: "" },
    { id: "hr",               label: "Headcount",            icon: "fa-users",            color: "info",      prompt: "" },
    { id: "payroll",          label: "Payroll Costs",        icon: "fa-id-card-o",        color: "warning",   prompt: "" },
    { id: "leaves",           label: "Leave Requests",       icon: "fa-calendar-times-o", color: "secondary", prompt: "" },
    { id: "sales",            label: "Sales Performance",    icon: "fa-trophy",           color: "success",   prompt: "" },
    { id: "pipeline",         label: "CRM Pipeline",         icon: "fa-filter",           color: "primary",   prompt: "" },
    { id: "payroll_revenue",  label: "Payroll vs Revenue",   icon: "fa-balance-scale",    color: "danger",    prompt: "Compare total payroll costs against revenue for the current month. Show the labour cost ratio and flag as critical if it exceeds 50% of revenue. Include P&L summary." },
];

export class AiBrainPanel extends Component {
    setup() {
        this.state = useState({
            loading: false,
            activeId: null,
            replyHtml: null,
            messages: [],
            error: "",
            customPrompt: "",
        });
        this.actions = ACTIONS;
    }

    // ── Quick Command → renders in big report area ──────────────────────────
    async onActionClick(action) {
        Object.assign(this.state, { loading: true, activeId: action.id, replyHtml: null, error: "" });
        try {
            const result = await rpc("/ai_brain/finance", { action: action.id, prompt: action.prompt });
            const raw = result?.reply ?? JSON.stringify(result, null, 2);
            this.state.replyHtml = raw ? markup(raw) : null;
        } catch (err) {
            this.state.error = err?.data?.message || err?.message || "Request failed — please try again.";
        } finally {
            this.state.loading = false;
        }
    }

    // ── Custom message → adds to chat history ───────────────────────────────
    async onAsk() {
        const q = this.state.customPrompt.trim();
        if (!q) return;
        this.state.messages = [...this.state.messages, { role: "user", text: q }];
        this.state.customPrompt = "";
        Object.assign(this.state, { loading: true, activeId: "custom" });
        try {
            const result = await rpc("/ai_brain/finance", { action: "custom", prompt: q });
            const raw = result?.reply ?? JSON.stringify(result, null, 2);
            this.state.messages = [
                ...this.state.messages,
                { role: "ai", text: raw, html: raw ? markup(raw) : null },
            ];
        } catch (err) {
            const msg = err?.data?.message || err?.message || "Request failed.";
            this.state.messages = [...this.state.messages, { role: "ai", text: msg, html: null }];
        } finally {
            this.state.loading = false;
        }
    }

    onKeydown(ev) { if (ev.key === "Enter") this.onAsk(); }

    onClear() {
        Object.assign(this.state, { replyHtml: null, error: "", activeId: null });
    }

    onClearChat() {
        this.state.messages = [];
    }

    getActiveLabel() {
        const a = ACTIONS.find(x => x.id === this.state.activeId);
        return a ? a.label : (this.state.activeId || "");
    }

    // ── Download current report as HTML attachment ──────────────────────────
    onDownloadReport() {
        if (!this.state.replyHtml) return;
        const label = this.getActiveLabel() || "report";
        const date  = new Date().toISOString().slice(0, 10);
        const htmlContent = `<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>SGCTech AI — ${label} — ${date}</title>
<style>
  body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; padding: 32px; max-width: 960px; margin: 0 auto; background: #0f1923; color: #f8fafc; }
  h1 { font-size: 1.25rem; font-weight: 700; color: #f8fafc; border-bottom: 1px solid #2d4057; padding-bottom: 8px; margin: 0 0 16px; }
  h2 { font-size: 1rem; font-weight: 700; color: #06BEA0; margin: 16px 0 10px; }
  h3 { font-size: 0.9rem; font-weight: 700; color: #94a3b8; margin: 12px 0 8px; }
  p  { color: #94a3b8; margin: 6px 0 10px; }
  hr { border: none; border-top: 1px solid #2d4057; margin: 14px 0; }
  ul, ol { padding-left: 20px; color: #94a3b8; }
  strong { color: #f8fafc; font-weight: 700; }
  table { width: 100%; border-collapse: collapse; margin: 12px 0; font-size: 0.85rem; background: #243447; border-radius: 8px; overflow: hidden; border: 1px solid #2d4057; }
  th { padding: 9px 12px; background: #1e2d3d; font-weight: 700; font-size: 0.72rem; text-transform: uppercase; letter-spacing: 0.06em; border-bottom: 1px solid #2d4057; text-align: left; color: #06BEA0; }
  td { padding: 8px 12px; border-bottom: 1px solid #2d4057; color: #94a3b8; }
  tr:last-child td { border-bottom: none; }
  tr:hover td { background: #1e2d3d; }
  .ai-metric-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)); gap: 12px; margin: 12px 0 18px; }
  .ai-metric-card { border: 1px solid #2d4057; border-radius: 10px; padding: 14px 16px; background: #243447; }
  .ai-metric-label { font-size: 0.7rem; color: #64748b; font-weight: 700; text-transform: uppercase; letter-spacing: 0.07em; }
  .ai-metric-value { font-size: 1.3rem; font-weight: 700; color: #f8fafc; margin-top: 5px; }
  .ai-metric-sub   { font-size: 0.72rem; color: #64748b; margin-top: 2px; }
  .ai-metric-card.danger  { border-color: #7f1d1d; background: #180808; } .ai-metric-card.danger  .ai-metric-value { color: #f87171; }
  .ai-metric-card.warning { border-color: #78350f; background: #180f04; } .ai-metric-card.warning .ai-metric-value { color: #fbbf24; }
  .ai-metric-card.success { border-color: #14532d; background: #061310; } .ai-metric-card.success .ai-metric-value { color: #4ade80; }
  .ai-progress-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)); gap: 12px; margin: 12px 0 18px; }
  .ai-progress-item { background: #243447; border: 1px solid #2d4057; border-radius: 10px; padding: 12px 14px; }
  .ai-progress-label { font-size: 0.7rem; color: #64748b; font-weight: 700; text-transform: uppercase; margin-bottom: 8px; }
  .ai-progress-track { height: 6px; background: #2d4057; border-radius: 4px; overflow: hidden; margin-bottom: 6px; }
  .ai-progress-fill  { height: 100%; border-radius: 4px; background: #06BEA0; min-width: 4px; }
  .ai-progress-pct   { font-size: 1.05rem; font-weight: 700; color: #f8fafc; }
  .ai-progress-sub   { font-size: 0.72rem; color: #64748b; }
  .ai-progress-item.danger  .ai-progress-fill { background: #ef4444; }
  .ai-progress-item.warning .ai-progress-fill { background: #f59e0b; }
  .ai-progress-item.success .ai-progress-fill { background: #22c55e; }
  .ai-progress-item.info    .ai-progress-fill { background: #3b82f6; }
  .ai-alert { border-left: 3px solid; padding: 10px 14px; margin: 10px 0; border-radius: 0 8px 8px 0; font-size: 0.87rem; }
  .ai-alert.critical { border-color: #ef4444; background: #180808; color: #f87171; }
  .ai-alert.warning  { border-color: #f59e0b; background: #180f04; color: #fbbf24; }
  .ai-alert.info     { border-color: #3b82f6; background: #080f1e; color: #60a5fa; }
  .ai-alert.success  { border-color: #06BEA0; background: #061310; color: #07D4B5; }
  .badge-ok,.badge-warn,.badge-danger,.badge-info { display:inline-block; padding:2px 9px; border-radius:9999px; font-size:0.72rem; font-weight:700; }
  .badge-ok { background:#14532d; color:#4ade80; } .badge-warn { background:#78350f; color:#fbbf24; }
  .badge-danger { background:#7f1d1d; color:#f87171; } .badge-info { background:#1e3a5f; color:#60a5fa; }
</style>
</head>
<body>
${this.state.replyHtml}
</body>
</html>`;
        const blob = new Blob([htmlContent], { type: "text/html" });
        const url  = URL.createObjectURL(blob);
        const a    = document.createElement("a");
        a.href = url;
        a.download = `ai-brain-${label.toLowerCase().replace(/\s+/g, "-")}-${date}.html`;
        a.click();
        URL.revokeObjectURL(url);
    }
}

AiBrainPanel.template = "ai_brain.AiBrainPanel";
registry.category("actions").add("ai_brain.panel", AiBrainPanel);

// Systray robot icon
class AiBrainSystray extends Component {
    static template = xml`
        <div class="o_menu_systray_item o_ai_brain_systray" title="AI Brain">
            <i class="fa fa-robot" role="img" aria-label="AI Brain"/>
        </div>
    `;
}

registry.category("systray").add("ai_brain.systray", { Component: AiBrainSystray }, { sequence: 1 });
