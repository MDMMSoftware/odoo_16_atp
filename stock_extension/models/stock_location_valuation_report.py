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
     
