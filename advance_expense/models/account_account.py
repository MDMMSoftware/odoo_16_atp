from odoo import models,fields

class AccountGroupReport(models.Model):
    _name = "account.group.report"
    _description = "Account Group Report"
    
    name = fields.Char("Name")
    account_ids = fields.Many2many(
                                    comodel_name="account.account",relation="account_group_report_account_account_rel",
                                    column1="account_group_report_id",column2="account_id",string="Chart of Accounts"
                                )
    
    _sql_constraints = [
        ('unique_account_group_report_name','unique(name)','Name must be unique..')
    ]