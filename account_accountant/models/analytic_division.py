from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

class AnalyticDivision(models.Model):
    _name = 'analytic.division'

    name = fields.Char("Name")
    company_id = fields.Many2one("res.company","Company",default=lambda self:self.env.company)
    analytic_plan_id = fields.Many2one("account.analytic.plan","Analytic Plan")
    analytic_account_id = fields.Many2one("account.analytic.account","Analytic Account")

    _sql_constraints = [
        ('unique_division_per_company','unique(name,company_id)','Division must be unique within the same company!!')
    ]    
    

    @api.model
    def create(self, vals):
        analytic_acc = False
        if vals['name'] and vals['name'].strip() != '' and vals['analytic_plan_id']:
            analytic_acc = self.env['account.analytic.account'].create({
                    'name': vals['name'],
                    'plan_id':vals['analytic_plan_id'],
                    'company_id': vals['company_id']
            })
            vals['analytic_account_id'] = analytic_acc.id
        else:
            raise ValidationError("Invalid Division Name!!")
        division = super().create(vals)
        if analytic_acc and hasattr(analytic_acc, 'division_id') and division:
            analytic_acc.division_id = division.id
        return division

    def write(self, vals):
        if 'name' in vals:
            div_objs = self.env['analytic.division'].search([('name','=',vals['name']),('id','!=',self.id)])
            if div_objs:
                raise ValidationError("Division Name is already existed!!")
            if self.analytic_account_id:
                self.analytic_account_id.name = vals['name'] 
        return super().write(vals)
    
    def unlink(self):
        for rec in self:
            div_obj = self.env['account.analytic.account'].search([('name','=',rec.name)])
            if div_obj:
                div_obj.unlink()
            return super().unlink()    

class AccountAnalyticAccount(models.Model):
    _inherit = 'account.analytic.account'

    division_id = fields.Many2one('analytic.division','Division')      

class ResCompany(models.Model):
    _inherit = 'res.company'

    allow_division_feature = fields.Boolean(string="Use Division Feature?",default=False) 
    allow_partner_prefix_feature = fields.Boolean(string="Allow Partner Prefix Feature", default=False)
    company_logo = fields.Image(string="Company Logo")
    allow_partner_domain_feature = fields.Boolean(string="Allow Partner Domain")