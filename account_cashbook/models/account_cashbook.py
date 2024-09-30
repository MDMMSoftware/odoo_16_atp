from odoo import models, fields, api
from datetime import datetime
from odoo.tools.translate import _
from collections import Counter
from odoo.exceptions import UserError
from ...generate_code import generate_code


CASH_TYPE = [
    ('pay', 'Cash Payment'),
    ('receive', 'Cash Received'),
    ]

class AccountMove(models.Model):
    _inherit = "account.move"

    cashbook_id = fields.Many2one('account.cashbook', string='Cash Book')

class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    cashbook_id = fields.Many2one('account.cashbook', string='Cash Book')

    @api.onchange('product_id')
    def onchange_product(self):
        if self.move_id.is_expense:
            return {"domain" : {'product_id' : [('expense_ok','=',True)]}}
  

class AccountCashBook(models.Model):
    _name = 'account.cashbook'
    _inherit = 'mail.thread'

    exchange_rate = fields.Float(string='Exchange Rate', store=True, copy=True,default=1.0,tracking=True)

    def _default_currency_id(self):
        return self.env.user.company_id.currency_id

    @api.model
    def get_today(self):
        my_date = fields.Datetime.context_timestamp(self, timestamp=datetime.now())
        return my_date
    
    def _get_branch_domain(self):
        """methode to get branch domain"""
        company = self.env.company
        branch_ids = self.env.user.branch_ids
        branch = branch_ids.filtered(
            lambda branch: branch.company_id == company)
        return [('id', 'in', branch.ids)]
    
    def _get_department_domain(self):
        """methode to get department domain"""
        company = self.env.company
        department_ids = self.env.user.department_ids
        department = department_ids.filtered(
            lambda department: department.company_id == company)
        return [('id', 'in', department.ids)]

    department_id = fields.Many2one('res.department', string='Department', store=True,readonly=True,required=False,tracking=True,
                                help='Leave this field empty if this account is'
                                     ' shared between all departmentes')

    branch_ids = fields.Many2one('res.branch', string='Branch', store=True,readonly=False,domain=_get_branch_domain,required=False)
    name = fields.Char('No', copy=False,track_visibility='onchange',readonly=True)
    date = fields.Date(string='Date', required=True,track_visibility='onchange', default=get_today)
    cash_type = fields.Selection(CASH_TYPE, string='Type', required=True,)
    account_id = fields.Many2one('account.account',string='Account', required=True,domain="[('account_type', '=', 'asset_cash')]",track_visibility='onchange')
    currency_id = fields.Many2one('res.currency', string="Currency",required=True,default=_default_currency_id)
    journal_id = fields.Many2one('account.journal', string='Journal', required=True, domain="[('type', 'in', ('bank', 'cash'))]",track_visibility='onchange')
    note = fields.Text(string='Note')
    company_id = fields.Many2one('res.company', string='Company', change_default=True,
        required=True, readonly=True, states={'draft': [('readonly', False)]},default=lambda self: self.env.company)
    state = fields.Selection([('draft', 'Draft'),('submit', 'Confirmed'),('done', 'Done'),('cancel', 'Cancel')], string='Status', default='draft',track_visibility='onchange')
    origin = fields.Char('Source Document')
    line_ids = fields.One2many('account.cashbook.line', 'cashbook',string='Cashbook Line')
    move_ids = fields.Many2one('account.move',string="Journal Entry")
    move_line_ids = fields.One2many('account.move.line', 'cashbook_id', string='Journal Item',domain=[('move_id.reversed_entry_id', '=', None)])
    reversed_move_ids = fields.Many2one('account.move',string="Reversed Journal Entry")
    reversed_move_line_id = fields.One2many('account.move.line', 'cashbook_id', string='Reversed Journal Item',domain=[('move_id.reversed_entry_id', '!=', None)])

    allow_division_feature = fields.Boolean(string="Use Division Feature?", related="company_id.allow_division_feature")

    amount_total = fields.Monetary(
        string='Total',
        compute='_compute_amount_cashbook', store=True, readonly=True,default=0.0
    )

    transfer_type = fields.Selection([('transfer','Cash Transfer'),('contra',"Contra"),('income','Income'),('expense','Expense'),('other','Other')], string='Transfer Type',track_visibility='onchange')
    transfer_company_id = fields.Many2one('transfer.company',track_visibility='onchange')
    transfer_branch_id = fields.Many2one('transfer.branch',track_visibility='onchange')
    desc = fields.Char(string="Description")
    
    @api.depends("line_ids.amount")
    def _compute_amount_cashbook(self):
        for cashbook in self:
            cashbook.amount_total = sum(cashbook.line_ids.mapped("amount"))
    
    @api.onchange('journal_id')
    def onchange_account(self):
        self.account_id = self.journal_id.default_account_id and self.journal_id.default_account_id.id or False
        self.currency_id =  self.journal_id.currency_id or self.journal_id.company_id.currency_id
            
    @api.onchange('branch_ids')
    def onchange_branch_id(self):
        """onchange method"""
        for res in self:
            if not res.journal_id:
                res.journal_id = self.env.user.payment_journal_id
            if not res.branch_ids:
                res.branch_ids = self.env.user.branch_id
            return {"domain": {"transfer_branch_id": [('branch_id','=',res.branch_ids.id)]}}
        
    @api.onchange("cash_type")
    def _onchange_cash_type(self):
        for res in self:
            res.transfer_type = 'expense' if res.cash_type == 'pay' else 'income'
                
    
    def submit_cashbook(self):
        if not (self.env.user.has_group('account.group_account_user') or self.env.user.has_group('account.group_account_manager')):
            raise UserError(("User %s doesn't get Financial Access")%(self.env.user.name))
        if self.department_id:
            if self.env.user.id not in self.department_id.approve_user_id.ids:
                raise UserError(_("User %s doesn't include in %s Department")%(self.env.user.name,self.department_id.name))
        move_lines = []
        distribution=name =False
        sequence = self.env['sequence.model']
        if self.cash_type=='pay':
            if not self.name or self.name == 'Draft':
                name = generate_code.generate_code(sequence,self,self.branch_ids,self.company_id,self.date,'pay',None)
            debit_amt = 0
            for line in self.line_ids:
                    vals = {
                        'name': line.name,
                        'account_id': line.account_id.id,
                        'date': self.date,
                        'date_maturity': self.date,
                        'amount_currency':line.amount,
                        'debit': (line.amount)/(1/self.exchange_rate),
                        'credit': 0.0,
                        'cashbook_id':self.id,
                        'analytic_distribution':line.analytic_distribution,
                        'job_code_id':line.job_code_id.id,
                        'report_remark_id':line.report_remark_id.id,
                        'voucher_type_id':line.voucher_type_id.id,
                        'voucher_no':line.voucher_no,
                        'remark':line.remark,
                        'currency_id':self.currency_id.id,
                        'currency_rate':1/self.exchange_rate ,
                        'division_id':line.division_id.id or False,                
                    }
                    if hasattr(line,"project_id"):
                        vals["project_id"] = ( line.project_id and line.project_id.id ) or False
                    if hasattr(line,"fleet_id"):
                        vals["fleet_id"] = ( line.fleet_id and line.fleet_id.id ) or False                        
                    move_lines.append(vals)
                    debit_amt += line.amount
                    # if distribution:
                    #     distribution= Counter(distribution)+Counter(line.analytic_distribution)
                    # else:
                    #     distribution=line.analytic_distribution
            
            vals = {
                'account_id': self.account_id.id,
                'date': self.date,
                'date_maturity': self.date,
                'amount_currency':debit_amt*-1,
                'debit': 0.0,
                'credit': debit_amt/(1/self.exchange_rate),
                'cashbook_id':self.id,
                'currency_id':self.currency_id.id,
                'currency_rate':1/self.exchange_rate,
                'name': self.desc,
                # 'analytic_distribution':distribution
            }
            move_lines.append(vals)
        else:
            credit_amt = 0
            if not self.name or self.name == 'Draft':
                name = generate_code.generate_code(sequence,self,self.branch_ids,self.company_id,self.date,'receive',None)
            for line in self.line_ids:
                
                    vals = {
                        'name': line.name,
                        'account_id': line.account_id.id,
                        'date': self.date,
                        'date_maturity': self.date,
                        'amount_currency':line.amount*-1,
                        'debit': 0,
                        'credit': line.amount/(1/self.exchange_rate),
                        'cashbook_id':self.id,
                        'analytic_distribution':line.analytic_distribution,
                        'job_code_id':line.job_code_id.id,
                        'report_remark_id':line.report_remark_id.id,
                        'voucher_type_id':line.voucher_type_id.id,
                        'voucher_no':line.voucher_no,
                        'remark':line.remark,
                        'currency_id':self.currency_id.id,
                        'currency_rate':1/self.exchange_rate,
                        'division_id':line.division_id.id or False, 
                    }
                    if hasattr(line, "project_id"):
                        vals["project_id"] = ( line.project_id and line.project_id.id ) or False
                    if hasattr(line,"fleet_id"):
                        vals["fleet_id"] = ( line.fleet_id and line.fleet_id.id ) or False                          
                    move_lines.append(vals)
                    credit_amt += line.amount
                    # if distribution:
                    #     distribution=Counter(distribution)+Counter(line.analytic_distribution)
                    # else:
                    #     distribution=line.analytic_distribution
            
            vals = {
                'account_id': self.account_id.id,
                'date': self.date,
                'date_maturity': self.date,
                'amount_currency':credit_amt,
                'debit': credit_amt/(1/self.exchange_rate),
                'credit': 0.0,
                'cashbook_id':self.id,
                'currency_id':self.currency_id.id,
                'currency_rate':1/self.exchange_rate
                # 'analytic_distribution':distribution
            }
            move_lines.append(vals)            
        m_line = [(0, 0, l) for l in move_lines]
        # if not name:
        #     name = generate_code.generate_code(sequence,self,self.branch_ids,self.company_id,self.date,None)
        self.name = name  if not self.name or self.name == 'Draft' else self.name
        move_vals = {
                'name': '/',
                'ref':self.name,
                'journal_id': self.journal_id.id,
                'date': self.date,
                'line_ids': m_line,
                'cashbook_id': self.id,
                'branch_id':self.branch_ids.id,
                'department_id':self.department_id.id,
                'exchange_rate':self.exchange_rate,
                'currency_id':self.currency_id.id,
                'desc':self.desc,
            }
        move_id = self.env['account.move'].create(move_vals)
        self.move_ids = move_id.id


        self.write({'state':'submit'})

    def validate_cashbook(self):
        if not self.env.user.has_group('account.group_account_manager'):
            raise UserError(("User %s doesn't get Financial Access")%(self.env.user.name))
        if self.department_id:
            if self.env.user.id not in self.department_id.approve_user_id.ids:
                raise UserError(_("User %s doesn't include in %s Department")%(self.env.user.name,self.department_id.name))
        if not self.origin:
            raise UserError('Source Document is required to validate cashbook!!')
        if self.move_ids:
            self.move_ids.action_post()
        self.write({'state':'done'})
    
    def reset_cashbook(self):
        if not self.env.user.has_group('account.group_account_manager'):
            raise UserError(("User %s doesn't get Financial Access")%(self.env.user.name))
        if self.department_id:
            if self.env.user.id not in self.department_id.approve_user_id.ids:
                raise UserError(_("User %s doesn't include in %s Department")%(self.env.user.name,self.department_id.name))
        move_cashbooks = self.env['account.move'].search([('cashbook_id','=',self.id)])
        if move_cashbooks:
            for move_cashbook in move_cashbooks:
                if move_cashbook.state=='posted':
                    move_cashbook.button_draft()
                move_cashbook.ref = False
                move_cashbook.with_context(force_delete=True).unlink()
        self.write({'state':'draft'})

    def cancel_cashbook(self):
        if not self.env.user.has_group('account.group_account_manager'):
            raise UserError(("User %s doesn't get Financial Access")%(self.env.user.name))
        if self.department_id:
            if self.env.user.id not in self.department_id.approve_user_id.ids:
                raise UserError(_("User %s doesn't include in %s Department")%(self.env.user.name,self.department_id.name))
        if self.move_ids:
            if self.move_ids.state=='posted':
                self.move_ids.button_draft()
                self.move_ids.button_cancel()
            if self.move_ids.state=='draft':
                self.move_ids.button_cancel()
                
        self.write({'state':'cancel'})
        
    @api.model_create_multi
    def create(self, vals_list):
        if not vals_list[0].get('name'):
            vals_list[0]['name'] = 'Draft'
        
        return super().create(vals_list)
        
    def unlink(self):
        for rec in self:
            if rec.state != 'draft' or (rec.name and rec.name != 'Draft'):
                raise UserError("Are you doing something fraudly! Why do you want to delete some records?? 🤔 ")
        return super().unlink()



