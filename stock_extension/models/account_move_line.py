from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    custom_part = fields.Char(string="Part ID", related= "product_id.product_tmpl_id.custom_part", store=True, readonly=False, required=False)

class AccountMove(models.Model):
    _inherit = "account.move"

    need_to_regenreate_sequence = fields.Boolean(string="Need to regenreate sequence",default=False)

    def regenerate_sequence(self):
        # account_moves = self.env['account.move'].browse(lst)
        for movee in self:
            sequence = movee._get_last_sequence(False,None,False)
            if sequence:
                sequence_parts = sequence.split("/")
                if len(sequence_parts) == 4:
                    sequence_number = int(sequence_parts[-1]) + 1
                    sequence_parts[-1] = str(sequence_number)
                    full_name = "/".join(sequence_parts)
                    sequence_prefix = "/".join(sequence_parts[:-1]) + '/'
                    self.env.cr.execute(f"UPDATE account_move SET name = '{full_name}', sequence_number = {sequence_number},sequence_prefix = '{sequence_prefix}' where id = {movee.id};")
                    self.env.cr.commit()
                    movee.need_to_regenreate_sequence = False
                else:
                    raise ValidationError(f"The sequence - {sequence} - does not have 4 parts in the id of {movee.id}!!!")
            else:
                raise ValidationError(f"The sequence - {sequence} - cannot be created in the id of {movee.id}!!!")



