
{
    'name': "Advance & Expense",
    'version': "16.0.1.0.1",
    'summary': """ Advance & Expense Setup for All 
                   Modules In Odoo""",
    'description': """Advance & Expense Setup for All 
                      Modules In Odoo""",
    'author': "Mudon Maung Maung Co.,Ltd",
    'category': 'Tools',
    'depends': ['account','analytic','base','multi_branch_base'],
    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',
        'views/account_advance.xml',
        'views/account_expense.xml',
        'views/account_tax.xml',
        'wizard/advance_wizard.xml',
    ],
    # This is for testing owl & qweb
    # 'assets': {
    #     'web.assets_backend': [
    #         'advance_expense/static/src/js/late_order_boolean_field.js',
    #         'advance_expense/static/src/xml/late_order_boolean_field.xml',
    #     ]
    # },
    # 
    'license': "AGPL-3",
    'installable': True,
    'application': True
}
