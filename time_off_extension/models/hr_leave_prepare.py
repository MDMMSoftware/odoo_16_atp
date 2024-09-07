# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

# Copyright (c) 2005-2006 Axelor SARL. (http://www.axelor.com)

import logging
import pytz

from collections import namedtuple, defaultdict

from datetime import datetime, timedelta, time
from pytz import timezone, UTC
from odoo.tools import date_utils

from odoo import api, Command, fields, models, tools
from odoo.addons.base.models.res_partner import _tz_get
from odoo.addons.resource.models.resource import float_to_time, HOURS_PER_DAY
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tools import float_compare, format_date
from odoo.tools.float_utils import float_round
from odoo.tools.misc import format_date
from odoo.tools.translate import _
from odoo.osv import expression
from dateutil.relativedelta import relativedelta

_logger = logging.getLogger(__name__)

# Used to agglomerate the attendances in order to find the hour_from and hour_to
# See _compute_date_from_to
DummyAttendance = namedtuple('DummyAttendance', 'hour_from, hour_to, dayofweek, day_period, week_type')
DAY_OF_WEEK = [0,1,2,3,4,5,6]
def get_employee_from_context(values, context, user_employee_id):
    employee_ids_list = [value[2] for value in values.get('employee_ids', []) if len(value) == 3 and value[0] == Command.SET]
    employee_ids = employee_ids_list[-1] if employee_ids_list else []
    employee_id_value = employee_ids[0] if employee_ids else False
    return employee_id_value or context.get('default_employee_id', context.get('employee_id', user_employee_id))

class HolidaysType(models.Model):
    _inherit = "hr.leave.type"
    _description = "Time Off Type"

    code = fields.Char('code')

