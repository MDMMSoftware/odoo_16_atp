import time
import datetime
from dateutil.relativedelta import relativedelta
from odoo import fields, models, api, _,Command
from odoo.exceptions import UserError
from odoo.exceptions import ValidationError
from odoo.tests import Form
from ...generate_code import generate_code


class RequestQuotation(models.Model):
    _name = "request.quotation"
    _description = "Request Quotation"
    _inherit = ['mail.thread']
    
    def _get_branch_domain(self):
        """methode to get branch domain"""
        company = self.env.company
        branch_ids = self.env.user.branch_ids
        branch = branch_ids.filtered(
            lambda branch: branch.company_id == company)
        return [('id', 'in', branch.ids)]
    
    def _default_pricelist_id(self):
        return self.env['product.pricelist'].search([
            '|', ('company_id', '=', False),
            ('company_id', '=', self.env.company.id)], limit=1)
    
    name = fields.Char('Reference No',required=True,tracking = True,default=lambda self: _("New") ,readonly=True,copy=False)
    customer = fields.Many2one("res.partner",string="Customer Name",required=True,tracking=True)
    issued_date = fields.Datetime(string="Issued Date",tracking=True,required=False,default=False)
    quotation_date = fields.Datetime(string="Quotation Date",required=False, tracking=True)
    mileage = fields.Float(string="Mileage",tracking=True)
    pic = fields.Many2one('hr.employee',tracking=False,string="Service Advisor",related="request_id.pic",store=True)
    payment_date = fields.Datetime(string="Payment Date",tracking=True)
    customer_order_no = fields.Char("Customer Requests")
    total_parts = fields.Float(string="Parts Total")
    total_labor = fields.Float(string="Service Total")
    labor_parts_total = fields.Float(string="Service & Parts",compute="_calculate_labor_parts",store=True)
    discount = fields.Float(string="Discount(%)")
    repair_service_type_id = fields.Many2one("repair.service.type",related="request_id.repair_service_type_id",string="Service Type")
    total = fields.Float(string="Total")
    amount_untaxed = fields.Float(string="Amount Untaxed")
    invoice_amt = fields.Float(string="Invoice Amount")
    job_lines = fields.One2many('service.data','quotation_id',string="Jobs")
    part_lines = fields.One2many('parts.data','quotation_id',string="Parts")
    company_id = fields.Many2one("res.company","Company",default=lambda self:self.env.company)
    job_order_id = fields.Many2one("job.order")
    job_order_ids = fields.Many2many("job.order","request_quotation_job_order_rel","quotation_id","job_order_id",string="Job Order")
    location_id = fields.Many2one('stock.location',string="Parts' Main Location",domain="[('usage', '=', 'internal')]")
    picking_id = fields.Many2one("stock.picking")
    picking_ids = fields.Many2many("stock.picking","request_quotation_stock_picking_rel","quotation_id","picking_id",string="Transfers")
    discount_account_id = fields.Many2one('account.account')
    move_id = fields.Many2one("account.move")
    # move_ids = fields.Many2many("account.move","request_qutation_account_move_rel","quotation_id","move_id",string="Invoices")
    # move_ids = fields.Many2many("account.move","request_qutation_account_move_rel","quotation_id","move_id",string="Invoices")
    state = fields.Selection([('draft','Draft'),('confirm','Confirmed'),('invoiced','Invoiced'),('cancel','Cancelled')],string="Request State",tracking=True,readonly=True,default='draft')
    fleet_id = fields.Many2one("fleet.vehicle",string="Fleet",required=True,tracking=True,domain=[("type", "=", "fleet")])
    branch_id = fields.Many2one('res.branch',string="Branch",store=True,required=True,domain=_get_branch_domain)
    request_id = fields.Many2one("customer.request.form",string="Cus. Req. Form")
    pricelist_id = fields.Many2one(comodel_name='product.pricelist',string="Pricelist",default=False,tracking=True) 
    term_type = fields.Selection([('direct','Cash Sales'),('credit','Credit Sales')],string='Payment Type',default="direct",required=True)
    invoice_state = fields.Selection([('waiting','Waiting Invoice'),('draft','Draft'),('posted','Finished')],default=None)
    show_status_for_invoice = fields.Selection(selection=[('hide','Hide'),('show','Show')],string="Show Status for Invoice",compute="_compute_create_invoice_without_validation")
    tax_id = fields.Many2one(comodel_name='account.tax',string="Taxes",default=False) 
    # create_invoice_without_validation = fields.Boolean("Create Invoice Without Validation",default=False)
    
    @api.onchange('customer')
    def _onchange_customer(self):
        if self.customer:
            if self.customer.property_product_pricelist:
                self.pricelist_id = self.customer.property_product_pricelist.id
            if self.customer.fleet_ids:
                return {"domain": {"fleet_id":[('id','in',self.customer.fleet_ids.ids)]}}
            
            return {"domain": {"fleet_id":[('id','=',-1)]}}
        return {"domain": {"fleet_id":[]}}
        
    @api.onchange('fleet_id')
    def _onchange_fleet_id(self):
        if self.fleet_id:
            if self.fleet_id.partner_ids:
                return {"domain": {"customer":[('id','in',self.fleet_id.partner_ids.ids)]}}
            return {"domain": {"customer":[('id','=',-1)]}}
        return {"domain": {"customer":[]}}     

    
    @api.onchange('customer','location_id','fleet_id','branch_id')
    def onchange_picking(self):
        # picking_type_id = self.env['stock.picking.type'].search([('warehouse_id','=',self.location_id.warehouse_id.id),('code','=','outgoing'),('active','=',True)],limit=1)
        for picking_id in self.picking_ids:
            picking_id.write({
                "partner_id":self.customer and self.customer.id or False,
                "location_id":self.location_id and self.location_id.id or False,
                "fleet_id":self.fleet_id and self.fleet_id.id or False,
                # 'picking_type_id':picking_type_id.id,
                'branch_id':self.branch_id and self.branch_id.id or False,
            })
            for move_line in picking_id.move_line_ids:
                move_line.write({
                "location_id":self.location_id and self.location_id.id or False
                })
            for move in picking_id.move_ids:
                move.write({
                "location_id":self.location_id and self.location_id.id or False
                })   
        if self.request_id:
            self.request_id.write({'customer':self.customer and self.customer.id or False,
                                   "fleet_id":self.fleet_id and self.fleet_id.id or False,
                                    'branch_id':self.branch_id and self.branch_id.id or False,})                         
        # if self.picking_id:
        #     self.picking_id.write({
        #         "partner_id":self.customer and self.customer.id or False,
        #         "location_id":self.location_id and self.location_id.id or False,
        #         "fleet_id":self.fleet_id and self.fleet_id.id or False,
        #         # 'picking_type_id':picking_type_id.id,
        #         'branch_id':self.branch_id and self.branch_id.id or False,
        #     })
        #     for move_line in self.picking_id.move_line_ids:
        #         move_line.write({
        #         "location_id":self.location_id and self.location_id.id or False
        #         })
        #     for move in self.picking_id.move_ids:
        #         move.write({
        #         "location_id":self.location_id and self.location_id.id or False
        #         })
        # if self.request_id:
        #     self.request_id.write({'customer':self.customer and self.customer.id or False,
        #                            "fleet_id":self.fleet_id and self.fleet_id.id or False,
        #                             'branch_id':self.branch_id and self.branch_id.id or False,})

    @api.depends('total_parts','total_labor','amount_untaxed','job_lines')
    def _calculate_labor_parts(self):
        for res in self:
            res.labor_parts_total = res.total_parts+res.total_labor
            # res.discount = sum(res.job_lines.mapped('discount'))+sum(res.part_lines.mapped('discount'))
            # res.total = sum(res.job_lines.mapped('sub_total'))+sum(res.part_lines.mapped('sub_total'))
            # res.invoice_amt = sum(res.job_lines.mapped('sub_total'))+sum(res.part_lines.mapped('sub_total'))        
            res.discount = res.total = res.invoice_amt = res.amount_untaxed = discount_amt = 0.0
            tax_line = False
            for job_line in res.job_lines:
                res.discount += job_line.discount
                res.total += job_line.sub_total
                res.invoice_amt += job_line.sub_total
                if job_line.is_tax_line:
                    tax_line = job_line
                else:
                    res.amount_untaxed += job_line.sub_total
                discount_amt += (job_line.qty*job_line.unit_price) - job_line.sub_total
            for part_line in res.part_lines:
                res.discount += part_line.discount
                res.total += part_line.sub_total
                res.invoice_amt += part_line.sub_total 
                res.amount_untaxed += part_line.sub_total
                discount_amt += (part_line.qty*part_line.unit_price) - part_line.sub_total
            if res.tax_id:
                if not res.company_id.tax_feature:
                    raise ValidationError("Please activate tax feature first!!")
                tax_amount = (res.tax_id.amount / 100) * (res.amount_untaxed)  
                pp_id = self.env['product.product'].search([('product_tmpl_id','=',res.tax_id.product_template_id.id)]) 
                if tax_line:
                    res.total -= tax_line.sub_total
                    res.invoice_amt -= tax_line.sub_total
                    tax_line.job_code = pp_id
                    tax_line.job_desc = pp_id.name
                    tax_line.qty = 1
                    tax_line.unit_price = tax_amount  
                    res.total += tax_amount
                    res.invoice_amt += tax_amount           
                else:            
                    res.job_lines = [Command.create({
                        "job_code":pp_id.id,
                        "job_desc":pp_id.name,
                        "qty":1,
                        "unit_price":tax_amount,
                        "is_tax_line":True,
                    })]
                    res.total += tax_amount
                    res.invoice_amt += tax_amount
            else:
                if tax_line:
                    tax_line.unlink()                   
         
    @api.constrains("tax_id")            
    def action_compute_tax(self):
        for res in self:
            if res.tax_id and not res.company_id.tax_feature:
                raise ValidationError("Please activate tax feature first!!")   
            res.amount_untaxed = 0.0
            
    def _compute_create_invoice_without_validation(self):
        for res in self:
            if res.state == 'confirm':
                if not res.picking_ids or not res.move_id:
                # if not res.picking_id or not res.move_id:
                    res.show_status_for_invoice = 'show'
                res.request_id.quotation_state = 'confirm'
            elif res.state == 'invoiced':
                if res.move_id and res.move_id.state == 'cancel':
                    res.show_status_for_invoice = 'show'
                    res.move_id = False
                    res.write({"state":"confirm"})
                    res.request_id.quotation_state = 'confirm'
                elif not res.move_id:
                    res.show_status_for_invoice = 'show'
                    res.write({"state":"confirm"})
                    res.request_id.quotation_state = 'confirm'
                else:
                    res.show_status_for_invoice = 'hide'
            else:
                res.show_status_for_invoice = 'hide'
        
    def action_submit(self):
        if not self.location_id:
            raise ValidationError("Parts Main Location is required to confirm the quotation!!")
        if not self.job_lines and not self.part_lines:
            raise UserError("To confirm the quotation, at least one of job line or part line is needed!!")
        if not self.name or self.name=='New':
            name = False
            sequence = self.env['sequence.model']
            name = generate_code.generate_code(sequence,self,self.branch_id,self.company_id,self.quotation_date,None,None)
            if not name:
                raise ValidationError(_("Sequence Not Found.Please Contact to the Administrator."))
            self.write({'name':name})
        self.state  = self.request_id.quotation_state = 'confirm'
        self.invoice_state = self.request_id.invoice_state = 'waiting'
        create_new_job_order = False
        for picking_id in self.picking_ids:
           picking_id.write({'origin':self.name})
        if (not self.job_order_ids and self.job_lines) or (self.job_order_ids and self.job_lines  and 'draft' not in self.job_order_ids.mapped('state') and 'job_start' not in self.job_order_ids.mapped('state')):
            job_order_id = self.env['job.order'].create({
                            'promised_date':self.request_id.promise_date,
                            'pic':self.pic and self.pic.id or False,
                            'mileage':self.mileage,
                            'estimated_time':self.request_id.estimate_time,
                            'branch_id':self.branch_id and self.branch_id.id or False,
                            'mileage':self.mileage,
                            "quotation_id":self.id,
                        })
            create_new_job_order = True
        elif self.job_order_ids:
            job_order_id = self.job_order_ids.filtered(lambda x:x.state in ('job_start','draft'))
            if not job_order_id:
                raise UserError("Something Unexpected error occured with the job orders..")
            job_order_id = job_order_id[0]  
        for line in self.job_lines:
            if not line.job_type_id and not line.is_tax_line:
                raise UserError("Job Type is required to confirm the quotation..")
            if line.unit_price <= 0:
                raise UserError("Unit Price of a job must be greater than zero!!!")
            if not line.job_order and not line.job_rate_line and not line.job_code.tax_ok and not line.is_tax_line:
                job_rate_line = self.env['job.rate.line'].create({
                    'job_type_id':line.job_type_id and line.job_type_id.id or False,
                    'amount':line.sub_total,
                    'service_line':line.id,
                    'job_code':line.job_code and line.job_code.id or False,
                })
                job_order_id.write({"job_rate_line":[(4,job_rate_line.id)]})
                line.job_order = job_order_id.id
                line.job_rate_line = job_rate_line.id  
                self.request_id.order_state = 'draft' 
        if create_new_job_order:
            self.sudo().write({"job_order_ids":[(4,job_order_id.id)]})              
            self.request_id.order_state = 'draft'        
        
    def action_reset_to_draft(self):
        self.state = 'draft'
        self.invoice_state = self.request_id.invoice_state = None

    def action_cancel(self):
        for res in self:
            if res.picking_ids.filtered(lambda x:x.state != 'cancel'):
            # if res.picking_id and res.picking_id.state != 'cancel':
                raise UserError("You can't cancel a quotation if the transfer is not in cancel state!!")
            if res.move_id and res.move_id.state != 'cancel':
                raise UserError("You can't cancel a quotation if the invoice is not in cancel state!!")
            if res.job_order_ids and any(job_order_id.state != 'cancel' for job_order_id in res.job_order_ids):
                raise UserError("You can't cancel a quotation if all job orders is not in cancel state!!")
            res.state = 'cancel'
            
    def action_open_invoice(self):
        invoices = self.env['account.move'].search([('repair_quotation_id','=',self.id)])
        invoice_ids = [invoice.id for invoice in invoices] if invoices else self.move_id.ids
        invoices = self.env['account.move'].search([('repair_quotation_id','=',self.id)])
        invoice_ids = [invoice.id for invoice in invoices] if invoices else self.move_id.ids
        return {
            'name': _('Invoice'),
            'view_mode': 'tree,form',
            'res_model': 'account.move',
            # 'res_id': self.move_id.id,
            'type': 'ir.actions.act_window',  
            'domain': [('id', 'in', invoice_ids)],                   
            'domain': [('id', 'in', invoice_ids)],                   
        } 
        
    def action_print(self):
        filename = self.env.context.get('filename')
        if not filename:
            raise ValidationError('Filename Not found!!!')
        birt_suffix = self.env['ir.config_parameter'].sudo().get_param('birt.report.url.suffix','')
        if self.id:
            url = self.env['ir.config_parameter'].sudo().get_param('birt.report.url.html') + str(filename) + str(birt_suffix) + '.rptdesign&invoice_id=' + str(self.id) + "&&__dpi=96&__format=html&__pageoverflow=0&__overwrite=false"
        if url :
            return {
            'type' : 'ir.actions.act_url',
            'url' : url,
            'target': 'new',
            }
        else:
            raise ValidationError('Report Not Not Found') 

    def action_open_job_orders(self):
        return {
            'name': _('Job Order'),
            'view_mode': 'tree,form',
            'res_model': 'job.order',
            'type': 'ir.actions.act_window',  
            'domain': [('id', 'in',self.job_order_ids.ids)],              
        }     

        
    def action_open_transfer(self):
        return {
            'name': _('Transfers'),
            'view_mode': 'tree,form',
            'res_model': 'stock.picking',
            'domain': [('id', 'in',self.picking_ids.ids)], 
            # 'res_id': self.picking_id.id,
            'type': 'ir.actions.act_window',            
        } 
    
    def action_create_invoice(self):
        invoice_line_dct = []
        if self.job_order_ids:
            for job_order in self.job_order_ids:
                if job_order.state == 'cancel':
                    continue
                if job_order.state != 'job_close':
                    raise UserError(_("With a start,You should close Job Order Manually"))
        # if self.job_order_id and self.job_order_id.state != 'job_close':
        #     raise UserError(_("With a start,You should close Job Order Manually"))
        if not self.payment_date:
            raise ValidationError("Payment Date is required to create invoice..")
        if not self.move_id:
            internal_ref = "/".join([job_order_id.job_instruction for job_order_id in self.job_order_ids if job_order_id.job_instruction]) if self.job_order_ids else ""
            internal_ref = "/".join([job_order_id.job_instruction for job_order_id in self.job_order_ids if job_order_id.job_instruction]) if self.job_order_ids else ""
            sale_journal = self.env['account.journal'].search([('type', '=', 'sale'), ('company_id', '=', self.env.company.id)], limit=1)
            for job in self.job_lines:
                vals=(0, 0, {
                            'product_id': job.job_code.id,
                            'name':job.job_code.name,
                            'quantity': job.qty,
                            'price_unit':job.unit_price,
                            'discount_type':job.discount_type,
                            'discount':job.discount,
                            'job_lines':job.id,
                            'remark':job.remark,
                            'is_tax_line':job.is_tax_line,
                                            })
                invoice_line_dct.append(vals)
            for parts in self.part_lines:
                if parts.qty > 0:
                    vals=(0, 0, {
                                'product_id': parts.parts_name.id,
                                'name':parts.parts_name.name,
                                'quantity': parts.qty,
                                'price_unit':parts.unit_price,
                                'discount_type':parts.discount_type,
                                'discount':parts.discount,
                                'part_lines':parts.id,
                                'remark':parts.remark,
                                                })
                    invoice_line_dct.append(vals)
            move = self.env['account.move'].create({
                            'move_type': 'out_invoice',
                            'internal_ref':internal_ref,
                            'internal_ref':internal_ref,
                            'partner_id': self.customer.id,
                            'invoice_date': fields.Datetime.now().date(),
                            'invoice_date_due': self.payment_date,
                            'invoice_line_ids': invoice_line_dct,
                            'discount_account_id':self.discount_account_id and self.discount_account_id.id or False,
                            'branch_id':self.branch_id and self.branch_id.id or False,
                            'term_type':self.term_type,
                            'journal_id':sale_journal and sale_journal.id or False,
                            'repair_quotation_id':self.id,
                            'journal_id':sale_journal and sale_journal.id or False,
                            'repair_quotation_id':self.id,
                            'tax_id':self.tax_id and self.tax_id.id or False,
                                })
            self.move_id = move.id
            # if self.picking_id and self.picking_id.state !='done' and self.show_status_for_invoice == 'show':
            for picking_id in self.picking_ids:
                if (not picking_id.name) or (picking_id and picking_id.state !='done' and picking_id.name.split("/")[1].lower() != 'ret'):
                    if not all([move_id.forecast_availability >= 0 for move_id in picking_id.move_ids]):
                        raise ValidationError("Insufficient Qunatity of transfers , please purchase first !!!")
                    picking_id.action_assign()
                    action = picking_id.button_validate()
                    if not type(action)==bool:
                        wizard = Form(self.env[action['res_model']].with_context(action['context'])).save()
                        wizard.process()
                    for move_id in picking_id.move_ids:
                        if move_id.product_uom_qty != move_id.quantity_done:
                            raise ValidationError(f"Demand Quantity and Issued Quantity are not equally processed in the {picking_id.name}..")
                        elif move_id.part_line and move_id.part_line.qty != move_id.quantity_done:
                            raise ValidationError(f"Required Quantity and Issued Quantity are not equally processed in the {picking_id.name}..")
            # if self.picking_id and self.picking_id.state !='done':
            #     action = self.picking_id.button_validate()
            #     if not type(action)==bool:
            #         wizard = Form(self.env[action['res_model']].with_context(action['context'])).save()
            #         wizard.process()
            #     self.picking_id.need_manual_validation_for_repair = False
            # elif self.picking_id and self.create_invoice_without_validation:
            #     self.picking_id.need_manual_validation_for_repair = True
                    
        self.state   = 'invoiced'
        self.invoice_state = self.request_id.invoice_state = 'draft'
        for job_order in self.job_order_ids:
            job_order.is_invoiced = True
    
    @api.constrains('quotation_date','pricelist_id')
    def _calculate_price_for_date_pricelist(self):
        for res in self:
            if res.quotation_date and res.pricelist_id:
                for job_line in res.job_lines:
                    product_price = res.pricelist_id._get_product_price(job_line.job_code,job_line.qty or 1,job_line.job_code.uom_id,res.quotation_date)                    
                    job_line.unit_price = product_price*job_line.qty if product_price else 0.0
                for part_line in res.part_lines:
                    product_price = res.pricelist_id._get_product_price(part_line.parts_name,part_line.qty or 1,part_line.parts_name.uom_id,res.quotation_date)
                    part_line.unit_price = product_price*part_line.qty if product_price else 0.0

                
            
    @api.constrains('job_lines')
    def create_job_order(self):
        if not all([data.qty > 0 for data in self.job_lines]):
            raise ValidationError(_("Job Lines' Qty should be greater than zero!!!"))  
        self.total_labor = sum(job_line.qty*job_line.unit_price for job_line in self.job_lines)
        if self.state == 'draft':
            for line in self.job_lines:
                if line.job_order and line.job_rate_line:
                    line.job_rate_line.write({
                        'job_type_id':line.job_type_id and line.job_type_id.id or False,
                        'amount':line.sub_total,
                        'service_line':line.id,
                        'job_code':line.job_code and line.job_code.id or False,
                    })            
        elif self.state == 'confirm': 
            for line in self.job_lines:
                if line.job_order and line.job_rate_line:
                    line.job_rate_line.write({
                        'job_type_id':line.job_type_id and line.job_type_id.id or False,
                        'amount':line.sub_total,
                        'service_line':line.id,
                        'job_code':line.job_code and line.job_code.id or False,
                    })
                elif not line.job_order and not line.job_rate_line:
                    if (not self.job_order_ids and not line.job_code.tax_ok and not line.is_tax_line) or (not line.job_code.tax_ok and not line.is_tax_line and self.job_order_ids and 'draft' not in self.job_order_ids.mapped('state') and 'job_start' not in self.job_order_ids.mapped('state')):
                        job_order_id = self.env['job.order'].create({
                            # 'issued_date':self.issued_date,
                            'promised_date':self.request_id.promise_date,
                            'pic':self.pic and self.pic.id or False,
                            'mileage':self.mileage,
                            'estimated_time':self.request_id.estimate_time,
                            'branch_id':self.branch_id and self.branch_id.id or False,
                            'quotation_id':self.id,
                        })
                
                        job_rate_line = self.env['job.rate.line'].create({
                            'job_type_id':line.job_type_id and line.job_type_id.id or False,
                            'amount':line.sub_total,
                            'service_line':line.id,
                            'job_code':line.job_code and line.job_code.id or False,
                        })
                        job_order_id.write({"job_rate_line":[(4,job_rate_line.id)],"quotation_id":self.id})
                        line.job_order = job_order_id.id
                        line.job_rate_line = job_rate_line.id                 
                        self.sudo().write({"job_order_ids":[(4,job_order_id.id)]}) 
                        self.request_id.order_state = 'draft' 
                    elif (self.job_order_ids and not line.job_code.tax_ok and not line.is_tax_line):
                        job_order_states = self.job_order_ids.mapped('state')
                        if 'draft' in job_order_states or 'job_start' in job_order_states:
                            opened_job_order = self.job_order_ids.filtered(lambda x:x.state in ['draft', 'job_start'])
                            job_rate_line = self.env['job.rate.line'].create({
                                'job_type_id':line.job_type_id and line.job_type_id.id or False,
                                'amount':line.sub_total,
                                'service_line':line.id,
                                'job_code':line.job_code and line.job_code.id or False,
                                'job_order_id':opened_job_order[0].id,
                            })
                            opened_job_order[0].write({"job_rate_line":[(4,job_rate_line.id)]})
                            line.job_order = opened_job_order[0].id
                            line.job_rate_line = job_rate_line.id     
                        self.request_id.order_state = 'draft'               
                else:
                    raise ValidationError("Hmm? What the hell is wrong?")
        
        
    @api.constrains('part_lines')
    def create_part_pickings(self):
        total_parts = 0
        if not all([data.qty > 0 for data in self.part_lines if data.state == 'draft']):
            raise ValidationError(_("Part Lines' Qty should not be zero!!!"))
        active_picking_id = self.picking_ids.filtered(lambda x:x.state != 'done' and x.name.split("/")[1].lower() != 'ret')
        for line in self.part_lines:
            if not self.location_id or not self.customer:
                raise ValidationError("Location or Partner must Not be Blank")
            else:
                picking_type_id = self.env['stock.picking.type'].search([('warehouse_id','=',self.location_id.warehouse_id.id),('code','=','outgoing'),('active','=',True)],limit=1)
                if not line.picking_id and not active_picking_id:
                    if line.parts_name and line.qty:
                        picking = self.env['stock.picking'].create({
                                'partner_id':self.customer.id,
                                'scheduled_date':self.issued_date,
                                'location_id':self.location_id.id,
                                'location_dest_id':self.customer.property_stock_customer.id,
                                'picking_type_id':picking_type_id.id,
                                'quotation_id':self.id,
                                'branch_id':self.branch_id and self.branch_id.id or False,
                                'fleet_id':self.fleet_id and self.fleet_id.id or False,
                                'origin':self.name,
                                'move_ids':[(0, 0, {
                                                    'product_id': val.parts_name.id,
                                                    'name':val.parts_name.name,
                                                    'product_uom_qty': val.qty,
                                                    'location_id':self.location_id.id,
                                                    'location_dest_id':self.customer.property_stock_customer.id,
                                                    'part_line':val.id,
                                                }) for val in line]
                            })
                        picking.action_confirm()
                        self.write({"picking_ids":[(4,picking.id)]})
                        self.picking_id = picking.id
                        line.picking_id = picking.id
                        line.stock_move = picking.move_ids and picking.move_ids.id or False
                        active_picking_id = picking
    
                    
                else:
                    if line.picking_id and line.stock_move and line.state == 'draft':
                        line.stock_move.write({
                            'product_id': line.parts_name.id,
                            'product_uom_qty': line.qty,
                            'location_id':self.location_id.id,
                            'location_dest_id':self.customer.property_stock_customer.id,
                            'part_line':line.id,
                        })
                    elif line.state == 'draft' and (not line.picking_id or not line.stock_move):
                        if not active_picking_id:
                            raise ValidationError(_("There's something wrong!!!!"))
                        stock_move = self.env['stock.move'].create({
                            'product_id': line.parts_name.id,
                            'name':line.parts_name.name,
                            'product_uom_qty': line.qty,
                            'location_id':self.location_id.id,
                            'location_dest_id':self.customer.property_stock_customer.id,
                            'part_line':line.id,
                            'picking_id': active_picking_id[0].id,
                        })
                        
                        stock_move._action_confirm()
                        line.picking_id = self.picking_id.id
                        line.stock_move = stock_move and stock_move.id or False
                
                
                
                total_parts += line.qty*line.unit_price
        self.total_parts = total_parts
    
