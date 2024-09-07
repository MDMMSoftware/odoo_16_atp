from odoo import models, fields, api, _
from datetime import datetime, timedelta, date
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT
from odoo.exceptions import UserError, RedirectWarning, ValidationError
from ...generate_code import generate_code


class RepairOrder(models.Model):
    _name = 'repair.order'
    _description = 'Job Order'
    _inherit = ['mail.thread']

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

    department_id = fields.Many2one('res.department', string='Department', store=True,required=False,readonly=False,tracking=True,
                                help='Leave this field empty if this account is'
                                     ' shared between all departmentes')

    name = fields.Char('Reference No',required=True,tracking = True,default=lambda self: _("New") ,readonly=True,copy=False)
    repair_job_code_id = fields.Many2one("repair.job.code",string="Repair Job Code",tracking=True,copy=False)
    repair_request_id = fields.Many2one('repair.request',string='Job Request No',tracking=True)
    repair_request_ids = fields.Many2many('repair.request',string='Job Requests\' No',compute=False)
    internal_ref = fields.Char("Internal Ref")
    request_date = fields.Date('Request Date',tracking = True)
    request_time = fields.Float('Request Time',tracking = True)
    start_time = fields.Float('Start Time',tracking = True)
    finish_time = fields.Float('Finish Time',tracking = True)
    scheduled_date_from = fields.Date('From')
    scheduled_date_to = fields.Date('To')
    finish_date = fields.Date('Job Finish Date',tracking = True)
    start_date = fields.Date('Job Start Date',tracking = True)
    company_id = fields.Many2one('res.company', string='Company', required=True,
        default=lambda self: self.env.company)
    company_no = fields.Many2one("fleet.vehicle",string="Fleet",required=True)
    owner_name = fields.Many2one('fleet.owner',string="Owner Name",store=True)
    engine_serial = fields.Char('Engine No',store=True)
    engine_models = fields.Many2one('fleet.engine.model',string="Engine Model")
    mc_models = fields.Many2one('fleet.vehicle.model', 'Model',
        tracking=True)
    #  s = fields.Char('MC Model.',store=True)
    mc_serial = fields.Char('MC Serial.',store=True,tracking=True)
    smu = fields.Char("SMU",store=True,tracking=True)
    mc_problem = fields.Char('MC Problem')
    owner_type = fields.Selection([
        ('family','Family'),
        ('internal','Internal'),
        ('external','External')
    ],string="Owner Type")
    partner_id = fields.Many2one('res.partner',tracking=True)
    street = fields.Text('Street',compute='get_partner_data')
    street2 = fields.Text('Street',compute='get_partner_data')
    township = fields.Char('Township')
    city = fields.Char('City',compute='get_partner_data')
    zip = fields.Char('Zip',compute='get_partner_data')
    region_id = fields.Many2one('res.country.state',string="Region",required=True)
    full_region = fields.Char("Remark")
    repair_sequence_prefix_id = fields.Many2one('repair.sequence.prefix', string="Prefix",tracking=True)
    state_id = fields.Many2one('res.country.state',string="State",compute='get_partner_data')
    country_id = fields.Many2one('res.country',compute='get_partner_data')
    request_type_id = fields.Many2one('repair.request.type',string='Repair Type',domain=[('repair_type','in',['n'])])
    branch_id = fields.Many2one('res.branch', string='Branch', store=True,
                                readonly=False,
                                default=_get_default_branch,
                                domain=_get_branch_domain,tracking=True)
    requisition_ids = fields.Many2many("part.requisition",readonly=True)
    so_id = fields.Many2many('sale.order')
    repair_so_id = fields.Many2one('sale.order',readonly=True)
    adjust_id = fields.Many2many('stock.inventory.adjustment')
    schedule_ids = fields.One2many('repair.work.schedule','repair_id')
    move_ids = fields.Many2many("account.move",readonly=True)
    location_id = fields.Many2one('stock.location')
    pricelist_id = fields.Many2one(comodel_name='product.pricelist',string="Pricelist")    
    repair_object_type = fields.Selection([
        ('fleet','Fleet'),
        ('repair_product','Repair Product')
    ],string="Repair Object",default='fleet')
    
    state = fields.Selection([
        ('draft', 'Draft'),
        ('approve','Approved'),
        ('repair', 'Processing'),
        ('done', 'Completed'),
        ('close', 'Closed'),
        ('reject', 'Rejected'),
        ], string='Status', readonly=True, copy=False, index=True, default='draft',tracking=True) 

    order_state = fields.Selection([
        ('draft', 'Waiting'),
        ('approve', 'Approved'),
        ('repair', 'Processing'),
        ('done', 'Completed'),
        ('close', 'Closed'),
        ('reject', 'Rejected'),
    ],string="Order State", copy = False, default='draft')    

    part_state = fields.Selection([
        ('request','Requesting'),
        ('wait','Waiting'),
        ('done','Finished'),
    ],string="Part State",related="repair_request_id.part_state", copy=False)           
    
    def action_prepare_requisition(self):
        return {
            'name': _('Parts Requisition'),
            'view_mode': 'form',
            'res_model': 'part.requisition',
            'type': 'ir.actions.act_window',
            'target': 'new',
            'context':  {
                            'default_job_order_id':self.id,
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
            'context': {'default_job_order_id':self.id,'default_branch_id':self.branch_id and self.branch_id.id or False,'default_department_id':self.department_id and self.department_id.id or False,'default_move_type':'in_invoice'},
        }
    
    def action_open_so_orders(self):
        return {
            'name': _('Sale Orders'),
            'view_mode': 'tree,form',
            'res_model': 'sale.order',
            'view_id': False,
            'type': 'ir.actions.act_window',  
            'domain': [('id', 'in',[self.repair_so_id.id])],              
        }        

    # @api.depends('repair_request_id')
    # def get_domain_request_ids(self):
    #     res = []
    #     if self.partner_id and self.company_no:
    #         res = self.env['repair.request'].search([('repair_order_id','=',None),('company_no','=',self.company_no.id),('partner_id','=',self.partner_id.id)]).ids
    #     elif self.company_no and not self.partner_id:
    #         res = self.env['repair.request'].search([('repair_order_id','=',None),('company_no','=',self.company_no.id),('partner_id','=',None)]).ids
    #     self.repair_request_ids = [(6,0,res)]
    
    @api.onchange('repair_job_code_id')
    def get_fleet_by_repair_job_code_id(self):
        for rec in self:
            if rec.repair_job_code_id:
                if rec.repair_job_code_id.repair_order_id and rec.repair_job_code_id.repair_order_id.id != rec.id and rec.repair_job_code_id.repair_order_id.state != 'reject':
                    raise ValidationError(f"Job Order {rec.repair_job_code_id.repair_order_id.name} is already used the job code {rec.repair_job_code_id.name}!!")                
                rec.company_no = rec.repair_job_code_id.fleet_id
                rec.repair_request_id = rec.repair_job_code_id.repair_request_id
                rec.request_date = rec.repair_job_code_id.repair_request_id.request_date
            else:
                rec.company_no = False
                
    @api.constrains("repair_job_code_id","company_no")
    def _save_job_code_with_repair_order(self):
        for res in self:
            if not res.company_no:
                raise UserError("Fleet is required!!")
            elif res.company_no:
                if res.repair_job_code_id and res.repair_job_code_id.fleet_id and res.company_no.id != res.repair_job_code_id.fleet_id.id:
                    raise UserError("Fleet of repair job code and fleet of repair request are not the same!!")
                res.engine_models = res.company_no.engine_model_id and res.company_no.engine_model_id.id or False
                res.engine_serial = res.company_no.engine_serial
                res.mc_models = res.company_no.model_id and res.company_no.model_id.id or False
                res.partner_id = res.company_no.partner_id and res.company_no.partner_id.id or False
                res.mc_serial = res.company_no.mc_serial
                res.smu = res.company_no.smu
                res.owner_name = res.company_no.owner_id and res.company_no.owner_id.id or False
                res.owner_type =  res.company_no.owner_type or False             
            if res.repair_job_code_id:
                if not res.repair_request_id:
                    res.repair_request_id = res.repair_job_code_id.repair_request_id
                res.repair_job_code_id.write({"repair_order_id":res.id})    

    @api.onchange('company_no')
    def get_machine_data(self):
        for rec in self:
            if rec.company_no:
                rec.engine_models = rec.company_no.engine_model_id and rec.company_no.engine_model_id.id or False
                rec.engine_serial = rec.company_no.engine_serial
                rec.mc_models = rec.company_no.model_id and rec.company_no.model_id.id or False
                rec.partner_id = rec.company_no.partner_id and rec.company_no.partner_id.id or False
                rec.mc_serial = rec.company_no.mc_serial
                rec.smu = rec.company_no.smu
                rec.owner_name = rec.company_no.owner_id and rec.company_no.owner_id.id or False
                rec.mc_problem =  ( rec.repair_request_id and rec.repair_request_id.mc_problem ) or False
                rec.owner_type =  rec.company_no.owner_type or False
            else:
                rec.engine_models = rec.engine_serial = rec.mc_models = rec.partner_id = rec.mc_serial = rec.smu = rec.owner_name = rec.mc_problem = rec.owner_type = False

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
                rec.pricelist_id = rec.partner_id.property_product_pricelist.id
            rec.street = street
            rec.street2 = street2
            rec.city = city
            rec.zip = zip
            rec.state_id = state_id
            rec.country_id = country_id

    @api.onchange('repair_object_type')
    def onchange_repair_request_type(self):
        for res in self:
            res.company_no = False
            if res.repair_object_type == 'fleet':
                return {"domain": {"company_no":[('type','=','fleet')]}}   
            else:
                return {"domain": {"company_no":[('type','=','repair_product')]}}                            

    # state changes buttons
    def action_approve(self):
        sequence = self.env['sequence.model']
        if not self.request_type_id:
            raise ValidationError(_("Request Type should not be blank"))
        if not self.repair_sequence_prefix_id:
            raise ValidationError(_("Repair Sequence Prefix shoud not be blank"))
        # date,seq = generate_code.generate_code(sequence,self,self.branch_id,self.company_id,self.request_date,None,None,self.request_type_id.id)
        date,seq = generate_code.generate_code(sequence,self,self.branch_id,self.company_id,self.request_date,None,None,self.repair_sequence_prefix_id.id)
        if date and seq:
            self.name = self.repair_sequence_prefix_id.name+str(date)+str(seq)+str(self.request_type_id.code)
        else:
            raise ValidationError(_("Sequence Not Found.Please Contact to the Administrator."))        
        self.state = self.order_state = 'approve'

    def action_reject(self):
        self.state = self.order_state ='reject'        


    def action_repair(self):
        if not self.repair_job_code_id:
            raise ValidationError("Repair Job Code is required!!")
        if not self.start_date or not self.start_time:
            raise UserError(_("Please add Job Start Date or Job Start Time"))
        self.state = self.order_state = 'repair'
        self.repair_request_id.write({"action_date":self.start_date,"action_time":self.start_time})

    def action_complete(self):
        if not self.finish_date:
            raise UserError(_("Please add Job Finish date"))
        if self.repair_request_id:
            self.repair_request_id.finish_date = self.finish_date        
        self.state = self.order_state  ='done'

    def unlink(self):
        for rec in self:
            if rec.state != 'draft':
                raise UserError("Are you doing something fraudly! Why do you want to delete some records?? 🤔 ")
        return super().unlink()

    def action_repaired(self):
        if not self.finish_date or not self.schedule_ids:
            raise UserError(_("Please add Working Schedule Lines"))
        elif self.partner_id and self.finish_date and self.request_type_id.code not in ['E','P']:
            if not self.location_id:
                raise UserError(_("Please add Location of Customer Details"))
            if not self.schedule_ids.filtered(lambda x:x.product_id):
                raise UserError(_("At least one product is required in schedules lines!!"))
            if self.schedule_ids.filtered(lambda self:self.product_id and self.amount <= 0.0):
                raise UserError(_("Amount of the product must be greater than zero"))
            order_line_from_bill = []
            if self.move_ids:
                first_bill_line = self.move_ids[0].invoice_line_ids[0]
                if first_bill_line:
                    sum_subtotal = sum([line.price_subtotal  for move in self.move_ids for line in move.invoice_line_ids])
                    order_line_from_bill = [(0,0, {
                        'product_id':first_bill_line.product_id.id,
                        'name':first_bill_line.product_id.name,
                        'product_uom_qty':1,
                        'price_unit': sum_subtotal + ( sum_subtotal * (10/100)),
                    })]
            order_line_fleet_or_repair_product_key = 'repair_object_id' if self.repair_object_type == 'repair_object' else 'fleet_id'
            so_id = self.env['sale.order'].create({'partner_id':self.partner_id.id,
                                                        'date_order':self.finish_date,
                                                       'location_id':self.location_id.id,
                                                       'warehouse_id':self.location_id.warehouse_id.id,
                                                       'branch_id':self.branch_id.id,
                                                       'department_id':self.department_id.id,
                                                       'repair_request_id':self.repair_request_id and self.repair_request_id.id or False,
                                                       'term_type': 'credit',
                                                       'job_order_id':self.id,
                                                        'order_line':[(0, 0, {
                                                                    'product_id': res.product_id.id,
                                                                    'name':res.product_id.name,
                                                                    'product_uom_qty': 1,
                                                                    'price_unit':res.amount,
                                                                    order_line_fleet_or_repair_product_key:self.company_no.id,
                                                                    'analytic_distribution':{self.company_no.analytic_fleet_id.id:100} if self.company_no.analytic_fleet_id.id else {},
                                                            }) for res in self.schedule_ids if res.product_id] + order_line_from_bill
                                                        })
            self.repair_so_id = so_id.id
            if self.repair_request_id:
                self.repair_request_id.so_id = [(4,so_id.id)]
        self.state = self.order_state ='close'
        
    def action_reopened_job_order(self):
        for res in self:
            if ( res.repair_so_id and res.repair_so_id.state == 'cancel' ) or not res.repair_so_id:
                if res.repair_so_id and res.repair_so_id.invoice_ids and any(state != 'cancel' for state in res.repair_so_id.invoice_ids.mapped('state')):
                    raise ValidationError("The invoice of sale order must be cancelled first..")
                res.repair_so_id = False
                res.state = res.order_state = 'done'
            else:
                raise ValidationError("As the sale order of job order is not in cancel state, you can't reopen the job order!!!")

    @api.constrains('repair_request_id')
    def check_repair_request_id(self):
        if self.repair_request_id:
            model = False
            if self.env.context.get('params'):
                model = self.env.context['params'].get('model') 
                if model:
                    if not self.repair_request_id.repair_order_id and model!='repair.request':
                        self.repair_request_id.repair_order_id = self.id
        else:
            exist = self.env['repair.request'].search([('repair_order_id','=',self.id)])
            if exist:
                exist.repair_order_id = None
             
            


class RepairWorkingSchedule(models.Model):
    _name = 'repair.work.schedule'

    date = fields.Date('Date')

    product_id = fields.Many2one('product.product',string="Job Code",domain="[('detailed_type', '=', 'service')]")
    product_name = fields.Char('Job Details',related='product_id.name')
    custom_category_id = fields.Many2one('custom.category',string='Job Type',related="product_id.custom_category_id")
    group_class_id = fields.Many2one('custom.group.class', string= 'System',related="product_id.group_class_id")
    custom_model_no_id = fields.Many2one('custom.model.no', string= 'Job Name',related="product_id.custom_model_no_id")    

    gp_leader_id = fields.Many2one('hr.employee',string= 'Leader')
    member_ids = fields.Many2many('hr.employee',string="Member")
    job_desc = fields.Char('Job Description')
    start_time = fields.Float('Start Time')
    end_time = fields.Float('End Time')
    duration = fields.Float('Total Hours')
    repair_id = fields.Many2one('repair.order','Repair ID')
    work_location = fields.Many2one('work.location')
    remark = fields.Char("Remark")

    service_group_id = fields.Many2one('service.group',string="Service Group")
    amount = fields.Float('Amount',default=0.0)

    @api.onchange('start_time','end_time')
    def set_duration(self):
        for rec in self:
            if rec.start_time and rec.end_time:
                rec.duration = abs((rec.start_time - rec.end_time))

    @api.onchange('product_id')
    def _onchange_product_id(self):
        if self.product_id:
            if self.repair_id.pricelist_id and self.repair_id.pricelist_id.item_ids and self.date:
                pricelist_items = self.repair_id.pricelist_id.item_ids.search([('product_tmpl_id','=',self.product_id.product_tmpl_id.id),('date_start','<=',self.date),('date_end','>=',self.date)],limit=1)
                if pricelist_items:
                    self.amount = pricelist_items.fixed_price
                else:
                    raise ValidationError("There is no price associated with working schedule date!!")
            else:
                raise ValidationError("Pricelist is not defined or Pricelist items are not defined or Working Schedule date is not defined!!")


class WorkLocation(models.Model):
    _name = "work.location"

    name = fields.Char()

class ServiceGroup(models.Model):
    _name = 'service.group'

    name =  fields.Char(string="Service Group")


class RepairSequencePrefix(models.Model):
    _description = "Repair Sequence Prefix"
    _name = 'repair.sequence.prefix'

    name = fields.Char("Prefix",tracking=True)

    _sql_constraints = [
        ('unqie_repair_sequence_prefix', 'unique(name)', 'Repair Sequence Prefix must be unique!!!')
    ]


# class CustomizeSequenceRepair(models.Model):
#     _inherit = 'sequence.model'

#     repair_sequence_prefix_id = fields.Many2one('repair.sequence.prefix',string='Repair Sequence Prefix')
#     request_type_id = fields.Many2one('repair.request.type',string='Repair Type')

class RepairJobCode(models.Model):
    _inherit = "repair.job.code"
    
    repair_order_id = fields.Many2one('repair.order',string="Repair Order",tracking=True)      