# -*- coding: utf-8 -*-
from odoo import models, fields, api


class PeriodFilterWizard(models.TransientModel):
    _name = 'bio.period.filter.wizard'
    _description = 'Period Filter Wizard'

    period_start = fields.Date(
        string='From Date',
        required=True,
        default=lambda self: fields.Date.today().replace(month=1, day=1)  # Start of current year
    )
    period_end = fields.Date(
        string='To Date',
        required=True,
        default=fields.Date.today
    )

    def action_apply_filter(self):
        """Apply custom period filter and open report."""
        self.ensure_one()

        return {
            'type': 'ir.actions.act_window',
            'name': 'Journal Items Balance',
            'res_model': 'bio.account.move.line.report',
            'view_mode': 'tree',
            'context': {
                'period_start': self.period_start.strftime('%Y-%m-%d'),
                'period_end': self.period_end.strftime('%Y-%m-%d'),
                'search_default_group_period': 1,
                'search_default_group_partner': 1,
            },
            'target': 'current',
        }
