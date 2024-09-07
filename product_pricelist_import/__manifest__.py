
{
    'name': "Pricelist Import",
    'version': "16.0.1.0.1",
    'summary': """ Pricelist Import Setup for All 
                   Modules In Odoo""",
    'description': """Pricelist Import Setup for All 
                      Modules In Odoo, Branch, Branch Operations, 
                      Multiple Branch, Branch Setup""",
    'author': "Mudon Maung Maung Co.,Ltd",
    'company': "Mudon Maung Maung .,Co.Ltd",
    'maintainer': "Mudon Maung Maung .,Co.Ltd",
    'category': 'Customization',
    'depends': ['sale','base','product'],
    'data': [
        'security/ir.model.access.csv',
        'views/pricelist_import.xml'
    ],
    'images': ['static/description/banner.png'],
    'license': "AGPL-3",
    'installable': True,
    'application': False
}
