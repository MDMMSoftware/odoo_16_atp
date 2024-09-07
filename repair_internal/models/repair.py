from odoo import models, fields, api, _
from datetime import datetime, timedelta, date
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT
from odoo.exceptions import UserError, RedirectWarning, ValidationError
from ...generate_code import generate_code


class RepairJobCode(models.Model):
    _name = "repair.job.code"
    _description = "Repair Job Code"
    _inherit = ['mail.thread', 'mail.activity.mixin'] 
    
    name = fields.Char("Job Code",tracking=True,required=True)
    fleet_id = fields.Many2one("fleet.vehicle",string="Fleet",required=True,tracking=True)
    
    _sql_constraints = [
        ('job_code_name_uniq', 'unique (name)', 'The name of the repair Job Code must be unique !')
    ]


class RepairRequest(models.Model):
    _name = 'repair.request'
    _description = 'Job Request'
    _inherit = ['mail.thread']
    _order = 'request_date desc'

    def _get_default_branch(self):
        if len(self.env.user.branch_ids) == 1:
            branch = self.env.user.branch_id
            return branch
        return False
    
    def _get_branch_domain(self):
        """methode to get branch domain"""
        company = self.env.company
        branch_ids = self.env.user.branch_ids
        branch = branch_ids.filtered(
            lambda branch: branch.company_id == company)
        return [('id', 'in', branch.ids)]
    
    def _get_department_domain(self):
        """methode to get department domain"""
        company = self.env.company
        department_ids = self.env.user.department_ids
        department = department_ids.filtered(
            lambda department: department.company_id == company)
        return [('id', 'in', department.ids)]

    department_id = fields.Many2one('res.department', string='Department', store=True,required=False,readonly=True,tracking=True,
                                help='Leave this field empty if this account is'
                                     ' shared between all departmentes')
    

    name = fields.Char('Reference No',required=True,tracking = True,default=lambda self: _("New") ,readonly=True,copy=False)
    company_no = fields.Many2one("fleet.vehicle",string="Fleet",required=True)
    request_date = fields.Date('Request Date',tracking = True, default= fields.Date.today(),required=True)
    working_days = fields.Float('Working Days',copy=False)
    finish_date = fields.Date('Job Finish Date',tracking = True,readonly=True)
    request_time = fields.Float('Request Time',tracking = True)
    action_date = fields.Date('Action Date',tracking = True)
    action_time = fields.Float('Action Time',tracking = True)
    urgency_grade = fields.Selection([('a','A'),
                                      ('b','B'),
                                      ('c','C'),
                                      ('d','D'),
                                      ('e','E')],string="Urgency Grade")
    service_meter =  fields.Float("Service Meter")
    owner_name = fields.Many2one('fleet.owner',string="Owner Name",store=True)
    contact_person = fields.Many2one('hr.employee',string= 'Contact Person')
    contact_no = fields.Char(string="Work Mobile",store=True)
    partner_id = fields.Many2one('res.partner')
    street = fields.Text('Street',compute='get_partner_data')
    street2 = fields.Text('Street',compute='get_partner_data')
    township = fields.Char('Township')
    city = fields.Char('City',compute='get_partner_data')
    zip = fields.Char('Zip',compute='get_partner_data')
    region_id = fields.Many2one('res.country.state',string="Region",required=False)
    repair_sequence_prefix_id = fields.Many2one('repair.sequence.prefix', string="Prefix",tracking=True)
    full_region = fields.Char("Remark")
    state_id = fields.Many2one('res.country.state',string="State",compute='get_partner_data')
    country_id = fields.Many2one('res.country',compute='get_partner_data')
    request_type_id = fields.Many2one('repair.request.type',string='Request Type',required=False,domain=[('repair_type','in',['i','e'])])
    state = fields.Selection([
        ('draft','Draft'),
        ('submit','Submit'),
        ('repair', 'Processing'),
        ('approve','Accepted'),
        ('close','Closed'),
        ('reject','Rejected'),
        ],string='State',default='draft', tracking=True)
    repair_object_type = fields.Selection([
        ('fleet','Fleet'),
        ('repair_product','Repair Product')
    ],string="Repair Object",default='fleet')
    
    company_id = fields.Many2one('res.company', string='Company', required=True,
        default=lambda self: self.env.company)
    branch_id = fields.Many2one('res.branch', string='Branch', store=True,
                                readonly=False,
                                default=_get_default_branch,
                                domain=_get_branch_domain)
    engine_serial = fields.Char('Engine No',store=True)
    engine_models = fields.Many2one('fleet.engine.model',string="Engine Model")
    mc_models = fields.Many2one('fleet.vehicle.model', 'Model',
        tracking=True)
    # mc_models = fields.Char('MC Model.',store=True)
    mc_serial = fields.Char('MC Serial.',store=True)
    smu = fields.Char("SMU",store=True)
    mc_problem = fields.Char("MC Problem")
    repair_job_code_id = fields.Many2one("repair.job.code",string="Repair Job Code",tracking=True,copy=False)
    owner_type = fields.Selection([
        ('family','Family'),
        ('internal','Internal'),
        ('external','External')
    ],string="Owner Type", related='company_no.owner_type')
    repair_order_id = fields.Many2one('repair.order',string="Repair Order",copy=False)
    so_id = fields.Many2many('sale.order',copy=False)
    adjust_id = fields.Many2many('stock.inventory.adjustment',copy=False)
    requisition_ids = fields.Many2many("part.requisition",readonly=True,copy=False)
    move_ids = fields.Many2many("account.move",readonly=True,copy=False)
    repair_type = fields.Selection([
        ('n','None'),
        ('i','Internal'),
        ('e','External')     
        ],string='Repair Type',related='request_type_id.repair_type',store=True)
    request_state = fields.Selection([
        ('draft','Draft'),
        ('submit','Waiting'),
        ('repair', 'Processing'),
        ('approve','Finished'),
        ('reject','Rejected'),
        ],string='Request State',default='draft',copy=False)
    order_state = fields.Selection([
        ('draft', 'Waiting'),
        ('approve', 'Approved'),
        ('repair', 'Processing'),
        ('done', 'Completed'),
        ('close', 'Closed'),
        ('reject', 'Rejected'),
    ],string="Job Order State", copy = False, related = 'repair_order_id.order_state')
    part_state = fields.Selection([
        ('request','Requesting'),
        ('wait','Waiting'),
        ('done','Finished'),        
    ],string="Part State",copy=False)
    accounting_status = fields.Boolean(string="Accounting Status", compute="_compute_accounting_status")
    invoice_state = fields.Selection([
        ('wait','Waiting'),
        ('done','Finished'),
    ],string="Invoicing State", copy=False)
    payment_state = fields.Selection([
        ('wait','Waiting'),
        ('done','Finished'),
    ],string="Payment State", copy=False)  
    allow_expense = fields.Boolean("Expense",default=False,copy=False)  
    
    def action_prepare_requisition(self):
        return {
            'name': _('Parts Requisition'),
            'view_mode': 'form',
            'res_model': 'part.requisition',
            'type': 'ir.actions.act_window',
            'target': 'new',
            'context':  {
                            'default_job_request_id':self.id,
                            'default_branch_id':self.branch_id and self.branch_id.id or False,
                            'default_department_id':self.department_id and self.department_id.id or False,
                            'default_company_no':self.company_no and self.company_no.id or False,
                            'default_pricelist_id':self.partner_id and self.partner_id.property_product_pricelist.id or False,
                            'default_repair_object_type':self.repair_object_type,
                            'default_owner_name':self.owner_name and self.owner_name.id or False,
                            'default_smu':self.smu or False,
                        },
        }

    def action_create_bill(self):
        return {
            'name': _('Bills'),
            'view_mode': 'form',
            'res_model': 'account.move',
            'type': 'ir.actions.act_window',
            'target': 'current',
            'context': {
                            'default_job_request_id':self.id,
                            'default_branch_id':self.branch_id and self.branch_id.id or False,
                            'default_department_id':self.department_id and self.department_id.id or False,
                            'default_move_type':'in_invoice'
                        },
        }
    

    def action_open_so_orders_adjustments(self):
        adjust_ids = [adj_id.id for req_id in self.requisition_ids for adj_id in req_id.adjust_id]
        if adjust_ids:
            return {
                'name': _('Adjustments'),
                'view_mode': 'tree,form',
                'res_model': 'stock.inventory.adjustment',
                'view_id': False,
                'type': 'ir.actions.act_window',  
                'domain': [('id', 'in',adjust_ids)],              
            } 
        else:                    
            return {
                'name': _('Sale Orders'),
                'view_mode': 'tree,form',
                'res_model': 'sale.order',
                'view_id': False,
                'type': 'ir.actions.act_window',  
                'domain': [('id', 'in',self.so_id.ids)],              
            } 

    def action_open_orders(self):
        job_order_ids =  self.env['repair.order'].search([('repair_request_id','=',self.id)]).ids if self.repair_job_code_id else self.repair_order_id.ids
        return {
            'name': _('Job Order'),
            'view_mode': 'tree,form',
            'res_model': 'repair.order',
            'view_id': False,
            'type': 'ir.actions.act_window',  
            'domain': [('id', 'in',job_order_ids)],              
        } 
    
    def action_open_part_req(self):
        return {
            'name': _('Part Requisitions'),
            'view_mode': 'tree,form',
            'res_model': 'part.requisition',
            'view_id': False,
            'type': 'ir.actions.act_window',  
            'domain': [('id', 'in',self.requisition_ids.ids)],              
        } 
            
    def action_open_move_ids(self):
        return {
            'name': _('Bills'),
            'view_mode': 'tree,form',
            'res_model': 'account.move',
            'view_id': False,
            'type': 'ir.actions.act_window',  
            'domain': [('id', 'in',self.move_ids.ids)],              
        } 


    @api.onchange('repair_job_code_id')
    def get_fleet_by_repair_job_code_id(self):
        for rec in self:
            if rec.repair_job_code_id:
                if rec.repair_job_code_id.repair_request_id and rec.repair_job_code_id.repair_request_id.id != rec.id and rec.repair_job_code_id.repair_request_id.state != 'reject':
                    raise ValidationError(f"Job Request {rec.repair_job_code_id.repair_request_id.name} is already used the job code {rec.repair_job_code_id.name}!!")
                rec.repair_job_code_id.repair_request_id = rec
                rec.company_no = rec.repair_job_code_id.fleet_id
            else:
                rec.company_no = False
                
    @api.constrains("repair_job_code_id")
    def _save_job_code_with_repair_request(self):
        for res in self:
            res.repair_job_code_id.write({"repair_request_id":res.id})                

    @api.onchange('company_no')
    def get_machine_data(self):
        for rec in self:
            if rec.company_no:
                rec.engine_models = rec.company_no.engine_model_id and rec.company_no.engine_model_id.id or False
                rec.engine_serial = rec.company_no.engine_serial
                rec.mc_models = rec.company_no.model_id and rec.company_no.model_id.id or False
                rec.mc_serial = rec.company_no.mc_serial
                rec.smu = rec.company_no.smu
                rec.owner_name = rec.company_no.owner_id and rec.company_no.owner_id.id or False
                rec.partner_id = rec.company_no.partner_id and rec.company_no.partner_id.id or False
            else:
                rec.engine_models = rec.engine_serial = rec.mc_models = rec.partner_id = rec.mc_serial = rec.smu = rec.owner_name = rec.mc_problem = rec.owner_type = False
    
    @api.onchange('contact_person')
    def get_contact_work_mobile(self):
        for res in self:
            res.contact_no = res.contact_person.mobile_phone

    @api.onchange('repair_object_type')
    def onchange_repair_request_type(self):
        for res in self:
            res.company_no = False
            if res.repair_object_type == 'fleet':
                return {"domain": {"company_no":[('type','=','fleet')]}}   
            else:
                return {"domain": {"company_no":[('type','=','repair_product')]}}       

    @api.constrains('mc_serial','smu','engine_serial','engine_models','mc_models','smu','owner_name')
    def get_machine(self):
        if self.company_no:
            if not self.company_no.mc_serial:
                self.company_no.mc_serial = self.mc_serial
            if not self.company_no.engine_serial:
                self.company_no.engine_serial = self.engine_serial
            if not self.company_no.engine_model_id:
                self.company_no.engine_model_id = self.engine_models and self.engine_models.id or False
            if not self.company_no.model_id:
                self.company_no.model_id = self.mc_models and self.mc_models.id or False
            if not self.company_no.smu:
                self.company_no.smu = self.smu
            if not self.company_no.owner_id:
                self.company_no.owner_id = self.owner_name and self.owner_name.id or False
                
    @api.constrains("repair_job_code_id","company_no")
    def _check_job_code_and_fleet(self):
        for res in self:
            if not res.company_no:
                raise UserError("Fleet is required!!")
            elif res.company_no and res.repair_job_code_id and res.repair_job_code_id.fleet_id and res.company_no.id != res.repair_job_code_id.fleet_id.id:
                raise UserError("Fleet of repair job code and fleet of repair request are not the same!!")
                
    @api.onchange('partner_id')
    def get_partner_data(self):
        for rec in self:
            street = street2 = city = zip = ''
            state_id = country_id = None
            if rec.partner_id:
                street = rec.partner_id.street
                street2 = rec.partner_id.street2
                city = rec.partner_id.city
                zip = rec.partner_id.zip
                state_id = rec.partner_id.state_id.id
                country_id = rec.partner_id.country_id.id
            rec.street = street
            rec.street2 = street2
            rec.city = city
            rec.zip = zip
            rec.state_id = state_id
            rec.country_id = country_id

    def _compute_accounting_status(self):
        for repair_request in self:
            if (repair_request.requisition_ids and repair_request.requisition_ids.so_id) or (repair_request.repair_order_id and repair_request.repair_order_id.repair_so_id):
                parts_so = [all(invoice.state == 'posted' for invoice in sale_id.invoice_ids) if sale_id.invoice_status == 'invoiced' else False for sale_id in repair_request.requisition_ids.so_id if sale_id.state != 'cancel']
                order_so = [all(invoice.state == 'posted' for invoice in sale_id.invoice_ids) if sale_id.invoice_status == 'invoiced' else False for sale_id in repair_request.repair_order_id.repair_so_id if sale_id.state != 'cancel']
                if len(parts_so) >= 1 and len(order_so) >= 1:
                    repair_request.invoice_state = 'done'  if all(parts_so) and all(order_so) else 'wait'
                else:
                    if len(parts_so) >= 1:
                        repair_request.invoice_state = 'done' if all(parts_so) else 'wait'
                    elif len(order_so) >= 1:
                        repair_request.invoice_state = 'done' if all(order_so) else 'wait'
                    else:
                        repair_request.invoice_state = None
            if (repair_request.requisition_ids and repair_request.requisition_ids.so_id and repair_request.requisition_ids.so_id.invoice_ids ) or (repair_request.repair_order_id and repair_request.repair_order_id.repair_so_id and repair_request.repair_order_id.repair_so_id.invoice_ids):
                parts_so = [invoice_id.payment_state == 'paid' for sale_id  in repair_request.requisition_ids.so_id for invoice_id in sale_id.invoice_ids if invoice_id.state != 'cancel']
                order_so = [invoice_id.payment_state == 'paid' for sale_id  in repair_request.repair_order_id.repair_so_id for invoice_id in sale_id.invoice_ids if invoice_id.state != 'cancel']              
                if len(parts_so) >= 1 and len(order_so) >= 1:
                    repair_request.payment_state = 'done' if all(parts_so) and all(order_so) else 'wait'
                else:
                    if len(parts_so) >= 1:
                        repair_request.payment_state = 'done' if all(parts_so) else 'wait'
                    elif len(order_so) >= 1:
                        repair_request.payment_state = 'done' if all(order_so) else 'wait'
                    else:
                        repair_request.payment_state = None
            if repair_request.repair_order_id:
                if repair_request.repair_order_id.start_date and repair_request.repair_order_id.state not in ['done', 'reject', 'cancel']:
                    repair_request.working_days = (date.today() - repair_request.repair_order_id.start_date).days
                elif repair_request.repair_order_id.finish_date and repair_request.repair_order_id.start_date:
                    repair_request.working_days = (repair_request.repair_order_id.finish_date - repair_request.repair_order_id.start_date).days
                else:
                    repair_request.working_days = None
            repair_request.accounting_status = True


    # def action_submit(self):
    #     sequence = self.env['sequence.model']
    #     if not self.request_type_id:
    #         raise ValidationError(_("Request Type should not be blank"))
    #     date,seq = generate_code.generate_code(sequence,self,self.branch_id,self.company_id,self.request_date,None,None,self.request_type_id.id)
    #     if date and seq:
    #         self.name = self.request_type_id.code+'-JR-MRS-'+str(date)+'-'+str(seq)
    #     else:
    #         raise ValidationError(_("Sequence Not Found.Please Contact to the Administrator."))
    #     self.write({'state':'submit', 'request_state':'submit'})
    
    def action_submit(self):
        sequence = self.env['sequence.model']
        name = generate_code.generate_code(sequence,self,None,self.company_id,self.request_date,None,None)
        if not name:
            raise ValidationError(_("Sequence Not Found.Please Contact to the Administrator."))
        self.name = name
        self.write({'state':'submit', 'request_state':'submit'})    


    def action_accept(self):
        # # remove auto craeate repair order feature due to SSYK CME
        # if self.request_type_id.repair_type != 'e':
        #     values_dct = {
        #         'repair_request_id':self.id,
        #         'repair_object_type':self.repair_object_type,
        #         'company_id':self.company_id and self.company_id.id or False,
        #         'branch_id':self.branch_id and self.branch_id.id or False,
        #         'department_id':self.department_id and self.department_id.id or False,
        #         'region_id':self.region_id and self.region_id.id or False,
        #         'partner_id':self.partner_id and self.partner_id.id or False,
        #         'company_no':self.company_no and self.company_no.id or False,
        #         'request_date':self.request_date,
        #         'request_time':self.request_time,
        #         'mc_serial':self.mc_serial,
        #         'mc_models':self.mc_models and self.mc_models.id or False,
        #         'owner_type':self.company_no.owner_type or False,
        #         'mc_problem':self.mc_problem,
        #         'engine_serial':self.engine_serial,
        #         'engine_models':self.engine_models and self.engine_models.id or False,
        #         'smu':self.smu,
        #         'owner_name':self.owner_name and self.owner_name.id or False,
        #         'repair_sequence_prefix_id':self.repair_sequence_prefix_id and self.repair_sequence_prefix_id.id or False,
        #         'full_region':self.full_region,
        #     }
        #     if hasattr(self, 'project_id'):
        #         values_dct['project_id'] = self.project_id.id or False
        #     repair_order_id = self.env['repair.order'].create(values_dct)
        #     self.write({'repair_order_id':repair_order_id.id})
        if not self.repair_job_code_id:
            raise ValidationError("Job Code is required!!")
        self.write({'state':'approve', 'request_state':'approve'})

    def action_reject(self):
        self.write({'state':'reject','request_state':'reject'})
    
    def action_repair(self):
        self.write({'state':'repair','request_state':'repair'})

    def action_wait(self):
        self.write({"part_state":'wait'})

    def action_close(self):
        self.write({'state':'close'})    

    def unlink(self):
        for rec in self:
            if rec.state != 'draft':
                raise UserError("Are you doing something fraudly! Why do you want to delete some records?? 🤔 ")
        return super().unlink()

class RepairRequestType(models.Model):
    _name = 'repair.request.type'

    repair_type = fields.Selection([
        ('n','None'),
        ('i','Internal'),
        ('e','External')     
        ],string='Repair Type',required=True)
    name = fields.Char(related='request_type')
    request_type = fields.Char("Request Type")
    code = fields.Char('Code')


class CountryState(models.Model):
    _description = "Country state"
    _inherit = 'res.country.state'


    region_code = fields.Char(string='Region Code', help='The region code.')
    
class CustomizeSequence(models.Model):
    _inherit = 'sequence.model'
    
    request_type_id = fields.Many2one('repair.request.type',string='Repair Type')
    repair_sequence_prefix_id = fields.Many2one('repair.sequence.prefix',string='Repair Sequence Prefix')
    
class RepairJobCode(models.Model):
    _inherit = "repair.job.code"
    
    repair_request_id = fields.Many2one('repair.request',string='Job Request No',tracking=True)