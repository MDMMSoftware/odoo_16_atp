from odoo import models,api, fields
from odoo.exceptions import ValidationError

class ResPartner(models.Model):
    _inherit = 'res.partner'

    company_id = fields.Many2one('res.company', 'Company', index=True , default=lambda self:self.env.company)
    township_id = fields.Many2one(comodel_name='res.state.township',string="Township")
    partner_code_prefix_id = fields.Many2one(string="Prefix",comodel_name='partner.code.prefix')
    partner_code_infix_id = fields.Many2one(string="Infix",comodel_name='partner.code.infix')
    seq = fields.Char(string="Sequence",store=True)
    allow_partner_code_defined = fields.Boolean(string="Allow Defined Code",default=False)
    partner_code_defined = fields.Char(string="Partner Code")
    partner_code = fields.Char(string="partner Code")
    is_duty_owner = fields.Boolean(string="Is Duty Owner?",default=False)
    company_type = fields.Selection(string='Company Type',
        selection=[('person', 'Individual'), ('company', 'Company')],
        compute='_compute_company_type', inverse='_write_company_type',default="person")    

    partner_type = fields.Selection([
        ('customer','Customer'),
        ('vendor','Vendor'),
        ('advance','Advance'),
        ('employee','Employee'),
        ('other','Other')
    ],string="Partner Type",default="customer")
    partner_relation_type = fields.Selection([('external','External'),('internal','Internal')],string="Partner Relation Type",default="external")


    advance_user = fields.Boolean(string="Advance User",default=False)
    property_account_advance_id = fields.Many2one('account.account', company_dependent=True,
        string="Account Advance",
        domain="[('account_type', 'in', ['liability_payable','asset_receivable']), ('non_trade', '=', True), ('company_id', '=', current_company_id)]",
        help="This account will be used instead of the default one as the advance account for the current partner",
        required=True)
    # account_advance_id = fields.Many2one('account.account', compute='_compute_account_id', store=True, readonly=False, precompute=True, string='Account Advance')
    account_advance_id = fields.Many2one('account.account', related='property_account_advance_id', store=True, readonly=False, precompute=True, string='Account Advance')
    owner_id = fields.Many2one(string="Owner",comodel_name='res.partner.owner')


    customer_category_id = fields.Many2one(string="Customer Category",comodel_name='res.partner.customer.category')
    vendor_category_id = fields.Many2one(string="Vendor Category",comodel_name='res.partner.vendor.category')
    other_category_id = fields.Many2one(string="Other Category",comodel_name='res.partner.other.category')

    advance_receivable_id = fields.Many2one(string="Advance Receivable",comodel_name='account.account')
    advance_payable_id = fields.Many2one(string="Advance Payable",comodel_name='account.account')
    partner_income_account_id = fields.Many2one(string="Income Account",comodel_name='account.account')
    partner_return_account_id = fields.Many2one(string="Return Account",comodel_name= 'account.account')
    sale_discount_account_id = fields.Many2one(string="Sale Discount Account",comodel_name='account.account')
    partner_name_prefix_id = fields.Many2one("partner.name.prefix")
    allow_prefix_name = fields.Boolean(compute="_compute_allow_prefix_name")
    partner_full_name = fields.Char(compute="_compute_partner_full_name", store=True)
    prefix_name_filter_ids = fields.Many2many("partner.name.prefix",'prefix_name_filter_rel',compute = "_compute_prefix_name_filter")
    concat_name = fields.Char()
    # records = self.env['your.model.name'].search([('your_field_name', 'ilike', 'AP/%')])

    def _compute_prefix_name_filter(self):
        for rec in self:
            if rec.partner_type == 'customer':
                prefix_records = self.env['partner.name.prefix'].search(['|',('name', 'ilike', 'AR/%'),('name', 'ilike', ('SV/%'))])
            elif rec.partner_type == 'vendor':
                prefix_records = self.env['partner.name.prefix'].search([('name', 'ilike', 'AP/%')])
            elif rec.partner_type == 'advance':
                prefix_records = self.env['partner.name.prefix'].search([('name', 'ilike', 'ADV/%')])
            else:
                prefix_records = self.env['partner.name.prefix'].search([])
            rec.prefix_name_filter_ids = prefix_records

    @api.onchange("partner_relation_type")
    def _onchange_partner_relation_type(self):
        for res in self:
            if res.partner_relation_type and res.company_id:
                default_parnter_configuration = res.env['res.partner.configuration'].sudo().search([('company_id','=',res.company_id.id),('partner_relation_type','=',res.partner_relation_type)],limit=1)
                if default_parnter_configuration:
                    res.property_account_receivable_id = default_parnter_configuration.property_account_receivable_id
                    res.property_account_payable_id = default_parnter_configuration.property_account_payable_id
                    res.customer_category_id  = default_parnter_configuration.customer_category_id
                    res.vendor_category_id = default_parnter_configuration.vendor_category_id
    
    @api.onchange('partner_type')
    def _onchange_partner_type_domain(self):
        for rec in self:
            if rec.partner_relation_type and rec.company_id:
                default_parnter_configuration = rec.env['res.partner.configuration'].sudo().search([('company_id','=',rec.company_id.id),('partner_relation_type','=',rec.partner_relation_type)],limit=1)            
            self.allow_partner_code_defined = True if self.partner_type in ('advance','employee') else False 
            self.partner_code_defined = '' if self.partner_type in ('advance','employee') else False             
            if rec.partner_type == 'customer':
                if default_parnter_configuration:
                    rec.customer_category_id = default_parnter_configuration.customer_category_id
                    rec.vendor_category_id = False
                prefix_records = self.env['partner.name.prefix'].search(['|',('name', 'ilike', 'AR/%'),('name', 'ilike', ('SV/%'))])
            elif rec.partner_type == 'vendor':
                if default_parnter_configuration:
                    rec.vendor_category_id = default_parnter_configuration.vendor_category_id
                    rec.customer_category_id = False
                prefix_records = self.env['partner.name.prefix'].search([('name', 'ilike', 'AP/%')])
            elif rec.partner_type == 'advance':
                prefix_records = self.env['partner.name.prefix'].search([('name', 'ilike', 'ADV/%')])
            else:
                prefix_records = self.env['partner.name.prefix'].search([])
            rec.prefix_name_filter_ids = prefix_records

    @api.depends('partner_name_prefix_id','concat_name')
    def _compute_partner_full_name(self):
        for rec in self:
            if rec.company_id.allow_partner_prefix_feature:
                if rec.partner_name_prefix_id:
                    rec.partner_full_name = '%s-%s' %(rec.partner_name_prefix_id.name,rec.concat_name)
                else:
                    rec.partner_full_name = rec.concat_name
                rec.name = rec.partner_full_name if rec.partner_full_name else rec.name
            else:
                rec.partner_full_name = rec.name

    @api.onchange('partner_name_prefix_id','concat_name')
    def _onchange_partner_full_name(self):
        for rec in self:
            if rec.company_id.allow_partner_prefix_feature:
                if rec.partner_name_prefix_id:
                    rec.name = rec.partner_name_prefix_id.name + '-'
                if rec.concat_name:
                    rec.name = rec.name + rec.concat_name
            
    @api.depends('company_id')
    def _compute_allow_prefix_name(self):
        for rec in self:
            if self.env.company.allow_partner_prefix_feature:
                rec.allow_prefix_name = True
            else:
                rec.allow_prefix_name = False
                
    # @api.model
    # def _name_search(self, name, args=None, operator='ilike', limit=100, name_get_uid=None):
    #     args = args or []
    #     domain = []
    #     if name:
    #         domain = [('partner_full_name',operator,name)]
    #     search_ids = self._search(domain + args,limit=limit,access_rights_uid=name_get_uid)
    #     return search_ids    

    # def name_get(self):
    #     result=[]
    #     for rec in self:
    #         if self.env.company.allow_partner_prefix_feature:
    #             result.append((rec.id,'%s-%s' %(rec.partner_name_prefix_id.name,rec.name)))
    #         else:
    #             result.append((rec.id,'%s' %(rec.name)))

    #     return result

    @api.onchange('partner_code_infix_id')
    def auto_generate_partner_code(self):
        partner_sequence = self.env['partner.code.sequence']
        if self.partner_code_infix_id:
            if not self.branch_id:
                self.branch_id = self.partner_code_infix_id.branch_id
            if not self.property_product_pricelist:
                pricelist_id = self.env['product.pricelist'].search([('branch_id','=',self.branch_id.id)],limit=1)
                self.property_product_pricelist = pricelist_id
            if self.partner_code_prefix_id:
                code_sequence = partner_sequence.search([('prefix','=',self.partner_code_prefix_id.id),('infix','=',self.partner_code_infix_id.id)])
                if code_sequence:
                    seq = str(code_sequence.seq)
                    if len(seq) > self.partner_code_infix_id.padding:
                        raise ValidationError("Sequence exceeded the defined padding!!")
                    self.seq = seq.zfill(self.partner_code_infix_id.padding)
                else:
                    partner_sequence.create({
                        'prefix':self.partner_code_prefix_id.id,
                        'infix':self.partner_code_infix_id.id,
                        'seq':1
                    })
                    self.seq = "1".zfill(self.partner_code_infix_id.padding)
            else:
                raise ValidationError("Please choose Partner Prefix first to generate code")
            
    # @api.depends('property_account_advance_id')
    def auto_fill_advance(self):
        self = self.search([])
        for res in self:
            if res.property_account_advance_id:
                res.account_advance_id = res.property_account_advance_id.id
            
    @api.constrains('partner_code_defined')
    def save_parter_code_defined(self):
        if self.allow_partner_code_defined and self.partner_code_defined:
            self.partner_code = self.partner_code_defined

    @api.constrains('partner_code_prefix_id','partner_code_infix_id')
    def save_partner_code(self):
        ptn_prefix = self.partner_code_prefix_id
        ptn_infix = self.partner_code_infix_id
        if ptn_prefix and ptn_infix and not self.allow_partner_code_defined:
            code_sequence = self.env['partner.code.sequence'].search([('prefix','=',ptn_prefix.id),('infix','=',ptn_infix.id)],limit=1)
            if code_sequence and self.seq:
                if int(self.seq) == code_sequence.seq:
                    self.partner_code = f"{ptn_prefix.name}-{ptn_infix.name}-{self.seq}"
                    code_sequence.seq += 1
            elif code_sequence:
                seq = str(code_sequence.seq)
                if len(seq) > self.partner_code_infix_id.padding:
                    raise ValidationError("Sequence exceeded the defined padding!!")
                self.seq = seq.zfill(self.partner_code_infix_id.padding)
                self.partner_code = f"{ptn_prefix.name}-{ptn_infix.name}-{self.seq}"
                code_sequence.seq += 1
            else:
                raise ValidationError("Sequence Not Found!!!")
            
    @api.model
    def create(self,vals):
        if vals.get('is_company') == True:
            vals['company_id'] = False
        return super().create(vals) 

