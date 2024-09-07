from odoo import fields, api, models, Command
from odoo.exceptions import UserError, ValidationError

class ResCompany(models.Model):
    _inherit = 'res.company'
    
    tax_feature = fields.Boolean("Tax Feature",default=False)


class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'
    
    is_tax_line = fields.Boolean("Is Tax Line?",default=False)
    
    @api.depends('product_id', 'product_uom_id')
    def _compute_tax_ids(self):
        for line in self:
            if line.display_type in ('line_section', 'line_note', 'payment_term'):
                continue
            # /!\ Don't remove existing taxes if there is no explicit taxes set on the account.
            if line.product_id or line.account_id.tax_ids or not line.tax_ids:
                line.tax_ids = False
    
class AccountMove(models.Model):
    _inherit = 'account.move'
    
    tax_id = fields.Many2one(comodel_name='account.tax',string="Taxes",default=False)
    
    @api.constrains("tax_id")
    def action_compute_tax(self,manual=True):
        for res in self:
            if res.tax_id and not res.company_id.tax_feature:
                raise ValidationError("Please activate tax feature first!!")
            elif manual and res.state != 'draft':
                raise ValidationError("Tax can be computed only when state is draft..")
            tax_line = res.line_ids.filtered(lambda x:x.is_tax_line == True)
            tax_amount = (res.tax_id.amount / 100) * (res.amount_untaxed-res.discount_amt)
            if tax_line:
                if res.tax_id:
                    pp_id = self.env['product.product'].search([('product_tmpl_id','=',res.tax_id.product_template_id.id)])
                    if not pp_id:
                        raise ValidationError("There is no product associated with the tax!!")
                    tax_line.product_id = pp_id
                    tax_line.quantity = 1
                    tax_line.product_uom_id = pp_id.uom_id
                    tax_line.price_unit = tax_amount
                else:
                    tax_line.unlink()
            else:
                if res.tax_id:
                    pp_id = self.env['product.product'].search([('product_tmpl_id','=',res.tax_id.product_template_id.id)])             
                    res.invoice_line_ids = [Command.create({
                        "product_id":pp_id.id,
                        "product_uom_id":pp_id.uom_id.id,
                        "quantity":1,
                        "price_unit":tax_amount,
                        "is_tax_line":True,
                    })]        
    
    # @api.constrains("tax_id")
    # def sale_order_tax_id(self):
    #     for res in self:
    #         res.action_compute_tax()    