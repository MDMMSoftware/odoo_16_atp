
{
    'name': "Purchase Extension",
    'version': "16.0.1.0.1",
    'summary': """ Purchase Setup for All 
                   Modules In Odoo""",
    'description': """Purchase Setup for All 
                      Modules In Odoo""",
    'author': "Mudon Maung Maung Co.,Ltd",
    'category': 'Tools',
    'depends': ['purchase','purchase_stock','reporting_module'],
    'data': [
        'security/ir.model.access.csv',
        'security/security.xml',
        'views/purchase_order.xml',
        'views/purchase_team.xml',
        'views/purchase_detail_wizard.xml',
        # 'views/account_tax.xml',
    ],
    'license': "AGPL-3",
    'installable': True,
    'application': True
}
