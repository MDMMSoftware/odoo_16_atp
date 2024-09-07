from odoo import fields, api, models, Command
from odoo.exceptions import UserError, ValidationError
    
class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'
    
    tax_id = fields.Many2one(comodel_name='account.tax',string="Taxes",default=False,copy=False) 
    
    def _prepare_invoice(self):
        """override prepare_invoice function to include department"""
        invoice_vals = super(PurchaseOrder, self)._prepare_invoice()
        invoice_vals['tax_id'] = self.tax_id.id or False
        return invoice_vals     
    
    @api.constrains("tax_id","order_line")
    def action_compute_tax(self):
        for res in self:
            if res.tax_id and not res.company_id.tax_feature:
                raise ValidationError("Please active tax feature first!!")
            res.amount_tax = (res.tax_id.amount / 100) * (res.amount_untaxed-res.discount_amt)
            res.amount_total = ( res.amount_untaxed - res.discount_amt ) + res.amount_tax 

        