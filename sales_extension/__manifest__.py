
{
    'name': "Sale Extension",
    'version': "16.0.1.0.1",
    'summary': """ Sale Setup for All 
                   Modules In Odoo""",
    'description': """Sale Setup for All 
                      Modules In Odoo""",
    'author': "Mudon Maung Maung Co.,Ltd",
    'category': 'Tools',
    'depends': ['sale','sale_stock','stock','account','analytic','multi_department_base','reporting_module'],
    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',
        'views/sale_order.xml',
        'views/account_journal.xml',
        'views/sale_detail_wizard.xml',
        'views/credit_limit.xml',
        # 'views/account_tax.xml',
        'report/quotations_report_template.xml',
        'report/invoice_report_template_tanz.xml',
        'report/ir_actions_report.xml',
    ],


    'license': "AGPL-3",
    'installable': True,
    'application': True
}
