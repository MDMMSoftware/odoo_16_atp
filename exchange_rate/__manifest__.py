# -*- coding: utf-8 -*-
{
    'name': "Exhange Rate",
    'version': "16.0.1.0.1",
    'summary': """ Exhange Rate for All 
                   Modules In Odoo""",
    'description': """Parts & Material Exhange Rate for All 
                      Modules In Odoo, Branch, Branch Operations, 
                      Multiple Branch, Branch Setup""",
    'author': "Mudon Maung Maung Co.,Ltd",
    'company': "Mudon Maung Maung Co.,Ltd",
    'maintainer': "Mudon Maung Maung Co.,Ltd",
    'category': 'Tools',
    'depends': ['purchase',
                'sale_stock', 'purchase_stock','stock','account','sale',
                'stock_account','base','advance_expense'],
    'data': [
        'views/purchase.xml',
        'views/sales.xml',
        'views/account.xml'
    ],
    'images': ['static/description/banner.png'],
    'license': "AGPL-3",
    'installable': True,
    'application': True
}
