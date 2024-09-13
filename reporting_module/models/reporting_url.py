from datetime import datetime
from odoo import api, fields, models, _
from odoo.exceptions import  ValidationError

class ReportingURL(models.Model):
    _name = 'reporting.url'

    name = fields.Char("Reporting Name")
    url = fields.Char("Reporting URL")


class DetailReportWizard(models.TransientModel):
    _name = 'detail.report.wizard'
    _description = "Detail Report Wizard"

    @api.model
    def _get_default_company(self):
        return self.env.user.company_id

    @api.model
    def _get_default_branch(self):
        return self.env.user.branch_id

    @api.model
    def get_today(self):
        my_date = fields.Datetime.context_timestamp(self, timestamp=datetime.now())
        return my_date
    
    date_from = fields.Date('From Date',default=get_today)
    date_to = fields.Date('To Date',default=get_today)
    company_id = fields.Many2one('res.company', 'Company',default=_get_default_company)
    shop_id = fields.Many2one('res.branch',string="Branch",default=_get_default_branch)
    department_id = fields.Many2one('res.department','Department',default=False,required=False,readonly=True,)
    partner_id = fields.Many2one('res.partner',string="Customer",domain=False)
    invoice_user_id = fields.Many2one('res.users',string="Sale Person", default=lambda self: self.env.user, readonly=False)
    # team_id = fields.Many2one('crm.team',string="Team")
    # purchase_team_id = fields.Many2one('crm.purchase_team',string="
    # all_read_user = fields.Boolean('Show Sale Person?')

    @api.onchange('unit_id')
    def onchange_business_unit(self):
        if self.unit_id.name in ['Machinery Rental Service','Machinery Rental Service']:
            self.invoice_user_id = False 

    def print_report(self):
        filename = self.env.context.get('filename')
        report_type = self.env.context.get('report_type')
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
        if report_type == 'sale':
            team_id = self.team_id.id
        elif report_type == 'purchase' and hasattr(self, 'purchase_team_id'):
            team_id = self.purchase_team_id.id
        else:
            team_id = False
        if rp:
            birt_url = self.env['ir.config_parameter'].sudo().get_param('birt.report.url')
            url = birt_url+f'{filename}&date_from='+str(date_from)+'&date_to='+str(date_to)
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
            'target': 'current',
               }
        else:
            raise ValidationError('Report Not Not Found')            