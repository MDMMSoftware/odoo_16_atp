from odoo import models, fields, api, _
from datetime import datetime, timedelta, date
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT
from odoo.exceptions import UserError, RedirectWarning, ValidationError
from collections import Counter
from ...generate_code import generate_code
from ..wizard import part_requisition_partial


class PartRequisition(models.Model):
    _name = 'part.requisition'
    _description = 'Part Requisition'
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
    
    def _get_today_date(self):
        return datetime.today()

    department_id = fields.Many2one('res.department', string='Department', store=True,required=False,readonly=True,tracking=True,
                                help='Leave this field empty if this account is'
                                     ' shared between all departmentes')

    name = fields.Char('Reference No',required=True,tracking = True,default=lambda self: _("New") ,readonly=True,copy=False)
    job_order_id = fields.Many2one('repair.order',string="Job Order No",readonly=True)
    job_request_id = fields.Many2one('repair.request',string="Job Request No",readonly=True)
    date = fields.Date(string="Date",tracking = True, default=_get_today_date,required=True)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('confirm', 'Submitted'),
        ('approve','Approved'),
        ('done', 'Finished'),
        ('reject', 'Rejected'),
        ('close', 'Closed'),
        ], string='Status', readonly=True, copy=False, index=True, default='draft',tracking=True)  
    requisition_line = fields.One2many('part.requisition.line','requisition_id',string="Requisition Line") 
    location_id = fields.Many2one('stock.location','Location',domain="[('usage','=','internal')]")
    branch_id = fields.Many2one('res.branch', string='Branch', store=True,
                                readonly=True,
                                default=_get_default_branch,
                                domain=_get_branch_domain)
    company_id = fields.Many2one('res.company', string='Company', required=True,
        default=lambda self: self.env.company)
    so_id = fields.Many2many('sale.order')
    adjust_id = fields.Many2many('stock.inventory.adjustment')
    journal_id = fields.Many2one('account.journal',string="Journal")
    smu = fields.Char("SMU",store=True)
    adjust_account_id = fields.Many2one('account.account',string="Adjust Account")
    company_no = fields.Many2one("fleet.vehicle",string="Fleet",required=True,readonly=True)
    owner_name = fields.Many2one('fleet.owner',string="Owner Name",store=True)
    pricelist_id = fields.Many2one(comodel_name='product.pricelist',string="Pricelist") 
    parts_state = fields.Selection([
        ('draft', 'Request'),
        ('confirm', 'Request'),
        ('approve','Waiting Parts'),
        ('done', 'Finished'),
        ('reject', 'Rejected'),
        ('close', 'Closed')
    ],string="Part Request Status",copy=False,default='draft',tracking=True)
    accounting_status = fields.Boolean(string="Accounting Status", compute="_compute_accounting_status")
    sale_state = fields.Selection([
            ('draft', "Quotation"),
            ('sent', "Quotation Sent"),
            ('sale', "Sales Order"),
            ('done', "Locked"),
            ('cancel', "Cancelled"),
    ],string="Sale Status",readonly=True, copy=False,defualt=None)  
    adjustment_state = fields.Selection([
        ('draft','Draft'),
        ('confirm','Confirm'),
        ('done','Done'),
        ('return','Return')
    ],string='Adjustment Status',default=None,tracking = True,copy=False)  
    repair_object_type = fields.Selection([
        ('fleet','Fleet'),
        ('repair_product','Repair Product')
    ],string="Repair Object",default='fleet')

    def action_open_sale_order(self):
        return {
            'name': _('Sale Order'),
            'view_mode': 'tree,form',
            'res_model': 'sale.order',
            'view_id': False,
            'type': 'ir.actions.act_window',  
            'domain': [('id', 'in',self.so_id.ids)],              
        } 
    
    def action_open_adjustment(self):
        return {
            'name': _('Adjustment'),
            'view_mode': 'tree,form',
            'res_model': 'stock.inventory.adjustment',
            'view_id': False,
            'type': 'ir.actions.act_window',  
            'domain': [('id', 'in',self.adjust_id.ids)],              
        } 
    
    @api.model
    def create(self, vals):
        if not vals.get('requisition_line',False):
            raise ValidationError("Please at least at least one requisition line..")
        res = super().create(vals)
        if res.job_order_id:
            res.write({'job_request_id':res.job_order_id.repair_request_id})
            res.job_order_id.write({'requisition_ids':[(4,res.id)]})
            if res.job_order_id.repair_request_id:
                res.job_order_id.repair_request_id.write({'requisition_ids':[(4,res.id)]})
        if res.job_request_id:
            res.job_request_id.write({'requisition_ids':[(4,res.id)]})
        return res
    
    def _compute_accounting_status(self):
        for part_req in self:
            if part_req.so_id:
                all_so_status = [each_so.state for each_so in part_req.so_id]
                max_so_status = max(all_so_status,key = lambda x: Counter(all_so_status)[x])
                temp = all([each_so.state == 'sale' for each_so in part_req.so_id] if part_req.so_id else [False])
                part_req.sale_state = 'sale' if temp else max_so_status
            if part_req.adjust_id:
                all_adj_status = [each_adj.state for each_adj in part_req.adjust_id]
                max_adj_status = max(all_adj_status,key = lambda x: Counter(all_adj_status)[x])
                temp = all([each_adj.state == 'done' for each_adj in part_req.adjust_id] if part_req.adjust_id else [False])
                part_req.adjustment_state = 'done' if temp else max_adj_status
            part_req.accounting_status = True
    
    def action_submit(self):
        sequence = self.env['sequence.model']
        date,seq = generate_code.generate_code(sequence,self,self.branch_id,self.company_id,self.date,None,None)
        if date and seq and self.job_order_id:
            self.name = "SPO"+str(self.job_order_id.repair_sequence_prefix_id.name)+str(date)+str(seq)
        elif date and seq and self.job_request_id:
            self.name = "SPO"+str(self.job_request_id.repair_sequence_prefix_id.name)+str(date)+str(seq)
        else:
            raise ValidationError(_("Sequence Not Found.Please Contact to the Administrator."))
        self.state = self.parts_state ='confirm'
        # update part state of job_request
        req_forms = self.job_order_id.requisition_ids + self.job_request_id.requisition_ids
        request_part_flag = part_requisition_partial.get_part_flag_from_part_requisition(req_forms)
        self.job_request_id.write({'part_state':request_part_flag})

   
    def action_approve(self):
        for line in self.requisition_line:
            if not line.product_id:
                raise ValidationError(_("Product in Requisition Line should not be blank"))
        self.state = self.parts_state = 'approve'
        self.job_request_id.action_wait()
        
    def action_revert_approve(self):
        self.state = self.parts_state = 'confirm'


    def action_done(self,partial_line):
        if self.job_order_id or self.job_request_id:
            partner_id = self.job_order_id.partner_id.id if self.job_order_id else self.job_request_id.partner_id.id
            fleet_id = self.job_order_id.company_no if self.job_order_id else self.job_request_id.company_no
            if  ( ( self.job_order_id and self.job_order_id.partner_id ) or ( self.job_request_id and self.job_request_id.partner_id ) ) and not self.job_request_id.allow_expense and (not self.job_order_id or self.job_order_id.request_type_id.code not in ['E','P']):
                    order_line_fleet_or_repair_product_key = 'repair_object_id' if self.repair_object_type == 'repair_product' else 'fleet_id'
                    so_id = self.env['sale.order'].create({'partner_id':partner_id,
                                                        'location_id':partial_line.requisition_line.requisition_id.location_id.id,
                                                        'warehouse_id':partial_line.requisition_line.requisition_id.location_id.warehouse_id.id,
                                                        'repair_request_id':self.job_request_id and self.job_request_id.id or False,
                                                        'job_order_id':self.job_order_id.id,
                                                        'internal_ref':self.name,
                                                        'branch_id':self.branch_id.id,
                                                        'department_id':self.department_id.id,
                                                        'term_type':'credit',
                                                        'requisition_id':partial_line.requisition_line.requisition_id.id,
                                                            'order_line':[(0, 0, {
                                                                        'product_id': res.product_id.id,
                                                                        'name':res.product_id.name,
                                                                        'product_uom_qty': res.quantity,
                                                                        'price_unit':res.requisition_line.unit_price,
                                                                        order_line_fleet_or_repair_product_key:fleet_id.id,
                                                                        'analytic_distribution':{fleet_id.analytic_fleet_id.id:100} if fleet_id.analytic_fleet_id else {},
                                                            }) for res in partial_line]})
                    
                    self.write({'so_id':[(4,so_id.id)]})  
                    if self.job_order_id: 
                        self.job_order_id.write({'so_id':[(4,so_id.id)]})   
                        if self.job_order_id.repair_request_id:
                            self.job_order_id.repair_request_id.write({'so_id':[(4,so_id.id)]}) 
                    elif self.job_request_id:
                        self.job_request_id.write({'so_id':[(4,so_id.id)]})  
            else:
                if self.company_no:
                    if not self.company_no.repair_account_id:
                        raise UserError(_("Please Configure for Machine Repair Account"))
                order_line_fleet_or_repair_product_key = 'repair_object_id' if self.repair_object_type == 'repair_product' else 'fleet_id'
                adjust_out = self.env['stock.inventory.adjustment'].create({'journal_id':partial_line.requisition_line.requisition_id.journal_id.id,
                                                       'location_id':partial_line.requisition_line.requisition_id.location_id.id,
                                                       'date':partial_line.requisition_line.requisition_id.date,
                                                       'repair_request_id':self.job_request_id and self.job_request_id.id or False,
                                                       'job_order_id':self.job_order_id.id,
                                                       'requisition_id':partial_line.requisition_line.requisition_id.id,
                                                       'branch_ids':self.branch_id.id,
                                                       'department_id':self.department_id.id,
                                                       'ref':self.name,
                                                        'adjustment_line_id':[(0, 0, {
                                                                    'product_id': res.product_id.id,
                                                                    'uom_id':res.product_id.uom_id.id,
                                                                    'desc':res.product_id.name,
                                                                    'quantity': -res.quantity,
                                                                    'unit_cost':res.requisition_line.unit_price,
                                                                    order_line_fleet_or_repair_product_key:partial_line.requisition_line.requisition_id.company_no.id,
                                                                    'adjust_account_id':self.company_no.repair_account_id.id, #need to refix after when machine config set up
                                                                    'analytic_distribution':{fleet_id.analytic_fleet_id.id:100} if fleet_id.analytic_fleet_id else {},
                                                        }) for res in partial_line]})
                self.write({'adjust_id':[(4,adjust_out.id)]})   
                if self.job_order_id:
                    self.job_order_id.write({'adjust_id':[(4,adjust_out.id)]})   
                    if self.job_order_id.repair_request_id:
                        self.job_order_id.repair_request_id.write({'adjust_id':[(4,adjust_out.id)]})   
                elif self.job_request_id:
                    self.job_request_id.write({'adjust_id':[(4,adjust_out.id)]})   
                     

        else:
            raise ValidationError(_("There is no Job Order for Part Requisition"))

   
    def action_reject(self):
        self.state  = self.parts_state ='reject'

    def action_close(self):
        self.state = self.parts_state = 'close'
        # update part state of job request
        req_forms = self.job_order_id.requisition_ids + self.job_request_id.requisition_ids
        request_part_flag = part_requisition_partial.get_part_flag_from_part_requisition(req_forms)
        if request_part_flag == 'done':
            self.job_order_id.write({'order_state':'repair'})
        self.job_request_id.write({'part_state':request_part_flag}) 

    def action_print(self):
        filename = self.env.context.get('filename')
        if not filename:
            raise ValidationError('Filename Not found!!!')
        if self.id:
            url = self.env['ir.config_parameter'].sudo().get_param('birt.report.url.html') + str(filename) + '.rptdesign&req_id=' + str(self.id) + "&&__dpi=96&__format=html&__pageoverflow=0&__overwrite=false"
        if url :
            return {
            'type' : 'ir.actions.act_url',
            'url' : url,
            'target': 'new',
            }
        else:
            raise ValidationError('Report Not Not Found')   

    def unlink(self):
        for rec in self:
            if rec.state != 'draft':
                raise UserError("Are you doing something fraudly! Why do you want to delete some records?? 🤔")
        return super().unlink()                          


