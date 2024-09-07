# -*- coding: utf-8 -*-
{
    'name': "Reporting All in One",
    'version': "16.0.1.0.1",
    'summary': """ Reporting Setup for All 
                   Modules In Odoo""",
    'description': """Reporting Setup for All 
                      Modules In Odoo, Branch, Branch Operations, 
                      Multiple Branch, Branch Setup""",
    'author': "Mudon Maung Maung Co.,Ltd",
    'company': "Mudon Maung Maung Co.,Ltd",
    'maintainer': "Mudon Maung Maung Co.,Ltd",
    'category': 'Tools',
    'depends': ['purchase','sale_stock', 'purchase_stock','stock_account','employee_extension'],
    'data': [
        'views/director_report.xml',
        'views/reporting_url.xml',
        'views/cashbook_ledger_report.xml',
        'views/sale_summary_report.xml',
        'views/purchase_summary_report.xml',
        'security/security.xml',
        'security/ir.model.access.csv',
    ],
    'images': ['static/description/banner.png'],
    'license': "AGPL-3",
    'installable': True,
    'application': True
}
