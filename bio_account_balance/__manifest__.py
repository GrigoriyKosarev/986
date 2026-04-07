# -*- coding: utf-8 -*-
{
    'name': 'Biosphera - Account Balance',
    'version': '16.0.1.0.1',
    'category': 'Accounting',
    'summary': 'Calculate and display opening/closing balances for account move lines',
    'description': """
        ODOO-834
    """,
    'author': 'Biosphera',
    'website': 'https://bio.com',
    'license': 'LGPL-3',
    'depends': [
        'account',
        'account_reports'
    ],
    'data': [
        'security/ir.model.access.csv',
        'security/ir_rule.xml',
        'data/ir_asset.xml',  # Force owl_timeout_suppress.js to load first
        'views/account_move_line_report_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'bio_account_balance/static/src/scss/bio_report_tree.scss',
            'bio_account_balance/static/src/js/period_filter.js',
            'bio_account_balance/static/src/js/period_filter_controller.js',
            'bio_account_balance/static/src/xml/period_filter.xml',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
    # 'post_init_hook': 'post_init_update_balances',
}
