from odoo import fields, api, models, Command
from odoo.exceptions import UserError, ValidationError

class AccountTax(models.Model):
    _inherit = 'account.tax'
    
    def _get_country_as_default(self):
        company_id = self.env.company or self.company_id
        country_id = company_id.account_fiscal_country_id
        if  not country_id:
            raise UserError("There is no configured company for the current company!!")
        return country_id
            
    
    product_template_id = fields.Many2one("product.template",string="Product")
    country_id = fields.Many2one(string="Country", comodel_name='res.country', required=True, help="The country for which this tax is applicable.",default=_get_country_as_default)
    
class SaleOrder(models.Model):
    _inherit = 'sale.order'
    
    tax_id = fields.Many2one(comodel_name='account.tax',string="Taxes",default=False,copy=False)    
    
    def _prepare_invoice(self):
        """override prepare_invoice function to include department"""
        invoice_vals = super(SaleOrder, self)._prepare_invoice()
        invoice_vals['tax_id'] = self.tax_id.id or False
        return invoice_vals    
    
    @api.constrains("tax_id","order_line")
    def action_compute_tax(self):
        for res in self:
            if res.tax_id and not res.company_id.tax_feature:
                raise ValidationError("Please activate tax feature first!!")
            res.amount_tax = (res.tax_id.amount / 100) * (res.amount_untaxed-res.discount_amt)
            res.amount_total = ( res.amount_untaxed - res.discount_amt ) + res.amount_tax             
            