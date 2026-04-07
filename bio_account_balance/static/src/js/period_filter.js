/** @odoo-module **/

import { Component, useState } from "@odoo/owl";

/**
 * Period Filter Component - Date Range Picker
 * Simple component that triggers events for parent controller
 */
export class PeriodFilter extends Component {
    static template = "bio_account_balance.PeriodFilter";
    static props = {
        onPeriodChange: { type: Function, optional: true },
        initialDateFrom: { type: String, optional: true },
        initialDateTo: { type: String, optional: true },
    };

    setup() {
        this.state = useState({
            // Use dates from context if available, otherwise defaults
            dateFrom: this.props.initialDateFrom || this.getDefaultDateFrom(),
            dateTo: this.props.initialDateTo || this.getDefaultDateTo(),
        });
    }

    getDefaultDateFrom() {
        const today = new Date();
        return `${today.getFullYear()}-01-01`;
    }

    getDefaultDateTo() {
        return new Date().toISOString().split('T')[0];
    }

    applyPeriod() {
        const { dateFrom, dateTo } = this.state;
        if (dateFrom && dateTo && this.props.onPeriodChange) {
            this.props.onPeriodChange(dateFrom, dateTo);
        }
    }

    onDateFromChange(ev) {
        this.state.dateFrom = ev.target.value;
    }

    onDateToChange(ev) {
        this.state.dateTo = ev.target.value;
    }

    onThisYear() {
        this.state.dateFrom = this.getDefaultDateFrom();
        this.state.dateTo = this.getDefaultDateTo();
        this.applyPeriod();
    }

    onThisMonth() {
        const today = new Date();
        this.state.dateFrom = `${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, '0')}-01`;
        this.state.dateTo = this.getDefaultDateTo();
        this.applyPeriod();
    }

    onLastMonth() {
        const today = new Date();
        const lastMonth = new Date(today);
        lastMonth.setMonth(lastMonth.getMonth() - 1);

        this.state.dateFrom = `${lastMonth.getFullYear()}-${String(lastMonth.getMonth() + 1).padStart(2, '0')}-01`;

        const lastDay = new Date(today.getFullYear(), today.getMonth(), 0);
        this.state.dateTo = lastDay.toISOString().split('T')[0];

        this.applyPeriod();
    }
}
