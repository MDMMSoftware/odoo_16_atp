# -*- coding: utf-8 -*-
{
    'name': "Duty Process",
    'version': "16.0.1.0.1",
    'summary': """ Duty Process for All 
                   Modules In Odoo""",
    'description': """Parts & Material Duty Process for All 
                      Modules In Odoo, Branch, Branch Operations, 
                      Multiple Branch, Branch Setup""",
    'author': "Mudon Maung Maung Co.,Ltd",
    'company': "Mudon Maung Maung Co.,Ltd",
    'maintainer': "Mudon Maung Maung Co.,Ltd",
    'category': 'Tools',
    'depends': ['purchase',
                'sale_stock', 'purchase_stock','stock',
                'stock_account','base','fleet_extension','mmm_project'],
    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',
        'views/duty_process.xml',
        'views/duty_report_views.xml',
        
        
    ],
    'images': ['static/description/banner.png'],
    'license': "AGPL-3",
    'installable': True,
    'application': True
}
