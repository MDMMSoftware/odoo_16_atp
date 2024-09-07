from dateutil.relativedelta import relativedelta
from odoo import fields, models, api, _
from odoo.exceptions import UserError
from odoo.exceptions import ValidationError
from datetime import datetime,timedelta
from ...generate_code import generate_code

def float_to_time(time):
    result = '{0:02.0f}:{1:02.0f}'.format(*divmod(time * 60, 60))
    return result+":00"

class JobOrder(models.Model):
    _name = "job.order"
    _description = "Job Order"
    _inherit = ['mail.thread']
    
    def _get_branch_domain(self):
        """methode to get branch domain"""
        company = self.env.company
        branch_ids = self.env.user.branch_ids
        branch = branch_ids.filtered(
            lambda branch: branch.company_id == company)
        return [('id', 'in', branch.ids)]
    
    name = fields.Char('Reference No',required=True,tracking = True,default=lambda self: _("New") ,readonly=True,copy=False)
    issued_date =  fields.Datetime(string="Issued Date",tracking=True)
    received_date = fields.Datetime('Received Date', default=False, required=False)
    promised_date = fields.Datetime(string="Promised Date", default=fields.Datetime.now, required=True)
    pic = fields.Many2one('hr.employee',required=True,tracking=True,string="Service Advisor")
    mileage = fields.Float("Mileage",tracking=True)
    estimated_time = fields.Float("Estimated Time",tracking=True)
    job_instruction = fields.Text("Diagnosis Result/Job Instruction",tracking=True)
    job_rate_line = fields.One2many('job.rate.line','job_order_id',string="Rate Lines")
    # job_duration_line = fields.One2many('job.duration.line','job_order_id',string="Duration Lines")
    company_id = fields.Many2one("res.company","Company",default=lambda self:self.env.company)
    quotation_id = fields.Many2one('request.quotation',string="Quotation",readonly=True)
    request_id = fields.Many2one("customer.request.form",string="Customer Request",related="quotation_id.request_id",store=True)
    customer = fields.Many2one("res.partner",string="Customer Name",related="quotation_id.customer",store=True)
    fleet_id = fields.Many2one('fleet.vehicle','Fleet',related="quotation_id.fleet_id",store=True)
    state = fields.Selection([('draft','Draft'),('job_start','Job Start'),('qc_check','QC Pass'),('job_close','Job Closed'),('cancel','Cancelled')],default='draft',tracking=True,readonly=False)
    job_state = fields.Selection([('draft','Pending'),('job_start','Received'),('progress','Processing'),('finish','Waiting QC'),('work_in_progress','WIP'),('qc_check','QC Passed'),('job_close','Finished'),('cancel','Cancelled')],default='draft')
    branch_id = fields.Many2one('res.branch',string="Branch",store=True,required=True,domain=_get_branch_domain,)
    is_invoiced = fields.Boolean(default=False) 
    qc_checker_id = fields.Many2one("hr.employee",string="QC Checker")  
    
    # @api.constrains('job_rate_line')
    # def check_job_rate(self):
    #     for rate_line in self.job_rate_line:
    #         rate_line.pic1_amt = rate_line.pic2_amt = rate_line.pic3_amt =rate_line.pic4_amt=rate_line.pic5_amt=0
    #         if rate_line.rate.pic1:
    #             if not rate_line.pic1:
    #                 raise UserError(_("Please insert Mechanic 1"))
    #             else:
    #                 rate_line.pic1_amt = round(rate_line.amount * (rate_line.rate.pic1/100),2)
                    
    #         if rate_line.rate.pic2:
    #             if not rate_line.pic2:
    #                 raise UserError(_("Please insert Mechanic 2"))
    #             else:
    #                 rate_line.pic2_amt = round(rate_line.amount * (rate_line.rate.pic2/100),2)
                    
    #         if rate_line.rate.pic3:
    #             if not rate_line.pic3:
    #                 raise UserError(_("Please insert Mechanic 3"))
    #             else:
    #                 rate_line.pic3_amt = round(rate_line.amount * (rate_line.rate.pic3/100),2)
                    
    #         if rate_line.rate.pic4:
    #             if not rate_line.pic4:
    #                 raise UserError(_("Please insert Mechanic 4"))
    #             else:
    #                 rate_line.pic4_amt = round(rate_line.amount * (rate_line.rate.pic4/100),2)
                    
    #         if rate_line.rate.pic5:
    #             if not rate_line.pic5:
    #                 raise UserError(_("Please insert Mechanic 5"))
    #             else:
    #                 rate_line.pic5_amt = round(rate_line.amount * (rate_line.rate.pic5/100),2)
            
        
           
    def action_job_start(self):
        if not self.name or self.name=='New':
            name = False
            if not self.received_date:
                raise ValidationError(_("Please insert Date"))
            sequence = self.env['sequence.model']
            name = generate_code.generate_code(sequence,self,self.branch_id,self.company_id,self.received_date,None,None)
            if not name:
                raise ValidationError(_("Sequence Not Found.Please Contact to the Administrator."))
            self.write({'name':name})
        self.state = self.job_state = self.quotation_id.request_id.order_state = 'job_start'

    def action_qc_check_wizard(self):
        for rate_line in self.job_rate_line:
            if not rate_line.job_rate_detail:
                raise UserError("You haven't add detail line for every job rate line!!")
            if 'progress' in rate_line.job_rate_detail.mapped('state') or 'ready' in rate_line.job_rate_detail.mapped('state'):
                raise UserError("Pease click Done Button in Job Rate Detail!!")
        view_id = self.env['ir.model.data']._xmlid_to_res_id('repair_external.view_qc_checker_wizard_form')
        for _ in self:
            return {
                "name": "QC Checking",
                "view_mode": "form",
                "view_id": view_id,
                "res_model": "qc.checker.wizard",
                "type": "ir.actions.act_window",
                "nodestroy": True,
                "target": "new",
                "domain": [],
                "context": dict(
                    self.env.context,
                    default_job_order_id = self.id,
                    default_branch_id = self.branch_id.id,
                )

            }
        return True
        
    def action_job_closed(self):
        if 'progress' in self.job_rate_line.job_rate_detail.mapped('state') or 'ready' in self.job_rate_line.job_rate_detail.mapped('state'):
            raise ValidationError(_("You should done in Rate Detail Firstly"))
        if not self.issued_date:
            raise UserError("Issued date is required to close the job!!")
        if not self.quotation_id:
            raise UserError("Hmm! Quotation is nout found!!")
        max_issued_date = max(self.quotation_id.job_order_ids.filtered(lambda x:x.issued_date != False).mapped('issued_date'))
        self.quotation_id.write({'issued_date':max_issued_date})
        self.quotation_id.request_id.write({'issued_date':max_issued_date})
        self.state = self.job_state = 'job_close'
        all_states = self.quotation_id.job_order_ids.mapped('state')
        if all_states[0] == 'job_close'  and all(statee == all_states[0] for statee in all_states if statee != 'cancel'):
            self.quotation_id.request_id.order_state = 'job_close'     
        return {
                'effect': {
                            'fadeout': 'slow',
                            'message': 'Job Order is successfully closed!!',
                            'type': 'rainbow_man',
                        }      
                }     

    def action_cancel(self):
        for res in self:
            if 'progress' in res.job_rate_line.job_rate_detail.mapped('state'):
                raise ValidationError(_("You should done working lines to cancel the job order!!"))
            res.state = res.job_state = 'cancel'
            all_states = self.quotation_id.job_order_ids.mapped('state')
            if all_states[0] == 'cancel'  and all(statee == all_states[0] for statee in all_states):
                self.quotation_id.request_id.order_state = 'cancel' 
            elif all(statee == 'job_close' for statee in all_states if statee != 'cancel'):
                self.quotation_id.request_id.order_state = 'job_close'                       
            for job_rate_line in res.job_rate_line:
                job_rate_line.service_line.sudo().job_rate_line = False
                job_rate_line.service_line.sudo().unlink()       
     
