
{
    'name': "Stock Adjustment",
    'version': "16.0.1.0.1",
    'summary': """ Stock Adjustment for All 
                   Modules In Odoo""",
    'description': """Stock Adjustment for All 
                      Modules In Odoo""",
    'author': "Mudon Maung Maung Co.,Ltd",
    'category': 'Tools',
    'depends': ['stock','product','base','stock_account','sale_stock','hr','advance_expense'],
    'data': [
        'wizard/adjust_return.xml',
        'views/adjustment.xml',
        'security/ir.model.access.csv',
    ],
    'license': "AGPL-3",
    'installable': True,
    'application': True
}