class PartnerCodePrefix(models.Model):
    _name = 'partner.code.prefix'

    name = fields.Char(string="Name")

    _sql_constraints = [
        ('uniq_partner_code_prefix', 'unique(name)', 'partner Code Prefix must be unique.'),
    ]       

class PartnerCodeInfix(models.Model):
    _name = 'partner.code.infix'

    name = fields.Char(string="Name")
    branch_id = fields.Many2one("res.branch",string="Branch")
    padding = fields.Integer(max=7,min=3)

class PartnerCodeSequence(models.Model):
    _name = 'partner.code.sequence'
    _order = "prefix, infix"

    prefix = fields.Many2one(string="Prefix",comodel_name="partner.code.prefix")
    infix = fields.Many2one(string="infix",comodel_name="partner.code.infix")
    seq = fields.Integer(string="Next Sequence",default=1)

class ResPartnerOwner(models.Model):
    _name = 'res.partner.owner'

    name = fields.Char(string="Name")

class PartnerCustomerCategory(models.Model):
    _name = 'res.partner.customer.category'

    name = fields.Char(string="Name")

class PartnerVendorCategory(models.Model):
    _name = 'res.partner.vendor.category'

    name = fields.Char(string="Name")


class PartnerOtherCategory(models.Model):
    _name = 'res.partner.other.category'

    name = fields.Char(string="Name")

