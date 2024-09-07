
{
    'name': "Record Rule",
    'version': "16.0.1.0.1",
    'summary': """ Record Rule Setup for All 
                   Modules In Odoo""",
    'description': """Record Rule Setup for All 
                      Modules In Odoo, Branch, Branch Operations, 
                      Multiple Branch, Branch Setup""",
    'author': "Mudon Maung Maung Co.,Ltd",
    'company': "Mudon Maung Maung .,Co.Ltd",
    'maintainer': "Mudon Maung Maung .,Co.Ltd",
    'category': 'Customization',
    'depends': ['sale_management',
                'sale_stock', 'purchase_stock','stock_extension','stock_adjustment',
                'stock_account','purchase','sale','account','stock','duty_process','advance_expense','repair_internal','sales_team'],
    'data': [
        'security/security.xml',
    ],
    'images': ['static/description/banner.png'],
    'license': "AGPL-3",
    'installable': True,
    'application': True
}
