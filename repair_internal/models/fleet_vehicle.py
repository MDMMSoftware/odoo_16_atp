from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

class FleetVehicle(models.Model):
    _inherit = "fleet.vehicle"

    type = fields.Selection(selection_add=[('repair_product', 'Repair Product')])
    repair_code_prefix_id = fields.Many2one(string="Prefix",comodel_name='repair.code.prefix')

    seq = fields.Char(string="Sequence",store=True)
    repair_code = fields.Char()


    @api.onchange('repair_code_prefix_id')
    def auto_generate_repair_code(self):
        repair_sequence = self.env['repair.code.sequence']
        if self.repair_code_prefix_id:
            code_sequence = repair_sequence.search([('prefix','=',self.repair_code_prefix_id.id)])

            if code_sequence:
                seq = str(code_sequence.seq)
                if len(seq) > self.repair_code_prefix_id.padding:
                    raise ValidationError("Sequence exceeded the defined padding!!")
                self.seq = seq.zfill(self.repair_code_prefix_id.padding)
            else:
                repair_sequence.create({
                    'prefix':self.repair_code_prefix_id.id,
                    'seq':1
                })
                self.seq = "1".zfill(self.repair_code_prefix_id.padding)
        

    @api.constrains('repair_code_prefix_id')
    def save_repair_code(self):
        repair_prefix = self.repair_code_prefix_id
        if repair_prefix:
            code_sequence = self.env['repair.code.sequence'].search([('prefix','=',repair_prefix.id)],limit=1)
            if code_sequence and self.seq:
                if int(self.seq) == code_sequence.seq:
                    self.repair_code = f"{repair_prefix.name}-{self.seq}"
                    code_sequence.seq += 1
            else:
                raise ValidationError("Sequence Not Found!!!")

class RepairCodeSequence(models.Model):
    _name = 'repair.code.sequence'
    _order = "prefix"

    prefix = fields.Many2one(string="Prefix",comodel_name="repair.code.prefix")
    seq = fields.Integer(string="Next Sequence",default=1)

class RepairCodePrefix(models.Model):
    _name = "repair.code.prefix"

    name = fields.Char()
    padding = fields.Integer(max=7,min=3)

    _sql_constraints = [
        ('uniq_repair_code_prefix', 'unique(name)', 'Repair Code Prefix must be unique.'),
    ]       
