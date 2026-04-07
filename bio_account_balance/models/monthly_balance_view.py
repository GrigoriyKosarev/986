# -*- coding: utf-8 -*-

from odoo import api, fields, models, tools


class BioMonthlyBalanceView(models.Model):
    """
    Pre-aggregated monthly balance view for FAST pivot.

    Automatically calculates opening/closing balances per partner/account/month.
    Uses SQL VIEW for maximum performance - no Python calculations!

    Use cases:
    - Fast monthly/yearly reports
    - Partner balance trends
    - Quick overview without heavy calculations

    Limitations:
    - Monthly granularity only (no daily/custom periods)
    - Cannot filter by move_id, journal_id, etc (aggregated data)

    For full flexibility, use standard account.move.line pivot with batch SQL.

    ODOO-834
    """
    _name = 'bio.monthly.balance.view'
    _description = 'Monthly Partner Balance - Fast Pivot View'
    _auto = False  # SQL VIEW - no table creation
    _rec_name = 'partner_id'
    _order = 'year desc, month desc, partner_id, account_id'

    # Dimensions (group by fields)
    partner_id = fields.Many2one('res.partner', string='Partner', readonly=True)
    account_id = fields.Many2one('account.account', string='Account', readonly=True)
    company_id = fields.Many2one('res.company', string='Company', readonly=True)
    currency_id = fields.Many2one('res.currency', string='Currency', readonly=True)
    year = fields.Integer(string='Year', readonly=True)
    month = fields.Integer(string='Month', readonly=True)

    # Measures (aggregatable fields)
    opening_balance = fields.Monetary(
        string='Opening Balance',
        currency_field='currency_id',
        readonly=True,
        help="Balance at the start of the month (first line's bio_initial_balance)"
    )
    closing_balance = fields.Monetary(
        string='Closing Balance',
        currency_field='currency_id',
        readonly=True,
        help="Balance at the end of the month (last line's bio_end_balance)"
    )
    balance_change = fields.Monetary(
        string='Balance Change',
        currency_field='currency_id',
        readonly=True,
        compute='_compute_balance_change',
        help="Difference between closing and opening balance (closing - opening)"
    )

    @api.depends('opening_balance', 'closing_balance')
    def _compute_balance_change(self):
        """Calculate balance change for each record"""
        for record in self:
            record.balance_change = record.closing_balance - record.opening_balance

    def init(self):
        """
        Create SQL VIEW with pre-aggregated monthly balances.

        Query logic:
        1. Group move lines by partner/account/month
        2. Find first line of each month (for opening balance)
        3. Find last line of each month (for closing balance)
        4. Join opening + closing balances

        Performance: ~100x faster than Python calculations!
        """
        tools.drop_view_if_exists(self.env.cr, self._table)

        self.env.cr.execute(f"""
            CREATE OR REPLACE VIEW {self._table} AS (
                WITH monthly_groups AS (
                    -- Step 1: Group lines by partner/account/month
                    SELECT
                        aml.partner_id,
                        aml.account_id,
                        aml.company_id,
                        aml.currency_id,
                        EXTRACT(YEAR FROM aml.date)::INTEGER as year,
                        EXTRACT(MONTH FROM aml.date)::INTEGER as month,
                        MIN(aml.date) as first_date,
                        MAX(aml.date) as last_date,
                        MIN(aml.id) as first_id_hint,  -- Hint for tie-breaking
                        MAX(aml.id) as last_id_hint
                    FROM account_move_line aml
                    WHERE aml.parent_state = 'posted'
                        AND aml.account_id IS NOT NULL
                    GROUP BY
                        aml.partner_id,
                        aml.account_id,
                        aml.company_id,
                        aml.currency_id,
                        EXTRACT(YEAR FROM aml.date),
                        EXTRACT(MONTH FROM aml.date)
                ),
                opening_balances AS (
                    -- Step 2: Find opening balance (first line of month)
                    SELECT DISTINCT ON (
                        mg.partner_id,
                        mg.account_id,
                        mg.year,
                        mg.month
                    )
                        mg.partner_id,
                        mg.account_id,
                        mg.company_id,
                        mg.currency_id,
                        mg.year,
                        mg.month,
                        COALESCE(bal.bio_initial_balance, 0) as opening_balance
                    FROM monthly_groups mg
                    JOIN account_move_line aml
                        ON COALESCE(aml.partner_id, 0) = COALESCE(mg.partner_id, 0)
                        AND aml.account_id = mg.account_id
                        AND aml.date = mg.first_date
                        AND aml.parent_state = 'posted'
                    LEFT JOIN bio_account_move_line_balance bal
                        ON bal.move_line_id = aml.id
                    ORDER BY
                        mg.partner_id,
                        mg.account_id,
                        mg.year,
                        mg.month,
                        aml.date ASC,
                        aml.id ASC
                ),
                closing_balances AS (
                    -- Step 3: Find closing balance (last line of month)
                    SELECT DISTINCT ON (
                        mg.partner_id,
                        mg.account_id,
                        mg.year,
                        mg.month
                    )
                        mg.partner_id,
                        mg.account_id,
                        mg.year,
                        mg.month,
                        COALESCE(bal.bio_end_balance, 0) as closing_balance
                    FROM monthly_groups mg
                    JOIN account_move_line aml
                        ON COALESCE(aml.partner_id, 0) = COALESCE(mg.partner_id, 0)
                        AND aml.account_id = mg.account_id
                        AND aml.date = mg.last_date
                        AND aml.parent_state = 'posted'
                    LEFT JOIN bio_account_move_line_balance bal
                        ON bal.move_line_id = aml.id
                    ORDER BY
                        mg.partner_id,
                        mg.account_id,
                        mg.year,
                        mg.month,
                        aml.date DESC,
                        aml.id DESC
                )
                -- Step 4: Join opening + closing balances
                SELECT
                    ROW_NUMBER() OVER (
                        ORDER BY ob.year DESC, ob.month DESC, ob.partner_id, ob.account_id
                    )::INTEGER as id,
                    ob.partner_id,
                    ob.account_id,
                    ob.company_id,
                    ob.currency_id,
                    ob.year,
                    ob.month,
                    ob.opening_balance,
                    cb.closing_balance
                FROM opening_balances ob
                JOIN closing_balances cb
                    ON COALESCE(cb.partner_id, 0) = COALESCE(ob.partner_id, 0)
                    AND cb.account_id = ob.account_id
                    AND cb.year = ob.year
                    AND cb.month = ob.month
            )
        """)
