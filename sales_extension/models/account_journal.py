from odoo import models, fields, api, _

class AccountJournalExt(models.Model):
    _inherit = 'account.journal'

    default_analytic_account_ids = fields.Many2many('account.analytic.account', 'journal_default_account_analytic_account_rel', 'journal_id', 'account_analytic_account_id', string="Default Analytic Accounts")

    @api.onchange("default_analytic_account_ids")
    def onchange_default_analytic_account_ids(self):
        if self.default_analytic_account_ids:
            added_plan = [default_analytic_account.plan_id.id for default_analytic_account in self.default_analytic_account_ids]
            all_analytic_plans = self.env['account.analytic.plan'].search([('id', 'not in', added_plan)]).ids
            return {"domain" : {"default_analytic_account_ids" : ['&',('plan_id','in', all_analytic_plans),('company_id','=',self.company_id.id)]}}
        return {"domain" : {"default_analytic_account_ids" : [('company_id','=',self.company_id.id)]}}