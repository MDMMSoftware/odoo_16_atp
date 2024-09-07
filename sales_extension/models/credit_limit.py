from odoo import models, api, fields, _
from odoo.exceptions import ValidationError
from collections import Counter
from odoo.tests import Form

class CreditLimitApprove(models.Model):
    _name = 'credit.limit.approve'
    _inherit = ['mail.thread']

    order_id = fields.Many2one('sale.order', string="Sale Order")
    order_date = fields.Datetime('Order Date', related="order_id.date_order")
    partner_id = fields.Many2one('res.partner', string="Partner", related="order_id.partner_id")
    credit_limit = fields.Float('Credit Limit', related="partner_id.credit_limit")
    currency_id = fields.Many2one(related="order_id.currency_id")
    order_amt = fields.Monetary("Sale Order Amount", related="order_id.amount_total")
    state = fields.Selection([
        ('draft', 'Draft'),
        ('approve', 'Approved'),
        ('reject', 'Rejected')
    ], string='Status', readonly=True, copy=False, default='draft', track_visibility='onchange')
    name = fields.Char('')

    credit = fields.Monetary("Past Credit",related="partner_id.credit")

    @api.depends('name')
    def name_get(self):
        result = []
        name = None
        val = ''
        for rec in self:
            if rec.order_id:
                val = rec.order_id.name
            name = "Quotation - " + val
            result.append((rec.id, name))
        return result

    def action_approve(self):
        self.order_id.credit_status = 'no'
        self.write({'state': 'approve'})

    def action_reject(self):
        self.order_id.credit_status = 'hold'
        self.write({'state': 'reject'})

    def action_reset_to_draft(self):
        self.order_id.credit_status = 'notify'
        self.write({'state': 'draft'})


