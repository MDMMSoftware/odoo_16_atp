
{
    'name': "Access Right",
    'version': "16.0.1.0.1",
    'summary': """ Access Right Setup for All 
                   Modules In Odoo""",
    'description': """Access Right Setup for All 
                      Modules In Odoo, Branch, Branch Operations, 
                      Multiple Branch, Branch Setup""",
    'author': "Mudon Maung Maung Co.,Ltd",
    'company': "Mudon Maung Maung .,Co.Ltd",
    'maintainer': "Mudon Maung Maung .,Co.Ltd",
    'category': 'Customization',
    'depends': ['sale_management','base',
                'sale_stock', 'purchase_stock',
                'stock_account','purchase','sale','account_accountant','stock','advance_expense','fleet'],
    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',
    ],
    'images': ['static/description/banner.png'],
    'license': "AGPL-3",
    'installable': True,
    'application': False
}
