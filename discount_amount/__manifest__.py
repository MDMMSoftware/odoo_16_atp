# -*- coding: utf-8 -*-
{
    'name': "Discount Amount",
    'version': "16.0.1.0.1",
    'summary': """ Discount Amount for All 
                   Modules In Odoo""",
    'description': """Parts & Material Discount Amount for All 
                      Modules In Odoo, Branch, Branch Operations, 
                      Multiple Branch, Branch Setup""",
    'author': "Mudon Maung Maung Co.,Ltd",
    'company': "Mudon Maung Maung Co.,Ltd",
    'maintainer': "Mudon Maung Maung Co.,Ltd",
    'category': 'Tools',
    'depends': ['purchase',
                'sale_stock', 'purchase_stock','stock','account','sale',
                'stock_account','base','advance_expense','exchange_rate'],
    'data': [
        'views/purchase.xml',
        'views/sale_order.xml',
        'views/account.xml'
    ],
    'images': ['static/description/banner.png'],
    'license': "AGPL-3",
    'installable': True,
    'application': True
}