class ServiceData(models.Model):
    _name = "service.data"
    _inherit = ['mail.thread']
    
    name = fields.Char()
    job_name = fields.Many2one('job.description',string="Job Name")
    job_desc = fields.Char("Job Name",related="job_code.name",store=True)
    job_type_id = fields.Many2one("custom.group.class",string="Job Type",store=True)
    job_code = fields.Many2one("product.product",required=True,domain="[('detailed_type', '=', 'service')]")
    qty = fields.Float("Qty")
    unit_price = fields.Float("Unit Price")
    discount = fields.Float(string="Discount")
    discount_type =  fields.Selection([('percent','%'),('amount','Amt')],string="Discount Type",default='percent')
    sub_total = fields.Float("Subtotal",compute="_compute_amount",store=True)
    quotation_id = fields.Many2one('request.quotation',string="Quotation")
    job_order = fields.Many2one('job.order')
    job_rate_line = fields.Many2one('job.rate.line')
    start_time = fields.Datetime(related='job_rate_line.start_time',store=True)
    end_time = fields.Datetime(related='job_rate_line.end_time',store=True)
    duration = fields.Float(related='job_rate_line.duration',store=True)  
    from_popular = fields.Boolean(string="From Popular Job",default=False)
    remark = fields.Char("Remark")
    is_tax_line = fields.Boolean(string="Is Tax Line",default=False)
    
    @api.depends('qty','unit_price','discount','discount_type')
    def _compute_amount(self):
        for res in self:
            res.sub_total = res.qty*res.unit_price
            if res.sub_total:
                if res.discount:
                    if res.discount_type == 'percent':
                        res.sub_total = res.sub_total * (1-(res.discount/100))
                    if res.discount_type == 'amount':
                        res.sub_total = res.sub_total - res.discount
                
    def unlink(self):
        for res in self:
            if res.is_tax_line:
                if res.quotation_id.tax_id:
                    raise ValidationError("You can't delete tax line manually")
            if res.job_rate_line.job_rate_detail:
                raise ValidationError("You can't delete job rate line with details lines..")
            res.job_rate_line.sudo().unlink()
        return super().unlink() 
    
    
    @api.onchange('job_code')
    def _get_price_by_job_code(self):
        if self.quotation_id and not self.quotation_id.pricelist_id:
            raise ValidationError("Pricelist is not defined in the quotation..")
        if not self.quotation_id.quotation_date:
            raise ValidationError("Quotation date must be specified first..")
        pricelist_id = self.quotation_id.pricelist_id
        if self.job_code:
            product_price = pricelist_id._get_product_price(self.job_code,self.qty or 1,self.job_code.uom_id,self.quotation_id.quotation_date)
            self.unit_price = product_price if product_price else 0.0 
            self.job_type_id = self.job_code.group_class_id  
     
        
        

    
    
