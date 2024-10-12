from odoo import models,fields,api

REPORT_TYPE = [
    ('adjustment', 'Adjustment'),
    ('adjustment_return','Adjustment Return'),
    ('delivery', 'Delivery'),
    ('delivery_return','Delivery Return'),
    ('receipt', 'Receipt'),
    ('receipt_return', 'Receipt Return'),
    ('transfer', 'Transfer'),
    ('transfer_return', 'Transfer Return'),
    ('duty', 'Duty'),
    ('landed_cost', 'Landed Cost'),
    ('mrp','Manufacturing'),
    ('unknown','Unknown')
]

class StockLocationValuationReport(models.Model):
    """ Stock Location Valuatin Report """
    _name = 'stock.location.valuation.report'
    _description = 'This is a stock location valuation report'
    
    department_id = fields.Many2one('res.department', string='Department',required=False,readonly=True,)

    stock_move_id = fields.Many2one('stock.move', string="Stock Move")
    report_type = fields.Selection(REPORT_TYPE, string="Type")
    company_id = fields.Many2one(comodel_name="res.company", string="Company")
    branch_id = fields.Many2one(comodel_name="res.branch", string="Branch")
    by_location = fields.Many2one(comodel_name="stock.location",string="By Location")
    report_date = fields.Date(string="Date")
    ref = fields.Char(string="Reference")
    seq = fields.Char(string="Sequence")
    location_id = fields.Many2one(comodel_name="stock.location",string="From Location")
    location_dest_id = fields.Many2one(comodel_name="stock.location",string="To Location")
    product_id = fields.Many2one('product.product',string="Product Code",required=True)
    product_code = fields.Char(related='product_id.product_tmpl_id.product_code',store=True,string="Code")
    product_name = fields.Char(string="Product Name")
    desc = fields.Char(string="Description")
    qty_in =  fields.Float('Qty. In',required=True)
    qty_out = fields.Float('Qty. Out',required=True)
    balance = fields.Float('Balance')
    product_uom_category_id = fields.Many2one(related='product_id.uom_id.category_id')
    uom_id = fields.Many2one('uom.uom',string="UOM",domain="[('category_id', '=', product_uom_category_id)]")
    unit_cost = fields.Float('Price')
    total_amt = fields.Float('Amount')
    division_id = fields.Many2one(comodel_name='analytic.division',string="Division")

    @api.onchange('product_id')
    def onchange_product_id(self):
        if self.product_id:
            self.product_name = self.product_id.name
            self.uom_id = self.product_id.uom_id.id    

    def go_to_picking(self):
        picking = self.env['stock.picking'].search([('name','=',self.ref)],limit=1)
        if picking:
            return {
                'type': 'ir.actions.act_window',
                'name': 'Transfer',
                'res_model': 'stock.picking',
                'view_mode': 'form',
                'view_id': self.env.ref('stock.view_picking_form').id,
                'target': 'current',
                'res_id': picking.id,
            }
        
    def go_to_origin(self):
        check_purchase = self.env['purchase.order'].search([('name','=',self.seq)],limit=1)
        if check_purchase:
            return {
                'type': 'ir.actions.act_window',
                'name': 'Purchase Order Form',
                'res_model': 'purchase.order',
                'view_mode': 'form',
                'view_id': self.env.ref('purchase.purchase_order_form').id,
                'target': 'current',
                'res_id': check_purchase.id,
            }
        check_requisition = self.env['requisition'].search([('name','=',self.seq)],limit=1)
        if check_requisition:
            return {
                'type': 'ir.actions.act_window',
                'name': 'Requisition Form',
                'res_model': 'requisition',
                'view_mode': 'form',
                'view_id': self.env.ref('requisition.requisition_form_view').id,
                'target': 'current',
                'res_id': check_requisition.id,
                }
        check_sale_order = self.env['sale.order'].search([('name','=',self.seq)],limit=1)
        if check_sale_order:
            return {
                'type': 'ir.actions.act_window',
                'name': 'Sale Order Form',
                'res_model': 'sale.order',
                'view_mode': 'form',
                'view_id': self.env.ref('sale.view_order_form').id,
                'target': 'current',
                'res_id': check_sale_order.id,
            }
        check_sale_order_by_quo = self.env['sale.order'].search([('quotation_ref','=',self.seq)],limit=1)
        if check_sale_order_by_quo:
            return {
                'type': 'ir.actions.act_window',
                'name': 'Sale Order Form',
                'res_model': 'sale.order',
                'view_mode': 'form',
                'view_id': self.env.ref('sale.view_order_form').id,
                'target': 'current',
                'res_id': check_sale_order_by_quo.id,
            }
            
            
    def recalculate_costing_for_wrong_transfer(self):
        
        product_ids = self.search([('report_type','=','transfer'),('company_id','=',1)]).product_id
        # product_ids = self.env['product.product'].search([('product_code','=','ESSP1044STH')])
        valuation = self.env['stock.valuation.layer']
        for product in product_ids:
            val_report = self.search([('product_id','=',product.id)],order='id')
            location_ids = val_report.mapped('by_location').filtered(lambda x:x.usage!='transit')
            for location in location_ids:
                product_cost = 0
                val_qty = 0
                val_cost = 0
                
                for layer in val_report.filtered(lambda x:x.by_location==location):
                    svl_vals = valuation.sudo().search([('stock_move_id','=',layer.stock_move_id.id)])
                    val_cost += layer.balance*layer.unit_cost
                    val_qty += layer.balance
                    if layer.balance>0:
                        product_cost=val_cost/val_qty
                        warehouse_valuation_ids = product.warehouse_valuation.filtered(lambda x:x.location_id==location)
                
                        if not warehouse_valuation_ids:
                            vals = self.env['warehouse.valuation'].create({'location_id':location.id,
                                                                        'location_cost':product_cost})
                            if vals:
                                product.write({'warehouse_valuation':[(4,vals.id)]})
                        else:
                            warehouse_valuation_ids.write({'location_cost':product_cost})
                    else:
                        if layer.unit_cost!=abs(product_cost):
                            layer.write({'unit_cost':product_cost,'total_amt':product_cost*layer.balance})
                            for svl in svl_vals:
                                svl.write({'unit_cost':product_cost,'value':product_cost*layer.balance})
                                if svl.account_move_id:
                                    svl.account_move_id.button_draft()
                                    for line in svl.account_move_id.line_ids.filtered(lambda x:x.product_id==product):
                                        if line.credit:
                                            query = """
                                                UPDATE account_move_line
                                                    SET credit = %s where id IN %s
                                            """
                                            self.env.cr.execute(query, [abs(svl.value),tuple(line.ids)])
                                        if line.debit:
                                            query = """
                                                UPDATE account_move_line
                                                    SET debit = %s where id IN %s
                                            """
                                            self.env.cr.execute(query, [abs(svl.value),tuple(line.ids)])
                                    svl.account_move_id.action_post()
                    
                                if val_cost:
                                    if len(svl)==1:
                                        if not svl.account_move_id:
                                            svl.filtered(lambda x:x.quantity>0)._validate_accounting_entries()
                    