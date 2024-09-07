from odoo import models, fields, api
from odoo.exceptions import ValidationError, UserError

class CustomizeSequence(models.Model):
    _name = 'sequence.model'
    _inherit = 'mail.thread'

    parent_type = fields.Selection([('company','Company'),('branch','Branch')], default='company')
    branch_id =  fields.Many2one('res.branch',string="Branch",required=False)
    company_id = fields.Many2one('res.company',string="Company",required=False)
    transfer_type = fields.Selection([
        ('pay','Pay'),
        ('receive','Receive'),
        ('transfer','Transfer')
    ],string="Transfer Type",default="pay") 
    code = fields.Char(string="Code")
    model_id = fields.Many2one('ir.model', string="Model", track_visibility='onchange',required=False)
    prefix = fields.Char('Prefix',required=True)
    padding = fields.Integer('Padding',required=True)    
    sequence_line_ids = fields.One2many('sequence.model.line', 'sequence_id', string='Sequence Line')
    padding_str = fields.Char('Padding Str',compute='compute_padding_str')
    ir_action_id = fields.Many2one(string='IR Actions',comodel_name='ir.actions.actions')
    fleet_service = fields.Boolean(default=False,string="Is Fleet Service?")
    

    @api.constrains('code','model_id','sequence_line_ids')
    def constrains_create_model(self):
        for rec in self:
            if not rec.model_id:
                raise ValidationError('Empty Model.')
            seq_ids = self.env['sequence.model'].search([('company_id','=',rec.company_id.id),('model_id','=',rec.model_id.id),('prefix','=',rec.prefix),('code','=',rec.code),('id','!=',rec.id)],limit=1)
            if seq_ids:
                raise ValidationError('Duplicate Code in Model.')
            if not rec.sequence_line_ids:
                raise ValidationError('Invalid Line.') 
            
    @api.onchange('branch_id')
    def onchange_branch_id(self):
        if self.branch_id:
            self.company_id = False
            if not self.branch_id.short_code:
                self.branch_id = False
                self.code = False
                raise ValidationError(f"Short Code is not defined for `{self.branch_id.name}` Company.")
            self.code = self.branch_id.short_code    

    @api.onchange('company_id')
    def onchange_unit_id(self):
        if self.company_id:
            self.branch_id = False
            if not self.company_id.short_code:
                self.company_id = False
                self.code = False
                raise ValidationError(f"Short Code is not defined for `{self.company_id.name}` Company.")
            self.code = self.company_id.short_code            

    @api.depends('padding')
    def compute_padding_str(self):
        for rec in self:
            rec.padding_str = '0' * rec.padding


class CustomizeSequenceLine(models.Model):
    _name = 'sequence.model.line'

    start_date = fields.Date('Start Date',required=True)
    end_date = fields.Date('End Date',required=True)
    sequence = fields.Integer('Next Number',default=0)
    sequence_id = fields.Many2one('sequence.model',string="Reference Sequence")
    company_id = fields.Many2one('res.company',string="Company",related='sequence_id.company_id',store=True)
    model_id = fields.Many2one('ir.model', string="Model",related='sequence_id.model_id',store=True)
    prefix = fields.Char('Prefix',related='sequence_id.prefix',store=True)
    padding = fields.Integer('Padding',related='sequence_id.padding',store=True)
    padding_str = fields.Char('Padding Str',related='sequence_id.padding_str',store=True)
    code = fields.Char('Code',related='sequence_id.code',store=True)  

    @api.constrains("start_date","end_date") 
    def check_sequence_line(self):
        if self.sequence_id:
            if self.start_date > self.end_date:
                raise UserError("End Date must be greater than Start Date")
            duplicate_lines = self.sequence_id.sequence_line_ids.filtered(lambda x:( (self.start_date >= x.start_date and self.start_date <= x.end_date) or (self.end_date >= x.start_date and self.end_date <= x.end_date) )and (x.id != self.id))
            if duplicate_lines:
                raise UserError("Duplicate Dates are found!!")

class ResCompany(models.Model):
    _inherit = "res.company"

    short_code = fields.Char(required=True, string="Short Code")    

    def action_view_sequence_model(self):
        sequences = self.env['sequence.model'].search([('company_id','=',self.id)]).ids
        action = self.env['ir.actions.actions']._for_xml_id('customize_sequence.view_sequence_model_action')
        if len(sequences) > 1 or len(sequences) == 0:
            action['domain'] = [('id', 'in', sequences)]
        elif len(sequences) == 1:
            form_view = [(self.env.ref('customize_sequence.view_sequence_mode_form').id, 'form')]
            if 'views' in action:
                action['views'] = form_view + [(state,view) for state,view in action['views'] if view != 'form']
            else:
                action['views'] = form_view
            action['res_id'] = sequences[0]
        else:
            action = {'type': 'ir.actions.act_window_close'}

        return action    