class PartsData(models.Model):
    _name = "parts.data"
    _inherit = ['mail.thread']
    
    name = fields.Char()
    parts_name = fields.Many2one('product.product',string="Part Code",domain="[('detailed_type', '=', 'product')]")
    parts_code = fields.Char("Part Name",related="parts_name.name",store=True)
    qty = fields.Float("Qty")
    unit_price = fields.Float("Unit Price")
    discount = fields.Float(string="Discount")
    discount_type =  fields.Selection([('percent','%'),('amount','Amt')],string="Discount Type",default='percent')
    sub_total = fields.Float("Subtotal",compute="_compute_amount",store=True)
    quotation_id = fields.Many2one('request.quotation',string="Quotation")
    picking_id = fields.Many2one('stock.picking')
    return_move_id = fields.Many2one("stock.move",string="Return Picking Line",default=False)
    stock_move = fields.Many2one('stock.move')
    state = fields.Selection([('draft','Draft'),('validate','Validate')],string="State",default='draft')
    remark = fields.Char("Remark")
    
    @api.depends('qty','unit_price','discount','discount_type')
    def _compute_amount(self):
        for res in self:
            res.sub_total = res.qty*res.unit_price
            if res.sub_total:
                if res.discount:
                    if res.discount_type == 'percent':
                        res.sub_total = res.sub_total * (1-(res.discount/100))
                    if res.discount_type == 'amount':
                        res.sub_total = res.sub_total - res.discount
                    
                    
    def unlink(self):
        self.stock_move.sudo().unlink()
        return super().unlink() 
    
    @api.onchange('parts_name')
    def _get_price_by_parts_name(self):
        if self.quotation_id and not self.quotation_id.pricelist_id:
            raise ValidationError("Pricelist is not defined in the quotation..")
        if not self.quotation_id.quotation_date:
            raise ValidationError("Quotation date must be specified first..")
        pricelist_id = self.quotation_id.pricelist_id
        if self.parts_name:
            product_price = pricelist_id._get_product_price(self.parts_name,self.qty or 1,self.parts_name.uom_id,self.quotation_id.quotation_date)
            self.unit_price = product_price if product_price else 0.0
    
    
