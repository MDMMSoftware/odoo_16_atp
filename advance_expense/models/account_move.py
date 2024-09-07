from odoo import models
from ...generate_code import generate_code

class ExtMoveReversal(models.TransientModel):
    _inherit = 'account.move.reversal'

    def reverse_moves(self):        
        result = super(ExtMoveReversal, self).reverse_moves()
        moves = self.move_ids
        sequence = self.env['sequence.model']
        for move in moves:
            for reverse_move in move.reversal_move_id:
                if self.date_mode == 'entry':
                    reverse_move.invoice_date = move.invoice_date
                # if not reverse_move.seq_no:
                #     code = generate_code.generate_code(sequence,reverse_move,reverse_move.branch_id,reverse_move.company_id,reverse_move.invoice_date,None,'account.action_move_out_refund_type')
                #     reverse_move.name = code
            # if move.move_type == 'out_invoice':
            #     if move.partner_id.return_account_id:
            #         partner_income_id = move.partner_id.return_account_id.id
            #         reverse_move_id = self.env['account.move'].search([('reversed_entry_id','=',move.id)])
            #         for line in reverse_move_id.invoice_line_ids:
            #             sql2 = "UPDATE account_move_line set account_id=%s where id=%s;"
            #             self._cr.execute(sql2,(partner_income_id,line.id))
        return result

    # def _prepare_default_reversal(self, move=None):
    #     result = super(ExtMoveReversal, self)._prepare_default_reversal(move=move)
    #     result.update({'ref': _('Reversal of: %(move_name)s, %(reason)s', move_name=move.ref, reason=self.reason) 
    #                if self.reason
    #                else _('Reversal of: %s', move.ref),})
    #     return result