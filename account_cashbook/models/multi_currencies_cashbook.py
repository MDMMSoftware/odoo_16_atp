from odoo import models, fields, api, _
from odoo.exceptions import UserError,ValidationError
from datetime import datetime, timedelta
from datetime import date
from ...generate_code import generate_code


class MultiCurrencyCashbook(models.Model):
    _name = 'account.multi.currencies.cashbook'
    _inherit = 'mail.thread'
    _description = 'Foreign Currency CashBook'

    name = fields.Char('No', copy=False,track_visibility='onchange',default=lambda self: _('New'))
    ref_no = fields.Char('Ref No', copy=False,track_visibility='onchange')
    desc = fields.Char('Description')
    date = fields.Date(string='Transfer Date', required=True,track_visibility='onchange', default=datetime.today())
    exchange_account_id = fields.Many2one('account.account',string='Gain/Loss Account', required=True,track_visibility='onchange',domain="[('company_id', '=', company_id)]")
    # journal_id = fields.Many2one('account.journal', string='Journal', required=True, domain="[('type', 'not in', ('bank', 'cash')), ('company_id', '=', company_id)]",track_visibility='onchange')

    company_id = fields.Many2one('res.company', string='Company', change_default=True,
        required=True, readonly=True, states={'draft': [('readonly', False)]},
        default=lambda self: self.env['res.company']._company_default_get('account.cashbook'))
    f_journal_id = fields.Many2one('account.journal',string='From Journal',domain="[('type', 'in', ('bank', 'cash')), ('company_id', '=', company_id)]")
    t_journal_id = fields.Many2one('account.journal',string='To Journal',domain="[('type', 'in', ('bank', 'cash')), ('company_id', '=', company_id)]")
    f_account_id = fields.Many2one('account.account',string='From', required=True,track_visibility='onchange')
    t_account_id = fields.Many2one('account.account',string='To', required=True,track_visibility='onchange')
    f_currency_id = fields.Many2one('res.currency', string="Currency",required=True,default=119 or None,track_visibility='onchange')
    t_currency_id = fields.Many2one('res.currency', string="Currency",required=True,default=119 or None,track_visibility='onchange')
    f_exchange_rate = fields.Float('Exchange Rate',default=1.0,track_visibility='onchange')
    t_exchange_rate = fields.Float('Exchange Rate',default=1.0,track_visibility='onchange')
    f_amt = fields.Float('Amount',track_visibility='onchange')
    t_amt = fields.Float('Amount',track_visibility='onchange')

    # analytic_company_id = fields.Many2one('analytic.company',string="Company",required=True,track_visibility='onchange')
    # department_id = fields.Many2one('analytic.department',string="Department",track_visibility='onchange')
    state = fields.Selection([('draft', 'Draft'),('confirm', 'Confirmed'),('done', 'Done')], string='Status', default='draft',track_visibility='onchange')
    move_line_ids = fields.One2many('account.move.line', 'multi_cashbook_id', string='Journal Item',domain=[('move_id.reversed_entry_id', '=', None)])
    calculation_method = fields.Selection([('method1', 'Calculate Amount'),('method2', 'Calculate From Rate'),('method3', 'Calculate To Rate'),('manual', 'Manual')], string='Calculation Method', default='manual',track_visibility='onchange')
    from_move_id = fields.Many2one('account.move',string="From Move")
    to_move_id = fields.Many2one('account.move',string="To Move")
    label_compount = fields.Char(compute='compute_label_compount')
    branch_id = fields.Many2one('res.branch',string="Branch",store=True,required=False,domain=lambda self:self._get_branch_domain())

    def _get_branch_domain(self):
        """methode to get branch domain"""
        company = self.env.company
        branch_ids = self.env.user.branch_ids
        branch = branch_ids.filtered(
            lambda branch: branch.company_id == company)
        return [('id', 'in', branch.ids)]

    @api.depends('name','ref_no')
    def compute_label_compount(self):
        for rec in self:
            name = ref_no = ''
            if rec.name:
                name = rec.name
            if rec.ref_no:
                ref_no = rec.ref_no
            rec.label_compount = str(name) + ' '+str(ref_no)

    @api.onchange('f_journal_id','t_journal_id')
    def _onchange_jounrals(self):
        for rec in self:
            if rec.f_journal_id:
                rec.f_account_id = rec.f_journal_id.default_account_id
            if rec.t_journal_id:
                rec.t_account_id = rec.t_journal_id.default_account_id


    @api.onchange('calculation_method','f_currency_id','f_exchange_rate','f_amt','t_currency_id','t_exchange_rate','t_amt')
    def calculate_on_method(self):
        for rec in self:
            if rec.calculation_method == 'method1':
                if rec.t_exchange_rate > 0:
                    rec.t_amt = round((rec.f_exchange_rate*rec.f_amt)/rec.t_exchange_rate,4)
            elif rec.calculation_method == 'method2':
                if rec.f_amt > 0.0:
                    rec.f_exchange_rate = round((rec.t_exchange_rate*rec.t_amt)/rec.f_amt,4) 
            elif rec.calculation_method == 'method3':
                if rec.t_amt > 0:
                    rec.t_exchange_rate = round((rec.f_exchange_rate*rec.f_amt)/rec.t_amt,4)        

    def action_confirm(self):
        self.ensure_one()
        if self.exchange_account_id:
            sequence = self.env['sequence.model']
            self.name = generate_code.generate_code(sequence,self,self.branch_id,self.company_id,self.date,None,None)
            f_ary1 = self._transfer_entry(self.f_account_id.id,self.f_currency_id.id,self.f_amt,'cr',self.f_exchange_rate)
            f_ary2 = self._transfer_entry(self.exchange_account_id.id,self.f_currency_id.id,self.f_amt,'dr',self.f_exchange_rate)
            t_ary1 = self._transfer_entry(self.exchange_account_id.id,self.t_currency_id.id,self.t_amt,'cr',self.t_exchange_rate)
            t_ary2 = self._transfer_entry(self.t_account_id.id,self.t_currency_id.id,self.t_amt,'dr',self.t_exchange_rate)

            res1 = f_ary1 + f_ary2
            res2 = t_ary1 + t_ary2
            m_line = [(0, 0, l) for l in res1]
            m_line2 = [(0, 0, l) for l in res2]
            move_vals = {
                'journal_id': self.f_journal_id.id,
                'desc': self.desc,
                'internal_ref': self.ref_no,
                'date': self.date,
                'line_ids': m_line,
                'currency_id': self.f_currency_id.id,
                'exchange_rate': self.f_exchange_rate,
                'branch_id':self.branch_id.id,
            }
            move_id = self.env['account.move'].create(move_vals)
            # move_id.post()
            move_id.line_ids.write({'branch_id':self.branch_id.id})

            self.from_move_id = move_id
            
            move_vals2 = {
                'journal_id': self.t_journal_id.id,
                'desc': self.desc,
                'internal_ref': self.ref_no,
                'date': self.date,
                'line_ids': m_line2,
                'currency_id': self.t_currency_id.id,
                'exchange_rate': self.t_exchange_rate,
                'branch_id':self.branch_id.id,
            }
            move_id2 = self.env['account.move'].create(move_vals2)
            move_id2.line_ids.write({'branch_id':self.branch_id.id})

            # move_id2.post()
            self.to_move_id = move_id2
        self.state = 'confirm'


    def action_reset_to_draft(self):
        if self.state == 'done':
            raise ValidationError('Only confirm state to set draft.')
        
        self.from_move_id.unlink()
        self.to_move_id.unlink()

        self.state = 'draft'
        
    
    def action_validate(self):  

        if self.from_move_id:
            self.from_move_id.action_post()
        if self.to_move_id:
            self.to_move_id.action_post()              
        self.state = 'done'


    def _transfer_entry(self,account_id,currency_id,amount,cash_type,exchange_rate):
        res = []
        move_line = {}
        move_line = {
            'name': self.label_compount,
            'account_id': account_id,
            'description': self.desc,
            'date_maturity': self.date,
            'amount_currency':0.0,
            'debit': 0.0,
            'credit': 0.0,
            'multi_cashbook_id':self.id,
            'branch_id': self.branch_id.id
        }

        if cash_type == 'dr':
            move_line['debit'] = amount
            # if self.company_id.currency_id.id != currency_id:
            move_line['currency_id'] = currency_id
            move_line['debit'] = amount*exchange_rate
            move_line['amount_currency'] = amount          
        else:
            move_line['credit'] = amount
            # if self.company_id.currency_id.id != currency_id:
            move_line['currency_id'] = currency_id
            move_line['credit'] = amount*exchange_rate
            move_line['amount_currency'] = amount*-1
        res.append(move_line)
        return res

class ExtAccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    multi_cashbook_id = fields.Many2one('account.multi.currencies.cashbook',string="Reference No.")