class JobDescription(models.Model):
    _name = "job.description"
    _inherit = ['mail.thread']
    
    name = fields.Char(required=True)
    job_code = fields.Char("Code",tracking=True,required=False)
    company_id = fields.Many2one("res.company","Company",default=lambda self:self.env.company)
    
class StockPicking(models.Model):
    _inherit = "stock.picking"
    
    quotation_id = fields.Many2one('request.quotation',string="Quotation")
    # need_manual_validation_for_repair = fields.Boolean("Need of Manual Validation for Repair",default=False)

class ReturnPicking(models.TransientModel):
    _inherit = 'stock.return.picking'

    def _create_returns(self):    
        if self.picking_id and self.picking_id.move_ids:
            part_lines = self.picking_id.move_ids.mapped('part_line')
            if part_lines:
                if part_lines[0].quotation_id.state != 'confirm':
                    raise ValidationError("You can't return a transfer if the quotation is not in confirmed state!!")
        new_picking_id, picking_type_id = super()._create_returns()
        if self.picking_id and self.picking_id.quotation_id:
            new_picking = self.env['stock.picking'].browse(new_picking_id)
            if new_picking:
                new_picking.quotation_id = False
            self.picking_id.quotation_id.write({"picking_ids":[(4,new_picking_id)]})
            for return_move in self.product_return_moves:
                if return_move.move_id.part_line:
                    returned_move_id = new_picking.move_ids.filtered(lambda x:x.origin_returned_move_id.id == return_move.move_id.id)
                    if returned_move_id:
                        return_move.move_id.part_line.return_move_id = returned_move_id
                        returned_move_id.part_line = return_move.move_id.part_line
        return new_picking_id, picking_type_id

