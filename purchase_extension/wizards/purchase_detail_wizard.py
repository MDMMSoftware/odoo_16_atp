from odoo import fields, models, _
from odoo.exceptions import  ValidationError

class SaleDetailReportWizard(models.TransientModel):
    _inherit = 'detail.report.wizard'
    _description = "Sale Detail Report Wizard"

    purchase_team_id = fields.Many2one('purchase.team',string="Team")

    def print_report(self):
        filename = self.env.context.get('filename')
        rp=self.ids
        date_from = self.date_from
        date_to = self.date_to
        project_code_id = self.department_id.id
        unit_id = False
        company_id = self.company_id.id
        department_id = False
        shop_id = self.shop_id.id
        partner_id = self.partner_id.id
        invoice_user_id = self.invoice_user_id.id
        team_id = self.team_id.id
        if rp:
            birt_url = self.env['ir.config_parameter'].sudo().get_param('birt.report.url')
            birt_suffix = self.env['ir.config_parameter'].sudo().get_param('birt.report.url.suffix','')
            url = birt_url + str(filename)  + str(birt_suffix) +f'.rptdesign&date_from='+str(date_from)+'&date_to='+str(date_to)
            if not project_code_id:
                project_code_id = 0
            if not department_id:
                department_id = 0            
            if not unit_id:
                unit_id = 0            
            if not shop_id:
                shop_id = 0            
            if not company_id:
                company_id = 0
            if not partner_id:
                partner_id = 0
            if not invoice_user_id:
                invoice_user_id = 0
            if not team_id:
                team_id = 0
            url = url + '&project_code_id='+str(project_code_id)
            url = url + '&department_id='+str(department_id)
            url = url + '&unit_id='+str(unit_id)
            url = url + '&shop_id='+str(shop_id)
            url = url + '&company_id='+str(company_id)
            url = url + '&partner_id='+str(partner_id)
            url = url + '&invoice_user_id='+str(invoice_user_id)
            url = url + '&team_id='+str(team_id)
            

        if url :
            return {
            'type' : 'ir.actions.act_url',
            'url' : url,
            'target': 'new',
               }
        else:
            raise ValidationError('Report Not Not Found')
       