
{
    'name': "Maintenance Extension",
    'version': "16.0.1.0.1",
    'summary': """ Maintenance Extension""",
    'description': """ Maintenance Module """,
    'author': "Mudon Maung Maung Co.,Ltd",
    'category': 'Tools',
    'depends': ['base','maintenance','repair_internal','fleet_extension','account_asset','hr'],
    'data': [
        'security/ir.model.access.csv',
        'security/security.xml',
        'views/maintenance_views.xml',
        'views/maintenance_menus.xml'
        ],
    'license': "LGPL-3",
    'installable': True,
    'application': False
}