class QCCheckerWizard(models.TransientModel):
    _name = 'qc.checker.wizard'

    qc_checker_id = fields.Many2one("hr.employee",string="QC Checker")   
    job_order_id =  fields.Many2one("job.order")   
    branch_id = fields.Many2one('res.branch',string="Branch",store=True,required=True)    

    def action_qc_check(self):
        self.job_order_id.qc_checker_id = self.qc_checker_id
        self.job_order_id.state = self.job_order_id.job_state = 'qc_check'
        for job_order in self.job_order_id.quotation_id.job_order_ids:
            if job_order.state == 'job_start':
                self.job_order_id.quotation_id.request_id.order_state = 'job_start'
                break
            elif job_order.state == 'qc_check':
                self.job_order_id.quotation_id.request_id.order_state = 'qc_check'    
    
class JobOrderRateLine(models.Model):
    _name = "job.rate.line"
    
    name = fields.Char('Reference No',required=True,tracking = True,default=lambda self: _("New") ,readonly=True,copy=False)
    rate = fields.Many2one("job.rate",required=False,domain=False)
    job_order_id = fields.Many2one("job.order")
    job_type_id = fields.Many2one("custom.group.class",string="Job Type")
    amount = fields.Float("Amount")
    pic1 = fields.Many2one('hr.employee',required=False,tracking=True,string="Mechanic 1",domain =lambda self: [('is_technician', '=', True)])
    pic2 = fields.Many2one('hr.employee',required=False,tracking=True,string="Mechanic 2",domain =lambda self: [('is_technician', '=', True)])
    pic3 = fields.Many2one('hr.employee',required=False,tracking=True,string="Mechanic 3",domain =lambda self: [('is_technician', '=', True)])
    pic4 = fields.Many2one('hr.employee',required=False,tracking=True,string="Mechanic 4",domain =lambda self: [('is_technician', '=', True)])
    pic5 = fields.Many2one('hr.employee',required=False,tracking=True,string="Mechanic 5",domain =lambda self: [('is_technician', '=', True)])
    pic1_amt = fields.Float("Pic 1 Amt",default=0.0,store=True)
    pic2_amt = fields.Float("Pic 2 Amt",default=0.0,store=True)
    pic3_amt = fields.Float("Pic 3 Amt",default=0.0,store=True)
    pic4_amt = fields.Float("Pic 4 Amt",default=0.0,store=True)
    pic5_amt = fields.Float("Pic 5 Amt",default=0.0,store=True)
    service_line = fields.Many2one("service.data")
    job_rate_detail = fields.One2many("job.rate.detail","job_rate_id",string="Rate Details")
    received_date = fields.Datetime('Received Date', required=True,related="job_order_id.received_date")
    promised_date = fields.Datetime(string="Promised Date", default=fields.Datetime.now, required=True,related="job_order_id.promised_date")
    job_code = fields.Many2one("product.product",required=True,domain="[('detailed_type', '=', 'service')]")
    start_time = fields.Datetime(readonly=True)
    end_time = fields.Datetime(readonly=True)
    duration = fields.Float(readonly=True,compute="_calculate_duration",store=True)
    job_desc = fields.Char("Job Name",related="job_code.name",store=True)
    company_id = fields.Many2one("res.company","Company",default=lambda self:self.env.company)
    branch_id = fields.Many2one("res.branch",string="Technical Branch",related="job_order_id.branch_id")
    is_cancel = fields.Boolean("Is Cancelled?",default=False)

    @api.constrains('job_rate_detail')
    def check_job_rate_detail(self):
        pic_lst = [0,0,0,0,0]
        self.pic1_amt = self.pic2_amt = self.pic3_amt =self.pic4_amt=self.pic5_amt=0
        for detail_line in self.job_rate_detail:
            for stng_idx in "12345":
                if pic_lst[int(stng_idx)-1] == 0 and stng_idx in detail_line.pic_id.name:
                    pic_lst[int(stng_idx)-1] = round(self.amount * (self.rate.pic1/100),2)  
        self.pic1_amt = pic_lst[0]
        self.pic2_amt = pic_lst[1]
        self.pic3_amt = pic_lst[2]
        self.pic4_amt = pic_lst[3]
        self.pic5_amt = pic_lst[4]
    
    @api.depends('start_time','end_time')
    def _calculate_duration(self):
        for res in self:
            if res.start_time and res.end_time:
                duration = 0
                duration = max(duration, (res.end_time.replace(microsecond=0) - res.start_time.replace(microsecond=0)).total_seconds() / 60.0)
                res.duration = round(duration,2)
    
    def action_show_details(self):
        return {
            'name': _('Jod Rate Details'),
            'type': 'ir.actions.act_window',
            'view_mode': 'form',
            'res_model': 'job.rate.line',
            # 'target': 'current',
            'res_id': self.id,
        }
    
