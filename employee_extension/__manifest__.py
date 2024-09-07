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
    'name': 'Employee Information Extension',
    'version': '16.0.1.0',
    'author': 'Mudon Maung Maung Co.,Ltd',
    'website': 'www.mudonmaungmaung.com',
    'category' : 'Employee',
    'depends': ['hr','base','hr_contract','account','analytic','multi_branch_base','fleet_extension','advance_expense','contacts','account_accountant'],
    'description': """
        
Modify Employee Information
==============================

This module will modify employee information.

    """,
    'data' : [
        'security/hr_security.xml',
        'security/ir.model.access.csv',
        'views/hr_employee_view.xml',
        'views/hr_department_view.xml',        
        'views/hr_education_configuration_view.xml',  
        'views/hr_education_view.xml',  
        'views/hr_pro_education.xml', 
        'views/hr_working_experience.xml',    
        'views/hr_training_configuration_view.xml',  
        'views/hr_training_view.xml',  
        'views/hr_training_import.xml',    
        'views/res_partner.xml',      
        'views/employee_template.xml',                                               
        'views/employee_report.xml',      
        'wizard/file_import_wizard.xml',       
        # 'views/hr_employee_accident_view.xml',
        # 'views/hr_employee_warning_view.xml',
        'views/configuration_view.xml',
        'data/ir.xml',
        # 'views/dashboard.xml',
    ],
    'license': 'LGPL-3',
    'assets': {
        'web.assets_backend': [
            '/employee_extension/static/src/xml/dept_import_btn.xml',
            '/employee_extension/static/src/js/dept_import_btn.js',
        ]
    },

}
