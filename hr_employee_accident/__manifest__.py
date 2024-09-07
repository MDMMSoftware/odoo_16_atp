# -*- encoding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#
#    Copyright (c) 2014 Noviat nv/sa (www.noviat.com). All rights reserved.
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as
#    published by the Free Software Foundation, either version 3 of the
#    License, or (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program. If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################

{
    'name': 'Employee Accident',
    'version': '16.0.1.0',
    'author': 'Mudon Maung Maung Co.,Ltd',
    'website': 'www.mudonmaungmaung.com',
    'category' : 'Employee',
    'depends': ['hr','employee_extension'],
    'description': """
    
Employee Accident and warning
==============================

This module will create hr employee accident and warning.

    """,
    'data' : [
        # 'security/security.xml',
        'security/ir.model.access.csv',


        'views/accident_view.xml',
        'views/warning_view.xml',
        'views/employee_accident_sequence.xml',
        'views/employee_view.xml',
        'views/salary_deduction_view.xml',
        'views/configuration_view.xml',
        'data/warning_cron.xml',
        'data/salary_deduction_data.xml'
    ],
    'license': 'LGPL-3',
    'assets': {
        'web.assets_backend': [
            'hr_employee_accident/static/src/css/custom_kanban.css',

        ]
    },

}
