/** @odoo-module **/

import { registry } from "@web/core/registry";
import { listView } from "@web/views/list/list_view";
import { ListController } from "@web/views/list/list_controller";
import { PeriodFilter } from "./period_filter";
import { useService } from "@web/core/utils/hooks";

/**
 * Custom List Controller with Period Filter
 */
export class BioAccountReportListController extends ListController {
    setup() {
        super.setup();
        this.actionService = useService("action");
    }

    static components = {
        ...ListController.components,
        PeriodFilter,
    };

    /**
     * Handle period change from PeriodFilter component
     * Uses doAction with replace to avoid breadcrumb spam
     * Preserves current grouping by passing it through context
     */
    async onPeriodChange(dateFrom, dateTo) {
        // Get current groupBy from model to preserve grouping
        let currentGroupBy = [];
        if (this.model && this.model.root && this.model.root.groupBy) {
            currentGroupBy = this.model.root.groupBy;
        }

        // Get current context safely
        const currentContext = this.props.context || this.model?.config?.context || {};

        // Reload action with new context
        await this.actionService.doAction(
            {
                type: 'ir.actions.act_window',
                res_model: 'bio.account.move.line.report',
                name: 'Journal Items Balance',
                views: [[false, 'list']],
                view_mode: 'list',
                target: 'current',
                context: {
                    ...currentContext,
                    period_start: dateFrom,
                    period_end: dateTo,
                    // Preserve grouping
                    group_by: currentGroupBy.length > 0 ? currentGroupBy : undefined,
                },
            },
            {
                clearBreadcrumbs: false,
                replace_last_action: true,
            }
        );
    }

    get periodFilterProps() {
        // Get context from props or model config (safe access)
        const context = this.props.context || this.model?.config?.context || {};

        return {
            onPeriodChange: this.onPeriodChange.bind(this),
            // Pass current period dates from context
            initialDateFrom: context.period_start || null,
            initialDateTo: context.period_end || null,
        };
    }
}

BioAccountReportListController.template = "bio_account_balance.ListView";

/**
 * Custom List View
 */
export const bioAccountReportListView = {
    ...listView,
    Controller: BioAccountReportListController,
};

registry.category("views").add("bio_account_move_line_report_list", bioAccountReportListView);
