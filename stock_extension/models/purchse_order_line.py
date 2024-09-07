from odoo import models, fields, api, _

class PurchaseOrderLine(models.Model):
    _inherit = "purchase.order.line"

    custom_part = fields.Char(string="Part ID", related= "product_id.product_tmpl_id.custom_part", store=True, readonly=False, required=False)
