from odoo import models, fields

class ResDepartment(models.Model):
    _description = 'Department'
    _name = 'res.department'
    _inherit = 'mail.thread'
    
    name = fields.Char("Department",tracking=True)
    approve_user_id = fields.Many2many("res.users","res_departments_res_approve_users_rels","department_ids","approve_user_id",string="Approve Users",tracking=True)
    company_id = fields.Many2one('res.company', required=True, string='Company',default=lambda self: self.env.company,readonly=False)
    
    _sql_constraints = [
        ('res_department_unique', 'unique(name,company_id)', 'Department must be unique in the same company!!')
    ] 

class ResUser(models.Model):
    _inherit = "res.users"
    
    department_ids = fields.One2many("res.department",'approve_user_id')