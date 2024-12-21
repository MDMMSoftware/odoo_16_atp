# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models,_
from odoo.exceptions import ValidationError
from collections import defaultdict
from dateutil.relativedelta import relativedelta
from odoo.tools import float_compare

ACCOUNT_DOMAIN = "['&', '&', '&', ('deprecated', '=', False), ('account_type', 'not in', ('asset_receivable','liability_payable','asset_cash','liability_credit_card')), ('company_id', '=', current_company_id), ('is_off_balance', '=', False)]"
    
class ProductTemplate(models.Model):
    _inherit = 'product.template'

    product_code = fields.Char("Product Code")
    expense_ok =  fields.Boolean('Can be Expensed')
    repair_ok =  fields.Boolean('Can be Repaired')

    custom_category_id = fields.Many2one('custom.category',string='Category')
    group_class_id = fields.Many2one('custom.group.class', string= 'Group/Class' )

    custom_brand_id = fields.Many2one('custom.brand', string= 'Brand')
    custom_model_no_id = fields.Many2one('custom.model.no', string= 'Model No.')
    custom_stock_code = fields.Char(string= 'Stock Code')
    custom_part = fields.Char(string= 'Part ID')
    product_location_id = fields.Many2one('product.location',string="Product Location")
    dead_stock_id = fields.Many2one('product.dead.stock.remark',string="Dead Stock Remark")     
    dead_stock_configuration_month = fields.Integer('Dead Stock Configuration Month', default=6)
    dead_stock_status = fields.Boolean('Is dead stock?',compute='_compute_dead_stock')
    # job_id = fields.Many2one('job.code',string="Job")
    function_use = fields.Selection([('autopart', 'AutoPart'), ('operation', 'Operation'),('agri', 'AGRI'),('constuction', 'Construction'),('msp', 'MSP'),('unit','Unit')], default='operation',string="Functional Use")

    # foc_limit = fields.Float('FOC Limit')
    # foc_limit_by = fields.Selection([
    #     ('bymonth','By Month'),('byyear','By Year')
    #     ],string='By',default='bymonth')
    # foc_account = fields.Many2one('account.account',string="FOC Account",domain="[('user_type_id.type', '!=', 'view')]")

    can_be_unit = fields.Boolean('Can be unit')
    can_be_recalculate = fields.Boolean('Recalculate')
    tax_ok = fields.Boolean('Exclude from Job Order?')

    _sql_constraints = [
        ('uniq_product_code_product', 'unique(product_code,company_id)', 'Product Code must be unique withing same company!!'),
    ]          

    def copy(self, default=None):
        default = dict(default or {})
        
        default['product_code'] = self.product_code + ' (Copy)'

        copy_record = super(ProductTemplate, self).copy(default)
        
        return copy_record

    def _compute_dead_stock(self):
        for rec in self:
            product_id = self.env['product.product'].search([('product_tmpl_id','=',rec.id)],limit=1)
            if product_id:

                stock_count = self.env['stock.move'].search_count([
                    ('product_id','=',rec.id),
                    ('date','<=',fields.Datetime.now()),
                    ('date','>=',fields.Datetime.now() - relativedelta(months=rec.dead_stock_configuration_month))
                ])
                if stock_count <= 0:
                    rec.dead_stock_status = True
                else:
                    rec.dead_stock_status = False

    @api.onchange('can_be_unit')
    def _onchange_can_be_unit(self):
        for rec in self:
            if rec.can_be_unit:
                return {
                    'domain': {
                        'custom_category_id': [('what_type','=','unit')],
                        'group_class_id': [('what_type','=','unit')],
                        'custom_brand_id': [('what_type','=','unit')],
                        'custom_model_no_id': [('what_type','=','unit')],
                    }
                }
            return {
                    'domain': {
                        'custom_category_id': [('what_type','=','product')],
                        'group_class_id': [('what_type','=','product')],
                        'custom_brand_id': [('what_type','=','product')],
                        'custom_model_no_id': [('what_type','=','product')],
                    }
                }
             

    analytic_plan_id = fields.Many2one('account.analytic.plan',string="Analytic Plan")
    analytic_account_id = fields.Many2one('account.analytic.account', string="Analytic Account")
    is_analytic_required = fields.Boolean(compute="_compute_is_analytic_required")

    
    def _compute_is_analytic_required(self):
        for rec in self:
            if rec.can_be_unit and rec.tracking == 'none':
                rec.is_analytic_required = True
            else:
                rec.is_analytic_required = False

    @api.onchange('can_be_unit','tracking')
    def _onchange_to_check_analytic_required(self):
        for rec in self:
            if rec.can_be_unit and rec.tracking == 'none':
                rec.is_analytic_required = True
            else:
                rec.is_analytic_required = False


    @api.model
    def create(self, vals_list):
        res = super().create(vals_list)
        if res.analytic_plan_id:
            analytic_account = self.env['account.analytic.account'].create({
                'name': res.product_code,
                'plan_id': res.analytic_plan_id.id
            })  
            res.analytic_account_id = analytic_account
        return res
      
    def write(self, vals_list):
        if 'product_code' in vals_list:
            pp_id = self.env['product.product'].sudo().search([('product_tmpl_id','=',self.id)]).id
            if self.env['stock.move'].sudo().search([('product_id','=',pp_id)],limit=1):
                raise ValidationError("Deleting a product with stock in / out is permitted...")
        res = super().write(vals_list)
        return res

    def name_get(self):
        return [(rec.id,'%s' %(rec.product_code)) for rec in self]  

    @api.onchange('type')
    def _onchange_type(self):
        res = super(ProductTemplate, self)._onchange_type()
        self.invoice_policy = 'order' if self.type == 'service' else 'delivery'
        return res      
    
    @api.model
    def _name_search(self, name, args=None, operator='ilike', limit=100, name_get_uid=None):
        args = args or []
        domain = []
        if name:
            domain = ['|',('name',operator,name),('product_code',operator,name)]
        search_ids = self._search(domain + args,limit=limit,access_rights_uid=name_get_uid)
        return search_ids    
    
