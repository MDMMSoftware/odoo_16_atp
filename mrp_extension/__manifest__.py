
{
    'name': "MRP Extension",
    'version': "16.0.1.0.1",
    'summary': """ Manufacturing Extension""",
    'description': """ Manufacturing Extension Module """,
    'author': "Mudon Maung Maung Co.,Ltd",
    'category': 'Tools',
    'depends': ['base','mrp','requisition'],
    'data': [
        # 'security/security.xml',
        'views/manufacturing_order_view.xml',
        'security/ir.model.access.csv',

        ],
    'license': "LGPL-3",
    'installable': True,
    'application': False
}
