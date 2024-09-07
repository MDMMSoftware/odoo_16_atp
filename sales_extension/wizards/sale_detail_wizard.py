from odoo import fields, models, _

class SaleDetailReportWizard(models.TransientModel):
    _inherit = 'detail.report.wizard'
    _description = "Sale Detail Report Wizard"

    team_id = fields.Many2one('crm.team',string="Team")