class JobRateDetail(models.Model):
    _name = "job.rate.detail"
    
    name = fields.Char('Reference No',required=True,tracking = True,default=lambda self: _("New") ,readonly=True,copy=False)
    pic = fields.Many2one('hr.employee',required=True,tracking=True,string="Mechanician")
    company_id = fields.Many2one(
        'res.company', required=True, index=True,
        default=lambda self: self.env.company)
    desc = fields.Char(string="Description")
    description = fields.Many2one('job.description',string="Job Name")
    job_rate_id = fields.Many2one("job.rate.line")   
    date_start = fields.Datetime(string="Start Time",readonly=False)
    date_end = fields.Datetime(string="End Time",readonly=True)
    pic_id = fields.Many2one("job.pic",string="PIC")
    state = fields.Selection([
        ('ready', 'Ready'),
        ('progress', 'In Progress'),
        ('done', 'Finished'),
        ('cancel', 'Cancelled')], string='Status',
        store=True,
        default='ready', copy=False, readonly=True, recursive=True, index=True)
    is_user_working = fields.Boolean(
        'Is the Current User Working', compute='_compute_working_users')
    time_ids = fields.One2many('job.rate.detail.productivity', 'detail_id', 'Time Logs')
    duration = fields.Float(
        'Real Duration', compute='_compute_duration', inverse='_set_duration',
        readonly=True, store=True, copy=False)
    working_state = fields.Selection([
        ('normal', 'Normal'),
        ('done', 'In Progress')], 'Workcenter Status', compute="_compute_working_state", store=True)
    branch_id = fields.Many2one("res.branch",string="Branch",related="job_rate_id.branch_id")
    received_date = fields.Datetime("Date",related="job_rate_id.job_order_id.received_date")
    fleet_id = fields.Many2one('fleet.vehicle','Fleet',related="job_rate_id.job_order_id.fleet_id",store=True)
    quotation_id = fields.Many2one('request.quotation','Quotation',related="job_rate_id.job_order_id.quotation_id",store=True)
    pic_ids = fields.Many2many('job.pic', 'job_pic_rel',
                                compute='_compute_pic_ids')
    pic_name_ids = fields.Many2many('hr.employee', 'pic_name_rel',
                                compute='_compute_pic_name_ids')


    def _compute_pic_ids(self):
        for record in self:
            if record.job_rate_id:
                record.pic_ids = (self.job_rate_id.rate.rate_pic.pic_id.ids)

    def _compute_pic_name_ids(self):
        for record in self:
            if record.job_rate_id:
                record.pic_name_ids = (self.job_rate_id.pic1.ids+self.job_rate_id.pic2.ids+self.job_rate_id.pic3.ids+self.job_rate_id.pic4.ids+self.job_rate_id.pic5.ids)

    @api.depends('time_ids', 'time_ids.date_end')
    def _compute_working_state(self):
        for detail in self:

            time_log = self.env['job.rate.detail.productivity'].search([
                ('detail_id', '=', detail.id),
                ('date_end', '=', False)
            ], limit=1)
            if not time_log:
                detail.working_state = 'normal'
            
            else:
                detail.working_state = 'done'

    @api.constrains("pic_id","pic")
    def _constarint_check_pic_and_technician(self):
        for each_line in self:
            for res in each_line.job_rate_id.job_rate_detail:
                if res.id != each_line.id:
                    if res.pic_id.id == each_line.pic_id.id:
                        if res.pic.id != each_line.pic.id:
                            raise UserError("Unmatched Technician Name with alredy existed PIC..")
                        if res.state == 'progress':
                            raise UserError("You can't create PIC while the exsited PIC is working..")
    
    def _prepare_timeline_vals(self, duration, date_start, date_end=False):
        # Need a loss in case of the real time exceeding the expected
        
        return {
            'detail_id': self.id,
            'description': _('Time Tracking: %(user)s', user=self.env.user.name),
            'date_start': date_start.replace(microsecond=0),
            'date_end': date_end.replace(microsecond=0) if date_end else date_end,
            'user_id': self.env.user.id,  # FIXME sle: can be inconsistent with company_id
            'company_id': self.company_id.id,
        }
    
    
    @api.depends('time_ids.duration')
    def _compute_duration(self):
        for order in self:
            order.duration = sum(order.time_ids.mapped('duration'))
            
    def _set_duration(self):

        def _float_duration_to_second(duration):
            minutes = duration // 1
            seconds = (duration % 1) * 60
            return minutes * 60 + seconds

        for order in self:
            old_order_duration = sum(order.time_ids.mapped('duration'))
            new_order_duration = order.duration
            if new_order_duration == old_order_duration:
                continue

            delta_duration = new_order_duration - old_order_duration

            if delta_duration > 0:
                enddate = datetime.now()
                date_start = enddate - timedelta(seconds=_float_duration_to_second(delta_duration))
                
                self.env['job.rate.detail.productivity'].create(
                    order._prepare_timeline_vals(new_order_duration, date_start, enddate)
                    )
               
            else:
                duration_to_remove = abs(delta_duration)
                timelines_to_unlink = self.env['job.rate.detail.productivity']
                for timeline in order.time_ids.sorted():
                    if duration_to_remove <= 0.0:
                        break
                    if timeline.duration <= duration_to_remove:
                        duration_to_remove -= timeline.duration
                        timelines_to_unlink |= timeline
                    else:
                        new_time_line_duration = timeline.duration - duration_to_remove
                        timeline.date_start = timeline.date_end - timedelta(seconds=_float_duration_to_second(new_time_line_duration))
                        break
                timelines_to_unlink.unlink()
                
    @api.onchange('pic_id')
    def onchange_domain_pic_id(self):
        return {"domain":{'pic_id':[('id','in',self.job_rate_id.rate.rate_pic.pic_id.ids)]}}
    
    @api.onchange('pic')
    def onchange_domain_pic(self):
        return {"domain":{'pic':[('id','in',self.job_rate_id.pic1.ids+self.job_rate_id.pic2.ids+self.job_rate_id.pic3.ids+self.job_rate_id.pic4.ids+self.job_rate_id.pic5.ids)]}}
    

    @api.onchange("date_start")
    def onchange_date_start_to_validate(self):
        if self.date_start:
            if self.state != 'ready':
                raise ValidationError("To set date start , the state must be in 'ready'.!!!")
            # if (self.date_start + timedelta(hours=6,minutes=30)).date() != datetime.today().date():
            if (self.date_start ).date() != datetime.today().date():
                raise ValidationError("Start Date must be today's date...")

    def _should_start_timer(self):
        return True
    
    def button_start(self):
        self.ensure_one()
        if self.job_rate_id.job_order_id.state != 'job_start':
            raise ValidationError("Job has not started yet or Job has already finished!!")
        self.job_rate_id.job_order_id.job_state = self.job_rate_id.job_order_id.quotation_id.request_id.order_state = 'progress'
        if self.env['job.rate.detail'].search([('pic','=',self.pic.id),('working_state','=','done')]):
            raise ValidationError(_("Technician cannot start twice on progress job detail.You must to pause one of them first"))
        if self.pic:
            if self.pic.is_technician:
                self.pic.job_order_id = self.job_rate_id.job_order_id and self.job_rate_id.job_order_id.id or False
                self.pic.job_detail_id = self.id
        if any(not time.date_end for time in self.time_ids.filtered(lambda t: t.user_id.id == self.env.user.id)):
            return True
        # As button_start is automatically called in the new view
        if self.state in ('done', 'cancel'):
            return True
        
        start_date = datetime.now()
        if self.date_start:
            if self.state == 'ready':
                # start_date = self.date_start + timedelta(hours=6,minutes=30)
                start_date = self.date_start
            # if (self.date_start + timedelta(hours=6,minutes=30)).replace(microsecond=0) > datetime.now().replace(microsecond=0):
            if (self.date_start).replace(microsecond=0) > datetime.now().replace(microsecond=0):
                raise ValidationError("Date start must not be greater than current time!!!")

        if self._should_start_timer():
            self.env['job.rate.detail.productivity'].create(
                self._prepare_timeline_vals(self.duration, start_date)
            )

        if self.state == 'progress':
            return True
        start_date = self.date_start if self.date_start else datetime.now()
        vals = {
            'state': 'progress',
            'date_start': start_date,
        }
        
        
        return self.write(vals)
    
    def end_previous(self, doall=False):
        domain = [('detail_id', 'in', self.ids), ('date_end', '=', False)]
        if not doall:
            domain.append(('user_id', '=', self.env.user.id))
        update_date_end_job_rate_detail = self.env['job.rate.detail.productivity'].search(domain, limit=None if doall else 1)
        update_date_end_job_rate_detail._close()
        return True
    
    def end_all(self):
        return self.end_previous(doall=True)
        
    def button_pending(self):
        self.end_previous()
        open_date_end_productivity_existed = self.env['job.rate.detail.productivity'].search([('detail_id', 'in', self.ids), ('date_end', '=', False)])
        if open_date_end_productivity_existed:
            raise ValidationError("Something went wrong!!!Please pause the job rate again!!")        
        if self.job_rate_id.job_order_id.state != 'job_start':
            raise ValidationError("Job has not started yet or Job has already finished!!")        
        if self.pic:
            if self.pic.is_technician:
                self.pic.job_order_id = self.job_rate_id.job_order_id and self.job_rate_id.job_order_id.id or False
                self.pic.job_detail_id = self.id
        for job_order in self.job_rate_id.job_order_id.quotation_id.job_order_ids:
            for rate_lines in job_order.job_rate_line:
                for detail_line in rate_lines.job_rate_detail:
                    if detail_line.state == 'progress' and detail_line.is_user_working == True:
                        self.job_rate_id.job_order_id.job_state = self.job_rate_id.job_order_id.quotation_id.request_id.order_state = 'progress'
                        return True
                    elif detail_line.state == 'done' or detail_line.is_user_working == False:
                        self.job_rate_id.job_order_id.job_state = self.job_rate_id.job_order_id.quotation_id.request_id.order_state = 'work_in_progress'
        return True
                
    
    def get_working_duration(self):
        """Get the additional duration for 'open times' i.e. productivity lines with no date_end."""
        self.ensure_one()
        duration = 0
        for time in self.time_ids.filtered(lambda time: not time.date_end):
            duration += (datetime.now() - time.date_start).total_seconds() / 60
        return duration
    
    def _compute_working_users(self):
        """ Checks whether the current user is working, all the users currently working and the last user that worked. """
        for order in self:
            if order.time_ids.filtered(lambda x: not x.date_end):
                order.is_user_working = True
            else:
                order.is_user_working = False
                
    def button_finish(self):
        if self.job_rate_id.job_order_id.state != 'job_start':
            raise ValidationError("Job has not started yet or Job has already finished!!")        
        end_date = fields.Datetime.now()
        for detail in self:
            if detail.state in ('done', 'cancel'):
                continue
            detail.end_all()
            vals = {
                'state': 'done',
                
            }
            if not detail.date_start:
                vals['date_start'] = end_date
            
            detail.write(vals)
        open_date_end_productivity_existed = self.env['job.rate.detail.productivity'].search([('detail_id', 'in', self.ids), ('date_end', '=', False)])
        if open_date_end_productivity_existed:
            raise ValidationError("Something went wrong!!!Please pause the job rate again!!")              
        self.date_end = fields.Datetime.now()
        if self.job_rate_id.job_rate_detail.mapped('date_start'):
            self.job_rate_id.start_time = min(list(filter(bool,self.job_rate_id.job_rate_detail.mapped('date_start'))))
        if self.job_rate_id.job_rate_detail.mapped('date_end'):
            self.job_rate_id.end_time = max(list(filter(bool,self.job_rate_id.job_rate_detail.mapped('date_end'))))
        if self.pic:
            if self.pic.is_technician:
                self.pic.job_order_id = self.job_rate_id.job_order_id and self.job_rate_id.job_order_id.id or False
                self.pic.job_detail_id = self.id
        all_states = [detail_line.state  for job_order in self.job_rate_id.job_order_id.quotation_id.job_order_ids for job_rate in job_order.job_rate_line for detail_line in job_rate.job_rate_detail]
        if 'progress' not in all_states:
            self.job_rate_id.job_order_id.job_state = self.job_rate_id.job_order_id.quotation_id.request_id.order_state = 'finish'
        return True
    
    def unlink(self):
        for res in self:
            if res.state != 'ready':
                raise UserError("You can only delete ready state job rate detail line..")
        return super().unlink()
                