class PartRequisitionLine(models.Model):
    _name = 'part.requisition.line'

    requisition_id = fields.Many2one('part.requisition')
    part_no = fields.Char(string="Parts No")
    product_id =  fields.Many2one('product.product',string="Item Code")
    product_name = fields.Char(string="Product Name",related="product_id.name")
    custom_brand_id = fields.Many2one('custom.brand',related="product_id.product_tmpl_id.custom_brand_id")
    desc = fields.Char("Parts Description")   
    uom_id = fields.Many2one('uom.uom',string="UOM", related='product_id.uom_id')
    onhand_qty = fields.Float("Onhand Qty",compute='_get_onhand_qty',store=True)
    done_qty = fields.Float("Done Qty",readonly=True)
    issue_qty = fields.Float("Request Qty")
    unit_price = fields.Float("Price")
    price_subtotal = fields.Float("Price Subtotal",compute="_compute_price",store=True)
    remark = fields.Char("Remark")
    parent_state = fields.Selection(related='requisition_id.state',default='draft', store=True)
    lead_time = fields.Float('Lead Time')
    freight = fields.Char("Freight")
    need_request = fields.Boolean("Need Request",default=False)
    custom_part = fields.Char(string="Part ID", related= "product_id.product_tmpl_id.custom_part", store=True)

    _sql_constraints = [('check_issue_quantity_in_repari_part_request', 'CHECK(issue_qty > 0)', 'Request Quantity must be greater than 0')]

    @api.model
    def create(self, data_list):
        res = super().create(data_list)
        if res.parent_state not in ['draft','confirm']:
            res.need_request = True
        if res.issue_qty <= 0.0:
            raise ValidationError(_("Request Quantity must be greate then zero"))
        return res

    @api.onchange('product_id')
    def _get_price_by_product_id(self):
        if self.product_id:
            if self.requisition_id.pricelist_id:
                pricelist_items = self.requisition_id.pricelist_id.item_ids.search([('product_tmpl_id','=',self.product_id.product_tmpl_id.id),('date_start','<=',self.requisition_id.date),('date_end','>=',self.requisition_id.date)],limit=1)
                if pricelist_items:
                    self.unit_price = pricelist_items.fixed_price
                else:
                    self.unit_price = 1.0

    @api.depends('requisition_id.location_id','product_id')
    def _get_onhand_qty(self):
        for res in self:
            qty=0
            cost = 0
            if res.requisition_id.location_id and res.product_id:
                quant = self.env['stock.quant'].search([('location_id','=',res.requisition_id.location_id.id),('product_id','=',res.product_id.id)])
                if quant:
                    qty += quant.quantity

                valuation = res.product_id.warehouse_valuation.filtered(lambda x:x.location_id==res.requisition_id.location_id)
                if valuation:
                    cost += valuation.location_cost
            if not self.requisition_id.pricelist_id:
                res.unit_price = cost
            res.onhand_qty = qty

    def view_action_stock_quant(self):
        return self.product_id.action_open_quants()
    
    @api.depends('unit_price','done_qty')
    def _compute_price(self):
        # flag = True
        for res in self:
            if res.unit_price and res.done_qty:
                res.price_subtotal = res.unit_price*res.done_qty
        #     if res.issue_qty!=res.done_qty:
        #         flag = False
        # if flag and self.requisition_id.state=='approve':
        #     self.requisition_id.state='done'



