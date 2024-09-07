from odoo import models, fields, api,_
from odoo.exceptions import ValidationError, UserError
from datetime import datetime, timedelta, time
from odoo.addons.resource.models.resource import float_to_time, HOURS_PER_DAY
from collections import namedtuple, defaultdict
from pytz import timezone, UTC

DummyAttendance = namedtuple('DummyAttendance', 'hour_from, hour_to, dayofweek, day_period, week_type')

from dateutil.relativedelta import relativedelta

DAY_OF_WEEK = [0,1,2,3,4,5,6]
class PrepareTimeoffLeave(models.Model):
    _name = "hr.leave.prepare.timeoff"

    request_date_from = fields.Date('Date From')
    request_date_to = fields.Date('Date To')
    request_unit_half = fields.Boolean('Half Day')
    hr_leave_prepare_id = fields.Many2one('hr.leave.prepare',string="Prepare")
    hr_leave_id = fields.Many2one('hr.leave',string="Hr Leave")
    employee_id = fields.Many2one(
        'hr.employee', compute='_compute_from_employee_ids', store=True, string='Employee', index=True, readonly=True, ondelete="restrict",
        tracking=True, compute_sudo=False)

    employee_company_id = fields.Many2one(related='employee_id.company_id', readonly=True, store=True)

    holiday_status_id = fields.Many2one(
        "hr.leave.type", compute='_compute_from_employee_id', store=True, string="Time Off Type", required=True, readonly=False,
        domain="[('company_id', '=?', employee_company_id), '|', ('requires_allocation', '=', 'no'), ('has_valid_allocation', '=', True)]", tracking=True)
    request_date_from_period = fields.Selection([
        ('am', 'Morning'), ('pm', 'Afternoon')],
        string="Date Period Start", default='am')
    leave_type_request_unit = fields.Selection(related='holiday_status_id.request_unit', readonly=True)
    date_from = fields.Datetime(
        'Start Date', compute='_compute_date_from_to', readonly=False, index=True, required=True, tracking=True,)
    date_to = fields.Datetime(
        'End Date', compute='_compute_date_from_to', readonly=False, required=True, tracking=True)
    
    number_of_days = fields.Float(
        'Duration (Days)', compute='_compute_number_of_days', store=True, readonly=False, copy=False, tracking=True)
    number_of_days_display = fields.Float(
        'Duration in days', compute='_compute_number_of_days_display', readonly=True)
    holiday_type = fields.Selection([
            ('employee', 'By Employee'),
            ('company', 'By Company'),
            ('department', 'By Department'),
            ('category', 'By Employee Tag')],
            string='Allocation Mode', readonly=True, required=True, default='employee')
    @api.onchange('request_date_from')
    def onchange_request_date_form(self):
        for res in self:
            if not res.hr_leave_prepare_id.time_off_ids:
                res.request_date_from = res.hr_leave_prepare_id.request_date_from

    def are_dates_consecutive(self,dates):        
        dates.sort()
        for i in range(1, len(dates)):
            if dates[i] != dates[i-1] + timedelta(days=1):
                return False
        return True
    
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
    
    def _get_non_working_days(self,employee):
        working_days = [int(i) for i in list(set(self.env['resource.calendar.attendance'].search([('calendar_id','=',employee.resource_calendar_id.id)]).mapped('dayofweek')))
        ]
        diff_list1 = set(DAY_OF_WEEK) - set(working_days)
        diff_list2 = set(working_days) - set(DAY_OF_WEEK)
        return sorted(list(diff_list1.union(diff_list2)))


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
    
    @api.depends('date_from', 'date_to', 'employee_id')
    def _compute_number_of_days(self):
        for holiday in self:
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
                    # elif holiday.request_unit_hours:
                    #     hour_from = holiday.request_hour_from
                    #     hour_to = holiday.request_hour_to
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
                    if holiday.employee_id and holiday.number_of_days > 0:
                        holiday.number_of_days += addional_day

                else:
                    holiday.number_of_days = 0
                    
    @api.constrains('number_of_days')
    def _check_number_of_days(self):
        for holiday in self:
            if holiday.number_of_days <= 0 and not self._context.get('import_file'):
                raise ValidationError(_("Number of days must be at least 1."))

    @api.depends('number_of_days')
    def _compute_number_of_days_display(self):
        for holiday in self:
            holiday.number_of_days_display = holiday.number_of_days

    @api.onchange('holiday_status_id')
    def onchange_holiday_status(self):
        for res in self:
            if res.request_unit_half:
                return {'domain': {'holiday_status_id': [('company_id', '=', res.employee_company_id.id),('request_unit','in',('half_day','hour')), '|', ('requires_allocation', '=', 'no'), ('has_valid_allocation', '=', True)]}}


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

    def action_register(self):
        
        for rec in self:
            if not rec.request_unit_half:
                if rec.request_date_from < rec.hr_leave_prepare_id.request_date_from or rec.request_date_to > rec.hr_leave_prepare_id.request_date_to:
                    raise UserError(_('Invalid Dates'))
  
            hr_leave_id = rec.hr_leave_prepare_id.create_time_off(rec) 
            rec.hr_leave_id = hr_leave_id
            # rec.checking_amount()
            # payment_id,move_id = rec.prepaid_id.prepaid_vendor_payment(rec)
            # if not move_id:
            #     raise ValidationError('Invalid Payment Register.')
            # rec.move_id = move_id[0]
            # rec.payment_id = payment_id[0]
            # rec.user_id = self.env.user.id

    @api.depends('employee_id')
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


    @api.depends('request_date_from_period', 'request_date_from', 'request_date_to',
                 'request_unit_half', 'employee_id')
    def _compute_date_from_to(self):
        for holiday in self:
            if holiday.request_date_from and holiday.request_date_to and holiday.request_date_from > holiday.request_date_to:
                holiday.request_date_to = holiday.request_date_from
            if not holiday.request_date_from:
                holiday.date_from = False
            elif not holiday.request_unit_half and not holiday.request_date_to:
                holiday.date_to = False
            else:
                if holiday.request_unit_half:
                    holiday.request_date_to = holiday.request_date_from

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
                else:
                    hour_from = attendance_from.hour_from
                    hour_to = attendance_to.hour_to

                holiday.date_from = self._get_start_or_end_from_attendance(hour_from, compensated_request_date_from, holiday.employee_id or holiday)
                holiday.date_to = self._get_start_or_end_from_attendance(hour_to, compensated_request_date_to, holiday.employee_id or holiday)


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
            # find week type of start_date
            start_week_type = self.env['resource.calendar.attendance'].get_week_type(request_date_from)
            attendance_actual_week = [att for att in attendances if att.week_type is False or int(att.week_type) == start_week_type]
            attendance_actual_next_week = [att for att in attendances if att.week_type is False or int(att.week_type) != start_week_type]
            # First, add days of actual week coming after date_from
            attendance_filtred = [att for att in attendance_actual_week if int(att.dayofweek) >= request_date_from.weekday()]
            # Second, add days of the other type of week
            attendance_filtred += list(attendance_actual_next_week)
            # Third, add days of actual week (to consider days that we have remove first because they coming before date_from)
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

    def _get_start_or_end_from_attendance(self, hour, date, employee):
        hour = float_to_time(float(hour))
        holiday_tz = timezone(employee.tz or self.env.user.tz or 'UTC')
        return holiday_tz.localize(datetime.combine(date, hour)).astimezone(UTC).replace(tzinfo=None)
