from odoo import models, fields, api


class ReportMutualSettlements(models.Model):
    _name = 'bio.account.move.line.report'
    _description = 'Journal Items Balance'
    _auto = False
    _rec_name = 'move_name'
    _order = 'partner_id asc, period_date asc, date asc, move_id asc'

    # ── Identification ───────────────────────────────────────────────
    partner_id      = fields.Many2one('res.partner',  string='Partner',    readonly=True)
    company_id      = fields.Many2one('res.company',  string='Company',    readonly=True)
    move_id         = fields.Many2one('account.move', string='Journal Entry', readonly=True)
    account_id      = fields.Many2one('account.account', string='Account', readonly=True)

    # ── Period / Dates ───────────────────────────────────────────────
    period_date     = fields.Date(string='Period',         readonly=True)
    date            = fields.Date(string='Date',           readonly=True)
    date_maturity   = fields.Date(string='Due Date',       readonly=True)

    # ── Journal Entry ────────────────────────────────────────────────
    move_name       = fields.Char(string='Number', readonly=True)
    move_type       = fields.Selection([
        ('entry',       'Journal Entry'),
        ('out_invoice', 'Customer Invoice'),
        ('out_refund',  'Customer Credit Note'),
        ('in_invoice',  'Vendor Bill'),
        ('in_refund',   'Vendor Credit Note'),
        ('out_receipt', 'Sales Receipt'),
        ('in_receipt',  'Purchase Receipt'),
    ], string='Entry Type', readonly=True)
    ref             = fields.Char(string='Move Ref', readonly=True)
    line_ref        = fields.Char(string='Ref', readonly=True)

    # ── Account / Partner Type ───────────────────────────────────────
    account_type    = fields.Selection([
        ('asset_receivable',  'Receivable'),
        ('liability_payable', 'Payable'),
    ], string='Account Type', readonly=True)

    partner_type    = fields.Selection([
        ('customer', 'Customer'),
        ('supplier', 'Vendor'),
    ], string='Partner Type', readonly=True)

    # ── Amounts ──────────────────────────────────────────────────────
    debit           = fields.Monetary(string='Debit',              readonly=True)
    credit          = fields.Monetary(string='Credit',             readonly=True)
    balance         = fields.Monetary(string='Balance',            readonly=True)

    # Document balances (changes for each document)
    # group_operator=False → not summed automatically, value set in read_group()
    # NOTE: Cannot be used in pivot view! Use debit/credit/balance instead
    opening_balance = fields.Monetary(
        string='Initial Balance',
        readonly=True,
        group_operator=False,  # Will be set manually in read_group() based on grouping level
        help="Initial balance. In GROUP BY taken from partner_opening_balance or period_opening_balance."
    )
    closing_balance = fields.Monetary(
        string='End Balance',
        readonly=True,
        group_operator=False,  # Will be set manually in read_group() based on grouping level
        help="End balance. In GROUP BY taken from partner_closing_balance or period_closing_balance."
    )

    # Partner balances (same for all documents of partner + account_type - for GROUP BY)
    # NOTE: These are per (partner_id, account_type, company_id)!
    # group_operator=False → values set in read_group() via search (accurate but slower)
    partner_opening_balance = fields.Monetary(
        string='Partner Initial Balance',
        readonly=True,
        group_operator=False,  # Set in read_group() via search to handle different account_types correctly
        help="Partner initial balance (first document). "
             "Per (partner_id, account_type). "
             "Calculated in read_group() by searching first record."
    )
    partner_closing_balance = fields.Monetary(
        string='Partner End Balance',
        readonly=True,
        group_operator=False,  # Set in read_group() via search to handle different account_types correctly
        help="Partner end balance (last document). "
             "Per (partner_id, account_type). "
             "Calculated in read_group() by searching last record."
    )

    # Period balances (same for all documents of partner in period - for GROUP BY)
    period_opening_balance = fields.Monetary(
        string='Period Initial Balance',
        readonly=True,
        group_operator=False,  # Set in read_group() via search to handle different account_types correctly
        help="Partner initial balance at period (month) start. "
             "Per (partner_id, account_type, period_date). "
             "Calculated in read_group() by searching first record in period."
    )
    period_closing_balance = fields.Monetary(
        string='Period End Balance',
        readonly=True,
        group_operator=False,  # Set in read_group() via search to handle different account_types correctly
        help="Partner end balance at period (month) end. "
             "Per (partner_id, account_type, period_date). "
             "Calculated in read_group() by searching last record in period."
    )

    currency_id     = fields.Many2one('res.currency', string='Currency', readonly=True)

    # Fields that should not be summed in group by (already handled by group_operator)
    NON_ADDITIVE = {
        'opening_balance', 'closing_balance',  # Document balances (cumulative)
        'partner_opening_balance', 'partner_closing_balance',  # Partner balances (same value for all rows)
        'period_opening_balance', 'period_closing_balance'  # Period balances (same value for all rows in period)
    }

    @api.model
    def search(self, args, offset=0, limit=None, order=None, count=False):
        """Override search to pass period dates to PostgreSQL session variables."""
        # Get period from context
        period_start = self.env.context.get('period_start')
        period_end = self.env.context.get('period_end')

        # Set PostgreSQL session variables (visible to SQL view)
        if period_start:
            self.env.cr.execute("SET LOCAL bio.period_start = %s", [period_start])
        if period_end:
            self.env.cr.execute("SET LOCAL bio.period_end = %s", [period_end])

        return super().search(args, offset, limit, order, count)

    @api.model
    def read_group(self, domain, fields, groupby, offset=0, limit=None,
                   orderby=False, lazy=True):
        """
        Override read_group to correctly handle opening_balance/closing_balance.

        Performance optimization:
        - ONE search() for all records (sorted by date)
        - filtered_domain() in memory for each group (fast!)
        - Avoids N search queries (N = number of groups)
        """
        # ⚠️ CRITICAL: Set PostgreSQL session variables BEFORE super().read_group()
        # super().read_group() makes SQL queries directly without calling search()
        period_start = self.env.context.get('period_start')
        period_end = self.env.context.get('period_end')

        if period_start:
            self.env.cr.execute("SET LOCAL bio.period_start = %s", [period_start])
        if period_end:
            self.env.cr.execute("SET LOCAL bio.period_end = %s", [period_end])

        groupby_list = [groupby] if isinstance(groupby, str) else (groupby or [])
        has_opening = any('opening_balance' in str(f) for f in fields)
        has_closing = any('closing_balance' in str(f) for f in fields)

        result = super().read_group(
            domain, fields, groupby,
            offset=offset, limit=limit,
            orderby=orderby, lazy=lazy,
        )

        if not result or not (has_opening or has_closing):
            return result

        # Performance: ONE search for all records, then filter in memory per group
        # This is MUCH faster than search() per group (1 query vs N queries)
        all_recs = self.search(domain, order='date asc, move_id asc')
        if not all_recs:
            return result

        # For each group, filter records in memory and get first/last
        for group in result:
            group_domain = group.get('__domain', domain)

            # Filter in memory (fast! no SQL query)
            group_recs = all_recs.filtered_domain(group_domain)
            if not group_recs:
                if has_opening:
                    group['opening_balance'] = 0.0
                if has_closing:
                    group['closing_balance'] = 0.0
                continue

            # Determine which balance level to use
            if 'period_date:month' in groupby_list:
                # GROUP BY period:month → use period balances
                if has_opening:
                    group['opening_balance'] = group_recs[0].period_opening_balance
                if has_closing:
                    group['closing_balance'] = group_recs[-1].period_closing_balance
            else:
                # GROUP BY partner/account → use partner balances
                if has_opening:
                    group['opening_balance'] = group_recs[0].partner_opening_balance
                if has_closing:
                    group['closing_balance'] = group_recs[-1].partner_closing_balance

        return result

    # ────────────────────────────────────────────────────────────────
    # SQL VIEW
    # ────────────────────────────────────────────────────────────────
    def init(self):
        self.env.cr.execute("DROP VIEW IF EXISTS bio_account_move_line_report")
        self.env.cr.execute("""
            CREATE VIEW bio_account_move_line_report AS

            -- ══════════════════════════════════════════════════════════════
            -- FILTER PARAMETERS (from session variables or defaults to current year)
            -- Session variables set by Python search() override
            -- ══════════════════════════════════════════════════════════════
            WITH filter_params AS (
                SELECT
                    COALESCE(
                        NULLIF(current_setting('bio.period_start', true), '')::date,
                        DATE_TRUNC('year', CURRENT_DATE)::date
                    ) AS period_start,
                    COALESCE(
                        NULLIF(current_setting('bio.period_end', true), '')::date,
                        CURRENT_DATE
                    ) AS period_end
            ),

            -- ══════════════════════════════════════════════════════════════
            -- OPENING BALANCES (calculated from ALL movements BEFORE period)
            -- ══════════════════════════════════════════════════════════════
            opening_balances AS (
                SELECT
                    aml.partner_id,
                    aa.account_type,
                    aml.company_id,
                    MIN(aml.account_id) AS account_id,
                    MIN(rc.id) AS currency_id,
                    CASE
                        WHEN aa.account_type = 'asset_receivable'
                        THEN 'customer' ELSE 'supplier'
                    END AS partner_type,
                    SUM(aml.balance) AS opening_balance
                FROM account_move_line aml
                JOIN account_account aa ON aa.id = aml.account_id
                JOIN account_move am ON am.id = aml.move_id
                JOIN res_company rc ON rc.id = aml.company_id
                WHERE aa.account_type IN ('asset_receivable', 'liability_payable')
                  AND am.state = 'posted'
                  AND aml.partner_id IS NOT NULL
                  AND aml.date < (SELECT period_start FROM filter_params)
                GROUP BY aml.partner_id, aa.account_type, aml.company_id
                HAVING SUM(aml.balance) != 0
            ),

            -- ══════════════════════════════════════════════════════════════
            -- BASE: Movements in filtered period only
            -- ══════════════════════════════════════════════════════════════
            base AS (
                SELECT
                    aml.id                                          AS aml_id,
                    aml.partner_id,
                    aml.company_id,
                    aml.account_id,
                    aml.date_maturity,
                    DATE_TRUNC('month', aml.date)::date            AS period_date,
                    am.id                                           AS move_id,
                    am.name                                         AS move_name,
                    am.move_type,
                    am.ref,
                    aml.ref                                         AS line_ref,
                    aml.date,
                    aa.account_type,
                    CASE
                        WHEN aa.account_type = 'asset_receivable'
                        THEN 'customer' ELSE 'supplier'
                    END                                             AS partner_type,
                    aml.debit                                       AS debit,
                    aml.credit                                      AS credit,
                    aml.balance                                     AS balance,
                    rc.id                                           AS currency_id
                FROM account_move_line aml
                JOIN account_account aa ON aa.id = aml.account_id
                JOIN account_move   am  ON am.id = aml.move_id
                JOIN res_company    rc  ON rc.id = aml.company_id
                WHERE
                    aa.account_type IN ('asset_receivable', 'liability_payable')
                    AND am.state       = 'posted'
                    AND aml.partner_id IS NOT NULL
                    AND aml.date >= (SELECT period_start FROM filter_params)
                    AND aml.date <= (SELECT period_end FROM filter_params)
            ),

            move_level AS (
                SELECT
                    aml_id,
                    partner_id,
                    company_id,
                    account_id,
                    currency_id,
                    period_date,
                    move_id,
                    move_name,
                    move_type,
                    ref,
                    line_ref,
                    date,
                    date_maturity,
                    account_type,
                    partner_type,
                    debit,
                    credit,
                    balance
                FROM base
            ),

            with_running AS (
                SELECT
                    ml.*,
                    -- Document balances (cumulative per document)
                    -- Include opening_balance from BEFORE period!
                    COALESCE(ob.opening_balance, 0) + COALESCE(
                        SUM(ml.balance) OVER (
                            PARTITION BY ml.partner_id, ml.account_type, ml.company_id
                            ORDER BY ml.date, ml.move_id, ml.aml_id
                            ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING
                        ), 0
                    )                   AS opening_balance,
                    COALESCE(ob.opening_balance, 0) + SUM(ml.balance) OVER (
                        PARTITION BY ml.partner_id, ml.account_type, ml.company_id
                        ORDER BY ml.date, ml.move_id, ml.aml_id
                        ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
                    )                   AS closing_balance
                FROM move_level ml
                LEFT JOIN opening_balances ob ON
                    ob.partner_id = ml.partner_id
                    AND ob.account_type = ml.account_type
                    AND ob.company_id = ml.company_id
            ),

            with_partner_balances AS (
                SELECT
                    *,
                    -- Partner balances (same for ALL documents of partner - for GROUP BY)
                    -- Apply FIRST_VALUE/LAST_VALUE to already calculated balances (no nesting!)
                    FIRST_VALUE(opening_balance) OVER (
                        PARTITION BY partner_id, account_type, company_id
                        ORDER BY date, move_id
                        ROWS BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING
                    )                   AS partner_opening_balance,
                    LAST_VALUE(closing_balance) OVER (
                        PARTITION BY partner_id, account_type, company_id
                        ORDER BY date, move_id
                        ROWS BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING
                    )                   AS partner_closing_balance,

                    -- Period balances (same for ALL documents of partner in period - for GROUP BY)
                    FIRST_VALUE(opening_balance) OVER (
                        PARTITION BY partner_id, account_type, company_id, period_date
                        ORDER BY date, move_id
                        ROWS BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING
                    )                   AS period_opening_balance,
                    LAST_VALUE(closing_balance) OVER (
                        PARTITION BY partner_id, account_type, company_id, period_date
                        ORDER BY date, move_id
                        ROWS BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING
                    )                   AS period_closing_balance
                FROM with_running
            )

            SELECT
                ROW_NUMBER() OVER (
                    ORDER BY company_id, partner_id, account_type, date, move_id
                )                       AS id,
                partner_id,
                company_id,
                account_id,
                currency_id,
                period_date,
                move_id,
                move_name,
                move_type,
                ref,
                line_ref,
                date,
                date_maturity,
                account_type,
                partner_type,
                debit,
                credit,
                balance,
                opening_balance,
                closing_balance,
                partner_opening_balance,
                partner_closing_balance,
                period_opening_balance,
                period_closing_balance
            FROM with_partner_balances

            UNION ALL

            -- ══════════════════════════════════════════════════════════════
            -- OPENING BALANCE ROWS (one per partner at period start)
            -- Shows balance for partners even if they have no movements in period
            -- ══════════════════════════════════════════════════════════════
            SELECT
                ROW_NUMBER() OVER (
                    ORDER BY partner_id, account_type
                ) + 100000000           AS id,
                partner_id,
                company_id,
                account_id,
                currency_id,
                (SELECT period_start FROM filter_params) AS period_date,
                NULL::int               AS move_id,
                ''                      AS move_name,  -- Empty for minimal visibility
                NULL                    AS move_type,
                NULL                    AS ref,
                NULL                    AS line_ref,
                (SELECT period_start FROM filter_params) AS date,
                NULL::date              AS date_maturity,
                account_type,
                partner_type,
                0.00                    AS debit,
                0.00                    AS credit,
                0.00                    AS balance,
                opening_balance         AS opening_balance,
                opening_balance         AS closing_balance,
                opening_balance         AS partner_opening_balance,
                opening_balance         AS partner_closing_balance,
                opening_balance         AS period_opening_balance,
                opening_balance         AS period_closing_balance
            FROM opening_balances
            WHERE NOT EXISTS (
                -- Only show if partner has NO movements in period
                SELECT 1
                FROM with_partner_balances wpb
                WHERE wpb.partner_id = opening_balances.partner_id
                  AND wpb.account_type = opening_balances.account_type
                  AND wpb.company_id = opening_balances.company_id
            )

            --WHERE partner_id = 10754  -- Uncomment for testing specific partner
        """)