class AccountCashBookLine(models.Model):
    _name = 'account.cashbook.line'
    _inherit = ['mail.thread', 'analytic.mixin']

    name = fields.Char('Description', copy=False)
    amount = fields.Monetary(string='Amount', default=0.0, currency_field='currency_id',track_visibility='onchange')
    cashbook = fields.Many2one('account.cashbook', string='Cash Book')
    date = fields.Date(string='Date', related='cashbook.date')
    account_id = fields.Many2one('account.account',string='Account', required=True,track_visibility='onchange')
    currency_id = fields.Many2one('res.currency', string="Currency",related="cashbook.currency_id")
    company_id = fields.Many2one('res.company', string='Company', change_default=True,required=True, readonly=True,default=lambda self: self.env.company)
    company_currency_id = fields.Many2one('res.currency', string='Company Currency',related='company_id.currency_id', track_visibility='always')
    cash_type = fields.Selection(CASH_TYPE, string='Type', related='cashbook.cash_type',store=True)
    division_id = fields.Many2one("analytic.division",string="Division",required=False,readonly=False,invisilbe=False)
    state = fields.Selection([('draft', 'Draft'),('cancel', 'Cancel'),('done', 'Done')], string='Status',related='cashbook.state',store=True)
    employee_id = fields.Many2one('hr.employee',string="Employee")
    branch_ids = fields.Many2one('res.branch', string='Branch', store=True,readonly=False,related="cashbook.branch_ids")
    department_id = fields.Many2one('res.department', string='Department', store=True,readonly=True,related="cashbook.department_id",required=False,Tracking=True)
    job_code_id = fields.Many2one(comodel_name='job.code',string="Job Code")
    report_remark_id = fields.Many2one(comodel_name='report.remark',string="Report Remark")
    voucher_type_id = fields.Many2one(comodel_name='voucher.type',string="Voucher Type")
    voucher_no = fields.Char(string="Voucher No.")
    voucher_date = fields.Date(string="Voucher Date")
    remark = fields.Char(string="Remark")   

    @api.onchange('division_id')
    def _onchage_analytic_by_division(self):
        envv = self.env['account.analytic.account']
        dct = {}
        if not self.division_id and len(self.cashbook.line_ids) > 1:
            prev_line = self.cashbook.line_ids[-2]
            dct = prev_line.analytic_distribution
            if hasattr(self, 'project_id'):
                self.project_id = prev_line.project_id
            if hasattr(self, 'division_id'):
                self.division_id = prev_line.division_id
            if hasattr(self, 'fleet_id'):
                prev_fleet = prev_line.fleet_id
                if prev_fleet and prev_fleet.analytic_fleet_id and str(prev_fleet.analytic_fleet_id.id) in dct:
                    dct.pop(str(prev_fleet.analytic_fleet_id.id))   
        elif self.division_id:
            if self.analytic_distribution:
                dct = {idd:val for idd,val in self.analytic_distribution.items() if envv.search([('id','=',idd)]).plan_id and envv.search([('id','=',idd)]).plan_id.name.lower() != 'division'}
            if self.division_id.analytic_account_id:
                dct[str(self.division_id.analytic_account_id.id)] = 100
        self.analytic_distribution = dct   

    @api.onchange('analytic_distribution')
    def _onchange_analytic_by_distribution(self):
        envv = self.env['account.analytic.account']
        dct = {}
        if self.analytic_distribution:
            dct = {idd:val for idd,val in self.analytic_distribution.items() if envv.search([('id','=',idd)]).plan_id and envv.search([('id','=',idd)]).plan_id.name.lower() not in ('vehicle','division','project')}        
        if hasattr(self, 'project_id') and self.project_id:         
            if self.project_id.analytic_project_id:
                dct[str(self.project_id.analytic_project_id.id)] = 100  
        if  hasattr(self, 'division_id') and self.division_id:
            if self.division_id.analytic_account_id:
                dct[str(self.division_id.analytic_account_id.id)] = 100 
        if hasattr(self,'fleet_id') and self.fleet_id and self.fleet_id.analytic_fleet_id and self.company_id == self.fleet_id.company_id:
            dct[str(self.fleet_id.analytic_fleet_id.id)] = 100
        self.analytic_distribution = dct             

    @api.onchange('name')
    def _onchange_account_id(self):
        if self.cashbook.transfer_branch_id:
            self.account_id = self.cashbook.transfer_branch_id.default_account_id.id


class TransferCompany(models.Model):
    _name = 'transfer.company'

    name = fields.Char()
    default_account_id = fields.Many2one('account.account',required=True)
    branch_name = fields.Char(string="Branch")
    diff_server = fields.Boolean(default=False)
    company_id = fields.Many2one('res.company',string="Company",default=False)


    def name_get(self):
        result=[]
        for rec in self:
            if rec.name and rec.branch_name:
                result.append((rec.id,'%s=>%s' %(rec.name,rec.branch_name)))
            if rec.name and not rec.diff_server:
                result.append((rec.id,'%s' %(rec.name)))
        return result
   
class TransferBranch(models.Model):
    _name = 'transfer.branch'

    name = fields.Char()
    default_account_id = fields.Many2one('account.account',required=True)
    branch_id = fields.Many2one('res.branch',string="Branch")
    company_id = fields.Many2one('res.company',string="Company",default=lambda self:self.env.company)


    # def name_get(self):
    #     result=[]
    #     for rec in self:
    #         if rec.name and rec.branch_id:
    #             result.append((rec.id,'%s=>%s' %(rec.name,rec.branch_id.name)))
    #     return result
   