class ResPartner(models.Model):
    _inherit = 'res.partner'

    credit_status = fields.Selection([
        ('notify', 'Notify Over Limit'),
        ('hold', 'Hold Credit Limit'),
        ('no', 'No Credit Limit')
    ], string='Credit Status', default="hold", tracking=True)
    use_partner_credit_limit = fields.Boolean(
        string='Partner Limit', groups='account.group_account_invoice,account.group_account_readonly',
        compute='_compute_use_partner_credit_limit', inverse='_inverse_use_partner_credit_limit', tracking=True)
    credit_limit = fields.Float(
        string='Credit Limit', help='Credit limit specific to this partner.',
        groups='account.group_account_invoice,account.group_account_readonly',
        company_dependent=True, copy=False, readonly=False, tracking=True)
    
    @api.depends_context('company')
    def _credit_debit_get(self):
        if not self.ids:
            self.debit = False
            self.credit = False
            return
        tables, where_clause, where_params = self.env['account.move.line']._where_calc([
            ('parent_state', '!=', 'cancel'),
            ('company_id', '=', self.env.company.id)
        ]).get_sql()

        where_params = [tuple(self.ids)] + where_params
        if where_clause:
            where_clause = 'AND ' + where_clause
        self._cr.execute("""SELECT account_move_line.partner_id, a.account_type, SUM(account_move_line.amount_residual)
                      FROM """ + tables + """
                      LEFT JOIN account_account a ON (account_move_line.account_id=a.id)
                      WHERE a.account_type IN ('asset_receivable','liability_payable')
                      AND account_move_line.partner_id IN %s
                      AND account_move_line.reconciled IS NOT TRUE
                      """ + where_clause + """
                      GROUP BY account_move_line.partner_id, a.account_type
                      """, where_params)
        treated = self.browse()
        for pid, type, val in self._cr.fetchall():
            partner = self.browse(pid)
            if type == 'asset_receivable':
                partner.credit = val
                if partner not in treated:
                    partner.debit = False
                    treated |= partner
            elif type == 'liability_payable':
                partner.debit = -val
                if partner not in treated:
                    partner.credit = False
                    treated |= partner
        remaining = (self - treated)
        remaining.debit = False
        remaining.credit = False    


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    term_type = fields.Selection([('direct', 'Cash Sales'), ('credit', 'Credit Sales')],
                                 string='Payment Type', default="direct", tracking=True)
    credit_status = fields.Selection([
        ('notify', 'Notify Over Limit'),
        ('hold', 'Hold Credit Limit'),
        ('no', 'No Credit Limit')
    ], string='Credit Status', default="no", tracking=True)

    @api.depends('company_id', 'partner_id', 'amount_total', 'term_type')
    def _compute_partner_credit_warning(self):
        for order in self:
            order.with_company(order.company_id)
            order.partner_credit_warning = ''
            show_warning = order.state in ('draft', 'sent') and \
                           order.company_id.account_use_credit_limit
            if order.term_type != 'credit':
                order.credit_status = False
            if show_warning and self.term_type == 'credit':
                updated_credit = order.partner_id.commercial_partner_id.credit + (order.amount_total / order.currency_rate)
                order.partner_credit_warning = self.env['account.move']._build_credit_warning_message(
                    order, updated_credit)
                credit_record = self.env['credit.limit.approve'].sudo().search([('order_id', '=', self.id)], limit=1)
                if order.partner_credit_warning != '':
                    if not credit_record:
                        order.credit_status = order.partner_id.credit_status
                        if order.partner_id.credit_status == 'notify':
                            self.env['credit.limit.approve'].sudo().create({
                                "order_id": self.id,
                                "state": "draft"
                            })
                    elif credit_record and credit_record.state == 'draft':
                        order.credit_status = order.partner_id.credit_status
                else:
                    order.credit_status = 'no'
                            
    def action_confirm(self):
        if self.term_type == 'credit' and self.company_id.account_use_credit_limit and self.partner_id.use_partner_credit_limit:
            if self.credit_status == 'hold':
                raise ValidationError("As the credit limit of the partner is exceeded, you can't confirm the current sale order!!")
            elif self.credit_status == 'notify':
                raise ValidationError("Please contact the manager to check the credit limit status of the partner!!")
        else:
            credit_record = self.env['credit.limit.approve'].sudo().search([('order_id', '=', self.id)], limit=1)
            if credit_record:
                credit_record.sudo().unlink()

        for line in self.order_line:
            if line.can_be_unit and not line.serial_no_id and not line.product_id.tracking == 'none':
                raise ValidationError(_('Serial Number is required for unit product: ') + line.product_id.name)
            if line.can_be_unit and not line.product_id.tracking == 'none':
                unit_lines = self.order_line.filtered(lambda x: x.can_be_unit == True)
                if len(unit_lines) != len(unit_lines.mapped('serial_no_id').ids):
                    raise ValidationError(_('Serial Number must be unique for each product. Check your Serial Numbers!!'))
                check_serial_number = self.env['sale.order.line'].search_count([('id', '!=', line.id), ('serial_no_id', '=', line.serial_no_id.id), ('state', 'not in', ('draft', 'cancel'))])
                if check_serial_number != 0:
                    raise ValidationError(_('Serial No %s already have a confirmed order!!' % line.serial_no_id.name))

            if line.product_id.detailed_type == 'product':
                line.check_stock()
        if self.partner_id and self.partner_id.partner_type == 'vendor' and self.partner_id.is_duty_owner:
            if hasattr(self.order_line[0], 'fleet_id'):
                dct = Counter([line_id.fleet_id.id for line_id in self.order_line])
                if False in dct:
                    raise ValidationError("Found blank fleet in the order line..")
                if len(dct) != 1:
                    raise ValidationError("You must add same fleet in all order lines when it is associated with duty owner - vendor!!")
        self.confirm_generate_code_so()

        if self.sale_type == 'counter_sale':
            for picking in self.picking_ids.filtered(lambda x: x.state != 'cancel'):
                picking.action_assign()
                wiz = picking.button_validate()
                wiz = Form(self.env['stock.immediate.transfer'].with_context(wiz['context'])).save()
                wiz.process()
            self._create_invoices(final=True)
            return self.action_view_invoice()
