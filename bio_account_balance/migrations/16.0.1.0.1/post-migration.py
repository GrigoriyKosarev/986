# -*- coding: utf-8 -*-
"""
Post-migration script to drop bio_initial_balance and bio_end_balance columns
from account_move_line table.

These fields are now computed fields that read from bio_account_move_line_balance table.
No need to store them in account_move_line anymore.

ODOO-834
"""

import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """
    Drop bio_initial_balance and bio_end_balance columns from account_move_line.
    """
    _logger.info("Starting migration: removing bio_initial_balance and bio_end_balance columns from account_move_line...")

    # Check if columns exist before dropping
    cr.execute("""
        SELECT column_name
        FROM information_schema.columns
        WHERE table_name='account_move_line'
          AND column_name IN ('bio_initial_balance', 'bio_end_balance');
    """)
    existing_columns = [row[0] for row in cr.fetchall()]

    if 'bio_initial_balance' in existing_columns:
        _logger.info("Dropping column bio_initial_balance from account_move_line...")
        cr.execute("ALTER TABLE account_move_line DROP COLUMN IF EXISTS bio_initial_balance CASCADE;")
        _logger.info("Column bio_initial_balance dropped successfully.")

    if 'bio_end_balance' in existing_columns:
        _logger.info("Dropping column bio_end_balance from account_move_line...")
        cr.execute("ALTER TABLE account_move_line DROP COLUMN IF EXISTS bio_end_balance CASCADE;")
        _logger.info("Column bio_end_balance dropped successfully.")

    if not existing_columns:
        _logger.info("Columns bio_initial_balance and bio_end_balance do not exist in account_move_line. Skipping.")

    _logger.info("Migration completed successfully!")
