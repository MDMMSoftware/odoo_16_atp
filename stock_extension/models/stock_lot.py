from odoo import models, api, fields

class StockLot(models.Model):
    _inherit = "stock.lot"

    analytic_plan_id = fields.Many2one('account.analytic.plan',string="Analytic Plan")
    can_be_unit = fields.Boolean(related='product_id.can_be_unit')
    analytic_account_id = fields.Many2one('account.analytic.account', string="Analytic Account")

    @api.model
    def create(self, vals_list):
        res = super().create(vals_list)
        if res.analytic_plan_id:
            analytic_account = self.env['account.analytic.account'].create({
                'name': res.name,
                'plan_id': res.analytic_plan_id.id
            })  
            res.analytic_account_id = analytic_account
        return res  


# class StockReport(models.TransientModel):
#     _inherit = 'stock.traceability.report'

#     def _make_dict_move(self, level, parent_id, move_line, unfoldable=False):
#         res_dict = super()._make_dict_move(level, parent_id, move_line, unfoldable)
#         res_dict[0]['partner_name'] = move_line.picking_partner_id.name
#         return res_dict