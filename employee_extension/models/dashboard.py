import hashlib
import json
import requests
import locale
from odoo import models, fields, api, _, tools
from odoo.exceptions import UserError,ValidationError
from datetime import datetime, timedelta
from datetime import date
from odoo.tools.float_utils import float_compare, float_round,float_is_zero

# please add in csv
# access_manpower_dashboard_report,access_manpower_dashboard_report,model_manpower_dashboard_report,,1,1,1,1
# access_gender_dashboard_report,access_gender_dashboard_report,model_gender_dashboard_report,,1,1,1,1
# access_top_leave_dashboard_report,access_top_leave_dashboard_report,model_top_leave_dashboard_report,,1,1,1,1

class TopLeaveDashboard(models.Model):
    _name = 'top.leave.dashboard.report'
    _auto = False
    _order = 'total desc'

    employee_id = fields.Many2one('hr.employee',string="Employee",readonly=True)
    department_id = fields.Many2one('hr.department',string="Department",compute="compute_get_data")
    total = fields.Integer('Total',readonly=True)

    def compute_get_data(self):
        for rec in self:
            result = None
            if rec.employee_id:
                result = rec.employee_id.department_id.id
            rec.department_id = result

    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute('''
            CREATE OR REPLACE VIEW %s AS (
                select 
                min(id) as id
                ,sum(number_of_days) as total
                ,employee_id
                from hr_leave
                group by employee_id
                order by sum(number_of_days) desc
                limit 10
                )''' % (self._table,)
        )

class ManPowerDashboard(models.Model):
    _name = 'manpower.dashboard.report'
    _auto = False
    _order = 'id'

    department_id = fields.Many2one('hr.department',string="Department",readonly=True)
    # total = fields.Integer('Total',readonly=True)

    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute('''
            CREATE OR REPLACE VIEW %s AS (
                select (
                row_number() over (order by id))::int as id 
                ,department_id as department_id 
                from hr_employee
                group by department_id,id
                )''' % (self._table,)
        )

class GenderDashboard(models.Model):
    _name = 'gender.dashboard.report'
    _auto = False
    _order = 'id'

    gender = fields.Selection([('male','Male'),('female','Female')],'Gender')
    total = fields.Integer('Total')

    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute('''
            CREATE OR REPLACE VIEW %s AS (
                select (
                row_number() over (order by id))::int as id 
                ,count(*):: int
                ,gender as gender 
                from hr_employee
                where gender in ('male','female')
                group by gender,id
                )''' % (self._table,)
        )

        # self.env.cr.execute('''
        #     CREATE OR REPLACE VIEW %s AS (
        #         select (
        #             row_number() over (order by a))::int as id
        #             ,a.male
        #             ,a.female
        #         from (select (select count(*)::int as name from hr_employee where gender='male' ) as male,
        #         (select count(*)::int as name from hr_employee where gender='female' ) as female
        #         ) as a
        #         )''' % (self._table,)
        # )