class ProductProduct(models.Model):
    _inherit = 'product.product'

    custom_part = fields.Char(string= "Part ID", related= "product_tmpl_id.custom_part",store=True, required=False)

    warehouse_valuation = fields.Many2many('warehouse.valuation','product_product_warehouse_valuation_rel',
                                           'product_product_id','warehouse_valuation_id',ondelete='cascade',readonly=True)    
    can_be_unit = fields.Boolean(related='product_tmpl_id.can_be_unit', store=True)
    can_be_recalculate = fields.Boolean(related='product_tmpl_id.can_be_recalculate', store=True)
    custom_brand_id = fields.Many2one('custom.brand', related= "product_tmpl_id.custom_brand_id")
    product_code = fields.Char(string="Product Code",related="product_tmpl_id.product_code",store=True)

    def name_get(self):
        return [(rec.id,'%s' %(rec.product_code)) for rec in self] 
    
    @api.constrains('barcode')
    def _check_barcode_uniqueness(self):
        """ With GS1 nomenclature, products and packagings use the same pattern. Therefore, we need
        to ensure the uniqueness between products' barcodes and packagings' ones"""
        all_barcode = [b for b in self.mapped('barcode') if b]
        domain = [('barcode', 'in', all_barcode),('company_id','=',self.company_id and self.company_id.id or False)]
        matched_products = self.sudo().search(domain, order='id')
        if len(matched_products) > len(all_barcode):  # It means that you find more than `self` -> there are duplicates
            products_by_barcode = defaultdict(list)
            for product in matched_products:
                products_by_barcode[product.barcode].append(product)

            duplicates_as_str = "\n".join(
                _("- Barcode \"%s\" already assigned to product(s): %s", barcode, ", ".join(p.display_name for p in products))
                for barcode, products in products_by_barcode.items() if len(products) > 1
            )
            raise ValidationError(_("Barcode(s) already assigned:\n\n%s", duplicates_as_str))

        if self.env['product.packaging'].search(domain, order="id", limit=1):
            raise ValidationError(_("A packaging already uses the barcode"))
        
    def _compute_average_price(self, qty_invoiced, qty_to_invoice, stock_moves, is_returned=False):
        """Go over the valuation layers of `stock_moves` to value `qty_to_invoice` while taking
        care of ignoring `qty_invoiced`. If `qty_to_invoice` is greater than what's possible to
        value with the valuation layers, use the product's standard price.

        :param qty_invoiced: quantity already invoiced
        :param qty_to_invoice: quantity to invoice
        :param stock_moves: recordset of `stock.move`
        :param is_returned: if True, consider the incoming moves
        :returns: the anglo saxon price unit
        :rtype: float
        """
        self.ensure_one()
        if not qty_to_invoice:
            return 0

        candidates = stock_moves\
            .sudo()\
            .filtered(lambda m: is_returned == bool(m.origin_returned_move_id and sum(m.stock_valuation_layer_ids.mapped('quantity')) >= 0))\
            .mapped('stock_valuation_layer_ids')\
            .sorted()

        value_invoiced = self.env.context.get('value_invoiced', 0)
        ## added line 
        if qty_invoiced == 0 and value_invoiced != 0:
            value_invoiced = 0
        if 'value_invoiced' in self.env.context:
            qty_valued, valuation = candidates._consume_all(qty_invoiced, value_invoiced, qty_to_invoice)
        else:
            qty_valued, valuation = candidates._consume_specific_qty(qty_invoiced, qty_to_invoice)

        # If there's still quantity to invoice but we're out of candidates, we chose the standard
        # price to estimate the anglo saxon price unit.
        missing = qty_to_invoice - qty_valued
        for sml in stock_moves.move_line_ids:
            if not sml.owner_id or sml.owner_id == sml.company_id.partner_id:
                continue
            missing -= sml.product_uom_id._compute_quantity(sml.qty_done, self.uom_id, rounding_method='HALF-UP')
        if float_compare(missing, 0, precision_rounding=self.uom_id.rounding) > 0:
            # valuation_price
            matched_valuations = candidates.filtered(lambda v:abs(v.quantity) == abs(qty_to_invoice)).sorted()
            if matched_valuations:
                stock_moves[0].sale_line_id.order_id.message_post(body=f"Used valuation price - {matched_valuations[0].unit_cost} for the missing quantity {missing} ")
                valuation +=  matched_valuations[0].unit_cost * missing
            else:
                stock_moves[0].sale_line_id.order_id.message_post(body=f"Used standard price - {self.standard_price} when confirming the invoice becuase of insufficient candidates!! ")
                valuation += self.standard_price * missing
            ## This is original code 
            # valuation += self.standard_price * missing                

        return valuation / qty_to_invoice        

    @api.model
    def _name_search(self, name, args=None, operator='ilike', limit=100, name_get_uid=None):
        args = args or []
        domain = []
        if name:
            domain = ['|',('name',operator,name),('product_code',operator,name)]
        search_ids = self._search(domain + args,limit=limit,access_rights_uid=name_get_uid)
        return search_ids   

