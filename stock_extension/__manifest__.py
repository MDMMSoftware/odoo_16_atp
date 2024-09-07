
{
    'name': "Stock Extension",
    'version': "16.0.1.0.1",
    'summary': """ Stock Setup for All 
                   Modules In Odoo""",
    'description': """Stock Setup for All 
                      Modules In Odoo""",
    'author': "Mudon Maung Maung Co.,Ltd",
    'category': 'Tools',
    'depends': ['stock','product','base','stock_account','sale_stock','account','multi_branch_base','stock_adjustment'],
    'data': [
        'views/stock_valuation_layer.xml',
        'views/product.xml',
        'views/stock_location_valuation_report.xml',
        'security/ir.model.access.csv',
        'views/stock_card_wizard.xml',
        'views/sale.xml',
        'views/purchase.xml',
        'views/adjustment.xml',
        'views/requisition.xml',
        'views/account_move.xml',
        'views/stock_move.xml',
        'views/stock_lot.xml'
    ],
    'license': "AGPL-3",
    'installable': True,
    'application': True
}
