# -*- coding: utf-8 -*-
{
    'name': "Parts & Material Requisition",
    'version': "16.0.1.0.1",
    'summary': """ Parts & Material Requisition Setup for All 
                   Modules In Odoo""",
    'description': """Parts & Material Requisition Setup for All 
                      Modules In Odoo, Branch, Branch Operations, 
                      Multiple Branch, Branch Setup""",
    'author': "Mudon Maung Maung Co.,Ltd",
    'company': "Mudon Maung Maung Co.,Ltd",
    'maintainer': "Mudon Maung Maung Co.,Ltd",
    'category': 'Tools',
    'depends': ['purchase',
                'sale_stock', 'purchase_stock',
                'stock_account','hr'],
    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',
        'wizard/requisition_partial.xml',
        'views/requisition.xml',
        
    ],
    'images': ['static/description/banner.png'],
    'license': "AGPL-3",
    'installable': True,
    'application': True
}
