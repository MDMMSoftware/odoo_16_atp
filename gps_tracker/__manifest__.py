{
    'name': 'GPS Tracker',
    'version': '14.0.1.0',
    'license': 'AGPL-3',
    'author': 'Mudon Maung Maung Co.,Ltd',
    'website': 'https://www.mudonmaungmaung.com/',
    'category' : 'GPS',
    'description': """
Connect GPS Platform to Odoo.

    """,
    'depends': ['fleet','duty_process'],
    'data' : [
        'security/security.xml',
        'security/ir.model.access.csv',
        'views/gps_daily_history.xml',
        'report/report.xml',
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
}