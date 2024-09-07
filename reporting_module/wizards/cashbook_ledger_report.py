from odoo import models, fields, api
from datetime import datetime
from odoo.exceptions import ValidationError

class CashbookLedgerWizard(models.TransientModel):
    _name = 'cashbook.ledger.report.wizard'
    _description = 'Cashbook Ledger Report Wizard'

    from_date = fields.Date('From Date', default=datetime.now())
    to_date = fields.Date('To Date', default=datetime.now())
    account_id = fields.Many2one('account.account',string='Account Name')
    account_code = fields.Char(string='Account Code',related="account_id.code")
    currency_id = fields.Many2one('res.currency',string='Currency',default=lambda self:self.env.company.currency_id)
    company_id = fields.Many2one('res.company',string='Company',default=lambda self:self.env.company)
    state = fields.Selection([('all','All'),('posted','Post')],string='State',default='posted')
    branch_id = fields.Many2one("res.branch",string="Branch")

    # Birt Report Print
    def print_cashbook_ledger(self):
        rp = self.ids
        filename = self.env.context.get("filename")

        date_from = self.from_date
        date_to = self.to_date
        account = self.account_id.id
        company_id = self.company_id.id

        currency_id = self.currency_id.id
        branch_id = self.branch_id.id
        st = self.state
        #print emp
        if rp and filename:
            if not branch_id:
                branch_id = 0    
            birt_suffix = self.env['ir.config_parameter'].sudo().get_param('birt.report.url.suffix','')       
            url = self.env['ir.config_parameter'].sudo().get_param('birt.report.url') + str(filename) + str(birt_suffix) + f'.rptdesign&date_from=' + str(date_from)+'&date_to='+str(date_to) + '&account=' + str(account) + '&company_id=' + str(company_id) + '&currency_id=' + str(currency_id) + '&shop_id='+str(branch_id) + '&state='+str(st) 

        if url :
            return {
            'type' : 'ir.actions.act_url',
            'url' : url,
            'target': 'new',
               }
        else:
            raise ValidationError('Report Not Not Found')