class ResStateTownship(models.Model):
    _name = 'res.state.township'

    state_id = fields.Many2one("res.country.state", string='State')
    name = fields.Char(string="Township")

    @api.constrains('name')
    def _constraint_check_state_township(self):
        if self.state_id and self.name:
            if self.env['res.state.township'].search([('state_id','=',self.state_id.id),('name','=',self.name),('id','!=',self.id)]):
                raise ValidationError("State and township is alredy existed")
            
class AdvancePrepaid(models.Model):
    _inherit = 'advance.prepaid'

    is_partner_duty_owner = fields.Boolean("Is Owner?",related="partner_id.is_duty_owner",default=False)

class PartnerPrefix(models.Model):
    _name = "partner.name.prefix"

    name = fields.Char('Name')
    company_id = fields.Many2one('res.company',default=lambda self: self.env.company)
    

class ResPartnerConfiguration(models.Model):
    _name = "res.partner.configuration"

    company_id = fields.Many2one('res.company',string="Company",default=lambda self: self.env.company)
    partner_relation_type = fields.Selection([('external','External'),('internal','Internal')],string="Partner Relation Type",default="external")
    property_account_receivable_id = fields.Many2one('account.account', company_dependent=True,
        string="Account Receivable",
        domain="[('account_type', '=', 'asset_receivable'), ('deprecated', '=', False), ('company_id', '=', current_company_id)]",
        help="This account will be used instead of the default one as the receivable account for the current partner",
        required=True)   
    property_account_payable_id = fields.Many2one('account.account', company_dependent=True,
        string="Account Payable",
        domain="[('account_type', '=', 'liability_payable'), ('deprecated', '=', False), ('company_id', '=', current_company_id)]",
        help="This account will be used instead of the default one as the payable account for the current partner",
        required=True)     
    customer_category_id = fields.Many2one(string="Customer Category",comodel_name='res.partner.customer.category')
    vendor_category_id = fields.Many2one(string="Vendor Category",comodel_name='res.partner.vendor.category')
    # property_account_advance_id = fields.Many2one('account.account', company_dependent=True,
    #     string="Account Advance",
    #     domain="[('account_type', 'in', ['liability_payable','asset_receivable']), ('non_trade', '=', True), ('company_id', '=', current_company_id)]",
    #     help="This account will be used instead of the default one as the advance account for the current partner",
    #     required=True)    
    # advance_receivable_id = fields.Many2one(string="Advance Receivable",comodel_name='account.account')

    _sql_constraints = [
        ('unique_company_partner_relation_type','unique(partner_relation_type,company_id)','Parnter Relation type must be unique within the same company!!')
    ]