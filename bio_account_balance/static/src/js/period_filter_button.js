/** @odoo-module **/

import { Component, useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { registry } from "@web/core/registry";
import { Dropdown } from "@web/core/dropdown/dropdown";
import { DropdownItem } from "@web/core/dropdown/dropdown_item";

/**
 * Period Filter Button - Dropdown with period selection
 *
 * Pure JavaScript implementation - NO wizard needed!
 */
export class PeriodFilterButton extends Component {
    setup() {
        this.action = useService("action");
        this.notification = useService("notification");

        this.state = useState({
            showCustomModal: false,
            customStart: this.getYearStart(),
            customEnd: this.getToday(),
        });
    }

    // ========================================================================
    // Date Helpers
    // ========================================================================

    getToday() {
        const date = new Date();
        return date.toISOString().split('T')[0];
    }

    getYearStart() {
        const date = new Date();
        return `${date.getFullYear()}-01-01`;
    }

    getMonthStart() {
        const date = new Date();
        const year = date.getFullYear();
        const month = String(date.getMonth() + 1).padStart(2, '0');
        return `${year}-${month}-01`;
    }

    getLastMonthStart() {
        const date = new Date();
        date.setMonth(date.getMonth() - 1);
        const year = date.getFullYear();
        const month = String(date.getMonth() + 1).padStart(2, '0');
        return `${year}-${month}-01`;
    }

    getLastMonthEnd() {
        const date = new Date();
        date.setDate(0); // Last day of previous month
        return date.toISOString().split('T')[0];
    }

    // ========================================================================
    // Period Application
    // ========================================================================

    /**
     * Apply period by reloading action with new context
     */
    async applyPeriod(periodStart, periodEnd) {
        // Get current action
        const currentAction = this.env.config?.actionId || this.env.config?.action?.id;

        if (!currentAction) {
            this.notification.add("Cannot reload action - no action found", {
                type: "warning"
            });
            return;
        }

        // Reload action with updated context
        await this.action.doAction(currentAction, {
            additionalContext: {
                period_start: periodStart,
                period_end: periodEnd,
            },
            clearBreadcrumbs: false,
            replace_last_action: true,
        });

        // Show success notification
        this.notification.add(
            `Period applied: ${periodStart} to ${periodEnd}`,
            { type: "success" }
        );
    }

    // ========================================================================
    // Event Handlers
    // ========================================================================

    async onThisYear() {
        await this.applyPeriod(this.getYearStart(), this.getToday());
    }

    async onThisMonth() {
        await this.applyPeriod(this.getMonthStart(), this.getToday());
    }

    async onLastMonth() {
        await this.applyPeriod(this.getLastMonthStart(), this.getLastMonthEnd());
    }

    /**
     * Open custom date picker modal
     */
    onCustomPeriod() {
        this.state.showCustomModal = true;
    }

    /**
     * Apply custom period from modal
     */
    async onApplyCustom() {
        const start = this.state.customStart;
        const end = this.state.customEnd;

        // Validation
        if (!start || !end) {
            this.notification.add(
                "Please select both start and end dates",
                { type: "warning" }
            );
            return;
        }

        if (start > end) {
            this.notification.add(
                "Start date must be before end date",
                { type: "warning" }
            );
            return;
        }

        this.state.showCustomModal = false;
        await this.applyPeriod(start, end);
    }

    /**
     * Cancel custom modal
     */
    onCancelCustom() {
        this.state.showCustomModal = false;
    }
}

PeriodFilterButton.template = "bio_account_balance.PeriodFilterButton";
PeriodFilterButton.components = { Dropdown, DropdownItem };

// Register as control panel button
registry.category("view_widgets").add("period_filter_button", PeriodFilterButton);