class JobRateDetailProductivity(models.Model):
    _name = "job.rate.detail.productivity"
    _description = "Repair Productivity Log"
    _order = "id desc"

    

    detail_id = fields.Many2one('job.rate.detail', "Job Rate Detail", required=True, check_company=True, index=True)
    company_id = fields.Many2one(
        'res.company', required=True, index=True,
        default=lambda self: self.env.company)
    user_id = fields.Many2one(
        'res.users', "User",
        default=lambda self: self.env.uid)
    
    description = fields.Text('Description')
    date_start = fields.Datetime('Start Date', default=fields.Datetime.now, required=True)
    date_end = fields.Datetime('End Date')
    duration = fields.Float('Duration', compute='_compute_duration', store=True)
    
    def _close(self):
        for timer in self:
            timer.write({'date_end': fields.Datetime.now()})
            

    @api.depends('date_end', 'date_start')
    def _compute_duration(self):
        for blocktime in self:
            if blocktime.date_start and blocktime.date_end:
                duration = 0
                duration = max(duration, (blocktime.date_end.replace(microsecond=0) - blocktime.date_start.replace(microsecond=0)).total_seconds() / 60.0)
                blocktime.duration = round(duration,2)
            else:
                blocktime.duration = 0.0


        


  
class JobRate(models.Model):
    _name = "job.rate"
    _inherit = ['mail.thread']
    
    name = fields.Char(readonly=True)
    pic1 = fields.Integer(string="PIC 1")
    pic2 = fields.Integer(string="PIC 2")
    pic3 = fields.Integer(string="PIC 3")
    pic4 = fields.Integer(string="PIC 4")
    pic5 = fields.Integer(string="PIC 5")
    rate_pic = fields.One2many('job.rate.pic','rate_id',string="PIC Rates")
    company_id = fields.Many2one("res.company","Company",default=lambda self:self.env.company)
    
    
    def name_get(self):
        result=[]
        for rec in self:
            result.append((rec.id,'%s,%s,%s,%s,%s' %(rec.pic1,rec.pic2,rec.pic3,rec.pic4,rec.pic5)))
        
        return result
    
    @api.onchange('pic1','pic2','pic3','pic4','pic5')
    def onchange_rate_amt(self):
        if self.pic1+self.pic2+self.pic3+self.pic4+self.pic5 >100:
         raise UserError(_("Rate calculate base on 100%"))
     
    @api.constrains('pic1','pic2','pic3','pic4','pic5')
    def calculate_rate_amt(self):
        if self.pic1+self.pic2+self.pic3+self.pic4+self.pic5!=100:
         raise UserError(_("Rate calculate base on 100%"))
        else:
            if self.rate_pic:
                self.rate_pic.sudo().unlink()
            if not self.rate_pic:
                pic1 = self.env['job.pic'].search([('name','=',"PIC 1")])
                if self.pic1 and pic1:
                    job_rate1 = self.env['job.rate.pic'].create({'pic_id':pic1.id,
                                                     'rate_amt':self.pic1})
                    self.write({"rate_pic":[(4,job_rate1.id)]})
                
                pic2 = self.env['job.pic'].search([('name','=',"PIC 2")])
                if self.pic2 and pic2:
                    job_rate2 = self.env['job.rate.pic'].create({'pic_id':pic2.id,
                                                     'rate_amt':self.pic2})
                    self.write({"rate_pic":[(4,job_rate2.id)]})
                    
                pic3 = self.env['job.pic'].search([('name','=',"PIC 3")])
                if self.pic3 and pic3:
                    job_rate3 = self.env['job.rate.pic'].create({'pic_id':pic3.id,
                                                     'rate_amt':self.pic3})
                    self.write({"rate_pic":[(4,job_rate3.id)]})
                    
                pic4 = self.env['job.pic'].search([('name','=',"PIC 4")])
                if self.pic4 and pic4:
                    job_rate4 = self.env['job.rate.pic'].create({'pic_id':pic4.id,
                                                     'rate_amt':self.pic4})
                    self.write({"rate_pic":[(4,job_rate4.id)]})
                    
                pic5 = self.env['job.pic'].search([('name','=',"PIC 5")])
                if self.pic5 and pic5:
                    job_rate5 = self.env['job.rate.pic'].create({'pic_id':pic5.id,
                                                     'rate_amt':self.pic5})
                    self.write({"rate_pic":[(4,job_rate5.id)]})
                    
            self.name = str(self.pic1)+","+str(self.pic2)+","+str(self.pic3)+","+str(self.pic4)+","+str(self.pic5)
            