class StockLocation(models.Model):
    _inherit = "stock.location"

    _sql_constraints = [
        ('uniq_stock_location_parent_company', 'unique(name,location_id,company_id)', 'Stock Location must be unique with the parent location and company..'),
    ]     

    
class ProductCategory(models.Model):
    _inherit = "product.category"

    property_account_transfer_id = fields.Many2one('account.account', company_dependent=True,
        string="Transfer Account",
        domain=ACCOUNT_DOMAIN,
        help="This account will be used when validating Requisition.")
    
    account_sale_return_id = fields.Many2one('account.account', company_dependent=True,
        string="Sale Return Account",
        domain=ACCOUNT_DOMAIN,
        help="This account will be used when validating Requisition.")


class WarehouseValuation(models.Model):
    _name = "warehouse.valuation"

    location_id = fields.Many2one('stock.location',string="Location",required=True)
    location_cost = fields.Float("Cost")
    warehouse_id = fields.Many2one(related="location_id.warehouse_id",store=True)

class CustomCategory(models.Model):
    _name = 'custom.category'

    name = fields.Char('Name')  
    what_type = fields.Selection([('product','Product'),('unit','Unit')],string="Type",default="product")

    _sql_constraints = [
        ('uniq_custom_proudct_category', 'unique(name)', 'Category name must be unique.'),
    ]    

class CustomGroupClass(models.Model):
    _name = 'custom.group.class'

    name = fields.Char('Name')
    what_type = fields.Selection([('product','Product'),('unit','Unit')],string="Type",default="product")

    _sql_constraints = [
        ('uniq_custom_product_group_calss', 'unique(name)', 'Group Class name must be unique.'),
    ]     

class CustomBrand(models.Model):
    _name = 'custom.brand'

    name = fields.Char('Brand')   
    what_type = fields.Selection([('product','Product'),('unit','Unit')],string="Type",default="product")

    _sql_constraints = [
        ('uniq_custom_product_brand', 'unique(name)', 'Brand name must be unique.'),
    ]       

class CustomModelNo(models.Model):
    _name = 'custom.model.no'

    name = fields.Char('Model No.')   
    what_type = fields.Selection([('product','Product'),('unit','Unit')],string="Type",default="product")

    _sql_constraints = [
        ('uniq_custom_product_model_no', 'unique(name)', 'Model No. must be unique.'),
    ]      

class ProductLocation(models.Model):
    _name = 'product.location'

    name = fields.Char('Name')   

    _sql_constraints = [
        ('uniq_custom_product_location', 'unique(name)', 'Product Location must be unique.'),
    ]                       

class DeadStockRemark(models.Model):
    _name = 'product.dead.stock.remark'

    name = fields.Char('Name') 

    _sql_constraints = [
        ('uniq_custom_product_dead_stock', 'unique(name)', 'Product Dead Stock Remark must be unique.'),
    ]           
    
class AcccountMoveLine(models.Model):
    _inherit = 'account.move.line'
    
    product_label = fields.Char(string="Product Label",related="product_id.product_code")