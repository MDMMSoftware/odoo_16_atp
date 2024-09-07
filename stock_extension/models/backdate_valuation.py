from odoo import models, fields, api
from odoo.exceptions import UserError


class StockPicking(models.Model):
    """inherited stock.picking"""
    _inherit = "stock.picking"

    def action_print(self):
        filename = self.env.context.get('filename')
        if not filename:
            raise UserError('Filename Not found!!!')
        birt_suffix = self.env['ir.config_parameter'].sudo().get_param('birt.report.url.suffix','')
        if self.id:
            url = self.env['ir.config_parameter'].sudo().get_param('birt.report.url.html') + str(filename)  + str(birt_suffix) + '.rptdesign&pp_id=' + str(self.id) + "&&__dpi=96&__format=html&__pageoverflow=0&__overwrite=false"
        if url :
            return {
            'type' : 'ir.actions.act_url',
            'url' : url,
            'target': 'new',
            }
        else:
            raise UserError('Report Not Not Found') 

    def _action_done(self):
        res = super()._action_done()
        for val in self:
            val.write({'date_done':val.scheduled_date})
            for res in val.move_ids:
                res.write({'date':val.scheduled_date})
            for res in val.move_line_ids:
                res.write({'date':val.scheduled_date})

    def unlink(self):
        for rec in self:
            if rec.state != 'draft':
                raise UserError("Are you doing something fraudly! Why do you want to delete some records?? 🤔")
        return super().unlink()
        
class SaleOrder(models.Model):
    """inherited sale order"""
    _inherit = 'sale.order'

    def _prepare_confirmation_values(self):
        """ Prepare the sales order confirmation values.

        Note: self can contain multiple records.

        :return: Sales Order confirmation values
        :rtype: dict
        """
        return {
            'state': 'sale',
            'date_order': self.date_order or fields.Datetime.now()
        }

