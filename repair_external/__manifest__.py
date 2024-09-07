# -*- coding: utf-8 -*-
{
    'name': "Repair External",
    'version': "16.0.1.0.1",
    'summary': """ Repair Setup for All 
                   Modules In Odoo""",
    'description': """Parts & Material Repair Setup for All 
                      Modules In Odoo, Branch, Branch Operations, 
                      Multiple Branch, Branch Setup""",
    'author': "Mudon Maung Maung Co.,Ltd",
    'company': "Mudon Maung Maung Co.,Ltd",
    'maintainer': "Mudon Maung Maung Co.,Ltd",
    'category': 'Tools',
    'depends': ['purchase',
                'sale_stock', 'purchase_stock','stock',
                'stock_account','base','hr'
                ,'web','sale','stock_extension'
                ],
    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',
        'views/customer_request_form.xml',
        'views/request_quotation.xml',
        'views/job_order.xml',
        'views/repair_call.xml',
        # 'views/repair_dashboard.xml',
        'data/data.xml',
        'report/repair_report.xml',
        
    ],
    'images': ['static/description/banner.png'],
    'license': "AGPL-3",
    'assets': {
        'web.assets_backend': [
            'repair_external/static/src/**/*',
            # 'repair_external/static/src/components/**/*.js',
            # 'repair_external/static/src/components/**/*.xml',
            # 'repair_external/static/src/components/**/*.scss',
        ]
    },
    'installable': True,
    'application': True
}
