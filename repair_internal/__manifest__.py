# -*- coding: utf-8 -*-
{
    'name': "Repair Internal",
    'version': "16.0.1.0.1",
    'summary': """ Repair Setup for All 
                   Modules In Odoo""",
    'description': """Parts & Material Repair Setup for All 
                      Modules In Odoo, Branch, Branch Operations, 
                      Multiple Branch, Branch Setup""",
    'author': "Mudon Maung Maung Co.,Ltd",
    'company': "Mudon Maung Maung Co.,Ltd",
    'maintainer': "Mudon Maung Maung Co.,Ltd",
    'category': 'Tools',
    'depends': ['purchase',
                'sale_stock', 'purchase_stock','stock',
                'stock_account','base','fleet_extension','stock_adjustment'],
    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',
        'views/repair.xml',
        'views/repair_order.xml',
        'wizard/part_requisition_partial.xml',
        'views/part_requisition.xml',
        'views/fleet_vehicle_views.xml',
        
    ],
    'images': ['static/description/banner.png'],
    'license': "AGPL-3",
    'installable': True,
    'application': True
}
