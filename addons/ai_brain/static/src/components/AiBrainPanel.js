/** @odoo-module **/

import { Component, useState, xml, markup } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { rpc } from "@web/core/network/rpc";

const ACTIONS = [
    {
        id: "summary",
        label: "Financial Summary",
        icon: "fa-bar-chart",
        color: "primary",
        prompt: "Give me a concise financial summary for today: total receivables outstanding, total payables due, and any overdue items requiring immediate attention.",
    },
    {
        id: "invoices",
        label: "Outstanding Invoices",
        icon: "fa-file-text-o",
        color: "info",
        prompt: "List outstanding unpaid customer invoices grouped by aging: 0-30 days, 31-60 days, 61-90 days, and 90+ days overdue. Show totals per bucket.",
    },
    {
        id: "cash",
        label: "Cash Position",
        icon: "fa-money",
        color: "success",
        prompt: "What is the current cash position? List bank account balances and total liquid cash available.",
    },
    {
        id: "reconcile",
        label: "Reconciliation Status",
        icon: "fa-refresh",
        color: "warning",
        prompt: "Are there any unreconciled bank statement lines? Summarise what is pending reconciliation and highlight any urgent items.",
    },
    {
        id: "aml",
        label: "AML Patterns",
        icon: "fa-search",
        color: "danger",
        prompt: "Run an AML pattern scan for the last 30 days. Identify structuring, round-number, or high-frequency transaction patterns. List any high-severity alerts.",
    },
    {
        id: "receivables",
        label: "Aged Receivables",
        icon: "fa-arrow-circle-up",
        color: "info",
        prompt: "Show the aged receivables report. Group amounts customers owe us by: current, 1-30 days, 31-60 days, 61-90 days, 90+ days. Include top 5 overdue customers.",
    },
    {
        id: "payables",
        label: "Aged Payables",
        icon: "fa-arrow-circle-down",
        color: "warning",
        prompt: "Show the aged payables report. Group amounts we owe vendors by due date. Highlight any overdue payables.",
    },
    {
        id: "tax",
        label: "VAT / Tax Summary",
        icon: "fa-calculator",
        color: "secondary",
        prompt: "Summarise tax obligations for the current period: VAT collected on sales, VAT paid on purchases, and net VAT payable or refundable.",
    },
    {
        id: "pnl",
        label: "P&L Snapshot",
        icon: "fa-line-chart",
        color: "success",
        prompt: "",
    },
    {
        id: "hr",
        label: "Headcount",
        icon: "fa-users",
        color: "info",
        prompt: "",
    },
    {
        id: "payroll",
        label: "Payroll Costs",
        icon: "fa-id-card-o",
        color: "warning",
        prompt: "",
    },
    {
        id: "leaves",
        label: "Leave Requests",
        icon: "fa-calendar-times-o",
        color: "secondary",
        prompt: "",
    },
    {
        id: "sales",
        label: "Sales Performance",
        icon: "fa-trophy",
        color: "success",
        prompt: "",
    },
    {
        id: "pipeline",
        label: "CRM Pipeline",
        icon: "fa-filter",
        color: "primary",
        prompt: "",
    },
    {
        id: "payroll_revenue",
        label: "Payroll vs Revenue",
        icon: "fa-balance-scale",
        color: "danger",
        prompt: "",
    },
];

export class AiBrainPanel extends Component {
    setup() {
        this.state = useState({
            loading: false,
            activeId: null,
            replyHtml: null,   // null = no content; markup(str) = content to render
            error: "",
            customPrompt: "",
        });
        this.actions = ACTIONS;
    }

    async _call(prompt, id) {
        Object.assign(this.state, { loading: true, activeId: id, replyHtml: null, error: "" });
        try {
            const isCustom = id === "custom";
            const result = isCustom
                ? await rpc("/ai_brain/finance", { action: "custom", prompt })
                : await rpc("/ai_brain/finance", { action: id, prompt });
            const raw = result?.reply ?? JSON.stringify(result, null, 2);
            this.state.replyHtml = raw ? markup(raw) : null;
        } catch (err) {
            this.state.error =
                err?.data?.message || err?.message || "Unexpected error — please try again.";
        } finally {
            this.state.loading = false;
        }
    }

    onActionClick(action) { this._call(action.prompt, action.id); }
    onAsk() { const q = this.state.customPrompt.trim(); if (q) this._call(q, "custom"); }
    onKeydown(ev) { if (ev.key === "Enter") this.onAsk(); }
    onClear() { Object.assign(this.state, { replyHtml: null, error: "", activeId: null }); }
}

AiBrainPanel.template = "ai_brain.AiBrainPanel";
registry.category("actions").add("ai_brain.panel", AiBrainPanel);

// Systray robot icon (top navigation bar)
class AiBrainSystray extends Component {
    static template = xml`
        <div class="o_menu_systray_item o_ai_brain_systray" title="AI Brain">
            <i class="fa fa-robot" role="img" aria-label="AI Brain"/>
        </div>
    `;
}

registry.category("systray").add("ai_brain.systray", {
    Component: AiBrainSystray,
}, { sequence: 1 });