class StockMove(models.Model):
    _inherit = "stock.move"
    
    part_line = fields.Many2one("parts.data",string="Parts Data")
    is_printed = fields.Boolean("Printed",default=False)
    
    @api.ondelete(at_uninstall=False)
    def _unlink_if_draft_or_cancel(self):
        if any(move.state not in ('draft', 'cancel') and not move.part_line for move in self):
            raise UserError(_('You can only delete draft or cancelled moves.'))
        
    # @api.constrains("quantity_done")
    # def _check_edit_quantity_done(self):
    #     for res in self:
    #         if res.part_line:
    #             if res.forecast_availability <= 0: 
    #                 raise ValidationError("You can't done moves manually when there is not enough stocks!!!")
    #             if res.product_uom_qty < res.quantity_done:
    #                 raise ValidationError("Your Manual Done Quantity must not be greater than the Demand Quantity!!")
        
class StockMoveLine(models.Model):
    _inherit = 'stock.move.line'

    is_printed = fields.Boolean("Printed",related="move_id.is_printed")
        
class AccountMoveLine(models.Model):
    _inherit = "account.move.line"
    
    job_lines = fields.Many2one('service.data',string="Jobs")
    part_lines = fields.Many2one('parts.data',string="Parts")

class AccountMove(models.Model):
    _inherit = "account.move"

    repair_quotation_id = fields.Many2one("request.quotation",string="Repair Quotation")

    def action_print_repair(self):
        filename = self.env.context.get('filename')
        if not filename:
            raise ValidationError('Filename Not found!!!')
        birt_suffix = self.env['ir.config_parameter'].sudo().get_param('birt.report.url.suffix','')
        if self.id:
            url = self.env['ir.config_parameter'].sudo().get_param('birt.report.url.html') + str(filename) + str(birt_suffix) + '.rptdesign&invoice_id=' + str(self.id) + "&&__dpi=96&__format=html&__pageoverflow=0&__overwrite=false"
        if url :
            return {
            'type' : 'ir.actions.act_url',
            'url' : url,
            'target': 'new',
            }
        else:
            raise ValidationError('Report Not Not Found')         

class AccountMoveReversal(models.TransientModel):
    _inherit = 'account.move.reversal'

    def reverse_moves(self):    
        result = super(AccountMoveReversal, self).reverse_moves()
        credit_move = self.env['account.move'].browse(result.get('res_id',0))
        if self.move_ids and credit_move:
            credit_move.repair_quotation_id = self.move_ids[0].repair_quotation_id
        return result    
