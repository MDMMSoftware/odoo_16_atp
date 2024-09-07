# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'Account Prepaidment Extensions',
    'version': '1.0',
    'author': 'Mudon Maung Maung Co.,Ltd',
    'sequence': 60,
    'summary': 'Account',
    'description': "",
    'depends': ['account','account_payment','multi_branch_base'],
    'data': [
        'security/ir.model.access.csv',
        'wizard/prepaid_wizard.xml',
        'views/vendor_prepaid.xml',
    ],
    'installable': True,
    'auto_install': False,
    'application': True,
}
