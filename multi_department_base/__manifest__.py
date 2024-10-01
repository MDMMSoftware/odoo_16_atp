{
    'name': "Multi Department Operations",
    'version': "16.0.1.0.1",
    'summary': """ Multiple Department Unit Operation Setup for All 
                   Modules In Odoo""",
    'description': """Multiple Department Unit Operation Setup for All 
                      Modules In Odoo, Department, Department Operations, 
                      Multiple Department, Department Setup""",
    'author': "Cybrosys Techno Solutions",
    'company': "Cybrosys Techno Solutions",
    'maintainer': "Cybrosys Techno Solutions",
    'website': "https://www.cybrosys.com",
    'category': 'Tools',
    'depends': ['sale_management',
                'sale_stock', 'purchase_stock',
                'stock_account','base'],
    'data': [
        # 'views/res_department.xml',
        'security/department_security.xml',
        'security/ir.model.access.csv',
        # 'views/department_res_partner_views.xml',
        # 'views/department_sale_order_views.xml',
        # 'views/department_purchase_order_views.xml',
        # 'views/department_res_users_views.xml',
        # 'views/department_stock_picking_views.xml',
        # 'views/department_account_move_views.xml',
        # 'views/department_account_payment_views.xml',
        # 'views/department_account_journal.xml',
        # 'views/department_stock_warehouse_views.xml',
        
    ],
    'images': ['static/description/banner.png'],
    'license': "AGPL-3",
    'installable': True,
    'application': False
}
