
from odoo import models, fields, api

class ResourceCalenderLeaves(models.Model):
    _inherit = "resource.calendar.leaves"

    company_id = fields.Many2one(
        'res.company', string="Company", readonly=False, store=True,
        default=lambda self: self.env.company, compute='_compute_company_id')
    description = fields.Char(string="Description")

class ResourceCalender(models.Model):
    _inherit = "resource.calendar"

    _sql_constraints = [
        ('unique_resource_name_per_company','unique(name,company_id)','Working Time Name must be unique per company!!!'),
    ]