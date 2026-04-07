# -*- coding: utf-8 -*-
from odoo import api, fields, models


class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    # Computed balance fields (НЕ зберігаються в account_move_line, читаються з bio_account_move_line_balance)
    # Розраховуються через SQL window function та зберігаються в окремій таблиці bio_account_move_line_balance
    # НЕ використовуються в pivot view - для pivot є динамічні поля bio_opening/closing_by_partner
    bio_initial_balance = fields.Monetary(
        string="Initial Balance",
        currency_field="company_currency_id",
        compute="_compute_balances",
        store=False,  # НЕ зберігається в account_move_line - читається з bio_account_move_line_balance!
        readonly=True,
        help="Balance BEFORE the current line (excluding current transaction). "
             "Calculated using SQL window functions with PARTITION BY account+partner. "
             "Stored in bio_account_move_line_balance table. "
             "Updated via scheduled cron or manually via 'Refresh Balances' button. "
             "Not available as pivot measure - use bio_opening_by_partner instead."
    )  # ODOO-834

    bio_end_balance = fields.Monetary(
        string="End Balance",
        currency_field="company_currency_id",
        compute="_compute_balances",
        store=False,  # НЕ зберігається в account_move_line - читається з bio_account_move_line_balance!
        readonly=True,
        help="Balance AFTER the current line (including current transaction). "
             "Calculated using SQL window functions with PARTITION BY account+partner. "
             "Stored in bio_account_move_line_balance table. "
             "Updated via scheduled cron or manually via 'Refresh Balances' button. "
             "Not available as pivot measure - use bio_closing_by_partner instead."
    )  # ODOO-834

    def _compute_balances(self):
        """
        Читає баланси з окремої таблиці bio_account_move_line_balance через SQL JOIN.
        Це швидше ніж зберігати в account_move_line та не блокує основну таблицю.
        ODOO-834
        """
        if not self:
            return

        # Batch SQL query для ефективного читання
        query = """
            SELECT move_line_id, bio_initial_balance, bio_end_balance
            FROM bio_account_move_line_balance
            WHERE move_line_id IN %s
        """
        self.env.cr.execute(query, (tuple(self.ids),))
        balance_dict = {row[0]: (row[1], row[2]) for row in self.env.cr.fetchall()}

        for rec in self:
            if rec.id in balance_dict:
                rec.bio_initial_balance = balance_dict[rec.id][0]
                rec.bio_end_balance = balance_dict[rec.id][1]
            else:
                # Якщо немає запису в balance таблиці - баланс 0
                rec.bio_initial_balance = 0.0
                rec.bio_end_balance = 0.0

    # Dynamic balance fields (НЕ зберігаються, розраховуються в read_group)
    # Використовуються в pivot view для коректного відображення балансів з урахуванням фільтрів
    bio_opening_by_partner = fields.Monetary(
        string="Opening Balance",
        currency_field="company_currency_id",
        store=False,  # Не зберігається в БД, розраховується динамічно
        readonly=True,
        help="Dynamic opening balance for partner grouping based on pivot filters. "
             "Calculated in read_group() method. "
             "Shows balance at the START of the filtered period. "
             "Formula: bio_opening_by_partner + sum(balance) = bio_closing_by_partner"
    )  # ODOO-834

    bio_closing_by_partner = fields.Monetary(
        string="Closing Balance",
        currency_field="company_currency_id",
        store=False,  # Не зберігається в БД, розраховується динамічно
        readonly=True,
        help="Dynamic closing balance for partner grouping based on pivot filters. "
             "Calculated in read_group() method. "
             "Shows balance at the END of the filtered period. "
             "Formula: bio_opening_by_partner + sum(balance) = bio_closing_by_partner"
    )  # ODOO-834

    @api.model
    def read_group(self, domain, fields, groupby, offset=0, limit=None, orderby=False, lazy=True):
        """
        Override read_group для динамічного розрахунку opening/closing полів.

        Поля bio_opening_by_partner і bio_closing_by_partner розраховуються динамічно
        на основі domain (фільтрів) в pivot view для будь-якого групування.

        Це дозволяє коректно відображати баланси при фільтрації по даті:
        - opening = баланс на початок періоду
        - closing = баланс на кінець періоду

        ODOO-834
        """
        # Список полів які треба розрахувати динамічно
        dynamic_fields = ['bio_opening_by_partner', 'bio_closing_by_partner']

        # Перевіряємо чи запитують хоча б одне динамічне поле
        requested_dynamic_fields = [f for f in fields if any(df in f for df in dynamic_fields)]

        if not requested_dynamic_fields:
            # Якщо не запитують динамічні поля - викликаємо стандартний read_group
            return super().read_group(domain, fields, groupby, offset, limit, orderby, lazy)

        # Викликаємо стандартний read_group для всіх інших полів
        other_fields = [f for f in fields if not any(df in f for df in dynamic_fields)]
        result = super().read_group(domain, other_fields, groupby, offset, limit, orderby, lazy)

        # Перевіряємо чи групуємо по partner_id - для batch оптимізації
        is_groupby_partner = groupby and any('partner_id' in g for g in (groupby if isinstance(groupby, list) else [groupby]))

        if is_groupby_partner:
            # BATCH OPTIMIZATION: Один SQL запит для всіх партнерів
            opening_balances = {}
            closing_balances = {}

            # Розраховуємо тільки ті поля які запитані
            if any('bio_opening_by_partner' in f for f in requested_dynamic_fields):
                opening_balances = self._calc_opening_by_partner_batch(domain)

            if any('bio_closing_by_partner' in f for f in requested_dynamic_fields):
                closing_balances = self._calc_closing_by_partner_batch(domain)

            # Заповнюємо результат з попередньо розрахованих балансів
            for group in result:
                partner_id = group.get('partner_id')
                if partner_id:
                    # partner_id може бути tuple (id, name) або просто id
                    partner_id = partner_id[0] if isinstance(partner_id, (tuple, list)) else partner_id
                else:
                    partner_id = False

                # Присвоюємо баланси з batch розрахунку
                if 'bio_opening_by_partner' in [f.split(':')[0] for f in requested_dynamic_fields]:
                    group['bio_opening_by_partner'] = opening_balances.get(partner_id, 0.0)

                if 'bio_closing_by_partner' in [f.split(':')[0] for f in requested_dynamic_fields]:
                    group['bio_closing_by_partner'] = closing_balances.get(partner_id, 0.0)

        else:
            # FALLBACK: Індивідуальний розрахунок для кожної групи (якщо не по partner_id)
            for group in result:
                # Створюємо domain для цієї конкретної групи
                group_domain = domain.copy() if domain else []

                # Додаємо умови групування до domain
                if groupby and '__domain' in group:
                    group_domain = group_domain + group['__domain']

                # Розраховуємо кожне запитане динамічне поле
                for field_spec in requested_dynamic_fields:
                    field_name = field_spec.split(':')[0]  # Видаляємо агрегацію якщо є

                    if field_name == 'bio_opening_by_partner':
                        group[field_name] = self._calc_opening_by_partner(group_domain)
                    elif field_name == 'bio_closing_by_partner':
                        group[field_name] = self._calc_closing_by_partner(group_domain)

        return result

    def _calc_opening_by_partner(self, domain):
        """
        Розрахунок opening balance для групування по partner
        з урахуванням фільтрів (особливо по даті).
        Оптимізований - використовує прямий SQL з JOIN до bio_account_move_line_balance.

        Логіка:
        1. Конвертуємо Odoo domain в SQL WHERE clause
        2. JOIN з bio_account_move_line_balance для отримання балансів
        3. Знаходимо ПЕРШІ рядки для кожного account+partner в межах фільтру
        4. Сумуємо їх bio_initial_balance

        ODOO-834
        """
        # Конвертуємо Odoo domain в SQL WHERE clause
        query_obj = self._where_calc(domain)
        from_clause, where_clause, where_params = query_obj.get_sql()

        # Якщо немає WHERE умов - значить немає фільтрів
        if not where_clause:
            where_clause = "1=1"

        # Замінюємо "account_move_line" на "aml" в where_clause (бо ми використовуємо аліас aml)
        where_clause = where_clause.replace('"account_move_line"', 'aml')

        # SQL запит з JOIN до balance таблиці
        query = f"""
            WITH filtered_lines AS (
                SELECT
                    aml.account_id,
                    aml.partner_id,
                    bal.bio_initial_balance,
                    aml.date,
                    aml.id
                FROM {from_clause} aml
                LEFT JOIN bio_account_move_line_balance bal ON bal.move_line_id = aml.id
                WHERE aml.parent_state='posted' AND ({where_clause})
            ),
            first_lines_per_account AS (
                SELECT DISTINCT ON (account_id, COALESCE(partner_id,0))
                    COALESCE(bio_initial_balance, 0) as bio_initial_balance
                FROM filtered_lines
                ORDER BY account_id, COALESCE(partner_id,0), date ASC, id ASC
            )
            SELECT COALESCE(SUM(bio_initial_balance), 0) as total
            FROM first_lines_per_account;
        """

        self.env.cr.execute(query, where_params)
        result = self.env.cr.fetchone()
        return result[0] if result else 0.0

    def _calc_closing_by_partner(self, domain):
        """
        Розрахунок closing balance для групування по partner
        з урахуванням фільтрів (особливо по даті).
        Оптимізований - використовує прямий SQL з JOIN до bio_account_move_line_balance.

        Логіка:
        1. Конвертуємо Odoo domain в SQL WHERE clause
        2. JOIN з bio_account_move_line_balance для отримання балансів
        3. Знаходимо ОСТАННІ рядки для кожного account+partner в межах фільтру
        4. Сумуємо їх bio_end_balance

        ODOO-834
        """
        # Конвертуємо Odoo domain в SQL WHERE clause
        query_obj = self._where_calc(domain)
        from_clause, where_clause, where_params = query_obj.get_sql()

        # Якщо немає WHERE умов - значить немає фільтрів
        if not where_clause:
            where_clause = "1=1"

        # Замінюємо "account_move_line" на "aml" в where_clause (бо ми використовуємо аліас aml)
        where_clause = where_clause.replace('"account_move_line"', 'aml')

        # SQL запит з JOIN до balance таблиці
        query = f"""
            WITH filtered_lines AS (
                SELECT
                    aml.account_id,
                    aml.partner_id,
                    bal.bio_end_balance,
                    aml.date,
                    aml.id
                FROM {from_clause} aml
                LEFT JOIN bio_account_move_line_balance bal ON bal.move_line_id = aml.id
                WHERE aml.parent_state='posted' AND ({where_clause})
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
        result = self.env.cr.fetchone()
        return result[0] if result else 0.0

    def _calc_opening_by_partner_batch(self, domain):
        """
        Batch розрахунок opening balance для ВСІХ партнерів одночасно.
        Використовується в read_group() для прискорення pivot view.

        Повертає словник: {partner_id: opening_balance, ...}

        Логіка:
        1. Знаходимо ПЕРШІ рядки для кожного account+partner
        2. Групуємо по partner_id (SUM по всіх акаунтах)
        3. Повертаємо словник для швидкого lookup

        ODOO-834
        """
        # Конвертуємо Odoo domain в SQL WHERE clause
        query_obj = self._where_calc(domain)
        from_clause, where_clause, where_params = query_obj.get_sql()

        # Якщо немає WHERE умов - значить немає фільтрів
        if not where_clause:
            where_clause = "1=1"

        # Замінюємо "account_move_line" на "aml" в where_clause (бо ми використовуємо аліас aml)
        where_clause = where_clause.replace('"account_move_line"', 'aml')

        # SQL запит з JOIN до balance таблиці + GROUP BY partner_id
        query = f"""
            WITH filtered_lines AS (
                SELECT
                    aml.account_id,
                    aml.partner_id,
                    bal.bio_initial_balance,
                    aml.date,
                    aml.id
                FROM {from_clause} aml
                LEFT JOIN bio_account_move_line_balance bal ON bal.move_line_id = aml.id
                WHERE aml.parent_state='posted' AND ({where_clause})
            ),
            first_lines_per_account AS (
                SELECT DISTINCT ON (account_id, COALESCE(partner_id,0))
                    partner_id,
                    COALESCE(bio_initial_balance, 0) as bio_initial_balance
                FROM filtered_lines
                ORDER BY account_id, COALESCE(partner_id,0), date ASC, id ASC
            )
            SELECT
                COALESCE(partner_id, 0) as partner_id,
                SUM(bio_initial_balance) as opening_balance
            FROM first_lines_per_account
            GROUP BY COALESCE(partner_id, 0);
        """

        self.env.cr.execute(query, where_params)

        # Конвертуємо результат в словник {partner_id: balance}
        result = {}
        for row in self.env.cr.fetchall():
            partner_id = row[0] if row[0] != 0 else False
            result[partner_id] = row[1]

        return result

    def _calc_closing_by_partner_batch(self, domain):
        """
        Batch розрахунок closing balance для ВСІХ партнерів одночасно.
        Використовується в read_group() для прискорення pivot view.

        Повертає словник: {partner_id: closing_balance, ...}

        Логіка:
        1. Знаходимо ОСТАННІ рядки для кожного account+partner
        2. Групуємо по partner_id (SUM по всіх акаунтах)
        3. Повертаємо словник для швидкого lookup

        ODOO-834
        """
        # Конвертуємо Odoo domain в SQL WHERE clause
        query_obj = self._where_calc(domain)
        from_clause, where_clause, where_params = query_obj.get_sql()

        # Якщо немає WHERE умов - значить немає фільтрів
        if not where_clause:
            where_clause = "1=1"

        # Замінюємо "account_move_line" на "aml" в where_clause (бо ми використовуємо аліас aml)
        where_clause = where_clause.replace('"account_move_line"', 'aml')

        # SQL запит з JOIN до balance таблиці + GROUP BY partner_id
        query = f"""
            WITH filtered_lines AS (
                SELECT
                    aml.account_id,
                    aml.partner_id,
                    bal.bio_end_balance,
                    aml.date,
                    aml.id
                FROM {from_clause} aml
                LEFT JOIN bio_account_move_line_balance bal ON bal.move_line_id = aml.id
                WHERE aml.parent_state='posted' AND ({where_clause})
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

        # Конвертуємо результат в словник {partner_id: balance}
        result = {}
        for row in self.env.cr.fetchall():
            partner_id = row[0] if row[0] != 0 else False
            result[partner_id] = row[1]

        return result

    # NOTE: create/write/unlink hooks REMOVED for performance optimization
    #
    # Previously these hooks updated balances in real-time, but this caused:
    # - Slow invoice opening (SQL queries on every line)
    # - High database load during batch operations
    #
    # New approach:
    # - Balances updated via scheduled cron job (every 15 minutes)
    # - Manual refresh available via "Refresh Balances" button
    # - Much faster user experience
    #
    # ODOO-834

    def _update_balances_incremental(self):
        """
        Інкрементальне оновлення балансів для рядків self та всіх наступних рядків
        в тих же партиціях (account_id + partner_id).

        Використовує SQL window function для ефективного перерахунку.

        Алгоритм:
        1. Фільтруємо тільки posted рядки
        2. Визначаємо унікальні партиції (account_id, partner_id) та мінімальну дату в кожній
        3. Знаходимо ВСІ рядки від min_date в кожній партиції (бо всі наступні потребують перерахунку)
        4. Виконуємо SQL window function для перерахунку балансів

        ODOO-834
        """
        if not self:
            return

        # Фільтруємо тільки posted рядки (draft/cancelled не впливають на баланси)
        posted_lines = self.filtered(lambda l: l.parent_state == 'posted')
        if not posted_lines:
            return  # Нема posted рядків - нема роботи

        # Збираємо унікальні партиції та мінімальні дати
        partitions = {}  # {(account_id, partner_id): min_date}
        for line in posted_lines:
            key = (line.account_id.id, line.partner_id.id if line.partner_id else False)
            if key not in partitions or line.date < partitions[key]:
                partitions[key] = line.date

        # Будуємо domain для пошуку всіх рядків які потрібно оновити
        domain_parts = []
        for (account_id, partner_id), min_date in partitions.items():
            domain_parts.append([
                ('account_id', '=', account_id),
                ('partner_id', '=', partner_id),
                ('date', '>=', min_date),
                ('parent_state', '=', 'posted'),
            ])

        if not domain_parts:
            return

        # Об'єднуємо всі domain через OR
        lines_to_update = self.env['account.move.line']
        for domain in domain_parts:
            lines_to_update |= self.env['account.move.line'].search(domain)

        if not lines_to_update:
            return

        # Виконуємо оновлення через SQL window function (зберігаємо тільки в bio_account_move_line_balance)
        query = """
            INSERT INTO bio_account_move_line_balance (move_line_id, bio_initial_balance, bio_end_balance, company_currency_id)
            SELECT
                aml.id,
                COALESCE(
                    SUM(aml.debit - aml.credit) OVER (
                        PARTITION BY aml.account_id, COALESCE(aml.partner_id,0)
                        ORDER BY aml.date, aml.id
                        ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING
                    ), 0
                ) AS initial_balance,
                COALESCE(
                    SUM(aml.debit - aml.credit) OVER (
                        PARTITION BY aml.account_id, COALESCE(aml.partner_id,0)
                        ORDER BY aml.date, aml.id
                        ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
                    ), 0
                ) AS end_balance,
                aml.company_currency_id
            FROM account_move_line aml
            WHERE aml.parent_state='posted' AND aml.id IN %s
            ON CONFLICT (move_line_id) DO UPDATE
            SET bio_initial_balance = EXCLUDED.bio_initial_balance,
                bio_end_balance = EXCLUDED.bio_end_balance,
                company_currency_id = EXCLUDED.company_currency_id;
            """
        self.env.cr.execute(query, (tuple(lines_to_update.ids),))

        # Інвалідуємо кеш щоб Odoo перечитав нові значення з bio_account_move_line_balance через compute
        lines_to_update.invalidate_recordset(['bio_initial_balance', 'bio_end_balance'])
