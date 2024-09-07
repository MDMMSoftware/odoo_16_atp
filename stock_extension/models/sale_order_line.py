from odoo import models, fields, api, _

class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    custom_part = fields.Char(string="Part ID", related= "product_template_id.custom_part", store=True, readonly=False, required=False)

class PricelistItem(models.Model):
    _inherit = "product.pricelist.item"
    
    name = fields.Char("Name",related="product_tmpl_id.name")
    custom_category_id = fields.Many2one('custom.category',string='Category',related="product_tmpl_id.custom_category_id")
    group_class_id = fields.Many2one('custom.group.class', string= 'Group/Class',related="product_tmpl_id.group_class_id")
    custom_brand_id = fields.Many2one('custom.brand', string= 'Brand',related="product_tmpl_id.custom_brand_id")
    custom_model_no_id = fields.Many2one('custom.model.no', string= 'Model No.',related="product_tmpl_id.custom_model_no_id")
    custom_part = fields.Char(string= 'Part ID',related="product_tmpl_id.custom_part")    
    default_code = fields.Char(string= 'Default Code',related="product_tmpl_id.default_code")