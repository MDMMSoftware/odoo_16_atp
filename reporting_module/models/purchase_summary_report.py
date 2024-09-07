from odoo import models, fields,  _, tools
from odoo.exceptions import ValidationError

class PurchaseSummaryReport(models.Model):
    _name = 'purchase.summary.report'
    _auto = False
    _order = 'id'

    internal_ref = fields.Char('Internal Ref.')
    type = fields.Char('Type',compute='compute_type')
    invoice_date = fields.Date('Invoiced Date',readonly=True)
    year_str = fields.Integer('Year',readonly=True)
    month_str = fields.Integer('Month',readonly=True)
    ref_invoice = fields.Char('Ref. #',readonly=True)
    partner_id = fields.Many2one('res.partner',string="Name",readonly=True)
    payment_term_id = fields.Many2one('account.payment.term',string="Terms Type",readonly=True)
    # project_code_id = fields.Many2one('analytic.project.code', 'Project Code',readonly=True)
    # pj_desc = fields.Char('Description',readonly=True)
    company_id = fields.Many2one('res.company',string="Company",readonly=True)  
    department_id = fields.Many2one('res.department',string="Department",readonly=True)  
    branch_id = fields.Many2one('res.branch',string="Branch",readonly=True)
    total_amount = fields.Float('Total Amount',readonly=True)
    discount = fields.Float('Discount',readonly=True)
    tax = fields.Float('Tax',readonly=True)
    net_amt = fields.Float('Net Amount',readonly=True)
    settled_amt = fields.Float('Settled Amount',readonly=True)
    balance = fields.Float('Balance',readonly=True)
    vendor_category_id = fields.Many2one('res.partner.vendor.category',string="Vendor Category",readonly=True)
    move_id = fields.Many2one('account.move',string="Move ID",readonly=True)

    def compute_type(self):
        for rec in self:
            type = 'Bill'
            if rec.move_id:
                if rec.move_id.move_type == 'in_refund':
                    type = 'Refund'
            rec.type = type

    def action_enter_move_id(self):
        for rec in self:
            if rec.move_id:
                return {
                    'name': _('Vendor Bill'),
                    'view_mode': 'form',
                    'res_model': 'account.move',
                    'res_id': rec.move_id.id,
                    'view_id': False,
                    'type': 'ir.actions.act_window',
                    'target': 'current',
                } 
            else:
                raise ValidationError('Currenlty Not Linked With Invoice.')

    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute('''
            CREATE OR REPLACE VIEW %s AS (
            select
            row_number() over () as id
            ,am.internal_ref as internal_ref
            ,'' as type
            ,am.invoice_date as invoice_date
            ,extract(year from am.invoice_date) as year_str
            ,extract(month from am.invoice_date) as month_str
            ,am.ref as ref_invoice
            ,am.partner_id as partner_id
            ,am.invoice_payment_term_id as payment_term_id
            ,am.company_id as company_id
            ,am.department_id as department_id
            ,am.branch_id as branch_id
            ,(case when am.move_type='in_refund' then -1*am.amount_untaxed else am.amount_untaxed end) as total_amount
            ,(case when am.move_type='in_refund' then -1*am.discount_amt_currency else am.discount_amt_currency end) as discount
            ,(case when am.move_type='in_refund' then -1*am.amount_tax else am.amount_tax end) as tax
            ,(case when am.move_type='in_refund' then -1*am.amount_total else am.amount_total end) as net_amt
            ,(case when am.move_type='in_refund' then -1*(am.amount_total-am.amount_residual) else (am.amount_total-am.amount_residual) end) as settled_amt 
            ,(case when am.move_type='in_refund' then -1*am.amount_residual else am.amount_residual end) as balance
            ,rp.vendor_category_id as vendor_category_id
            ,am.id as move_id
            from account_move as am
            left join res_partner rp on rp.id = am.partner_id
            where am.move_type in ('in_invoice','in_refund') and am.state='posted'
                )''' % (self._table,)
        )