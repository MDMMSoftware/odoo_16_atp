
{
    'name': "Attendance Extension",
    'version': "16.0.1.0.1",
    'summary': """ HR Attendance Extension""",
    'description': """ HR Attendance """,
    'author': "Mudon Maung Maung Co.,Ltd",
    'category': 'Tools',
    'depends': ['hr_attendance','hr','employee_extension'],
    'data': [
        'views/attendance.xml',
        'views/employee_view.xml',
        'views/attendance_export_wizard.xml',
        'security/ir.model.access.csv',
        'security/security.xml',
        ],
    'assets': {
        'web.assets_backend': [
            'attendance_extension/static/src/js/attendance.js'
        ]
    },
    'license': "LGPL-3",
    'installable': True,
    'application': False
}
