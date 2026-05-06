/** @odoo-module **/

import { Component, xml } from "@odoo/owl";
import { registry } from "@web/core/registry";

// Placeholder systray icon — replaced by the full side-panel component in M3.
class AiBrainSystray extends Component {
    static template = xml`
        <div class="o_menu_systray_item o_ai_brain_systray" title="AI Brain">
            <i class="fa fa-robot" role="img" aria-label="AI Brain"/>
        </div>
    `;
}

registry.category("systray").add("ai_brain.panel", {
    Component: AiBrainSystray,
}, { sequence: 1 });
