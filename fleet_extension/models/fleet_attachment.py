from odoo import fields, models, api
from odoo.exceptions import ValidationError,UserError

class FleetAttachment(models.Model):
    _name = 'fleet.attachment'

    name = fields.Char()
    company_id = fields.Many2one('res.company', string='Company', required=True,
        default=lambda self: self.env.company)
    attachment_lines = fields.One2many('fleet.attachment.line','attachment_id')

    def unlink(self):
        for attachment_form in self:
            for rec in attachment_form:
                if rec.attachment_id and rec.date_from and rec.date_to and (rec.family_price != 0.0 or rec.internal_price != 0.0 or rec.external_price != 0.0):
                    used_attachments_lines = self.env['duty.process.line'].search([('attachment_id', '=', rec.attachment_id)])
                    for line in used_attachments_lines:
                        if   rec.date_from <= line.duty_id.period_from <= rec.date_to:
                            raise ValidationError("You can't delete attachments lines if some machines have already used it!!")
        return super().unlink()

class FleetAttachmentLine(models.Model):
    _name = 'fleet.attachment.line'

    attachment_id = fields.Many2one('fleet.attachment')
    date_from = fields.Date(string='Start Date', required=True)
    date_to = fields.Date(string='End Date', required=True)
    family_price = fields.Float(default=0.0)
    internal_price = fields.Float(default=0.0)
    external_price = fields.Float(default=0.0)

    def unlink(self):
        for rec in self:
            if rec.attachment_id and rec.date_from and rec.date_to and (rec.family_price != 0.0 or rec.internal_price != 0.0 or rec.external_price != 0.0):
                used_attachments_lines = self.env['duty.process.line'].search([('attachment_id', '=', rec.attachment_id)])
                for line in used_attachments_lines:
                    if   rec.date_from <= line.duty_id.period_from <= rec.date_to:
                        raise ValidationError("You can't delete attachments lines if some machines have already used it!!")
        return super().unlink()