class SaleOrder(models.Model):
    _inherit = "sale.order"

    repair_request_id = fields.Many2one('repair.request',string='Job Request No')
    job_order_id = fields.Many2one('repair.order',string="Job Order No")
    requisition_id = fields.Many2one('part.requisition')

class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    repair_object_id = fields.Many2one('fleet.vehicle',string="Repair Object",domain=[("type", "=", "repair_product")])


class AccountMove(models.Model):
    _inherit = 'account.move'

    job_order_id = fields.Many2one('repair.order',string="Job Order No",readonly=True)
    job_request_id = fields.Many2one('repair.request',string="Job Request No",readonly=True)

    @api.model
    def create(self,vals_list):
        res = super().create(vals_list)
        if res.job_order_id:
            res.job_order_id.write({'move_ids':[(4,res.id)]})
            if res.job_order_id.repair_request_id:
                res.job_order_id.repair_request_id.write({'move_ids':[(4,res.id)]})
        elif res.job_request_id:
            res.job_request_id.write({'move_ids':[(4,res.id)]})
            
        return res

class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    repair_object_id = fields.Many2one('fleet.vehicle',string="Repair Object",domain=[("type", "=", "repair_product")])

class Requisition(models.Model):
    _inherit = 'requisition.line'
    
    repair_object_id = fields.Many2one('fleet.vehicle',string="Repair Object",domain=[("type", "=", "repair_product")])