class HolidaysRequestPrepare(models.Model):
    
    _name = "hr.leave.prepare"
    _description = "Time Off Prepare"
    _order = "date_from desc"
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _mail_post_access = 'read'

    active = fields.Boolean(default=True, readonly=True)
    # description
    name = fields.Char('Description', compute='_compute_description', inverse='_inverse_description', search='_search_description', compute_sudo=False)
    private_name = fields.Char('Time Off Description', groups='hr_holidays.group_hr_holidays_user')
    state = fields.Selection([
        ('draft', 'To Submit'),
        ('confirm', 'Waiting For HOD Approve'),
        ('refuse', 'Refused'),
        ('hod_approve', 'HOD Approved'),
        ], string='Status', compute='_compute_state', store=True, tracking=True, copy=False, readonly=False,
        help="The status is set to 'To Submit', when a time off request is created." +
        "\nThe status is 'To Approve', when time off request is confirmed by user." +
        "\nThe status is 'Refused', when time off request is refused by manager." +
        "\nThe status is 'Approved', when time off request is approved by manager.")
    report_note = fields.Text('HR Comments', copy=False, groups="hr_holidays.group_hr_holidays_manager")
    user_id = fields.Many2one('res.users', string='User', related='employee_id.user_id', related_sudo=True, compute_sudo=True, store=True, readonly=True, index=True)
    manager_id = fields.Many2one('hr.employee', compute='_compute_from_employee_id', store=True, readonly=False)
    # leave type configuration
    holiday_status_id = fields.Many2one(
        "hr.leave.type", compute='_compute_from_employee_id', store=True, string="Time Off Type", required=True, readonly=False,
        states={'cancel': [('readonly', True)], 'refuse': [('readonly', True)], 'validate1': [('readonly', True)], 'validate': [('readonly', True)]},
        domain="[('company_id', '=?', employee_company_id), '|', ('requires_allocation', '=', 'no'), ('has_valid_allocation', '=', True)]", tracking=True)
    holiday_allocation_id = fields.Many2one(
        'hr.leave.allocation', compute='_compute_from_holiday_status_id', string="Allocation", store=True, readonly=False)
    color = fields.Integer("Color", related='holiday_status_id.color')
    validation_type = fields.Selection(string='Validation Type', related='holiday_status_id.leave_validation_type', readonly=False)
    # HR data

    employee_id = fields.Many2one(
        'hr.employee', compute='_compute_from_employee_ids', store=True, string='Employee', index=True, readonly=False, ondelete="restrict",
        states={'cancel': [('readonly', True)], 'refuse': [('readonly', True)], 'validate1': [('readonly', True)], 'validate': [('readonly', True)]},
        tracking=True, compute_sudo=False)
    employee_company_id = fields.Many2one(related='employee_id.company_id', readonly=True, store=True)
    active_employee = fields.Boolean(related='employee_id.active', string='Employee Active', readonly=True)
    tz_mismatch = fields.Boolean(compute='_compute_tz_mismatch')
    tz = fields.Selection(_tz_get, compute='_compute_tz')
    department_id = fields.Many2one(
        'hr.department', compute='_compute_department_id', store=True, string='Department', readonly=False,
        states={'cancel': [('readonly', True)], 'refuse': [('readonly', True)], 'validate1': [('readonly', True)], 'validate': [('readonly', True)]})
    notes = fields.Text('Reasons', readonly=True, states={'draft': [('readonly', False)], 'confirm': [('readonly', False)]})
    # duration
    date_from = fields.Datetime(
        'Start Date', compute='_compute_date_from_to', required=False, store=True, readonly=False, index=True, copy=False, tracking=True,
        states={'cancel': [('readonly', True)], 'refuse': [('readonly', True)], 'validate1': [('readonly', True)], 'validate': [('readonly', True)]})
    date_to = fields.Datetime(
        'End Date', compute='_compute_date_from_to', required=False, store=True, readonly=False, copy=False, tracking=True,
        states={'cancel': [('readonly', True)], 'refuse': [('readonly', True)], 'validate1': [('readonly', True)], 'validate': [('readonly', True)]})
    number_of_days = fields.Float(
        'Duration (Days)', compute='_compute_number_of_days', store=True, readonly=False, copy=False, tracking=True,
        help='Number of days of the time off request. Used in the calculation. To manually correct the duration, use this field.')
    number_of_days_display = fields.Float(
        'Duration in days', compute='_compute_number_of_days_display', readonly=True,
        help='Number of days of the time off request according to your working schedule. Used for interface.')
    number_of_hours_display = fields.Float(
        'Duration in hours', compute='_compute_number_of_hours_display', readonly=True,
        help='Number of hours of the time off request according to your working schedule. Used for interface.')
    number_of_hours_text = fields.Char(compute='_compute_number_of_hours_text')
    duration_display = fields.Char('Requested (Days/Hours)', compute='_compute_duration_display', store=True,
        help="Field allowing to see the leave request duration in days or hours depending on the leave_type_request_unit")    # details
    # details
    meeting_id = fields.Many2one('calendar.event', string='Meeting', copy=False)
    parent_id = fields.Many2one('hr.leave', string='Parent', copy=False)
    linked_request_ids = fields.One2many('hr.leave', 'parent_id', string='Linked Requests')
    holiday_type = fields.Selection([
        ('employee', 'By Employee'),
        ('company', 'By Company'),
        ('department', 'By Department'),
        ('category', 'By Employee Tag')],
        string='Allocation Mode', readonly=True, required=True, default='employee',
        states={'draft': [('readonly', False)], 'confirm': [('readonly', False)]},
        help='By Employee: Allocation/Request for individual Employee, By Employee Tag: Allocation/Request for group of employees in category')
    employee_ids = fields.Many2many(
        'hr.employee', compute='_compute_from_holiday_type', store=True, string='Employees', readonly=False, groups="hr_holidays.group_hr_holidays_user",
        states={'cancel': [('readonly', True)], 'refuse': [('readonly', True)], 'validate1': [('readonly', True)], 'validate': [('readonly', True)]})
    multi_employee = fields.Boolean(
        compute='_compute_from_employee_ids', store=True, compute_sudo=False,
        help='Holds whether this allocation concerns more than 1 employee')
    category_id = fields.Many2one(
        'hr.employee.category', compute='_compute_from_holiday_type', store=True, string='Employee Tag',
        states={'draft': [('readonly', False)], 'confirm': [('readonly', False)]}, help='Category of Employee')
    mode_company_id = fields.Many2one(
        'res.company', compute='_compute_from_holiday_type', store=True, string='Company Mode',
        states={'draft': [('readonly', False)], 'confirm': [('readonly', False)]})
    hod_approver_id = fields.Many2one(
        'hr.employee', string='HOD Approval', readonly=True, copy=False,
        help='This area is automatically filled by the user who validate the time off')

    attachment_ids = fields.One2many('ir.attachment', 'res_id', string="Attachments")
    # UX fields
    all_employee_ids = fields.Many2many('hr.employee', compute='_compute_all_employees', compute_sudo=True)
    leave_type_request_unit = fields.Selection(related='holiday_status_id.request_unit', readonly=True)
    leave_type_support_document = fields.Boolean(related="holiday_status_id.support_document")
    # Interface fields used when not using hour-based computation
    request_date_from = fields.Date('Request Start Date')
    request_date_to = fields.Date('Request End Date')
    # Interface fields used when using hour-based computation
    validation_status = fields.Boolean(default=False)
    request_hour_from = fields.Selection([
        ('0', '12:00 AM'), ('0.5', '12:30 AM'),
        ('1', '1:00 AM'), ('1.5', '1:30 AM'),
        ('2', '2:00 AM'), ('2.5', '2:30 AM'),
        ('3', '3:00 AM'), ('3.5', '3:30 AM'),
        ('4', '4:00 AM'), ('4.5', '4:30 AM'),
        ('5', '5:00 AM'), ('5.5', '5:30 AM'),
        ('6', '6:00 AM'), ('6.5', '6:30 AM'),
        ('7', '7:00 AM'), ('7.5', '7:30 AM'),
        ('8', '8:00 AM'), ('8.5', '8:30 AM'),
        ('9', '9:00 AM'), ('9.5', '9:30 AM'),
        ('10', '10:00 AM'), ('10.5', '10:30 AM'),
        ('11', '11:00 AM'), ('11.5', '11:30 AM'),
        ('12', '12:00 PM'), ('12.5', '12:30 PM'),
        ('13', '1:00 PM'), ('13.5', '1:30 PM'),
        ('14', '2:00 PM'), ('14.5', '2:30 PM'),
        ('15', '3:00 PM'), ('15.5', '3:30 PM'),
        ('16', '4:00 PM'), ('16.5', '4:30 PM'),
        ('17', '5:00 PM'), ('17.5', '5:30 PM'),
        ('18', '6:00 PM'), ('18.5', '6:30 PM'),
        ('19', '7:00 PM'), ('19.5', '7:30 PM'),
        ('20', '8:00 PM'), ('20.5', '8:30 PM'),
        ('21', '9:00 PM'), ('21.5', '9:30 PM'),
        ('22', '10:00 PM'), ('22.5', '10:30 PM'),
        ('23', '11:00 PM'), ('23.5', '11:30 PM')], string='Hour from')
    request_hour_to = fields.Selection([
        ('0', '12:00 AM'), ('0.5', '12:30 AM'),
        ('1', '1:00 AM'), ('1.5', '1:30 AM'),
        ('2', '2:00 AM'), ('2.5', '2:30 AM'),
        ('3', '3:00 AM'), ('3.5', '3:30 AM'),
        ('4', '4:00 AM'), ('4.5', '4:30 AM'),
        ('5', '5:00 AM'), ('5.5', '5:30 AM'),
        ('6', '6:00 AM'), ('6.5', '6:30 AM'),
        ('7', '7:00 AM'), ('7.5', '7:30 AM'),
        ('8', '8:00 AM'), ('8.5', '8:30 AM'),
        ('9', '9:00 AM'), ('9.5', '9:30 AM'),
        ('10', '10:00 AM'), ('10.5', '10:30 AM'),
        ('11', '11:00 AM'), ('11.5', '11:30 AM'),
        ('12', '12:00 PM'), ('12.5', '12:30 PM'),
        ('13', '1:00 PM'), ('13.5', '1:30 PM'),
        ('14', '2:00 PM'), ('14.5', '2:30 PM'),
        ('15', '3:00 PM'), ('15.5', '3:30 PM'),
        ('16', '4:00 PM'), ('16.5', '4:30 PM'),
        ('17', '5:00 PM'), ('17.5', '5:30 PM'),
        ('18', '6:00 PM'), ('18.5', '6:30 PM'),
        ('19', '7:00 PM'), ('19.5', '7:30 PM'),
        ('20', '8:00 PM'), ('20.5', '8:30 PM'),
        ('21', '9:00 PM'), ('21.5', '9:30 PM'),
        ('22', '10:00 PM'), ('22.5', '10:30 PM'),
        ('23', '11:00 PM'), ('23.5', '11:30 PM')], string='Hour to')
    # used only when the leave is taken in half days
    request_date_from_period = fields.Selection([
        ('am', 'Morning'), ('pm', 'Afternoon')],
        string="Date Period Start", default='am')
    # request type
    request_unit_half = fields.Boolean('Half Day', compute='_compute_request_unit_half', store=True, readonly=False)
    request_unit_hours = fields.Boolean('Custom Hours', compute='_compute_request_unit_hours', store=True, readonly=False)
    time_off_ids = fields.Many2many(
        'hr.leave','time_off_prepare_hr_leave_rel','prepare_id','time_off_ids',
        string='Time Offs', readyonly=True, ondelete='cascade',copy=False,
        check_company=True
    )
    done_no_of_days = fields.Float('Done Duration', default=0, readonly=True, copy=False)
    upcoming_request_date = fields.Date('Upcoming Request Date', readonly=True)
    hr_approval_state = fields.Selection([('pending','Pending'),('approve','Approved')],default='pending', string="HR Status")
    duty_cover_by = fields.Many2one('hr.employee')
    relation_of_deceased = fields.Selection([
        ('father','Father'),
        ('Mother','mother'),
        ('other','Other'),
    ],string="Relation Of Deceased")
    holiday_status_code = fields.Char(related = 'holiday_status_id.code' )
    timeoff_prepare_attachment_ids = fields.One2many('hr.leave.prepare.attachment','prepare_id', string='Attachments', readyonly=True, ondelete='cascade',)
    
    _sql_constraints = [
        ('type_value',
         "CHECK((holiday_type='employee' AND (employee_id IS NOT NULL OR multi_employee IS TRUE)) or "
         "(holiday_type='company' AND mode_company_id IS NOT NULL) or "
         "(holiday_type='category' AND category_id IS NOT NULL) or "
         "(holiday_type='department' AND department_id IS NOT NULL) )",
         "The employee, department, company or employee category of this request is missing. Please make sure that your user login is linked to an employee."),
        ('date_check2', "CHECK ((date_from <= date_to))", "The start date must be anterior to the end date."),
        ('duration_check', "CHECK ( number_of_days >= 0 )", "If you want to change the number of days you should use the 'period' mode"),
    ]

    def _auto_init(self):
        res = super(HolidaysRequestPrepare, self)._auto_init()
        tools.create_index(self._cr, 'hr_leave_date_to_date_from_index',
                           self._table, ['date_to', 'date_from'])
        return res

    @api.depends('employee_id', 'employee_ids')
    def _compute_all_employees(self):
        for leave in self:
            leave.all_employee_ids = leave.employee_id | leave.employee_ids

    @api.constrains('holiday_status_id', 'number_of_days')
    def _check_allocation_duration(self):
        # Deprecated as part of https://github.com/odoo/odoo/pull/96545
        # TODO: remove in master
        return

    @api.depends_context('uid')
    def _compute_description(self):
        self.check_access_rights('read')
        self.check_access_rule('read')

        is_officer = self.user_has_groups('hr_holidays.group_hr_holidays_user')

        for leave in self:
            if is_officer or leave.user_id == self.env.user or leave.employee_id.leave_manager_id == self.env.user:
                leave.name = leave.sudo().private_name
            else:
                leave.name = '*****'

    def _get_non_working_days(self,employee):
        working_days = [int(i) for i in list(set(self.env['resource.calendar.attendance'].search([('calendar_id','=',employee.resource_calendar_id.id)]).mapped('dayofweek')))
        ]
        diff_list1 = set(DAY_OF_WEEK) - set(working_days)
        diff_list2 = set(working_days) - set(DAY_OF_WEEK)
        return sorted(list(diff_list1.union(diff_list2)))
    
    def get_non_working_days_v2(self,employee, date_from, date_to):
        """
        Get non-working days between two dates.
        :param date_from: Start date
        :param date_to: End date
        :return: List of non-working dates
        """
        non_working_days = []
        calendar = employee.resource_calendar_id or self.env['resource.calendar'].search([], limit=1)  # Adjust to get the correct calendar

        if not calendar:
            return non_working_days
        
        current_date = fields.Date.from_string(date_from)
        end_date = fields.Date.from_string(date_to)
        if current_date and end_date:
            while current_date <= end_date:
                if not self._is_working_day(calendar, current_date):
                    non_working_days.append(current_date)
                current_date += timedelta(days=1)
        
        return non_working_days

    def _is_working_day(self, calendar, date):
        weekday = date.weekday()
        is_working = any(attendance.dayofweek == str(weekday) for attendance in calendar.attendance_ids)
        is_public_holiday = self.env['resource.calendar.leaves'].search_count([
            ('date_from', '<=', date),
            ('date_to', '>=', date),
            ('calendar_id','=',calendar.id),
            ('holiday_id','=',False)
 
        ]) > 0        
        return is_working and not is_public_holiday
    def _inverse_description(self):
        is_officer = self.user_has_groups('hr_holidays.group_hr_holidays_user')

        for leave in self:
            if is_officer or leave.user_id == self.env.user or leave.employee_id.leave_manager_id == self.env.user:
                leave.sudo().private_name = leave.name

    def _search_description(self, operator, value):
        is_officer = self.user_has_groups('hr_holidays.group_hr_holidays_user')
        domain = [('private_name', operator, value)]

        if not is_officer:
            domain = expression.AND([domain, [('user_id', '=', self.env.user.id)]])

        leaves = self.search(domain)
        return [('id', 'in', leaves.ids)]

    @api.depends('holiday_status_id')
    def _compute_state(self):
        for leave in self:
            leave.state = 'draft' if leave.validation_type != 'no_validation' else 'confirm'

    @api.depends('holiday_status_id.requires_allocation', 'validation_type', 'employee_id', 'date_from', 'date_to')
    def _compute_from_holiday_status_id(self):
        self.holiday_allocation_id = False
        # today = fields.Date.from_string(fields.Datetime.now().date())
        
        # if self.holiday_status_id.requires_allocation == 'yes':
        #     allocation_id = self.env['hr.leave.allocation'].search([
        #                             ('employee_id','=',self.employee_id.id),
        #                             ('holiday_status_id','=',self.holiday_status_id.id),
        #                             ('date_from','>=',f"{today.year}-01-01"),
        #                             ('date_from','<=',f"{today.year}-12-31"),
        #                             ('date_to','>=',f"{today.year}-01-01"),
        #                             ('date_to','<=',f"{today.year}-12-31"),
        #                         ], order="create_date desc", limit = 1)
        #     self.holiday_allocation_id = allocation_id

    @api.onchange('employee_id')
    def onchange_duty_cover_employees(self):
        for res in self:
            return {'domain': {'duty_cover_by': [('active','=',True),('division_id','=',res.employee_id.division_id.id),(('id','!=',res.employee_id.id))]}}

    @api.onchange('request_unit_half','request_date_to','request_date_from')
    def _onchange_request_date_from(self):
        if self.request_unit_half:
            self.request_date_to = self.request_date_from

    def get_date_from_dayofweek_today(self,dayofweek):
        if not (0 <= dayofweek <= 6):
            raise ValueError("dayofweek must be between 0 (Monday) and 6 (Sunday)")

        today = datetime.today()

        start_of_week = today - timedelta(days=today.weekday())

        target_date = start_of_week + timedelta(days=dayofweek)

        return target_date.date()

    def get_date_from_dayofweek(self,specific_date, dayofweek):
        if not (0 <= dayofweek <= 6):
            raise ValueError("dayofweek must be between 0 (Monday) and 6 (Sunday)")

        # specific_date = datetime.strptime(specific_date, "%Y-%m-%d")

        start_of_week = specific_date - timedelta(days=specific_date.weekday())

        target_date = start_of_week + timedelta(days=dayofweek)

        return target_date
    @api.depends('request_date_from_period', 'request_hour_from', 'request_hour_to', 'request_date_from', 'request_date_to',
                 'request_unit_half', 'request_unit_hours', 'employee_id')
    def _compute_date_from_to(self):
        for holiday in self:
            if holiday.request_date_from and holiday.request_date_to and holiday.request_date_from > holiday.request_date_to:
                holiday.request_date_to = holiday.request_date_from
            if not holiday.request_date_from:
                holiday.date_from = False
            elif not holiday.request_unit_half and not holiday.request_unit_hours and not holiday.request_date_to:
                holiday.date_to = False
            else:
                # if holiday.request_unit_half or holiday.request_unit_hours:
                #     holiday.request_date_to = holiday.request_date_from
                attendance_from, attendance_to = holiday._get_attendances(holiday.employee_id, holiday.request_date_from, holiday.request_date_to)
                
                compensated_request_date_from = holiday.request_date_from
                compensated_request_date_to = holiday.request_date_to

                if holiday.request_unit_half:
                    if holiday.request_date_from_period == 'am':
                        hour_from = attendance_from.hour_from
                        hour_to = attendance_from.hour_to
                    else:
                        hour_from = attendance_to.hour_from
                        hour_to = attendance_to.hour_to
                elif holiday.request_unit_hours:
                    hour_from = holiday.request_hour_from
                    hour_to = holiday.request_hour_to
                else:
                    hour_from = attendance_from.hour_from
                    hour_to = attendance_to.hour_to

                holiday.date_from = self._get_start_or_end_from_attendance(hour_from, compensated_request_date_from, holiday.employee_id or holiday)
                holiday.date_to = self._get_start_or_end_from_attendance(hour_to, compensated_request_date_to, holiday.employee_id or holiday)
                holiday.upcoming_request_date = holiday.date_from
                
    @api.depends('holiday_status_id', 'request_unit_hours')
    def _compute_request_unit_half(self):
        for holiday in self:
            if holiday.holiday_status_id or holiday.request_unit_hours:
                holiday.request_unit_half = False

    @api.depends('holiday_status_id', 'request_unit_half')
    def _compute_request_unit_hours(self):
        for holiday in self:
            if holiday.holiday_status_id or holiday.request_unit_half:
                holiday.request_unit_hours = False

    @api.depends('employee_ids')
    def _compute_from_employee_ids(self):
        for holiday in self:
            if len(holiday.employee_ids) == 1:
                holiday.employee_id = holiday.employee_ids[0]._origin
            else:
                holiday.employee_id = False
            holiday.multi_employee = (len(holiday.employee_ids) > 1)

    @api.depends('holiday_type')
    def _compute_from_holiday_type(self):
        allocation_from_domain = self.env['hr.leave.allocation']
        if (self._context.get('active_model') == 'hr.leave.allocation' and
           self._context.get('active_id')):
            allocation_from_domain = allocation_from_domain.browse(self._context['active_id'])
        for holiday in self:
            if holiday.holiday_type == 'employee':
                if not holiday.employee_ids:
                    if allocation_from_domain:
                        holiday.employee_ids = allocation_from_domain.employee_id
                        holiday.holiday_status_id = allocation_from_domain.holiday_status_id
                    else:
                        # This handles the case where a request is made with only the employee_id
                        # but does not need to be recomputed on employee_id changes
                        holiday.employee_ids = holiday.employee_id or self.env.user.employee_id
                holiday.mode_company_id = False
                holiday.category_id = False
            elif holiday.holiday_type == 'company':
                holiday.employee_ids = False
                if not holiday.mode_company_id:
                    holiday.mode_company_id = self.env.company.id
                holiday.category_id = False
            elif holiday.holiday_type == 'department':
                holiday.employee_ids = False
                holiday.mode_company_id = False
                holiday.category_id = False
            elif holiday.holiday_type == 'category':
                holiday.employee_ids = False
                holiday.mode_company_id = False
            else:
                holiday.employee_ids = self.env.context.get('default_employee_id') or holiday.employee_id or self.env.user.employee_id

    @api.depends('employee_id', 'employee_ids')
    def _compute_from_employee_id(self):
        for holiday in self:
            holiday.manager_id = holiday.employee_id.parent_id.id
            if holiday.holiday_status_id.requires_allocation == 'no':
                continue
            if not holiday.employee_id or holiday.employee_ids:
                holiday.holiday_status_id = False
            elif holiday.employee_id.user_id != self.env.user and holiday._origin.employee_id != holiday.employee_id:
                if holiday.employee_id and not holiday.holiday_status_id.with_context(employee_id=holiday.employee_id.id).has_valid_allocation:
                    holiday.holiday_status_id = False

    @api.depends('employee_id', 'holiday_type')
    def _compute_department_id(self):
        for holiday in self:
            if holiday.employee_id:
                holiday.department_id = holiday.employee_id.department_id
            elif holiday.holiday_type == 'department':
                if not holiday.department_id:
                    holiday.department_id = self.env.user.employee_id.department_id
            else:
                holiday.department_id = False
    
    def are_dates_consecutive(self,dates):        
        dates.sort()
        for i in range(1, len(dates)):
            if dates[i] != dates[i-1] + timedelta(days=1):
                return False
        return True

    def get_attendance_hours(self,date):
        # Get the current employee
        employee = self.env.user.employee_id
        if not employee:
            return None, None
        
        # Get the resource calendar of the employee
        resource_calendar = employee.resource_calendar_id
        if not resource_calendar:
            return None, None

        # Get today's date
        today = datetime.today().date()

        # Find the attendance hours for today
        attendance_hours = resource_calendar.attendance_ids.filtered(lambda a: int(a.dayofweek) == date.weekday())

        if not attendance_hours:
            return None, None
        return attendance_hours

    @api.depends('date_from', 'date_to', 'employee_id')
    def _compute_number_of_days(self):
        for holiday in self:
            # if holiday.number_of_days == 0:
            if holiday.date_from and holiday.date_to:
                attendance_from, attendance_to = holiday._get_attendances(holiday.employee_id, holiday.request_date_from, holiday.request_date_to)

                hour_from,hour_to = 0,0
                if holiday.request_unit_half:
                    if holiday.request_date_from_period == 'am':
                        hour_from = attendance_from.hour_from
                        hour_to = attendance_from.hour_to
                    else:
                        hour_from = attendance_to.hour_from
                        hour_to = attendance_to.hour_to
                elif holiday.request_unit_hours:
                    hour_from = holiday.request_hour_from
                    hour_to = holiday.request_hour_to
                else:
                    hour_from = attendance_from.hour_from
                    hour_to = attendance_to.hour_to
                holiday.number_of_days = holiday._get_number_of_days(holiday.date_from, holiday.date_to, holiday.employee_id.id)['days']
                addional_day = 0

                if holiday.date_from and holiday.date_to:
                    # New Approach
                    non_working_days = holiday.get_non_working_days_v2(holiday.employee_id,holiday.request_date_from, holiday.request_date_to)
                    non_working_days.sort()
                    request_days = [holiday.date_from+timedelta(days=x) for x in range(((holiday.date_to+timedelta(days=1) )-holiday.date_from ).days)]
                    temp_to = holiday.request_date_to
                    temp_from = holiday.request_date_from

                    while temp_to > temp_from:
                        if temp_to in non_working_days:
                                non_working_days.remove(temp_to)
                                temp_to = temp_to - relativedelta(days=1)
                        else:
                            break
                        
                    # temp_to = holiday.date_to.date()
                    # temp_from = holiday.date_from.date()

                    while temp_from < temp_to:
                        if temp_from in non_working_days:
                            non_working_days.remove(temp_from)
                            temp_from = temp_from + relativedelta(days=1)
                        else:
                            break
                    # dates_between = self.get_dates_between(temp_from,temp_to)
                    for non in non_working_days:
                        if holiday.date_to.date() != non and holiday.date_from.date() != non:
                            addional_day +=1
                    
                    # Before Leave Day
                    before_leave_day = self.env['hr.leave'].search([
                                    ('date_to','<',holiday.date_from.date()),
                                    ('employee_id','=',holiday.employee_id.id),
                                    ('state','not in',('refuse',))
                                ],order='date_to desc', limit=1)
                    if before_leave_day:
                        date_range_before = holiday.get_non_working_days_v2(holiday.employee_id,before_leave_day.date_to, temp_from)
                        date_range_before.extend([holiday.date_from.date()+timedelta(days=x) for x in range(((holiday.date_to.date()+timedelta(days=1) )-holiday.date_from.date()).days)]  )

                        date_range_before.append(before_leave_day.date_to.date())
                        date_range_before = list(set(date_range_before))
                        date_range_before.sort()
                        if holiday.are_dates_consecutive(date_range_before):
                            if temp_from != date_range_before[1]:
                                addional_day += len(holiday.get_non_working_days_v2(holiday.employee_id,before_leave_day.date_to, temp_from))
                                
                                # hour_from = 1.5
                                # get_attendance = holiday.get_attendance_hours(date_range_before[1])
                                # if get_attendance[0]:
                                #     hour_from = get_attendance[0].hour_from
                                
                                holiday.date_from = holiday._get_start_or_end_from_attendance(hour_from, date_range_before[1], holiday.employee_id or holiday)

                                # holiday.date_from = datetime(date_range_before[1].year,date_range_before[1].month,date_range_before[1].day,holiday.date_to.hour,holiday.date_to.minute,holiday.date_to.second)
                                holiday.request_date_from = date_range_before[1]
                        else:
                            # hour_from = 1.5
                            # get_attendance = holiday.get_attendance_hours(temp_from)
                            # if get_attendance[0]:
                            #     hour_from = get_attendance[0].hour_from
                            holiday.date_from = holiday._get_start_or_end_from_attendance(hour_from, temp_from, holiday.employee_id or holiday)
                            holiday.request_date_from = temp_from

                    else:
                        # hour_from = 1.5
                        # get_attendance = holiday.get_attendance_hours(temp_from)
                        # if get_attendance[0]:
                        #     hour_from = get_attendance[0].hour_from
                        holiday.date_from = self._get_start_or_end_from_attendance(hour_from, temp_from, holiday.employee_id or holiday)
                        holiday.request_date_from = temp_from
                    # After Leave Day
                    after_leave_day = self.env['hr.leave'].search([
                                    ('date_from','>',holiday.date_to.date()),
                                    ('employee_id','=',holiday.employee_id.id),
                                    ('state','not in',('refuse',))
                                ],order='date_to asc', limit=1)
                    if after_leave_day:
                        date_range_after = holiday.get_non_working_days_v2(holiday.employee_id,temp_to, after_leave_day.date_from)

                        date_range_after.extend([holiday.date_from.date()+timedelta(days=x) 
                        for x in range(((holiday.date_to.date()+timedelta(days=1) )-holiday.date_from.date()).days)]
                        )
                        date_range_after.append(after_leave_day.date_from.date())
                        date_range_after = list(set(date_range_after))
                        date_range_after.sort()
                        if holiday.are_dates_consecutive(date_range_after):
                            addional_day += len(holiday.get_non_working_days_v2(holiday.employee_id,temp_to, after_leave_day.date_from))
                            if holiday.request_unit_half:
                                holiday.request_unit_half = False
                                addional_day += 0.5
                                hour_from = attendance_to.hour_to

                            # hour_to = 10.0
                            # get_attendance = holiday.get_attendance_hours(date_range_after[-2])
                            # if get_attendance[1]:
                            #     hour_to = get_attendance[1].hour_to

                            holiday.date_to = holiday._get_start_or_end_from_attendance(hour_to, date_range_after[-2], holiday.employee_id or holiday)
                            
                            holiday.request_date_to = date_range_after[-2]
                        else:
                            # hour_to = 10.0
                            # get_attendance = holiday.get_attendance_hours(temp_to)
                            # if get_attendance[1]:
                            #     hour_to = get_attendance[1].hour_to

                            holiday.date_to = holiday._get_start_or_end_from_attendance(hour_to, temp_to, holiday.employee_id or holiday)
                            
                            holiday.request_date_to = temp_to

                    else:
                        # hour_to = 10.0
                        # get_attendance = holiday.get_attendance_hours(temp_to)
                        # if get_attendance[1]:
                        #     hour_to = get_attendance[1].hour_to

                        holiday.date_to = holiday._get_start_or_end_from_attendance(hour_to, temp_to, holiday.employee_id or holiday)
                        
                        holiday.request_date_to = temp_to

                    ################
                if len(holiday.employee_ids) <= 1 and holiday.number_of_days > 0:
                    holiday.number_of_days += addional_day

            else:
                holiday.number_of_days = 0


    @api.depends('tz')
    @api.depends_context('uid')
    def _compute_tz_mismatch(self):
        for leave in self:
            leave.tz_mismatch = leave.tz != self.env.user.tz

    @api.depends('employee_id', 'holiday_type', 'department_id.company_id.resource_calendar_id.tz', 'mode_company_id.resource_calendar_id.tz')
    def _compute_tz(self):
        for leave in self:
            tz = False
            if leave.holiday_type == 'employee':
                tz = leave.employee_id.tz
            elif leave.holiday_type == 'department':
                tz = leave.department_id.company_id.resource_calendar_id.tz
            elif leave.holiday_type == 'company':
                tz = leave.mode_company_id.resource_calendar_id.tz
            leave.tz = tz or self.env.company.resource_calendar_id.tz or self.env.user.tz or 'UTC'

    @api.depends('number_of_days')
    def _compute_number_of_days_display(self):
        for holiday in self:
            holiday.number_of_days_display = holiday.number_of_days

    def _get_calendar(self):
        self.ensure_one()
        return self.employee_id.resource_calendar_id or self.env.company.resource_calendar_id

    @api.depends('number_of_days')
    def _compute_number_of_hours_display(self):
        for holiday in self:
            calendar = holiday._get_calendar()
            if holiday.date_from and holiday.date_to:
                # Take attendances into account, in case the leave validated
                # Otherwise, this will result into number_of_hours = 0
                # and number_of_hours_display = 0 or (#day * calendar.hours_per_day),
                # which could be wrong if the employee doesn't work the same number
                # hours each day
                if holiday.state == 'validate':
                    start_dt = holiday.date_from
                    end_dt = holiday.date_to
                    if not start_dt.tzinfo:
                        start_dt = start_dt.replace(tzinfo=UTC)
                    if not end_dt.tzinfo:
                        end_dt = end_dt.replace(tzinfo=UTC)
                    resource = holiday.employee_id.resource_id
                    intervals = calendar._attendance_intervals_batch(start_dt, end_dt, resource)[resource.id] \
                                - calendar._leave_intervals_batch(start_dt, end_dt, None)[False]  # Substract Global Leaves
                    number_of_hours = sum((stop - start).total_seconds() / 3600 for start, stop, dummy in intervals)
                else:
                    number_of_hours = holiday._get_number_of_days(holiday.date_from, holiday.date_to, holiday.employee_id.id)['hours']
                holiday.number_of_hours_display = number_of_hours or (holiday.number_of_days * (calendar.hours_per_day or HOURS_PER_DAY))
            else:
                holiday.number_of_hours_display = 0

    @api.depends('number_of_hours_display', 'number_of_days_display')
    def _compute_duration_display(self):
        for leave in self:
            leave.duration_display = '%g %s' % (
                (float_round(leave.number_of_hours_display, precision_digits=2)
                if leave.leave_type_request_unit == 'hour'
                else float_round(leave.number_of_days_display, precision_digits=2)),
                _('hours') if leave.leave_type_request_unit == 'hour' else _('days'))

    @api.depends('number_of_hours_display')
    def _compute_number_of_hours_text(self):
        # YTI Note: All this because a readonly field takes all the width on edit mode...
        for leave in self:
            leave.number_of_hours_text = '%s%g %s%s' % (
                '' if leave.request_unit_half or leave.request_unit_hours else '(',
                float_round(leave.number_of_hours_display, precision_digits=2),
                _('Hours'),
                '' if leave.request_unit_half or leave.request_unit_hours else ')')



    @api.constrains('date_from', 'date_to', 'employee_id')
    def _check_date(self):
        if self.env.context.get('leave_skip_date_check', False):
            return

        all_employees = self.all_employee_ids
        all_leaves = self.env['hr.leave'].search([
            ('date_from', '<', max(self.mapped('date_to'))),
            ('date_to', '>', min(self.mapped('date_from'))),
            ('employee_id', 'in', all_employees.ids),
            ('id', 'not in', self.ids),
            ('state', 'not in', ['cancel', 'refuse']),
        ])
        for holiday in self:
            domain = [
                ('date_from', '<', holiday.date_to),
                ('date_to', '>', holiday.date_from),
                ('id', '!=', holiday.id),
                ('state', 'not in', ['cancel', 'refuse']),
            ]

            employee_ids = (holiday.employee_id | holiday.employee_ids).ids
            search_domain = domain + [('employee_id', 'in', employee_ids)]
            conflicting_holidays = all_leaves.filtered_domain(search_domain)

            if conflicting_holidays:
                conflicting_holidays_list = []
                # Do not display the name of the employee if the conflicting holidays have an employee_id.user_id equivalent to the user id
                holidays_only_have_uid = bool(holiday.employee_id)
                holiday_states = dict(conflicting_holidays.fields_get(allfields=['state'])['state']['selection'])
                for conflicting_holiday in conflicting_holidays:
                    conflicting_holiday_data = {}
                    conflicting_holiday_data['employee_name'] = conflicting_holiday.employee_id.name
                    conflicting_holiday_data['date_from'] = format_date(self.env, min(conflicting_holiday.mapped('date_from')))
                    conflicting_holiday_data['date_to'] = format_date(self.env, min(conflicting_holiday.mapped('date_to')))
                    conflicting_holiday_data['state'] = holiday_states[conflicting_holiday.state]
                    if conflicting_holiday.employee_id.user_id.id != self.env.uid:
                        holidays_only_have_uid = False
                    if conflicting_holiday_data not in conflicting_holidays_list:
                        conflicting_holidays_list.append(conflicting_holiday_data)
                if not conflicting_holidays_list:
                    return
                conflicting_holidays_strings = []
                if holidays_only_have_uid:
                    for conflicting_holiday_data in conflicting_holidays_list:
                        conflicting_holidays_string = _('From %(date_from)s To %(date_to)s - %(state)s',
                                                        date_from=conflicting_holiday_data['date_from'],
                                                        date_to=conflicting_holiday_data['date_to'],
                                                        state=conflicting_holiday_data['state'])
                        conflicting_holidays_strings.append(conflicting_holidays_string)
                    raise ValidationError(_('You can not set two time off that overlap on the same day.\nExisting time off:\n%s') %
                                          ('\n'.join(conflicting_holidays_strings)))
                for conflicting_holiday_data in conflicting_holidays_list:
                    conflicting_holidays_string = _('%(employee_name)s - From %(date_from)s To %(date_to)s - %(state)s',
                                                    employee_name=conflicting_holiday_data['employee_name'],
                                                    date_from=conflicting_holiday_data['date_from'],
                                                    date_to=conflicting_holiday_data['date_to'],
                                                    state=conflicting_holiday_data['state'])
                    conflicting_holidays_strings.append(conflicting_holidays_string)
                conflicting_employees = set(employee_ids) - set(conflicting_holidays.employee_id.ids)
                # Only one employee has a conflicting holiday
                if len(conflicting_employees) == len(employee_ids) - 1:
                    raise ValidationError(_('You can not set two time off that overlap on the same day for the same employee.\nExisting time off:\n%s') %
                                          ('\n'.join(conflicting_holidays_strings)))
                raise ValidationError(_('You can not set two time off that overlap on the same day for the same employees.\nExisting time off:\n%s') %
                                      ('\n'.join(conflicting_holidays_strings)))

    @api.constrains('state', 'number_of_days', 'holiday_status_id')
    def _check_holidays(self):
        for holiday in self:
            holiday_status = self.env['hr.leave.type'].with_context(employee_id=holiday.employee_id.id).search([('id','=',holiday.holiday_status_id.id)])

            if holiday.holiday_status_id.requires_allocation == 'yes' and holiday_status.remaining_leaves < holiday.number_of_days:
                raise ValidationError(_('The number of remaining time off is not sufficient for this time off type.\n'
                                                            'Please also check the time off waiting for validation.'))

            if holiday.holiday_status_id.code == 'BL':
                bl_conflict_status = False
                if holiday.relation_of_deceased == 'father':
                    check_exist = self.env['hr.leave'].search([('employee_id','=',holiday.employee_id.id),('holiday_status_id','=',holiday.holiday_status_id.id),('relation_of_deceased','=','father'),('state','=','validate')], limit=1)
                    if check_exist or (holiday.employee_id.father_dop and holiday.employee_id.father_dop < holiday.employee_id.trial_date_start):
                        bl_conflict_status = True

                elif holiday.relation_of_deceased == 'mother':
                    check_exist = self.env['hr.leave'].search([('employee_id','=',holiday.employee_id.id),('holiday_status_id','=',holiday.holiday_status_id.id),('relation_of_deceased','=','mother'),('state','=','validate')], limit=1)
                    if check_exist or (holiday.employee_id.mother_dop and holiday.employee_id.mother_dop < holiday.employee_id.trial_date_start):
                        bl_conflict_status = True

                if bl_conflict_status:
                    raise ValidationError(_('You can not take the Bereavement Leave.\n' 
                                            'There may be conflict or misunderstanding with your private information.\n'
                                            'Please contect your HR.'))
                

    # @api.constrains('state', 'number_of_days', 'holiday_status_id')
    # def _check_holidays(self):
    #     for holiday in self:
    #         mapped_days = self.holiday_status_id.get_employees_days((holiday.employee_id | holiday.sudo().employee_ids).ids, holiday.date_from.date())
    #         if holiday.holiday_type != 'employee'\
    #                 or not holiday.employee_id and not holiday.sudo().employee_ids\
    #                 or holiday.holiday_status_id.requires_allocation == 'no':
    #             continue
    #         if holiday.employee_id:
    #             leave_days = mapped_days[holiday.employee_id.id][holiday.holiday_status_id.id]
    #             if float_compare(leave_days['remaining_leaves'], 0, precision_digits=2) == -1\
    #                     or float_compare(leave_days['virtual_remaining_leaves'], 0, precision_digits=2) == -1:
    #                 raise ValidationError(_('The number of remaining time off is not sufficient for this time off type.\n'
    #                                         'Please also check the time off waiting for validation.'))
    #         else:
    #             unallocated_employees = []
    #             for employee in holiday.sudo().employee_ids:
    #                 leave_days = mapped_days[employee.id][holiday.holiday_status_id.id]
    #                 if float_compare(leave_days['remaining_leaves'], holiday.number_of_days, precision_digits=2) == -1\
    #                         or float_compare(leave_days['virtual_remaining_leaves'], holiday.number_of_days, precision_digits=2) == -1:
    #                     unallocated_employees.append(employee.name)
    #             if unallocated_employees:
    #                 raise ValidationError(_('The number of remaining time off is not sufficient for this time off type.\n'
    #                                         'Please also check the time off waiting for validation.')
    #                                     + _('\nThe employees that lack allocation days are:\n%s',
    #                                         (', '.join(unallocated_employees))))

    @api.constrains('date_from', 'date_to', 'employee_id')
    def _check_date_state(self):
        if self.env.context.get('leave_skip_state_check'):
            return
        for holiday in self:
            if holiday.state in ['cancel', 'refuse', 'validate1', 'validate']:
                raise ValidationError(_("This modification is not allowed in the current state."))

    def _get_number_of_days_batch(self, date_from, date_to, employee_ids):
        """ Returns a float equals to the timedelta between two dates given as string."""
        employee = self.env['hr.employee'].browse(employee_ids)
        # We force the company in the domain as we are more than likely in a compute_sudo
        domain = [('time_type', '=', 'leave'),
                  ('company_id', 'in', self.env.company.ids + self.env.context.get('allowed_company_ids', []))]

        result = employee._get_work_days_data_batch(date_from, date_to, domain=domain)
        for employee_id in result:
            if self.request_unit_half and result[employee_id]['hours'] > 0:
                result[employee_id]['days'] = 0.5
        return result

    def _get_number_of_days(self, date_from, date_to, employee_id):
        """ Returns a float equals to the timedelta between two dates given as string."""
        if employee_id:
            return self._get_number_of_days_batch(date_from, date_to, employee_id)[employee_id]

        today_hours = self.env.company.resource_calendar_id.get_work_hours_count(
            datetime.combine(date_from.date(), time.min),
            datetime.combine(date_from.date(), time.max),
            False)

        hours = self.env.company.resource_calendar_id.get_work_hours_count(date_from, date_to)
        days = hours / (today_hours or HOURS_PER_DAY) if not self.request_unit_half else 0.5
        return {'days': days, 'hours': hours}

    def _adjust_date_based_on_tz(self, leave_date, hour):
        """ request_date_{from,to} are local to the user's tz but hour_{from,to} are in UTC.

        In some cases they are combined (assuming they are in the same tz) as a datetime. When
        that happens it's possible we need to adjust one of the dates. This function adjust the
        date, so that it can be passed to datetime().

        E.g. a leave in America/Los_Angeles for one day:
        - request_date_from: 1st of Jan
        - request_date_to:   1st of Jan
        - hour_from:         15:00 (7:00 local)
        - hour_to:           03:00 (19:00 local) <-- this happens on the 2nd of Jan in UTC
        """
        user_tz = timezone(self.env.user.tz if self.env.user.tz else 'UTC')
        request_date_to_utc = UTC.localize(datetime.combine(leave_date, hour)).astimezone(user_tz).replace(tzinfo=None)
        return request_date_to_utc.date()

    ####################################################
    # ORM Overrides methods
    ####################################################

    @api.depends('employee_id', 'holiday_status_id')
    def _compute_display_name(self):
        super()._compute_display_name()

    def onchange(self, values, field_name, field_onchange):
        # Try to force the leave_type name_get when creating new records
        # This is called right after pressing create and returns the name_get for
        # most fields in the view.
        if field_onchange.get('employee_id') and 'employee_id' not in self._context and values:
            employee_id = get_employee_from_context(values, self._context, self.env.user.employee_id.id)
            self = self.with_context(employee_id=employee_id)
        return super().onchange(values, field_name, field_onchange)

    def name_get(self):
        res = []
        for leave in self:
            user_tz = timezone(leave.tz)
            date_from_utc = leave.date_from and leave.date_from.astimezone(user_tz).date()
            date_to_utc = leave.date_to and leave.date_to.astimezone(user_tz).date()
            if self.env.context.get('short_name'):
                if leave.leave_type_request_unit == 'hour':
                    res.append((leave.id, _("%s : %.2f hours") % (leave.name or leave.holiday_status_id.name, leave.number_of_hours_display)))
                else:
                    res.append((leave.id, _("%s : %.2f days") % (leave.name or leave.holiday_status_id.name, leave.number_of_days)))
            else:
                if leave.holiday_type == 'company':
                    target = leave.mode_company_id.name
                elif leave.holiday_type == 'department':
                    target = leave.department_id.name
                elif leave.holiday_type == 'category':
                    target = leave.category_id.name
                elif leave.employee_id:
                    target = leave.employee_id.name
                else:
                    target = ', '.join(leave.employee_ids.mapped('name'))
                display_date = format_date(self.env, date_from_utc) or ""
                if leave.leave_type_request_unit == 'hour':
                    if self.env.context.get('hide_employee_name') and 'employee_id' in self.env.context.get('group_by', []):
                        res.append((
                            leave.id,
                            _("%(person)s on %(leave_type)s: %(duration).2f hours on %(date)s",
                                person=target,
                                leave_type=leave.holiday_status_id.name,
                                duration=leave.number_of_hours_display,
                                date=display_date,
                            )
                        ))
                    else:
                        res.append((
                            leave.id,
                            _("%(person)s on %(leave_type)s: %(duration).2f hours on %(date)s",
                                person=target,
                                leave_type=leave.holiday_status_id.name,
                                duration=leave.number_of_hours_display,
                                date=display_date,
                            )
                        ))
                else:
                    if leave.number_of_days > 1 and date_from_utc and date_to_utc:
                        display_date += ' - %s' % format_date(self.env, date_to_utc) or ""
                    if not target or self.env.context.get('hide_employee_name') and 'employee_id' in self.env.context.get('group_by', []):
                        res.append((
                            leave.id,
                            _("%(leave_type)s: %(duration).2f days (%(start)s)",
                                leave_type=leave.holiday_status_id.name,
                                duration=leave.number_of_days,
                                start=display_date,
                            )
                        ))
                    else:
                        res.append((
                            leave.id,
                            _("%(person)s on %(leave_type)s: %(duration).2f days (%(start)s)",
                                person=target,
                                leave_type=leave.holiday_status_id.name,
                                duration=leave.number_of_days,
                                start=display_date,
                            )
                        ))
        return res

    def add_follower(self, employee_id):
        employee = self.env['hr.employee'].browse(employee_id)
        if employee.user_id:
            self.message_subscribe(partner_ids=employee.user_id.partner_id.ids)

    @api.constrains('holiday_allocation_id')
    def _check_allocation_id(self):
        # Deprecated as part of https://github.com/odoo/odoo/pull/96545
        # TODO: remove in master
        # print(self)
        return

    @api.constrains('holiday_allocation_id', 'date_to', 'date_from')
    def _check_leave_type_validity(self):
        # Deprecated as part of https://github.com/odoo/odoo/pull/96545
        # TODO: remove in master
        return


    def _check_double_validation_rules(self, employees, state):
        if self.user_has_groups('hr_holidays.group_hr_holidays_manager'):
            return

        is_leave_user = self.user_has_groups('hr_holidays.group_hr_holidays_user')
        if state == 'validate1':
            employees = employees.filtered(lambda employee: employee.leave_manager_id != self.env.user)
            if employees and not is_leave_user:
                raise AccessError(_('You cannot first approve a time off for %s, because you are not his time off manager', employees[0].name))
        elif state == 'validate' and not is_leave_user:
            # Is probably handled via ir.rule
            raise AccessError(_('You don\'t have the rights to apply second approval on a time off request'))


    def write(self, values):
        if 'active' in values and not self.env.context.get('from_cancel_wizard'):
            raise UserError(_("You can't manually archive/unarchive a time off."))

        # is_officer = self.env.user.has_group('hr_holidays.group_hr_holidays_user') or self.env.is_superuser()
        # if not is_officer and values.keys() - {'attachment_ids', 'supported_attachment_ids', 'message_main_attachment_id'}:
        #     if any(hol.date_from.date() < fields.Date.today() and hol.employee_id.leave_manager_id != self.env.user for hol in self):
        #         raise UserError(_('You must have manager rights to modify/validate a time off that already begun'))

        

        employee_id = values.get('employee_id', False)
        if not self.env.context.get('leave_fast_create'):
            if values.get('state'):
                self._check_approval_update(values['state'])
                if any(holiday.validation_type == 'both' for holiday in self):
                    if values.get('employee_id'):
                        employees = self.env['hr.employee'].browse(values.get('employee_id'))
                    else:
                        employees = self.mapped('employee_id')
                    self._check_double_validation_rules(employees, values['state'])
            if 'date_from' in values:
                values['request_date_from'] = values['date_from']
            if 'date_to' in values:
                values['request_date_to'] = values['date_to']
        result = super(HolidaysRequestPrepare, self).write(values)
        # if not self.env.context.get('leave_fast_create'):
        #     for holiday in self:
        #         if employee_id:
        #             holiday.add_follower(employee_id)

        return result

    def unlink(self):
        return super(HolidaysRequestPrepare, self.with_context(leave_skip_date_check=True)).unlink()

    def copy_data(self, default=None):
        if default and 'date_from' in default and 'date_to' in default:
            default['request_date_from'] = default.get('date_from')
            default['request_date_to'] = default.get('date_to')
            return super().copy_data(default)
        elif self.state in {"cancel", "refuse"}:  # No overlap constraint in these cases
            return super().copy_data(default)
        raise UserError(_('A time off cannot be duplicated.'))

    def _get_mail_redirect_suggested_company(self):
        return self.holiday_status_id.company_id

    @api.model
    def read_group(self, domain, fields, groupby, offset=0, limit=None, orderby=False, lazy=True):
        if not self.user_has_groups('hr_holidays.group_hr_holidays_user') and 'private_name' in groupby:
            raise UserError(_('Such grouping is not allowed.'))
        return super(HolidaysRequestPrepare, self).read_group(domain, fields, groupby, offset=offset, limit=limit, orderby=orderby, lazy=lazy)



    # def action_cancel(self):
    #     self.ensure_one()

    #     return {
    #         'name': _('Cancel Time Off'),
    #         'type': 'ir.actions.act_window',
    #         'target': 'new',
    #         'res_model': 'hr.holidays.cancel.leave',
    #         'view_mode': 'form',
    #         'views': [[False, 'form']],
    #         'context': {
    #             'default_leave_id': self.id,
    #         }
    #     }

    def action_draft(self):
        if any(holiday.state not in ['confirm', 'refuse'] for holiday in self):
            raise UserError(_('Time off request state must be "Refused" or "To Approve" in order to be reset to draft.'))
        self.write({
            'state': 'draft',
            'hod_approver_id': False,
        })
        return True

    def action_confirm(self):
        if self.filtered(lambda holiday: holiday.state != 'draft'):
            raise UserError(_('Time off request must be in Draft state ("To Submit") in order to confirm it.'))
        self.write({'state': 'confirm'})
        return True

    def action_approve(self):
        # if validation_type == 'both': this method is the first approval approval
        # if validation_type != 'both': this method calls action_validate() below
        if any(holiday.state != 'confirm' for holiday in self):
            raise UserError(_('Time off request must be confirmed ("To Approve") in order to approve it.'))
        
        current_employee = self.env.user.employee_id
        self.filtered(lambda hol: hol.validation_type == 'both').write({'state': 'hod_approve', 'hod_approver_id': current_employee.id})


        # Post a second message, more verbose than the tracking message
        # for holiday in self.filtered(lambda holiday: holiday.employee_id.user_id):
        #     user_tz = timezone(holiday.tz)
        #     utc_tz = pytz.utc.localize(holiday.date_from).astimezone(user_tz)
        #     holiday.message_post(
        #         body=_(
        #             'Your %(leave_type)s planned on %(date)s has been accepted',
        #             leave_type=holiday.holiday_status_id.display_name,
        #             date=utc_tz.replace(tzinfo=None)
        #         ),
        #         partner_ids=holiday.employee_id.user_id.partner_id.ids)

        # self.filtered(lambda hol: not hol.validation_type == 'both').action_validate()
        return True
    def check_duty_cover_exist(self,employee_id,date_from,date_to):
        duty_cover_exist = self.env['hr.leave.prepare'].search([('state','not in',('refuse',)),
        ('date_from','<=',date_from),
        ('date_to','>=',date_to),
        ('duty_cover_by','=',employee_id)])
        return bool(duty_cover_exist)

    def action_hod_approve(self, skip=False):
        if any(holiday.state != 'confirm' for holiday in self):
            raise UserError(_('Time off request must be confirmed ("To Approve") in order to approve it.'))

        current_employee = self.env.user.employee_id
        if not current_employee:
            raise UserError(_('User must be an employee to approve the time off request!!'))
        elif current_employee == self.employee_id:
            raise UserError(_('You can not approve your own time off request, dummy!!'))
        elif self.employee_id.department_id not in self.env.user.hr_department_ids:
            raise UserError(_('You do not have permission to approve the time off request of this employee!!'))
        if not skip:

            duty_cover_exist = self.check_duty_cover_exist(self.employee_id.id,self.date_from,self.date_to)
            if duty_cover_exist:
                view_id = self.env['ir.model.data']._xmlid_to_res_id('time_off_extension.duty_cover_timeoff_warning_wizard_form')
                warning_message = _(
                        "Warning!! Employee has duty cover on  <b>%s</b>"
                        "<br/>Do you still want to approve?",
                        self.date_from.date()
                    )
                for a in self:
                    return {
                        "name": "Duty Cover Warning",
                        "view_mode": "form",
                        "view_id": view_id,
                        "res_model": "dutycover.timeoff.warning.wizard",
                        "type": "ir.actions.act_window",
                        "nodestroy": True,
                        "target": "new",
                        "domain": [],
                        "context": dict(
                            self.env.context,
                            default_message = warning_message,
                            default_prepare_id = self.id
                        )

                    }
        self.write({'state': 'hod_approve', 'hod_approver_id': current_employee.id})
        return True
    
    def action_validate(self):
        self.ensure_one()
        view_id = self.env['ir.model.data']._xmlid_to_res_id('time_off_extension.view_prepare_time_off')
        for _ in self:
            return {
                "name": "Time Off",
                "view_mode": "form",
                "view_id": view_id,
                "res_model": "hr.leave.prepare.timeoff",
                "type": "ir.actions.act_window",
                "nodestroy": True,
                "target": "new",
                "domain": [],
                "context": dict(
                    self.env.context,
                    default_request_date_from = self.upcoming_request_date,
                    default_request_date_to = self.request_date_to,
                    default_request_unit_half = self.request_unit_half,
                    default_hr_leave_prepare_id = self.id,
                    default_holiday_status_id = self.holiday_status_id.id,
                    default_employee_id = self.employee_id.id,
                    default_employee_company_id = self.employee_company_id.id,
                    default_request_date_from_period = self.request_date_from_period,
                    default_leave_type_request_unit = self.leave_type_request_unit,
                    default_name = self.name,
                    default_holiday_type = self.holiday_type,
                    holiday_status_name_get =  True
                )

            }
        return True
    
    @api.constrains('number_of_days')
    def _check_number_of_days(self):
        for holiday in self:
            if holiday.number_of_days <= 0 and not self._context.get('import_file'):
                raise ValidationError(_("Number of days must be at least 1."))

    def action_refuse(self):
        current_employee = self.env.user.employee_id
        if any(holiday.state not in ['draft', 'confirm'] for holiday in self):
            raise UserError(_('Time off request must be confirmed in order to refuse it.'))
        current_employee = self.env.user.employee_id
        if not current_employee:
            raise UserError(_('User must be an employee to refuse the time off request!!'))
        elif current_employee == self.employee_id:
            raise UserError(_('You can not refuse your own time off request, dummy!!'))
        elif self.employee_id.department_id not in self.env.user.hr_department_ids:
            raise UserError(_('You do not have permission to refuse the time off request of this employee!!'))

        self.write({'state':'refuse','hod_approver_id': current_employee.id})
        # validated_holidays = self.filtered(lambda hol: hol.state == 'confirm')
        # validated_holidays.write({'state': 'refuse', 'hod_approver_id': current_employee.id})
        # (self - validated_holidays).write({'state': 'refuse', 'second_approver_id': current_employee.id})
        # # Delete the meeting
        # self.mapped('meeting_id').write({'active': False})
        # # Post a second message, more verbose than the tracking message
        # for holiday in self:
        #     if holiday.employee_id.user_id:
        #         holiday.message_post(
        #             body=_('Your %(leave_type)s planned on %(date)s has been refused', leave_type=holiday.holiday_status_id.display_name, date=holiday.date_from),
        #             partner_ids=holiday.employee_id.user_id.partner_id.ids)
        return True
    
    def action_documents(self):
        domain = [('id', 'in', self.attachment_ids.ids)]
        return {
            'name': _("Supporting Documents"),
            'type': 'ir.actions.act_window',
            'res_model': 'ir.attachment',
            'context': {'create': False},
            'view_mode': 'kanban',
            'domain': domain
        }

    def _check_approval_update(self, state):
        """ Check if target state is achievable. """
        if self.env.is_superuser():
            return

        current_employee = self.env.user.employee_id
        is_officer = self.env.user.has_group('hr_holidays.group_hr_holidays_user')
        is_manager = self.env.user.has_group('hr_holidays.group_hr_holidays_manager')

        for holiday in self:
            val_type = holiday.validation_type

            if not is_manager and state != 'confirm':
                if state == 'draft':
                    if holiday.state == 'refuse':
                        raise UserError(_('Only a Time Off Manager can reset a refused leave.'))
                    if holiday.date_from and holiday.date_from.date() <= fields.Date.today():
                        raise UserError(_('Only a Time Off Manager can reset a started leave.'))
                    if holiday.employee_id != current_employee:
                        raise UserError(_('Only a Time Off Manager can reset other people leaves.'))
                else:
                    if val_type == 'no_validation' and current_employee == holiday.employee_id:
                        continue
                    # use ir.rule based first access check: department, members, ... (see security.xml)
                    holiday.check_access_rule('write')

                    # This handles states validate1 validate and refuse
                    if holiday.employee_id == current_employee:
                        raise UserError(_('Only a Time Off Manager can approve/refuse its own requests.'))

                    if (state == 'validate1' and val_type == 'both') and holiday.holiday_type == 'employee':
                        if not is_officer and self.env.user != holiday.employee_id.leave_manager_id:
                            raise UserError(_('You must be either %s\'s manager or Time off Manager to approve this leave') % (holiday.employee_id.name))

                    if (state == 'validate' and val_type == 'manager') and self.env.user != (holiday.employee_id | holiday.sudo().employee_ids).leave_manager_id:
                        if holiday.employee_id:
                            employees = holiday.employee_id
                        else:
                            employees = ', '.join(holiday.employee_ids.filtered(lambda e: e.leave_manager_id != self.env.user).mapped('name'))
                        raise UserError(_('You must be %s\'s Manager to approve this leave', employees))

                    if not is_officer and (state == 'validate' and val_type == 'hr') and holiday.holiday_type == 'employee':
                        raise UserError(_('You must either be a Time off Officer or Time off Manager to approve this leave'))

    ####################################################
    # Messaging methods
    ####################################################

    def _notify_change(self, message, subtype_xmlid='mail.mt_note'):
        for leave in self:
            leave.message_post(body=message, subtype_xmlid=subtype_xmlid)

            recipient = None
            if leave.user_id:
                recipient = leave.user_id.partner_id.id
            elif leave.employee_id:
                recipient = leave.employee_id.address_home_id.id

            if recipient:
                self.env['mail.thread'].sudo().message_notify(
                    body=message,
                    partner_ids=[recipient]
                )

    def _get_start_or_end_from_attendance(self, hour, date, employee):
        hour = float_to_time(float(hour))
        holiday_tz = timezone(employee.tz or self.env.user.tz or 'UTC')
        return holiday_tz.localize(datetime.combine(date, hour)).astimezone(UTC).replace(tzinfo=None)

    def _get_attendances(self, employee, request_date_from, request_date_to):
        resource_calendar_id = employee.resource_calendar_id or self.env.company.resource_calendar_id
        domain = [('calendar_id', '=', resource_calendar_id.id), ('display_type', '=', False)]
        attendances = self.env['resource.calendar.attendance'].read_group(domain,
            ['ids:array_agg(id)', 'hour_from:min(hour_from)', 'hour_to:max(hour_to)',
             'week_type', 'dayofweek', 'day_period'],
            ['week_type', 'dayofweek', 'day_period'], lazy=False)

        # Must be sorted by dayofweek ASC and day_period DESC
        attendances = sorted([DummyAttendance(group['hour_from'], group['hour_to'], group['dayofweek'], group['day_period'], group['week_type']) for group in attendances], key=lambda att: (att.dayofweek, att.day_period != 'morning'))

        default_value = DummyAttendance(0, 0, 0, 'morning', False)

        if resource_calendar_id.two_weeks_calendar:
            start_week_type = self.env['resource.calendar.attendance'].get_week_type(request_date_from)
            attendance_actual_week = [att for att in attendances if att.week_type is False or int(att.week_type) == start_week_type]
            attendance_actual_next_week = [att for att in attendances if att.week_type is False or int(att.week_type) != start_week_type]
            attendance_filtred = [att for att in attendance_actual_week if int(att.dayofweek) >= request_date_from.weekday()]
            attendance_filtred += list(attendance_actual_next_week)
            attendance_filtred += list(attendance_actual_week)
            end_week_type = self.env['resource.calendar.attendance'].get_week_type(request_date_to)
            attendance_actual_week = [att for att in attendances if att.week_type is False or int(att.week_type) == end_week_type]
            attendance_actual_next_week = [att for att in attendances if att.week_type is False or int(att.week_type) != end_week_type]
            attendance_filtred_reversed = list(reversed([att for att in attendance_actual_week if int(att.dayofweek) <= request_date_to.weekday()]))
            attendance_filtred_reversed += list(reversed(attendance_actual_next_week))
            attendance_filtred_reversed += list(reversed(attendance_actual_week))

            # find first attendance coming after first_day
            attendance_from = attendance_filtred[0]
            # find last attendance coming before last_day
            attendance_to = attendance_filtred_reversed[0]
        else:
            # find first attendance coming after first_day
            attendance_from = next((att for att in attendances if int(att.dayofweek) >= request_date_from.weekday()), attendances[0] if attendances else default_value)
            # find last attendance coming before last_day
            attendance_to = next((att for att in reversed(attendances) if int(att.dayofweek) <= request_date_to.weekday()), attendances[-1] if attendances else default_value)

        return (attendance_from, attendance_to)


    # def create(self):
    def create_time_off(self,register_id):
        if register_id.request_date_from >= register_id.hr_leave_prepare_id.request_date_from and register_id.request_date_to <= register_id.hr_leave_prepare_id.request_date_to:
            val_list = {
                'name': register_id.hr_leave_prepare_id.name,
                'request_date_from': register_id.request_date_from,
                'request_date_to': register_id.request_date_to,
                'number_of_days': register_id.number_of_days,
                'date_from': register_id.date_from,
                'date_to': register_id.date_to,
                'request_unit_half': register_id.request_unit_half,
                'employee_id': register_id.employee_id.id,
                'employee_company_id': register_id.employee_company_id.id,
                'holiday_status_id': register_id.holiday_status_id.id,
                'request_date_from_period': register_id.request_date_from_period,
                'leave_type_request_unit': register_id.leave_type_request_unit,
                'prepare_id': register_id.hr_leave_prepare_id.id,
                'request_hour_from': 0,
                'request_hour_to': 0,
                'request_unit_hours': 0,
                'duty_cover_id': register_id.hr_leave_prepare_id.duty_cover_by.id,
                'relation_of_deceased': register_id.hr_leave_prepare_id.relation_of_deceased,
                'timeoff_attachment_ids': register_id.hr_leave_prepare_id.timeoff_prepare_attachment_ids.ids
                # 'holiday_allocation_id': register_id.hr_leave_prepare_id.holiday_allocation_id.id,
            }
            time_off = self.env['hr.leave'].create(val_list)
            time_off.prepare_id.time_off_ids = [[4,time_off.id]]

            done_no_of_days = 0
            for time_off_obj in self.time_off_ids.filtered(lambda x:x.state not in ('refuse')):
                done_no_of_days += time_off_obj.number_of_days
            time_off.prepare_id.write({'done_no_of_days': done_no_of_days})
            if time_off.prepare_id.number_of_days <= time_off.prepare_id.done_no_of_days:
                time_off.prepare_id.write({'validation_status': True})
                time_off.prepare_id.write({'upcoming_request_date': register_id.request_date_to})
            else:
                time_off.prepare_id.write({'upcoming_request_date': register_id.request_date_to + relativedelta(days=1)})

            return time_off.id

    def action_open_time_off(self):
        return {
            'name': _('Time Off'),
            'view_mode': 'tree,form',
            'res_model': 'hr.leave',
            'view_id': False,
            'type': 'ir.actions.act_window',  
            'domain': [('id', 'in',self.time_off_ids.ids)],              
        } 

    @api.ondelete(at_uninstall=False)
    def _unlink_if_correct_states(self):
        error_message = _('You cannot delete a time off which is in %s state')
        state_description_values = {elem[0]: elem[1] for elem in self._fields['state']._description_selection(self.env)}
        now = fields.Datetime.now()

        # if not self.user_has_groups('hr_holidays.group_hr_holidays_user'):
        for hol in self:
            if hol.state not in ['draft']:
                raise UserError(error_message % state_description_values.get(self[:1].state))
            if hol.date_from < now:
                raise UserError(_('You cannot delete a time off which is in the past'))
            if hol.sudo().employee_ids and not hol.employee_id:
                raise UserError(_('You cannot delete a time off assigned to several employees'))
        # else:
        #     for holiday in self.filtered(lambda holiday: holiday.state in ['draft']):
        #         raise UserError(error_message % (state_description_values.get(holiday.state),))


class TimeOffPrepareAttachment(models.Model):
    _name = 'hr.leave.prepare.attachment'
    _description = 'Time Off Prepare Attachment'

    import_fname = fields.Char(string='Filename')
    import_file = fields.Binary(string='File', required=True)
    prepare_id = fields.Many2one('hr.leave.prepare', ondelete='cascade')
    leave_id = fields.Many2one('hr.leave', ondelete='cascade')
