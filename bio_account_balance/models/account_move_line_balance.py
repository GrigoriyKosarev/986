from odoo import models, fields, api


class AccountMoveLineBalance(models.Model):
    _name = 'bio.account.move.line.balance'
    _description = 'Stored balances for account.move.line'

    move_line_id = fields.Many2one(
        comodel_name='account.move.line',
        string='Journal Item',
        required=True,
        ondelete='cascade',
        index=True
    )
    company_currency_id = fields.Many2one(
        comodel_name='res.currency',
        string='Currency',
        required=True,
    )
    bio_initial_balance = fields.Monetary(
        string='Initial Balance',
        currency_field='company_currency_id',
        readonly=True,
        store=True,
    )
    bio_end_balance = fields.Monetary(
        string='End Balance',
        currency_field='company_currency_id',
        readonly=True,
        store=True,
    )

    _sql_constraints = [
        ('move_line_unique', 'unique(move_line_id)', 'Move line must be unique!'),
    ]

    @api.model
    def update_balances_sql(self):
        query = """
        INSERT INTO bio_account_move_line_balance (
            move_line_id,
            bio_initial_balance,
            bio_end_balance,
            company_currency_id
        )
        SELECT
            aml.id AS move_line_id,

            COALESCE(
                SUM(aml.debit - aml.credit) OVER (
                    PARTITION BY aml.account_id, COALESCE(aml.partner_id,0)
                    ORDER BY aml.date, aml.id
                    ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING
                ), 0
            ) AS bio_initial_balance,

            COALESCE(
                SUM(aml.debit - aml.credit) OVER (
                    PARTITION BY aml.account_id, COALESCE(aml.partner_id,0)
                    ORDER BY aml.date, aml.id
                    ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
                ), 0
            ) AS bio_end_balance,

            aml.company_currency_id
        FROM account_move_line aml
        WHERE aml.parent_state = 'posted'
        ON CONFLICT (move_line_id) DO UPDATE
        SET
            bio_initial_balance = EXCLUDED.bio_initial_balance,
            bio_end_balance = EXCLUDED.bio_end_balance,
            company_currency_id = EXCLUDED.company_currency_id;
        """
        self.env.cr.execute(query)

    @api.model
    def reset_and_update_balances(self):
        """
        Повне перерахування балансів для всіх проводок.
        1. Очищує таблицю bio_account_move_line_balance
        2. Розраховує баланси через SQL window function

        Баланси зберігаються тільки в bio_account_move_line_balance.
        account_move_line.bio_initial_balance та bio_end_balance - це computed fields
        які читають дані з bio_account_move_line_balance через JOIN.

        ODOO-834
        """
        import logging
        _logger = logging.getLogger(__name__)

        try:
            # Крок 1: Очищення таблиці балансів
            _logger.info("Truncating bio_account_move_line_balance table...")
            self.env.cr.execute("TRUNCATE TABLE bio_account_move_line_balance RESTART IDENTITY;")
            self.env.invalidate_all()

            # Крок 2: Розрахунок балансів через window function
            _logger.info("Calculating balances via SQL window function...")
            self.update_balances_sql()

            # Рахуємо скільки рядків оновили
            self.env.cr.execute("SELECT COUNT(*) FROM bio_account_move_line_balance;")
            total_count = self.env.cr.fetchone()[0]

            # Інвалідуємо кеш щоб Odoo перечитав нові значення через computed fields
            self.env['account.move.line'].invalidate_model(['bio_initial_balance', 'bio_end_balance'])

            _logger.info(f"Balance calculation completed successfully! Calculated {total_count} records.")

            # Повертаємо success notification
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Success',
                    'message': f'Balance calculation completed! Calculated {total_count} records.',
                    'type': 'success',
                    'sticky': False,
                }
            }

        except Exception as e:
            _logger.error("Failed to calculate balances: %s", str(e), exc_info=True)

            # Повертаємо error notification
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Error',
                    'message': f'Failed to calculate balances: {str(e)}',
                    'type': 'danger',
                    'sticky': True,
                }
            }
