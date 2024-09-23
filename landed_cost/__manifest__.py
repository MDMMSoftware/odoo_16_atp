
{
    'name': "Landed Cost Extension",
    'version': "16.0.1.0.1",
    'summary': """ Landed Cost Setup for All 
                   Modules In Odoo""",
    'description': """Landed Cost Setup for All 
                      Modules In Odoo""",
    'author': "Mudon Maung Maung Co.,Ltd",
    'category': 'Tools',
    'depends': ['stock_landed_costs','multi_branch_base'],
    'data': [
       'views/landed_cost.xml'
    ],
    'license': "AGPL-3",
    'installable': True,
    'application': True
}
