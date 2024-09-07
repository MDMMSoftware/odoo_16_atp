from datetime import datetime,timedelta
from odoo import fields, models, Command ,api, _
from odoo.exceptions import UserError
from odoo.exceptions import ValidationError
from ...generate_code import generate_code

class RepairServiceType(models.Model):
    _name = 'repair.service.type'
    _description = "Repair Type - External"

    name = fields.Char("Name")
    company_id = fields.Many2one("res.company","Company",default=lambda self:self.env.company,required=True)
    is_default = fields.Boolean("Is Default?",default=False)

    @api.constrains('name')
    def _check_only_one_default_field(self):
        default_true_records = self.search([('is_default', '=', True),('company_id','=',self.company_id.id)])
        if default_true_records and len(default_true_records) > 1:
            raise UserError("Only one default true value is allowed!!!")

class CustomerReqForm(models.Model):
    _name = "customer.request.form"
    _description = "Customer Request"
    _inherit = ['mail.thread']
    _order = "reception_date desc"
    
    def _get_branch_domain(self):
        """methode to get branch domain"""
        company = self.env.company
        branch_ids = self.env.user.branch_ids
        branch = branch_ids.filtered(
            lambda branch: branch.company_id == company)
        return [('id', 'in', branch.ids)]
    
    def _get_default_repair_service_type(self):
        default_service_type = self.env['repair.service.type'].search([('is_default','=',True)])
        return default_service_type and default_service_type[0] or False
    
    name = fields.Char('Reference No',required=True,tracking = True,default=lambda self: _("New") ,readonly=True,copy=False)
    received_date = fields.Datetime(string="Received Date",default=datetime.now(),required=False, tracking=True)
    promise_date = fields.Datetime(string="Promised Date",required=True, tracking=True)
    issued_date = fields.Datetime(string="Issued Date",required=False,default=False)
    estimate_time = fields.Float(string="Estimate Time", tracking=True,compute="_calculate_estimate_time",store=True)
    reception_date = fields.Datetime(string="Reception Date",default=False,readonly=False, tracking=True)
    request_type = fields.Selection([('wait','Wait'),('reserve','Reservation')],string="Request Type",tracking=True)
    pic = fields.Many2one('hr.employee',required=True,tracking=True,string="Service Advisor")
    repair_service_type_id = fields.Many2one("repair.service.type",default=_get_default_repair_service_type,string="Service Type")
    mileage = fields.Float("Mileage / KM",tracking=True,default=False)
    customer_request = fields.Text("Customer Request",tracking=True)
    company_id = fields.Many2one("res.company","Company",default=lambda self:self.env.company)
    state = fields.Selection([('draft','Draft'),('approve','Approved'),('reject','Rejected')],string="Request",tracking=True,readonly=True,default='draft')
    quotation_id = fields.Many2many("request.quotation",copy=False)
    fleet_id = fields.Many2one("fleet.vehicle",string="Fleet",required=True,tracking=True,domain=[("type", "=", "fleet")])
    brand_id = fields.Many2one("fleet.vehicle.model.brand",string="Brand",related="fleet_id.brand_id")
    model_id = fields.Many2one("fleet.vehicle.model",string="Model",related="fleet_id.model_id")
    vin_sn = fields.Char("Chassis Number",related="fleet_id.vin_sn")
    customer = fields.Many2one("res.partner",string="Customer Name",required=True,tracking=True,domain=[('company_id','=',company_id)])
    phone = fields.Char("Cus. Phone")
    branch_id = fields.Many2one('res.branch',string="Branch",store=True,required=True,domain=_get_branch_domain,default=lambda x:x.env.user.branch_id or False)
    popular_job = fields.Many2many('product.product',domain="[('detailed_type', '=', 'service')]")
    description = fields.Text("Description",tracking=True,readonly=True)
    compute_repair_status = fields.Boolean("Computer",compute="_compute_repair_status")
    quotation_state = fields.Selection(string="Quotation",selection=[('draft','Draft'),('confirm','Finished')])
    order_state = fields.Selection(string="Job Order",selection=[('draft','Pending'),('job_start','Received'),('progress','Processing'),('finish','Waiting QC'),('work_in_progress','WIP'),('qc_check','QC Passed'),('job_close','Finished'),('cancel','Cancelled')])
    part_state = fields.Selection(string="Part",selection=[('draft','Waiting'),('done','Done')],default=None)
    invoice_state = fields.Selection(string="Invoice",selection=[('waiting','Waiting Invoice'),('draft','Draft'),('posted','Finished'),('cancel','Cancelled')])
    payment_state = fields.Selection(string="Payment",selection=[('in_payment','Waiting'),('partial','Waiting'),('not_paid','Waiting'),('paid','Finished'),('reversed','Waiting'),('invoicing_legacy','Waiting')])
    is_late_issued = fields.Boolean(compute='_compute_is_late_issued',default=False,string="Is Late Issued?")

    # @api.depends('issued_date', 'promise_date')
    def _compute_is_late_issued(self):
        for record in self:
            is_late_issued = (record.issued_date - record.promise_date) > timedelta(days=1) if record.issued_date and record.promise_date else False
            record.sudo().write({"is_late_issued":is_late_issued})
    
    @api.constrains('popular_job','customer_request')
    def check_customer_request(self):
        self.description = ""
        if not self.popular_job:
            self.description = self.customer_request
        else:
            self.description = self.customer_request + ' / ' + ' / '.join(self.popular_job.mapped('name')) if self.customer_request and self.customer_request.strip() != '' else ' / '.join(self.popular_job.mapped('name'))

    @api.constrains('mileage')
    def check_recalculate_mileage(self):
        for res in self:
            if res.quotation_id:
                res.quotation_id.mileage = res.mileage
                for job_order_id in res.quotation_id.job_order_ids:
                    job_order_id.mileage = res.mileage   
    
    @api.onchange('customer')
    def _onchange_customer(self):
        if self.customer:
            if self.customer.partner_type != 'customer':
                raise UserError("Only Customer Types are allowed!!!")
            if self.fleet_id and self.fleet_id.id not in self.customer.fleet_ids.ids:
                self.fleet_id = False
            if self.customer.phone:
                self.phone = self.customer.phone
            if self.customer.fleet_ids:
                return {"domain": {"fleet_id":[('id','in',self.customer.fleet_ids.ids)]}}
            return {"domain": {"fleet_id":[('id','=',-1)]}}
        return {"domain": {"fleet_id":[]}}
        
    @api.onchange('fleet_id')
    def _onchange_fleet_id(self):
        branch_id = self.branch_id.id if self.branch_id else (self.env.user.branch_id and self.env.user.branch_id.id) or False        
        if self.fleet_id:
            if self.customer and self.customer.id not in self.fleet_id.partner_ids.ids:
                self.customer = False
            if self.fleet_id.partner_ids:
                return {"domain": {"customer":[('id','in',self.fleet_id.partner_ids.ids),('partner_type','=','customer')]}}
            return {"domain": {"customer":[('id','=',-1),('partner_type','=','customer')]}}
        return {"domain": {"customer":['&',('partner_type','=','customer'),'|',('branch_id','=',branch_id),('branch_id','=',False)]}}     
    
    def _compute_repair_status(self):
        for rec in self:
            if rec.quotation_id and rec.quotation_id.picking_ids:
                part_state = "done" if all([move_id.product_uom_qty == move_id.quantity_done for picking_id in rec.quotation_id.picking_ids for move_id in picking_id.move_ids if picking_id.state != 'cancel']) else "draft"
            else:
                part_state = False
            if rec.quotation_id and rec.quotation_id.move_id and rec.quotation_id.move_id.state in ('draft','posted','cancel'):
                invoice_state = rec.quotation_id.move_id.state
            elif rec.quotation_id and rec.quotation_id.state == 'confirm':
                invoice_state = 'waiting'
            else:
                invoice_state = False      
            rec.sudo().write({
                "part_state": part_state,
                "invoice_state": invoice_state,
                "payment_state": rec.quotation_id.move_id.payment_state,
                "compute_repair_status": True
            })
    
    def action_open_request_quotation(self):
        return {
            'name': _('Quotations'),
            'view_mode': 'tree,form',
            'res_model': 'request.quotation',
            'view_id': False,
            'type': 'ir.actions.act_window',  
            'domain': [('id', 'in',self.quotation_id.ids)],              
        } 
        
    def action_approve(self):
        if self.mileage <= 0.0:
            raise UserError("Mileage must be greater than zero!!")
        if not self.phone or self.phone.strip() == "":
            raise UserError("Phone Number is required for to accept customer request..")
        if not self.name or self.name=='New':
            name = False
            if not self.reception_date:
                raise ValidationError(_("Please insert Date"))
            sequence = self.env['sequence.model']
            name = generate_code.generate_code(sequence,self,self.branch_id,self.company_id,self.reception_date,None,None)
            if not name:
                raise ValidationError(_("Sequence Not Found.Please Contact to the Administrator."))
            self.write({'name':name})
        if not self.quotation_id:
            pricelist_id = self.customer and self.customer.property_product_pricelist
            quotation_id  = self.env['request.quotation'].create({
                'customer':self.customer and self.customer.id or False,
                'pricelist_id':pricelist_id and pricelist_id.id or False,
                'mileage':self.mileage,
                'pic':self.pic and self.pic.id or False,
                'fleet_id':self.fleet_id and self.fleet_id.id or False,
                'customer_order_no':self.description,
                'branch_id':self.branch_id and self.branch_id.id or False,
                'request_id':self.id,
                'job_lines':[
                    Command.create({
                        'job_code':each_job.id,
                        'job_desc':each_job.name,
                        'job_type_id':each_job.group_class_id.id,
                        'qty':1.0,
                        'from_popular':True,
                    }) for each_job in self.popular_job
                ]
            })
            self.quotation_state = 'draft'
            self.write({'quotation_id':[(4,quotation_id.id)]})
        else:
            self.quotation_id.write({
                'customer':self.customer and self.customer.id or False,
                'pricelist_id':self.customer and self.customer.property_product_pricelist and self.customer.property_product_pricelist.id or False,
                'mileage':self.mileage,
                'pic':self.pic and self.pic.id or False,
                'fleet_id':self.fleet_id and self.fleet_id.id or False,
                'customer_order_no':self.description,
                'branch_id':self.branch_id and self.branch_id.id or False,
                'request_id':self.id,
            })
            for each_job in self.popular_job:
                alredy_existed = self.quotation_id.job_lines.filtered(lambda x:x.from_popular == True and x.job_code.id == each_job.id )
                if not alredy_existed:
                    service_data_line = self.env['service.data'].create({'job_code':each_job.id,'job_desc':each_job.name,'job_type_id':each_job.group_class_id.id,'from_popular':True,'qty':1.0})
                    self.quotation_id.write({"job_lines":[4,service_data_line.id]})
            for picking_id in self.quotation_id.picking_ids:
                picking_id.write({
                    "partner_id":self.customer and self.customer.id or False,
                    "fleet_id":self.fleet_id and self.fleet_id.id or False,
                    'branch_id':self.branch_id and self.branch_id.id or False,
                })
        self.state = 'approve'
        
    def action_reset_to_draft(self):
        if self.quotation_id:
            if self.quotation_id.state=='invoiced':
                raise UserError(_("You can't reset to draft if your quotation is invoiced"))
        self.state = 'draft'
        
    def action_reject(self):
        for res in self:
            if res.quotation_id and  res.quotation_id.state != 'cancel':
                raise UserError("You can't cancel a customer request if the quotation is not in cancel state!!")
            res.state = 'reject'
    
    @api.depends('reception_date','promise_date')
    def _calculate_estimate_time(self):
        if self.reception_date and self.promise_date:
            if self.promise_date<self.reception_date:
                raise UserError(_("Promise Date should be greater than Received Date"))
            else:
                total_sec = (self.promise_date-self.reception_date).days*24+(self.promise_date-self.reception_date).seconds/3600
                self.estimate_time = round(total_sec,2)