
from odoo import models, fields, api, _
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
from odoo.exceptions import UserError
class HrLeaveAllocation(models.Model):
    _inherit = "hr.leave.allocation"

    end_of_year_date = datetime(datetime.now().year, 12, 31)
    start_of_year_date = datetime(datetime.now().year, 1, 1)
    today = fields.Date.from_string(fields.Datetime.now().date())
    remaining_leaves = fields.Float(compute = '_compute_remain_leaves')
    virtual_leaves_taken = fields.Float(compute = '_compute_remain_leaves')
    virtual_remaining_leaves = fields.Float(compute = '_compute_remain_leaves')
    time_off_burmese_name = fields.Char(related='holiday_status_id.burmese_name',store=True)

    @api.depends('max_leaves','leaves_taken')
    def _compute_remain_leaves(self):
        for allocation in self:
            allocation.virtual_leaves_taken = allocation.holiday_status_id.virtual_leaves_taken
            allocation.remaining_leaves = allocation.max_leaves - allocation.leaves_taken
            allocation.virtual_remaining_leaves = allocation.max_leaves - allocation.virtual_leaves_taken

    @api.model
    def _leave_allocation_action(self):

        time_off_type_obj = self.env['hr.leave.type'].search([('requires_allocation','=','yes'),('code','in',('EL','MAL','PTL','MTL','PEL','BL','CL'))])
        for time_off_type in time_off_type_obj:
            months_filter = fields.Datetime.now() - relativedelta(months=time_off_type['configuration_months'])
            domain_employee = [('active','=',True),('trial_date_start','!=',False),('trial_date_start', '<=', months_filter.date())]
            employees = self.env['hr.employee'].search(domain_employee)
            # filtered_employees = employees.filtered(lambda emp: not self.env['hr.leave.allocation'].search_count([
            #         ('employee_id', '=', emp.id),
            #         ('holiday_status_id', '=', time_off_type['id']),
            #         ('remaining_leaves', '<=', 0)
            #     ]))      
            
            if time_off_type['code'] == 'MAL': # Marriage Leave

                employees = employees.filtered(lambda employee: employee.marital != 'married')
                mal_holiday = self.env['hr.leave.type'].search([('code','in',('PTL','MTL','PEL'))])
                record = self.env['hr.leave.allocation'].search([
                        ('employee_id','in',employees.ids),
                        ('holiday_status_id','in',mal_holiday.ids),
                        ('date_from','>=',f"{self.today.year}-01-01"),
                        ('date_from','<=',f"{self.today.year}-12-31"),
                        ]
                        ).with_context(toggle_active=True).write({'date_to':self.today,'active': False})  
            elif time_off_type['code'] == 'PTL': # Paternity Leave

                employees = employees.filtered(lambda employee: employee.marital == 'married' and employee.gender == 'male')

            elif time_off_type['code'] == 'MTL': # Maternity Leave

                employees = employees.filtered(lambda employee: employee.marital == 'married' and employee.gender == 'female')

            elif time_off_type['code'] == 'PEL': # Prenatal Examination Leave

                employees = employees.filtered(lambda employee: employee.marital == 'married' and employee.gender == 'female')
            
            
            if time_off_type['code'] in ('PTL','MTL','PEL'):
                mal_holiday = self.env['hr.leave.type'].search([('code','=','MAL')],limit=1)
                record = self.env['hr.leave.allocation'].search([
                    ('employee_id','in',employees.ids),
                    ('holiday_status_id','=',mal_holiday.id),
                    ('date_from','>=',f"{self.today.year}-01-01"),
                    ('date_from','<=',f"{self.today.year}-12-31"),
                    ]
                    ).with_context(toggle_active=True).write({'date_to':self.today,'active': False})

            for emp in employees:
                expire_date = self.end_of_year_date
                start_date = self.start_of_year_date

                search_domain = [
                    ('employee_id','=',emp.id),
                    ('holiday_status_id','=',time_off_type['id']),
                    ('date_from','>=',f"{self.today.year}-01-01"),
                    ('date_from','<=',f"{self.today.year}-12-31"),
                    ('date_to','>=',f"{self.today.year}-01-01"),
                    ('date_to','<=',f"{self.today.year}-12-31")
                ]
                if time_off_type['code'] == 'EL':
                    # 18/Nov/2022
                    start_date = datetime(self.today.year,emp.trial_date_start.month,emp.trial_date_start.day)

                    expire_date = (start_date + relativedelta(months=12)) - relativedelta(days=1)
                    search_domain = [
                                ('employee_id','=',emp.id),
                                ('holiday_status_id','=',time_off_type['id']),
                                ('date_from','>=',start_date),
                                ('date_from','<=',start_date+relativedelta(months=12)),
                                ('date_to','>=',start_date),
                                ('date_to','<=',expire_date),

                                        ]
                elif time_off_type['code'] in ('BL','MAL','PTL','MTL','PEL'):
                    expire_date = None
                
                    search_domain = [
                    ('employee_id','=',emp.id),
                    ('holiday_status_id','=',time_off_type['id']),
                    ('date_from','>=',f"{self.today.year}-01-01"),
                    ('date_from','<=',f"{self.today.year}-12-31"),
                    ('date_to','=',False)
                ]
                check_allocate_obj = self.search(search_domain)
                if len(check_allocate_obj) <= 0:
                    create_allocate = self.sudo().create({
                            'name': time_off_type['name'],
                            'holiday_status_id': time_off_type['id'],
                            'allocation_type': 'regular',
                            'date_from': start_date,
                            'date_to': expire_date,
                            'number_of_days': time_off_type['allow_allocation_days'],
                            'holiday_type': 'employee',
                            'employee_id': emp.id,
                            'remaining_leaves': time_off_type['allow_allocation_days']
                        })
                else:
                    if time_off_type['code'] in ('BL','MAL','PTL','MTL','PEL'):
                        for allocation in check_allocate_obj:
                            temp_allocation = allocation.with_context(employee_id=emp.id)

                            if allocation.remaining_leaves <= 0:
                                # allocation.number_of_days = time_off_type['allow_allocation_days']
                                allocation.with_context(toggle_active=True).write({'date_to': self.today, 'active': False})
                                create_allocate = self.sudo().create({
                                    'name': time_off_type['name'],
                                    'holiday_status_id': time_off_type['id'],
                                    'allocation_type': 'regular',
                                    'date_from': self.today + relativedelta(days=1),
                                    'date_to': expire_date,
                                    'number_of_days': time_off_type['allow_allocation_days'],
                                    'holiday_type': 'employee',
                                    'employee_id': emp.id,
                                    'remaining_leaves': time_off_type['allow_allocation_days']
                                })

        
    @api.model
    def _calender_year_open_allocation(self):
        if datetime.now().date == self.start_of_year_date:
            time_off_type_obj = self.env['hr.leave.type'].search([('requires_allocation','=','yes'),('code','in',('CL',))])
            for time_off_type in time_off_type_obj:
                months_filter = fields.Datetime.now() - relativedelta(months=time_off_type['configuration_months'])

                domain_employee = [('active','=',True),('trial_date_start','!=',False),('trial_date_start', '<=', months_filter.date())]

                employees = self.env['hr.employee'].search(domain_employee)
                    
                

                for emp in employees:
                    remain_leaves = self.search([
                        ('employee_id','=',emp.id),
                        ('holiday_status_id','=',time_off_type['id'])
                    ])
                    remain_leaves.write({'active': False})
                    check_allocate_obj = self.search([
                        ('employee_id','=',emp.id),
                        ('holiday_status_id','=',time_off_type['id']),
                        ('date_from','>=',f"{self.today.year}-01-01"),
                        ('date_from','<=',f"{self.today.year}-12-31"),
                        ('date_to','>=',f"{self.today.year}-01-01"),
                        ('date_to','<=',f"{self.today.year}-12-31")
                    ])
                    if len(check_allocate_obj) <= 0:
                        create_allocate = self.sudo().create({
                            'name': time_off_type['name'],
                            'holiday_status_id': time_off_type['id'],
                            'allocation_type': 'regular',
                            'date_from': self.start_of_year_date,
                            'date_to': self.end_of_year_date,
                            'number_of_days': time_off_type['allow_allocation_days'],
                            'holiday_type': 'employee',
                            'employee_id': emp.id,
                            'remaining_leaves': time_off_type['allow_allocation_days']
                        })
                        # print(create_allocate)


        # fields.datetime.date() == 
    @api.model
    def _leave_allocation_action_for_back_date(self):

        if datetime.now() != self.end_of_year_date:
            time_off_type_obj = self.env['hr.leave.type'].search([('requires_allocation','=','yes'),('code','in',('EL','MAL','PTL','MTL','PEL','BL','CL'))])
            for time_off_type in time_off_type_obj:
                months_filter = fields.Datetime.now() - relativedelta(months=time_off_type['configuration_months'])
                domain_employee = [('active','=',True),('trial_date_start','!=',False),('trial_date_start', '<=', months_filter.date())]
                employees = self.env['hr.employee'].search(domain_employee)
                filtered_employees = employees
                # filtered_employees = employees.filtered(lambda emp: not self.env['hr.leave.allocation'].search_count([
                #         ('employee_id', '=', emp.id),
                #         ('holiday_status_id', '=', time_off_type['id'])
                #     ]))      
                
                if time_off_type['code'] == 'MAL': # Marriage Leave

                    filtered_employees = filtered_employees.filtered(lambda employee: employee.marital != 'married')
                    
                elif time_off_type['code'] == 'PTL': # Paternity Leave

                    filtered_employees = filtered_employees.filtered(lambda employee: employee.marital == 'married' and employee.gender == 'male')
                    
                elif time_off_type['code'] == 'MTL': # Maternity Leave

                    filtered_employees = filtered_employees.filtered(lambda employee: employee.marital == 'married' and employee.gender == 'female')

                elif time_off_type['code'] == 'PEL': # Prenatal Examination Leave

                    filtered_employees = filtered_employees.filtered(lambda employee: employee.marital == 'married' and employee.gender == 'female')

                for emp in filtered_employees:
                    expire_date = self.end_of_year_date
                    start_date = self.start_of_year_date
                    search_domain = [
                        ('employee_id','=',emp.id),
                        ('holiday_status_id','=',time_off_type['id']),
                        ('date_from','>=',f"{self.today.year}-01-01"),
                        ('date_from','<=',f"{self.today.year}-12-31"),
                        ('date_to','>=',f"{self.today.year}-01-01"),
                        ('date_to','<=',f"{self.today.year}-12-31")
                    ]

                    
                    if time_off_type['code'] == 'EL':
                        start_date = datetime((self.today-relativedelta(months=12)).year,emp.trial_date_start.month,emp.trial_date_start.day)
                        if start_date.date() == emp.trial_date_start:
                            continue
                        expire_date = (start_date + relativedelta(months=12)) - relativedelta(days=1)
                        search_domain = [
                                ('employee_id','=',emp.id),
                                ('holiday_status_id','=',time_off_type['id']),
                                ('date_from','>=',start_date),
                                ('date_from','<=',start_date+relativedelta(months=12)),
                                ('date_to','>=',start_date),
                                ('date_to','<=',expire_date),
                                        ]
                    elif time_off_type['code'] in ('BL','MAL','PTL','MTL','PEL'):
                        expire_date = None
                        search_domain = [
                        ('employee_id','=',emp.id),
                        ('holiday_status_id','=',time_off_type['id']),
                        ('date_from','>=',f"{self.today.year}-01-01"),
                        ('date_from','<=',f"{self.today.year}-12-31"),
                    ]
                    check_allocate_obj = self.search(search_domain)
                    if len(check_allocate_obj) <= 0:
                                
                        create_allocate = self.sudo().create({
                            'name': time_off_type['name'],
                            'holiday_status_id': time_off_type['id'],
                            'allocation_type': 'regular',
                            'date_from': start_date,
                            'date_to': expire_date,
                            'number_of_days': time_off_type['allow_allocation_days'],
                            'holiday_type': 'employee',
                            'employee_id': emp.id,
                            'remaining_leaves': time_off_type['allow_allocation_days']
                        })
    