class JobPIC(models.Model):
    _name = "job.pic"
    
    name = fields.Char()
    company_id = fields.Many2one("res.company","Company",default=lambda self:self.env.company)
    
class JobRatePic(models.Model):
    _name = "job.rate.pic"
    
    rate_id = fields.Many2one("job.rate")
    pic_id = fields.Many2one("job.pic",string="PIC")
    rate_amt = fields.Integer("Rate Percentage")
    company_id = fields.Many2one("res.company","Company",default=lambda self:self.env.company)
    
class Employees(models.Model):
    _inherit = 'hr.employee'
    
    
    is_technician = fields.Boolean(string="Is Technician?",default=False)
    repair_status = fields.Selection([('free','Free'),('repair','Repairing')],string="Repair Status",compute='_check_schedule',store=True,default='free', copy=False, readonly=True, recursive=True, index=True)
    job_detail_id = fields.Many2one("job.rate.detail",string="Job Detail",readonly=True)
    job_order_id = fields.Many2one("job.order",string="Job Order",readonly=True)
    fleet_id = fields.Many2one('fleet.vehicle','Fleet',related="job_order_id.fleet_id",store=True)
    res_branch_id =  fields.Many2one('res.branch',string="Technician Branch",required=False)
    filter_branch = fields.Boolean("Filter Branch",default=False)

    @api.model
    def search(self, args, offset=0, limit=None, order=None, count=False):
        # If context indicates we should filter by the user's branch, add this domain
        if args:
            first_idx_filter = [data[0] for data in args]
            if 'filter_branch' in first_idx_filter:
                if 'res_branch_id' in first_idx_filter:
                    res_branch_domain = args[first_idx_filter.index('res_branch_id')]
                    compared_datas = res_branch_domain[-1]
                    if type(compared_datas) == type(1):
                        compared_datas = [compared_datas]
                    compared_set = set(self.env.user.branch_ids.ids)
                    final_filter = [item for item in compared_datas if item in compared_set]
                    args[first_idx_filter.index('res_branch_id')] = ['res_branch_id','in',final_filter]
                else:
                    args += [('res_branch_id', 'in', self.env.user.branch_ids.ids)]

        return super().search(args, offset=offset, limit=limit, order=order, count=count)

    @api.depends('job_detail_id')
    def _check_schedule(self):
        if self.job_detail_id.working_state == 'normal':
            self.repair_status = 'free'
            self.job_detail_id = None
            self.job_order_id = None
            self.fleet_id = None
        if self.job_detail_id.working_state == 'done':
            self.repair_status = 'repair'