from odoo import models, fields, api,_
from odoo.exceptions import ValidationError

class PrepaidRegisterPayment(models.Model):
    _name = "prepaid.register.payment"

    date = fields.Date('Date',default=fields.date.today(),required=True)
    amount = fields.Float('Amount',required=True)
    prepaid_id = fields.Many2one('account.payment.prepaid',string="Prepaid")
    payment_id = fields.Many2one('account.payment',string="Payment")
    move_id = fields.Many2one('account.move',string="Entry:")
    user_id = fields.Many2one('res.users',string="User:")
    ref = fields.Char('Ref.',required=True)

    def checking_amount(self):
        if self.amount <= 0.0:
            raise ValidationError('Invalid amount.')
        if self.prepaid_id.amount+self.amount == self.prepaid_id.prepare_amount:
            self.prepaid_id.state='paid'
            return True
        
    def action_register(self):
        for rec in self:
            rec.checking_amount()
            payment_id,move_id = rec.prepaid_id.prepaid_vendor_payment(rec)
            if not move_id:
                raise ValidationError('Invalid Payment Register.')
            rec.move_id = move_id[0]
            rec.payment_id = payment_id[0]
            rec.user_id = self.env.user.id