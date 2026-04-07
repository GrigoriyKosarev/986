# -*- coding: utf-8 -*-

from odoo import api, fields, models, tools


class BioAccountMoveLineView(models.Model):
    """
    Fast Journal Items View with Real-Time Balance Calculations (Partner Ledger Style).

    This SQL VIEW provides the same interface as account.move.line
    but with automatic opening/closing balances calculated on-the-fly
    using PostgreSQL window functions.

    Display Style: Partner Ledger (standard accounting report)
    - Balances calculated per partner (cumulative across all accounts)
    - Rows grouped by partner, then sorted chronologically
    - Snake display: End Balance → Initial Balance → End Balance

    Benefits:
    - Same familiar interface as Journal Items
    - Real-time balances (always up-to-date, no cron needed)
    - No additional balance table required (simpler architecture)
    - Fast SQL window functions
    - Can be used for pivot/tree/graph analysis

    Use cases:
    - Partner Ledger reports with full transaction details
    - Partner balance analysis
    - Export partner transactions with running balance
    - Real-time partner balance monitoring

    Performance: Window functions calculate cumulative sums efficiently
    in PostgreSQL. Works well even with large datasets when properly indexed.

    Technical: Uses SUM() OVER (PARTITION BY partner, company ORDER BY date, id) for
    cumulative balance calculation per partner (Partner Ledger style).

    ODOO-834
    """
    _name = 'bio.account.move.line.view'
    _description = 'Journal Items with Balances - Fast View'
    _auto = False  # SQL VIEW - no table creation
    _rec_name = 'move_id'
    _order = 'sort_sequence'  # Partner Ledger style: partner grouped, chronological within partner

    # Core Journal Item fields (from account.move.line)
    move_id = fields.Many2one('account.move', string='Journal Entry', readonly=True)
    date = fields.Date(string='Date', readonly=True)
    name = fields.Char(string='Label', readonly=True)
    ref = fields.Char(string='Reference', readonly=True)

    # Account & Partner
    account_id = fields.Many2one('account.account', string='Account', readonly=True)
    partner_id = fields.Many2one('res.partner', string='Partner', readonly=True)

    # Journal & Company
    journal_id = fields.Many2one('account.journal', string='Journal', readonly=True)
    company_id = fields.Many2one('res.company', string='Company', readonly=True)
    currency_id = fields.Many2one('res.currency', string='Currency', readonly=True)

    # Amounts
    debit = fields.Monetary(
        string='Debit',
        currency_field='currency_id',
        readonly=True
    )
    credit = fields.Monetary(
        string='Credit',
        currency_field='currency_id',
        readonly=True
    )
    balance = fields.Monetary(
        string='Balance',
        currency_field='currency_id',
        readonly=True,
        help="Debit - Credit"
    )

    # Balance fields (from bio_account_move_line_balance)
    bio_initial_balance = fields.Monetary(
        string='Initial Balance',
        currency_field='currency_id',
        readonly=True,
        group_operator='min',  # MIN = balance of first row in group (correct for Partner Ledger)
        help="Cumulative balance before this line. "
             "Group totals use MIN (first row's balance) - Partner Ledger style."
    )
    bio_end_balance = fields.Monetary(
        string='End Balance',
        currency_field='currency_id',
        readonly=True,
        group_operator='max',  # MAX = balance of last row in group (correct for Partner Ledger)
        help="Cumulative balance after this line (initial + debit - credit). "
             "Group totals use MAX (last row's balance) - Partner Ledger style."
    )

    # Additional useful fields
    move_name = fields.Char(string='Entry Number', readonly=True)
    parent_state = fields.Selection([
        ('draft', 'Unposted'),
        ('posted', 'Posted'),
    ], string='Status', readonly=True)

    # Additional fields like in account.move.line
    product_id = fields.Many2one('product.product', string='Product', readonly=True)
    # Note: tax_ids and tax_tag_ids are many2many fields which cannot be included in SQL VIEW
    # They would require additional relation tables which complicates the view
    amount_currency = fields.Monetary(
        string='Amount in Currency',
        currency_field='currency_id',
        readonly=True
    )
    discount_date = fields.Date(string='Discount Date', readonly=True)
    discount_amount_currency = fields.Monetary(
        string='Discount Amount',
        currency_field='currency_id',
        readonly=True
    )
    tax_line_id = fields.Many2one('account.tax', string='Originator Tax', readonly=True)
    date_maturity = fields.Date(string='Due Date', readonly=True)
    matching_number = fields.Char(string='Matching Number', readonly=True)
    amount_residual = fields.Monetary(
        string='Residual Amount',
        currency_field='currency_id',
        readonly=True
    )
    amount_residual_currency = fields.Monetary(
        string='Residual Amount in Currency',
        currency_field='currency_id',
        readonly=True
    )
    analytic_distribution = fields.Json(string='Analytic Distribution', readonly=True)
    analytic_precision = fields.Integer(
        string='Analytic Precision',
        readonly=True,
        default=2,
        help="Decimal precision for analytic distribution percentages"
    )

    # Technical fields
    move_type = fields.Selection([
        ('entry', 'Journal Entry'),
        ('out_invoice', 'Customer Invoice'),
        ('out_refund', 'Customer Credit Note'),
        ('in_invoice', 'Vendor Bill'),
        ('in_refund', 'Vendor Credit Note'),
        ('out_receipt', 'Sales Receipt'),
        ('in_receipt', 'Purchase Receipt'),
    ], string='Type', readonly=True)
    account_type = fields.Selection([
        ('asset_receivable', 'Receivable'),
        ('asset_cash', 'Bank and Cash'),
        ('asset_current', 'Current Assets'),
        ('asset_non_current', 'Non-current Assets'),
        ('asset_prepayments', 'Prepayments'),
        ('asset_fixed', 'Fixed Assets'),
        ('liability_payable', 'Payable'),
        ('liability_credit_card', 'Credit Card'),
        ('liability_current', 'Current Liabilities'),
        ('liability_non_current', 'Non-current Liabilities'),
        ('equity', 'Equity'),
        ('equity_unaffected', 'Current Year Earnings'),
        ('income', 'Income'),
        ('income_other', 'Other Income'),
        ('expense', 'Expenses'),
        ('expense_depreciation', 'Depreciation'),
        ('expense_direct_cost', 'Cost of Revenue'),
        ('off_balance', 'Off-Balance Sheet'),
    ], string='Account Type', readonly=True)
    statement_line_id = fields.Many2one('account.bank.statement.line', string='Bank Statement Line', readonly=True)
    company_currency_id = fields.Many2one('res.currency', string='Company Currency', readonly=True)
    is_same_currency = fields.Boolean(string='Same Currency', readonly=True)
    is_account_reconcile = fields.Boolean(string='Account Allows Reconciliation', readonly=True)
    sequence = fields.Integer(string='Sequence', readonly=True)
    sort_sequence = fields.Integer(
        string='Sort Sequence',
        readonly=True,
        help='Sorting order matching Partner Ledger style (partner, date, id). '
             'Ensures balance flow: End Balance of previous row = Initial Balance of next row (snake display)'
    )

    @api.model
    def read_group(self, domain, fields, groupby, offset=0, limit=None, orderby=False, lazy=True):
        dynamic_fields = ['bio_initial_balance', 'bio_end_balance']

        requested_dynamic_fields = [f for f in fields if any(df in f for df in dynamic_fields)]
        if not requested_dynamic_fields:
            return super().read_group(domain, fields, groupby, offset, limit, orderby, lazy)

        other_fields = [f for f in fields if not any(df in f for df in dynamic_fields)]
        result = super().read_group(domain, other_fields, groupby, offset, limit, orderby, lazy)

        groupby_list = groupby if isinstance(groupby, list) else ([groupby] if groupby else [])
        is_groupby_partner = any(g == 'partner_id' or g.startswith('partner_id:') for g in groupby_list)

        requested_names = {f.split(':')[0] for f in requested_dynamic_fields}

        base_domain, date_from, date_to = self._split_domain_by_date(domain)

        opening_domain = base_domain + ([('date', '<', date_from)] if date_from else [])
        closing_domain = base_domain + ([('date', '<=', date_to)] if date_to else [])

        if is_groupby_partner:
            opening_balances = {}
            closing_balances = {}

            if 'bio_initial_balance' in requested_names:
                opening_balances = self._calc_opening_batch_by_partner(opening_domain)
            if 'bio_end_balance' in requested_names:
                closing_balances = self._calc_closing_batch_by_partner(closing_domain)

            for group in result:
                partner_id = group.get('partner_id')
                if partner_id:
                    partner_id = partner_id[0] if isinstance(partner_id, (tuple, list)) else partner_id
                else:
                    partner_id = False

                if 'bio_initial_balance' in requested_names:
                    group['bio_initial_balance'] = opening_balances.get(partner_id, 0.0)
                if 'bio_end_balance' in requested_names:
                    group['bio_end_balance'] = closing_balances.get(partner_id, 0.0)
        else:
            for group in result:
                group_domain = domain.copy() if domain else []
                if groupby_list and '__domain' in group:
                    group_domain = group_domain + group['__domain']

                group_base_domain, group_date_from, group_date_to = self._split_domain_by_date(group_domain)
                group_opening_domain = group_base_domain + ([('date', '<', group_date_from)] if group_date_from else [])
                group_closing_domain = group_base_domain + ([('date', '<=', group_date_to)] if group_date_to else [])

                if 'bio_initial_balance' in requested_names:
                    group['bio_initial_balance'] = self._calc_opening(group_opening_domain)
                if 'bio_end_balance' in requested_names:
                    group['bio_end_balance'] = self._calc_closing(group_closing_domain)

        return result

    def _split_domain_by_date(self, domain):
        """Split domain into base_domain (without date constraints) + extracted date_from/date_to.

        Supported extraction:
        - ('date', '>=', value) / ('date', '>', value)  -> date_from (max)
        - ('date', '<=', value) / ('date', '<', value)  -> date_to (min)

        If domain contains OR/NOT operators ('|' or '!'), extraction is skipped and the domain is returned as-is.
        """
        if not domain:
            return [], None, None

        if isinstance(domain, (tuple,)):
            domain = [domain]

        # If the domain uses OR/NOT logic, avoid stripping dates to prevent changing semantics.
        if isinstance(domain, list) and any(tok in ('|', '!') for tok in domain):
            return domain, None, None

        def _is_date_leaf(leaf):
            return (
                isinstance(leaf, (tuple, list))
                and len(leaf) >= 3
                and leaf[0] == 'date'
                and leaf[1] in ('>=', '>', '<=', '<')
            )

        # Extract date bounds from any leaf-like triplets
        date_from = None
        date_to = None
        for term in domain:
            if _is_date_leaf(term):
                op = term[1]
                value = term[2]
                if op in ('>=', '>'):
                    if date_from is None or value > date_from:
                        date_from = value
                elif op in ('<=', '<'):
                    if date_to is None or value < date_to:
                        date_to = value

        # If it's a simple implicit-AND domain, just filter date leaves
        if isinstance(domain, list) and not any(tok in ('&', '|', '!') for tok in domain):
            base_domain = [t for t in domain if not _is_date_leaf(t)]
            return base_domain, date_from, date_to

        # Prefix-notation AND domain: parse and remove date leaves without breaking '&'
        def _parse(node_list, idx):
            token = node_list[idx]

            if token == '&':
                left, next_idx = _parse(node_list, idx + 1)
                right, next_idx = _parse(node_list, next_idx)

                if left is None and right is None:
                    return None, next_idx
                if left is None:
                    return right, next_idx
                if right is None:
                    return left, next_idx
                return ['&', left, right], next_idx

            # Leaf (tuple/list) or unknown token
            if _is_date_leaf(token):
                return None, idx + 1
            return token, idx + 1

        try:
            tree, next_idx = _parse(domain, 0)
            if next_idx != len(domain):
                # Unexpected trailing tokens; fallback to safest behavior
                return domain, None, None
        except Exception:
            return domain, None, None

        if tree is None:
            return [], date_from, date_to
        if isinstance(tree, list) and tree and tree[0] == '&':
            return tree, date_from, date_to
        return [tree], date_from, date_to

    def _get_sql_where_from_domain(self, domain):
        query_obj = self._where_calc(domain)
        from_clause, where_clause, where_params = query_obj.get_sql()

        if not where_clause:
            where_clause = "1=1"

        where_clause = where_clause.replace(f'"{self._table}"', 'aml')
        return from_clause, where_clause, where_params

    def _calc_opening(self, domain):
        from_clause, where_clause, where_params = self._get_sql_where_from_domain(domain)

        query = f"""
            WITH filtered_lines AS (
                SELECT
                    aml.account_id,
                    aml.partner_id,
                    aml.bio_end_balance,
                    aml.date,
                    aml.id
                FROM {from_clause} aml
                WHERE ({where_clause})
            ),
            last_lines_per_account AS (
                SELECT DISTINCT ON (account_id, COALESCE(partner_id,0))
                    COALESCE(bio_end_balance, 0) as bio_end_balance
                FROM filtered_lines
                ORDER BY account_id, COALESCE(partner_id,0), date DESC, id DESC
            )
            SELECT COALESCE(SUM(bio_end_balance), 0) as total
            FROM last_lines_per_account;
        """

        self.env.cr.execute(query, where_params)
        row = self.env.cr.fetchone()
        return row[0] if row else 0.0

    def _calc_closing(self, domain):
        from_clause, where_clause, where_params = self._get_sql_where_from_domain(domain)

        query = f"""
            WITH filtered_lines AS (
                SELECT
                    aml.account_id,
                    aml.partner_id,
                    aml.bio_end_balance,
                    aml.date,
                    aml.id
                FROM {from_clause} aml
                WHERE ({where_clause})
            ),
            last_lines_per_account AS (
                SELECT DISTINCT ON (account_id, COALESCE(partner_id,0))
                    COALESCE(bio_end_balance, 0) as bio_end_balance
                FROM filtered_lines
                ORDER BY account_id, COALESCE(partner_id,0), date DESC, id DESC
            )
            SELECT COALESCE(SUM(bio_end_balance), 0) as total
            FROM last_lines_per_account;
        """

        self.env.cr.execute(query, where_params)
        row = self.env.cr.fetchone()
        return row[0] if row else 0.0

    def _calc_opening_batch_by_partner(self, domain):
        from_clause, where_clause, where_params = self._get_sql_where_from_domain(domain)

        query = f"""
            WITH filtered_lines AS (
                SELECT
                    aml.account_id,
                    aml.partner_id,
                    aml.bio_end_balance,
                    aml.date,
                    aml.id
                FROM {from_clause} aml
                WHERE ({where_clause})
            ),
            last_lines_per_account AS (
                SELECT DISTINCT ON (account_id, COALESCE(partner_id,0))
                    partner_id,
                    COALESCE(bio_end_balance, 0) as bio_end_balance
                FROM filtered_lines
                ORDER BY account_id, COALESCE(partner_id,0), date DESC, id DESC
            )
            SELECT
                COALESCE(partner_id, 0) as partner_id,
                SUM(bio_end_balance) as opening_balance
            FROM last_lines_per_account
            GROUP BY COALESCE(partner_id, 0);
        """

        self.env.cr.execute(query, where_params)
        result = {}
        for partner_id, opening in self.env.cr.fetchall():
            result[partner_id if partner_id != 0 else False] = opening
        return result

    def _calc_closing_batch_by_partner(self, domain):
        from_clause, where_clause, where_params = self._get_sql_where_from_domain(domain)

        query = f"""
            WITH filtered_lines AS (
                SELECT
                    aml.account_id,
                    aml.partner_id,
                    aml.bio_end_balance,
                    aml.date,
                    aml.id
                FROM {from_clause} aml
                WHERE ({where_clause})
            ),
            last_lines_per_account AS (
                SELECT DISTINCT ON (account_id, COALESCE(partner_id,0))
                    partner_id,
                    COALESCE(bio_end_balance, 0) as bio_end_balance
                FROM filtered_lines
                ORDER BY account_id, COALESCE(partner_id,0), date DESC, id DESC
            )
            SELECT
                COALESCE(partner_id, 0) as partner_id,
                SUM(bio_end_balance) as closing_balance
            FROM last_lines_per_account
            GROUP BY COALESCE(partner_id, 0);
        """

        self.env.cr.execute(query, where_params)
        result = {}
        for partner_id, closing in self.env.cr.fetchall():
            result[partner_id if partner_id != 0 else False] = closing
        return result

    def init(self):
        """
        Create SQL VIEW with real-time balance calculations using window functions.

        Partner Ledger Style: Balances calculated per partner (not per account).

        Calculates cumulative balances on-the-fly using PostgreSQL window functions:
        - PARTITION BY partner_id, company_id: separate balance per partner
        - ORDER BY date, id: chronological order within partner
        - ROWS BETWEEN: cumulative sum up to current/previous row

        Benefits:
        - Always up-to-date (no cron needed)
        - No additional balance table required
        - Fast thanks to PostgreSQL window functions
        - Simple architecture
        - Standard accounting display (Partner Ledger)

        Performance: Window functions are optimized in PostgreSQL and work great
        even with millions of rows when properly indexed (partner_id, date, id).
        """
        tools.drop_view_if_exists(self.env.cr, self._table)

        self.env.cr.execute(f"""
            CREATE OR REPLACE VIEW {self._table} AS (
                SELECT
                    aml.id,
                    aml.move_id,
                    aml.date,
                    aml.name,
                    aml.ref,
                    aml.account_id,
                    aml.partner_id,
                    aml.journal_id,
                    aml.company_id,
                    aml.currency_id,
                    aml.debit,
                    aml.credit,
                    aml.balance,
                    aml.parent_state,
                    am.name as move_name,

                    -- Additional fields like in account.move.line
                    aml.product_id,
                    aml.amount_currency,
                    aml.discount_date,
                    aml.discount_amount_currency,
                    aml.tax_line_id,
                    aml.date_maturity,
                    aml.matching_number,
                    aml.amount_residual,
                    aml.amount_residual_currency,
                    aml.analytic_distribution,
                    2 as analytic_precision,  -- Constant: precision for analytic percentages
                    aml.sequence,
                    aml.statement_line_id,

                    -- From account.move
                    am.move_type,

                    -- From account.account
                    aa.account_type,
                    aa.reconcile as is_account_reconcile,

                    -- Company currency
                    rc.currency_id as company_currency_id,
                    CASE WHEN aml.currency_id = rc.currency_id THEN TRUE ELSE FALSE END as is_same_currency,

                    -- Sort sequence: Partner Ledger style (grouped by partner, chronological within)
                    -- MUST match window function PARTITION BY + ORDER BY for correct balance flow
                    ROW_NUMBER() OVER (
                        ORDER BY aml.partner_id, aml.company_id, aml.date, aml.id
                    ) as sort_sequence,

                    -- Calculate initial balance (cumulative sum BEFORE current row)
                    -- Partner Ledger style: balance per partner (not per account!)
                    COALESCE(
                        SUM(aml.debit - aml.credit) OVER (
                            PARTITION BY aml.partner_id, aml.company_id
                            ORDER BY aml.date, aml.id
                            ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING
                        ),
                        0
                    ) as bio_initial_balance,
                    -- Calculate end balance (cumulative sum INCLUDING current row)
                    -- Partner Ledger style: balance per partner (not per account!)
                    COALESCE(
                        SUM(aml.debit - aml.credit) OVER (
                            PARTITION BY aml.partner_id, aml.company_id
                            ORDER BY aml.date, aml.id
                            ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
                        ),
                        0
                    ) as bio_end_balance
                FROM account_move_line aml
                LEFT JOIN account_move am ON am.id = aml.move_id
                LEFT JOIN account_account aa ON aa.id = aml.account_id
                LEFT JOIN res_company rc ON rc.id = aml.company_id
                WHERE aml.parent_state = 'posted'
                    AND aml.account_id IS NOT NULL
            )
        """)