class StockAdjustment(models.Model):
    _inherit = "stock.inventory.adjustment"

    # for Repair and Service
    repair_request_id = fields.Many2one('repair.request',string='Job Request No')
    job_order_id = fields.Many2one('repair.order',string="Job Order No")
    requisition_id = fields.Many2one('part.requisition')

class StockInventoryAdjustmentLine(models.Model):
    _inherit = "stock.inventory.adjustment.line"

    repair_object_id = fields.Many2one('fleet.vehicle',string="Repair Object",domain=[("type", "=", "repair_product")])

class StockMove(models.Model):
    _inherit = 'stock.move'

    repair_object_id = fields.Many2one('fleet.vehicle',string="Repair Object",domain=[("type", "=", "repair_product")])

class StockMoveLine(models.Model):
    _inherit = 'stock.move.line'

    repair_object_id = fields.Many2one('fleet.vehicle',string="Repair Object",related="move_id.fleet_id") 

class StockValuaionLayer(models.Model):
    _inherit = 'stock.valuation.layer'

    repair_object_id = fields.Many2one('fleet.vehicle',string="Repair Object") 

class StockAdjustmentLine(models.Model):
    _inherit = "stock.location.valuation.report"

    repair_object_id = fields.Many2one('fleet.vehicle',string="Repair Object")  
