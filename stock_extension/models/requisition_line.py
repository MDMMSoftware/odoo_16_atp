from odoo import models, fields, api, _

class RequisitionLine(models.Model):
    _inherit = "requisition.line"

    custom_part = fields.Char(string="Part ID", related= "product_id.product_tmpl_id.custom_part", store=True, readonly=False, required=False)
