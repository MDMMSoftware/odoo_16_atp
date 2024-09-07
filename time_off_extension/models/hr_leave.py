from odoo import models, fields, api
from odoo.exceptions import UserError, ValidationError
from odoo.tools.translate import _ as _getText
from datetime import datetime, date

from odoo.tools.translate import _
from datetime import datetime, timedelta, time

from dateutil.relativedelta import relativedelta

DAY_OF_WEEK = [0,1,2,3,4,5,6]

class HrLeave(models.Model):
    _inherit = "hr.leave"

    employee_ids = fields.Many2many(
        'hr.employee', compute='_compute_from_holiday_type', store=True, string='Employees', readonly=False, groups="hr_holidays.group_hr_holidays_user",
        states={'cancel': [('readonly', True)], 'refuse': [('readonly', True)], 'validate1': [('readonly', True)], 'validate': [('readonly', True)]}, domain=lambda self:self._get_employee_domain())
    prepare_id = fields.Many2one('hr.leave.prepare',required=False,readonly=True,string="Time Off Prepare")        
    employee_company_id = fields.Many2one(related='employee_id.company_id', readonly=False, store=True)

    department_ids = fields.Many2many('hr.department','hr_department_leave_rel','leave_ids','department_ids')
    duty_cover_id = fields.Many2one('hr.employee')
    duty_cover_ids = fields.Many2many('hr.employee','hr_leave_duty_cover_rel', 'leave_id', 'employee_id', string='Duty Covers')
    hr_remark = fields.Char('HR Remark', states={'cancel': [('readonly', True)], 'refuse': [('readonly', True)], 'validate1': [('readonly', True)], 'validate': [('readonly', True)]})
    relation_of_deceased = fields.Selection([
        ('father','Father'),
        ('Mother','mother'),
        ('other','Other'),
    ],string="Relation Of Deceased")
    relation_of_deceased = fields.Selection([
        ('father','Father'),
        ('Mother','mother'),
        ('other','Other'),
    ],string="Relation Of Deceased")
    holiday_status_code = fields.Char(related = 'holiday_status_id.code')
    timeoff_attachment_ids = fields.One2many('hr.leave.prepare.attachment','leave_id', string='Attachments', readyonly=True, ondelete='cascade',)
    is_beyound_working_hour_boundry = fields.Boolean()


    def _get_employee_domain(self):
        return [('department_id', 'in', self.env.user.hr_department_ids.ids)]
    
    def get_dates_of_current_week(self,date):
        # today = datetime.today().date()
        # start_of_week = self.request_date_to - relativedelta(days=self.request_date_to.weekday() + 1)
        # dates_of_week = [(start_of_week + relativedelta(days=i)) for i in range(7)]
        # return dates_of_week
        # today = datetime.date.today()
        start_of_week = date - relativedelta(days=date.weekday())  # Monday
        dates_of_week = [start_of_week + relativedelta(days=i) for i in range(7)]
        return dates_of_week


    
    def _working_hour_boundry_calculation(self,record):
        current_week_dates = self.get_dates_of_current_week(record.request_date_to)
        day_of_week = ['0','1','2','3','4','5','6']

        calendar = record.employee_id.resource_calendar_id or self.env['resource.calendar'].search([], limit=1)
        att_days_of_week = list(set(self.env['resource.calendar.attendance'].search([
    ('calendar_id','=',record.employee_id.resource_calendar_id.id)]).mapped('dayofweek')))
        non_office_dow = list(set(day_of_week) - set(att_days_of_week))
        non_office_dow.sort()
        if non_office_dow:

            consecutive_non_office_dow = []
            for index,day in enumerate(non_office_dow):
                if day != non_office_dow[len(non_office_dow)-1]:
                    if int(day)+1 == int(non_office_dow[int(index)+1]):
                        consecutive_non_office_dow.append(day)
                else:
                    if int(day) == int(non_office_dow[index]):
                        consecutive_non_office_dow.append(day)
            if not consecutive_non_office_dow:
                consecutive_non_office_dow.append(non_office_dow[0])

            current_day_index = day_of_week.index(str(record.request_date_to.weekday()))
            off_day_index = day_of_week.index(str(non_office_dow[0]))
            start_diff = (current_day_index - off_day_index) % 7
            start_date = record.request_date_to - timedelta(days=start_diff)
            start_date += relativedelta(days=len(consecutive_non_office_dow))

            week_dates = [(start_date + timedelta(days=i)) for i in range(7)]
            off_in_this_week = []
            for date in week_dates:
                for non in non_office_dow:
                    if int(non) == date.weekday():
                        off_in_this_week.append(date)

            is_there_pub_off = []
            is_there_pub_off = []
            for date in off_in_this_week:
                is_there_pub_off.append(self._is_public_holiday(date,record.employee_id.resource_calendar_id.id))

            if not any(is_there_pub_off):

                total_leave_days = []
                current_date = record.request_date_from

                while current_date <= record.request_date_to:
                    total_leave_days.append(current_date)
                    current_date += timedelta(days=1)

                get_leaves_in_week = self.search([
                    ('employee_id','=',record.employee_id.id),
                    ('request_date_from','>=',week_dates[0]),
                    ('request_date_to','<=',week_dates[-1]),
                    ('state','not in',['refuse','cancel'])
                ])

                for leave in get_leaves_in_week:
                    total_leave_days.extend(record._get_days_between_two_dates(leave.request_date_from,leave.request_date_to))
                total_leave_days = list(set(total_leave_days))
                total_leave_days.sort()
                if all(element in week_dates for element in total_leave_days) and (7 - len(total_leave_days)) == len(consecutive_non_office_dow):
                    date_from = self._get_start_or_end_from_attendance(8.0, off_in_this_week[0], record.employee_id or record)
                    date_to = self._get_start_or_end_from_attendance(16.0, off_in_this_week[-1], record.employee_id or record)

                    create_boundry_leave = self.create({
                        'employee_id': record.employee_id.id,
                        'holiday_status_id': record.holiday_status_id.id,
                        'request_date_from': off_in_this_week[0],
                        'request_date_to': off_in_this_week[-1],
                        'date_from': date_from,
                        'date_to': date_to,
                        'number_of_days': len(consecutive_non_office_dow),
                        'is_beyound_working_hour_boundry': True,
                        'name': 'Beyond Working Hour Boundry',
                        'prepare_id': record.prepare_id
                    })



    def _get_days_between_two_dates(self,date_from,date_to):
        dates_list = []
        current_date = date_from

        while current_date <= date_to:
            dates_list.append(current_date)
            current_date += timedelta(days=1)
        return dates_list
    
    def _is_public_holiday(self,date,calendar_id):
        is_public_holiday = self.env['resource.calendar.leaves'].search_count([
                            ('date_from', '<=', date),
                            ('date_to', '>=', date),
                            ('calendar_id','=',calendar_id)
                            ]) > 0
        return is_public_holiday

    def _is_non_office_day(self,date):
        weekday = date.weekday()
        # non_working_days = []
        calendar = self.employee_id.resource_calendar_id or self.env['resource.calendar'].search([], limit=1)  # Adjust to get the correct calendar

        if not calendar:
            return False

        check_att = any(attendance.dayofweek == str(weekday) for attendance in calendar.attendance_ids)

        if not check_att:
            is_public_holiday = self.env['resource.calendar.leaves'].search_count([
                            ('date_from', '<=', date),
                            ('date_to', '>=', date),
                            ('calendar_id','=',calendar.id)
                            ]) > 0
            if is_public_holiday:
                return False
            return True
        return False


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


    def are_dates_consecutive(self,dates):        
        dates.sort()
        for i in range(1, len(dates)):
            if dates[i] != dates[i-1] + timedelta(days=1):
                return False
        return True
    
    def get_attendance_hours(self,date):
        employee = self.employee_id
        if not employee:
            return None, None
        
        resource_calendar = employee.resource_calendar_id or self.env.company.resource_calendar_id
        if not resource_calendar:
            return None, None


        attendance_hours = resource_calendar.attendance_ids.filtered(lambda a: int(a.dayofweek) == date.weekday())

        if not attendance_hours:
            return None, None
        return attendance_hours
    

    # def get_dates_between(self,start_date, end_date):
    #     date_list = []
    #     current_date = start_date
    #     while current_date <= end_date:
    #         date_list.append(current_date)
    #         current_date += timedelta(days=1)
    #     return date_list

    @api.depends('date_from', 'date_to', 'employee_id')
    def _compute_number_of_days(self):
        for holiday in self:
            if not self._context.get('import_file'):
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
    @api.onchange('employee_ids')
    def _onchange_department_ids(self):
        for holiday in self:
            departments = holiday.employee_ids.mapped('department_id')
            holiday.department_ids = [[6,0,departments.ids]]

    @api.onchange('employee_ids')
    def _onchnage_duty_cover_ids(self):
        for holiday in self:
            return {'domain': {'duty_cover_ids': [('active','=',True),(('id','not in',holiday.employee_ids.ids))]}}


    def _get_hour_from_hour_to(self,holiday,date_from,date_to):
        attendance_from, attendance_to = holiday._get_attendances(holiday.employee_id, date_from, holiday.date_to)

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
        return hour_from,hour_to
    
    def _compute_date_from_to_import(self):
        for holiday in self:
            
            if holiday.request_date_from and holiday.request_date_to and holiday.request_date_from >= holiday.request_date_to:
                holiday.request_date_to = holiday.request_date_from
            if not holiday.request_date_from:
                holiday.date_from = False
            elif not holiday.request_unit_half and not holiday.request_unit_hours and not holiday.request_date_to:
                holiday.date_to = False
            else:
                if holiday.request_unit_half or holiday.request_unit_hours:
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
                elif holiday.request_unit_hours:
                    hour_from = holiday.request_hour_from
                    hour_to = holiday.request_hour_to
                else:
                    hour_from = attendance_from.hour_from
                    hour_to = attendance_to.hour_to
                holiday_date_from = 0
                holiday_date_to = 0

                holiday_date_from = self._get_start_or_end_from_attendance(hour_from, compensated_request_date_from, holiday.employee_id or holiday)

                holiday_date_to = self._get_start_or_end_from_attendance(hour_to, compensated_request_date_to, holiday.employee_id or holiday)
                
                holiday.write({
                    'date_from':holiday_date_from,
                    'date_to':holiday_date_to,
                })
                
                if holiday.date_from and holiday.date_to:
                    holiday.number_of_days = holiday._get_number_of_days(holiday.date_from, holiday.date_to, holiday.employee_id.id)['days']
                    addional_day = 0
                    working_days = list(set(self.env['resource.calendar.attendance'].search([('calendar_id','=',self.employee_id.resource_calendar_id.id)]).mapped('dayofweek')))

                    if holiday.date_from and holiday.date_to:
                        # New Approach
                        non_working_days = self.get_non_working_days_v2(holiday.employee_id,holiday.request_date_from, holiday.request_date_to)
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
                            date_range_before = self.get_non_working_days_v2(holiday.employee_id,before_leave_day.date_to, temp_from)
                            date_range_before.extend([holiday.date_from.date()+timedelta(days=x) for x in range(((holiday.date_to.date()+timedelta(days=1) )-holiday.date_from.date()).days)]  )

                            date_range_before.append(before_leave_day.date_to.date())
                            date_range_before = list(set(date_range_before))
                            date_range_before.sort()
                            if self.are_dates_consecutive(date_range_before):
                                if self.request_date_from != date_range_before[1]:
                                    addional_day += len(self.get_non_working_days_v2(holiday.employee_id,before_leave_day.date_to, temp_from))
                                    if holiday.request_unit_half:
                                        holiday.request_unit_half = False
                                        addional_day += 0.5
                                        hour_from = attendance_from.hour_from
                                    # hour_from = 1.5
                                    # get_attendance = self.get_attendance_hours(date_range_before[1])
                                    # if get_attendance[0]:
                                    #     hour_from = get_attendance[0].hour_from
                                    
                                    holiday.date_from = self._get_start_or_end_from_attendance(hour_from, date_range_before[1], holiday.employee_id or holiday)

                                    # holiday.date_from = datetime(date_range_before[1].year,date_range_before[1].month,date_range_before[1].day,holiday.date_to.hour,holiday.date_to.minute,holiday.date_to.second)
                                    holiday.request_date_from = date_range_before[1]
                            else:
                                # hour_from = 1.5
                                # get_attendance = self.get_attendance_hours(temp_from)
                                # if get_attendance[0]:
                                #     hour_from = get_attendance[0].hour_from
                                holiday.date_from = self._get_start_or_end_from_attendance(hour_from, temp_from, holiday.employee_id or holiday)
                                holiday.request_date_from = temp_from

                        else:
                            # hour_from = 1.5
                            # get_attendance = self.get_attendance_hours(temp_from)
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
                            date_range_after = self.get_non_working_days_v2(holiday.employee_id,temp_from, after_leave_day.date_from)

                            date_range_after.extend([holiday.date_from.date()+timedelta(days=x) 
                            for x in range(((holiday.date_to.date()+timedelta(days=1) )-holiday.date_from.date()).days)]
                            )
                            date_range_after.append(after_leave_day.date_from.date())
                            date_range_after = list(set(date_range_after))
                            date_range_after.sort()
                            if self.are_dates_consecutive(date_range_after):
                                addional_day += len(self.get_non_working_days_v2(holiday.employee_id,temp_from, after_leave_day.date_from))
                                if holiday.request_unit_half:
                                    holiday.request_unit_half = False
                                    addional_day += 0.5
                                    hour_from = attendance_to.hour_to

                                # hour_to = 10.0
                                # get_attendance = self.get_attendance_hours(date_range_after[-2])
                                # if get_attendance[1]:
                                #     hour_to = get_attendance[1].hour_to

                                holiday.date_to = self._get_start_or_end_from_attendance(hour_to, date_range_after[-2], holiday.employee_id or holiday)
                                
                                holiday.request_date_to = date_range_after[-2]
                            else:
                                # hour_to = 10.0
                                # get_attendance = self.get_attendance_hours(temp_to)
                                # if get_attendance[1]:
                                #     hour_to = get_attendance[1].hour_to

                                holiday.date_to = self._get_start_or_end_from_attendance(hour_to, temp_to, holiday.employee_id or holiday)
                                
                                holiday.request_date_to = temp_to

                        else:
                            # hour_to = 10.0
                            # get_attendance = self.get_attendance_hours(temp_to)
                            # if get_attendance[1]:
                            #     hour_to = get_attendance[1].hour_to

                            holiday.date_to = self._get_start_or_end_from_attendance(hour_to, temp_to, holiday.employee_id or holiday)
                            
                            holiday.request_date_to = temp_to
                    if len(holiday.employee_ids) <= 1 and holiday.number_of_days > 0:
                        holiday.number_of_days += addional_day

                else:
                    holiday.number_of_days = 0

    @api.model
    def create(self, vals):
        record = super(HrLeave, self).create(vals)
        if self._context.get('import_file') and not record.is_beyound_working_hour_boundry:
            record._compute_date_from_to_import()
            # record._compute_number_of_days()
        if not record.is_beyound_working_hour_boundry:
            self._working_hour_boundry_calculation(record)
        return record

    @api.model
    def load(self, fields, data):
        context = dict(self.env.context, skip_validation=True)  # Example context key

        # Perform the import with the custom context
        return super(HrLeave, self.with_context(context)).load(fields, data)

    @api.depends('request_date_from_period', 'request_hour_from', 'request_hour_to', 'request_date_from', 'request_date_to',
                 'request_unit_half', 'request_unit_hours', 'employee_id')
    def _compute_date_from_to(self):
        for holiday in self:
            if holiday.request_date_from and holiday.request_date_to and holiday.request_date_from >= holiday.request_date_to:
                holiday.request_date_to = holiday.request_date_from
            if not holiday.request_date_from:
                holiday.date_from = False
            elif not holiday.request_unit_half and not holiday.request_unit_hours and not holiday.request_date_to:
                holiday.date_to = False
            else:
                if holiday.request_unit_half or holiday.request_unit_hours:
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
                elif holiday.request_unit_hours:
                    hour_from = holiday.request_hour_from
                    hour_to = holiday.request_hour_to
                else:
                    hour_from = attendance_from.hour_from
                    hour_to = attendance_to.hour_to
                if holiday.date_from < fields.datetime.now():
                    holiday.date_from = self._get_start_or_end_from_attendance(hour_from, compensated_request_date_from, holiday.employee_id or holiday)

                    holiday.date_to = self._get_start_or_end_from_attendance(hour_to, compensated_request_date_to, holiday.employee_id or holiday)
                else:
                    holiday.date_to = self._get_start_or_end_from_attendance(hour_to, compensated_request_date_to, holiday.employee_id or holiday)

                    holiday.date_from = self._get_start_or_end_from_attendance(hour_from, compensated_request_date_from, holiday.employee_id or holiday)

    @api.constrains('duty_cover_ids')
    def check_duty_cover_availibility(self):
        for holiday in self:
            for employee in holiday.duty_cover_ids:
                time_off_check = self.env['hr.leave'].search([
                    ('date_from','>=',holiday.date_from),
                    ('date_to','<=',holiday.date_to),
                    '|',('employee_id','=',employee.id),
                    ('employee_ids','in',(employee.id)),
                    ])
                if len(time_off_check) > 0:
                    raise ValidationError(_('Duty Cover has time off on this day'))

    @api.onchange('request_date_from','request_date_to')
    def _onchange_request_date_from(self):
        if self.prepare_id:
            if self.request_date_from < self.prepare_id.request_date_from or self.request_date_to > self.prepare_id.request_date_to:
                raise UserError(_getText('Invalid Request Date'))


    def action_refuse(self):
        super(HrLeave, self).action_refuse()
        # if self.holiday_allocation_id:
        #     self.holiday_allocation_id.write({'remaining_leaves': self.holiday_allocation_id.remaining_leaves + self.number_of_days})
        if self.prepare_id:
            self.prepare_id.write({
                'done_no_of_days': self.prepare_id.done_no_of_days - self.number_of_days,
                'upcoming_request_date': self.date_from,
                'validation_status': False,
                'hr_approval_state': 'pending'
                })
        
    def action_approve(self,skip=False):
        if skip == False:
            warning_message = ''
            for employee in self.employee_ids:
                duty_cover_check = self.env['hr.leave'].search([
                        ('state','not in',('refuse',)),
                        ('date_from','<=',self.date_from),
                        ('date_to','>=',self.date_to),
                         '|',('duty_cover_id','=',employee.id),
                        ('duty_cover_ids','in',(employee.id)),
                        ])
                if len(duty_cover_check) > 0:
                    _getText(
                        "Warning!! Employee is taking <b>%s (%s)</b> over <b>%s</b> days !!"
                        "<br/>Do you still want to approve?",
                        self.holiday_status_id.name, self.holiday_status_id.code, self.holiday_status_id.warning_over_days
                    )
                    warning_message += _getText('%s has duty cover on this dates<br/>', employee.name)
            if warning_message:
                view_id = self.env['ir.model.data']._xmlid_to_res_id('time_off_extension.timeoff_warning_wizard_form')

                for _ in self:
                    return {
                        "name": "Duty Cover Warning",
                        "view_mode": "form",
                        "view_id": view_id,
                        "res_model": "timeoff.warning.wizard",
                        "type": "ir.actions.act_window",
                        "nodestroy": True,
                        "target": "new",
                        "domain": [],
                        "context": dict(
                            self.env.context,
                            default_message = warning_message,
                            default_hr_leave_id = self.id
                        )

                    }
            time_off_ids = self.prepare_id.time_off_ids.filtered(lambda x:x.state not in ('refuse',))
            done_days = sum(timeoff.number_of_days for timeoff in time_off_ids)
            # if self.prepare_id.number_of_days < done_days:
            #     raise UserError(_getText('Time off forms can not approve anymore'))
            self.ensure_one()
            start_date, end_date = self.get_calendar_year_dates()
            records = self.search([
                    ('employee_id','=',self.employee_id.id),
                    ('holiday_status_id','=',self.holiday_status_id.id),
                    ('state','in',('confirm','validate1','validate')),
                    ('date_from', '>=', start_date),
                    ('date_from', '<=', end_date)
                ])

            total_days = sum(records.mapped('number_of_days'))
            if self.holiday_status_id.requires_allocation == 'no' and self.holiday_status_id.warning_over_days != 0 and self.holiday_status_id.warning_over_days < total_days:
                view_id = self.env['ir.model.data']._xmlid_to_res_id('time_off_extension.timeoff_warning_wizard_form')
                warning_message = _getText(
                        "Warning!! Employee is taking <b>%s (%s)</b> over <b>%s</b> days !!"
                        "<br/>Do you still want to approve?",
                        self.holiday_status_id.name, self.holiday_status_id.code, self.holiday_status_id.warning_over_days
                    )
                for _ in self:
                    return {
                        "name": "Time Off Warning",
                        "view_mode": "form",
                        "view_id": view_id,
                        "res_model": "timeoff.warning.wizard",
                        "type": "ir.actions.act_window",
                        "nodestroy": True,
                        "target": "new",
                        "domain": [],   
                        "context": dict(
                            self.env.context,
                            default_message = warning_message,
                            default_hr_leave_id = self.id
                        )

                    }
        super(HrLeave, self).action_approve()
        if self.prepare_id:
            approve_time_off_ids = self.prepare_id.time_off_ids.filtered(lambda x:x.state in ('validate',))
            approve_days = sum(timeoff.number_of_days for timeoff in approve_time_off_ids)
            if self.prepare_id.number_of_days <= approve_days:
                self.prepare_id.write({'hr_approval_state':'approve'})


    def get_calendar_year_dates(self):
        current_date = date.today()
        start_date = date(current_date.year, 1, 1)
        end_date = date(current_date.year, 12, 31)
        return start_date, end_date


    @api.ondelete(at_uninstall=False)
    def _unlink_if_correct_states(self):
        error_message = _getText('You cannot delete a time off which is in %s state')
        state_description_values = {elem[0]: elem[1] for elem in self._fields['state']._description_selection(self.env)}
        now = fields.Datetime.now()

        if self.user_has_groups('hr_holidays.group_hr_holidays_user'):
            for hol in self:
                if hol.state in ['draft','confirm','refuse','validate1','validate']:
                    raise UserError(error_message % state_description_values.get(self[:1].state))
                if hol.date_from < now:
                    raise UserError(_getText('You cannot delete a time off which is in the past'))
                if hol.sudo().employee_ids and not hol.employee_id:
                    raise UserError(_getText('You cannot delete a time off assigned to several employees'))
        else:
            for holiday in self.filtered(lambda holiday: holiday.state not in ['draft', 'cancel', 'confirm']):
                raise UserError(error_message % (state_description_values.get(holiday.state),))

    def action_validate(self):
        current_employee = self.env.user.employee_id
        leaves = self._get_leaves_on_public_holiday()
        if leaves:
            raise ValidationError(_('The following employees are not supposed to work during that period:\n %s') % ','.join(leaves.mapped('employee_id.name')))

        if any(holiday.state not in ['confirm', 'validate1'] and holiday.validation_type != 'no_validation' for holiday in self):
            raise UserError(_('Time off request must be confirmed in order to approve it.'))

        self.write({'state': 'validate'})

        leaves_second_approver = self.env['hr.leave']
        leaves_first_approver = self.env['hr.leave']

        for leave in self:
            if leave.validation_type == 'both':
                leaves_second_approver += leave
            else:
                leaves_first_approver += leave

            if leave.holiday_type != 'employee' or\
                (leave.holiday_type == 'employee' and len(leave.employee_ids) > 1):
                employees = leave._get_employees_from_holiday_type()

                conflicting_leaves = self.env['hr.leave'].with_context(
                    tracking_disable=True,
                    mail_activity_automation_skip=True,
                    leave_fast_create=True
                ).search([
                    ('date_from', '<=', leave.date_to),
                    ('date_to', '>', leave.date_from),
                    ('state', 'not in', ['cancel', 'refuse']),
                    ('holiday_type', '=', 'employee'),
                    ('employee_id', 'in', employees.ids)])

                if conflicting_leaves:
                    if leave.leave_type_request_unit != 'day' or any(l.leave_type_request_unit == 'hour' for l in conflicting_leaves):
                        raise ValidationError(_('You can not have 2 time off that overlaps on the same day.'))

                    target_states = {l.id: l.state for l in conflicting_leaves}
                    conflicting_leaves.action_refuse()
                    split_leaves_vals = []
                    for conflicting_leave in conflicting_leaves:
                        if conflicting_leave.leave_type_request_unit == 'half_day' and conflicting_leave.request_unit_half:
                            continue

                        if conflicting_leave.date_from < leave.date_from:
                            before_leave_vals = conflicting_leave.copy_data({
                                'date_from': conflicting_leave.date_from.date(),
                                'date_to': leave.date_from.date() + timedelta(days=-1),
                                'state': target_states[conflicting_leave.id],
                            })[0]
                            before_leave = self.env['hr.leave'].new(before_leave_vals)
                            before_leave._compute_date_from_to()

                            if before_leave.date_from < before_leave.date_to:
                                split_leaves_vals.append(before_leave._convert_to_write(before_leave._cache))
                        if conflicting_leave.date_to > leave.date_to:
                            after_leave_vals = conflicting_leave.copy_data({
                                'date_from': leave.date_to.date() + timedelta(days=1),
                                'date_to': conflicting_leave.date_to.date(),
                                'state': target_states[conflicting_leave.id],
                            })[0]
                            after_leave = self.env['hr.leave'].new(after_leave_vals)
                            after_leave._compute_date_from_to()

                            if after_leave.date_from < after_leave.date_to:
                                split_leaves_vals.append(after_leave._convert_to_write(after_leave._cache))

                    split_leaves = self.env['hr.leave'].with_context(
                        tracking_disable=True,
                        mail_activity_automation_skip=True,
                        leave_fast_create=True,
                        leave_skip_state_check=True
                    ).create(split_leaves_vals)

                    split_leaves.filtered(lambda l: l.state in 'validate')._validate_leave_request()

                values = leave._prepare_employees_holiday_values(employees)
                leaves = self.env['hr.leave'].with_context(
                    tracking_disable=True,
                    mail_activity_automation_skip=True,
                    leave_fast_create=True,
                    no_calendar_sync=True,
                    leave_skip_state_check=True,
                    leave_compute_number_of_days=True,
                ).create(values)

                leaves._validate_leave_request()

        leaves_second_approver.write({'second_approver_id': current_employee.id})
        leaves_first_approver.write({'first_approver_id': current_employee.id})

        employee_requests = self.filtered(lambda hol: hol.holiday_type == 'employee')
        employee_requests._validate_leave_request()
        if not self.env.context.get('leave_fast_create'):
            employee_requests.filtered(lambda holiday: holiday.validation_type != 'no_validation').activity_update()
        return True

    @api.constrains('date_from', 'date_to', 'employee_id')
    def _check_date_state(self):
        if self.env.context.get('leave_skip_state_check'):
            return
        for holiday in self:
            if holiday.state in ['cancel', 'refuse', 'validate1']:
                raise ValidationError(_("This modification is not allowed in the current state."))

    @api.constrains('number_of_days')
    def _check_number_of_days(self):
        for holiday in self:
            if holiday.number_of_days <= 0 and not self._context.get('import_file'):
                raise ValidationError(_("Number of days must be at least 1."))
 
    # @api.depends('holiday_status_id', 'request_unit_half')
    # def _compute_request_unit_hours(self):
    #     for holiday in self:

    #         attendance_from, attendance_to = holiday._get_attendances(holiday.employee_id, holiday.request_date_from, holiday.request_date_to)

    #         compensated_request_date_from = holiday.request_date_from
    #         compensated_request_date_to = holiday.request_date_to

    #         if holiday.request_unit_half:
    #             if holiday.request_date_from_period == 'am':
    #                 hour_from = attendance_from.hour_from
    #                 hour_to = attendance_from.hour_to
    #             else:
    #                 hour_from = attendance_to.hour_from
    #                 hour_to = attendance_to.hour_to
    #         elif holiday.request_unit_hours:
    #             hour_from = holiday.request_hour_from
    #             hour_to = holiday.request_hour_to
    #         else:
    #             hour_from = attendance_from.hour_from
    #             hour_to = attendance_to.hour_to

    #         holiday.date_from = self._get_start_or_end_from_attendance(hour_from, compensated_request_date_from, holiday.employee_id or holiday)
    #         holiday.date_to = self._get_start_or_end_from_attendance(hour_to, compensated_request_date_to, holiday.employee_id or holiday)
            
    #         if holiday.holiday_status_id or holiday.request_unit_half:
    #             holiday.request_unit_hours = False


class TimeOffAttachment(models.Model):
    _name = 'hr.leave.attachment'
    _description = 'Time Off Attachment'

    import_fname = fields.Char(string='Filename')
    import_file = fields.Binary(string='File', required=True)
    leave_id = fields.Many2one('hr.leave.prepare', ondelete='cascade')
