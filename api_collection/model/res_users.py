import json

import werkzeug

from odoo.exceptions import AccessDenied, UserError
from odoo import api, models, fields, _


class Users(models.Model):
    _inherit = "res.users"
    _description = 'Res Users'
    
    noti_token = fields.Char("Noti Token")
    is_operation = fields.Boolean("Accessed Operation",default=False)
    

class HREmployee(models.Model):
    _inherit = "hr.employee"
    
    is_operation = fields.Boolean(related='user_id.is_operation',store=True)