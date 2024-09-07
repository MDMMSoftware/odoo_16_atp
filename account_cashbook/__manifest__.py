
{
    'name': "Account Cashbook",
    'version': "16.0.1.0.1",
    'summary': """ Cashbook Setup for All 
                   Modules In Odoo""",
    'description': """Cashbook Setup for All 
                      Modules In Odoo, Branch, Branch Operations, 
                      Multiple Branch, Branch Setup""",
    'author': "Mudon Maung Maung Co.,Ltd",
    'category': 'Tools',
    'depends': ['account','multi_branch_base','hr','analytic','advance_expense'],
    'data': [
        'security/ir.model.access.csv',
        'security/security.xml',
        'views/account_cashbook.xml',
        'views/multi_currencies_cashbook.xml',
        'wizard/cashbook_check.xml',
        'wizard/cashbook_report.xml',
    ],
    'license': "AGPL-3",
    'installable': True,
    'application': False
}
