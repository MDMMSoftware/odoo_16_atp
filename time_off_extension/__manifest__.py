
{
    'name': "Time Off Extension",
    'version': "16.0.1.0.1",
    'summary': """ Time Off Setup for All 
                   Modules In Odoo""",
    'description': """Time Off Setup for All 
                      Modules In Odoo""",
    'author': "Mudon Maung Maung Co.,Ltd",
    'category': 'Tools',
    'depends': ['resource','hr_holidays','employee_extension','hr_attendance'],
    'data': [
        'data/time_off_cron.xml',
        'security/security.xml',
        'security/ir.model.access.csv',
        'views/hr_leave_view.xml',
        'views/hr_leave_prepare.xml',
        'views/hr_leave_type_view.xml',
        'views/hr_leave_allocation.xml',
        'views/resource_calendar.xml',
        'wizard/prepare_timeoff_wizard.xml',
        'wizard/timeoff_warning_wizard.xml',
        'wizard/duty_cover_time_off_warning.xml',
        'wizard/leave_export_wizard.xml'
    ],
    'license': "AGPL-3",
    'installable': True,
    'application': True,
    'assets': {
        'web.assets_backend': [
            'time_off_extension/static/src/views/**/*.xml',
            # 'time_off_extension/static/src/views/calendar/calendar_controller.xml',
            # 'time_off_extension/static/src/js/alert_confirmation.js',
                ]
    }

}
