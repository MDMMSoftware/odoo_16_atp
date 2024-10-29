import datetime
from datetime import timedelta,datetime
from odoo import fields, models, api, _

class DailyCashbookReport(models.TransientModel):
    _name = "cashbook.report"
    start_date = fields.Date(string="Start Date",required=False)
    # end_date = fields.Date(string="End Date",required=False)
    # company_id = fields.Many2many("res.company",required=False)
    # branch_ids = fields.Many2many("res.branch")
    entry_type = fields.Selection([('draft','Draft Entries'),('posted','Posted Entries'),('draft,posted','All Entries')],default='draft,posted')
    report_type = fields.Selection([('account_group_report','Accounts Group'),('coa','Chart of Account')],default='coa')
    account_id = fields.Many2one("account.account","Account")
    account_group_report_id = fields.Many2one("account.group.report",name="Accounts Group")
    
    @api.onchange("report_type")
    def _onchange_report_type(self):
        if self.report_type == 'coa':
            self.account_group_report_id = False
        elif self.report_type == 'account_group_report':
            self.account_id = False
        else:
            self.account_group_report_id = False
            self.account_id = False
    
    def download_cash_report_excel(self):
        data = { 'form_data':self.read()[0], 'account_datas':self.account_id.id if self.report_type == 'coa' else self.account_group_report_id.account_ids.ids }
        return self.env.ref("account_cashbook.export_cash_report_xlsx").report_action(self,data=data,config=False) 
    

class ExcelWizardCashReport(models.AbstractModel):
    _name = 'report.account_cashbook.export_cash_report_xls'
    _inherit = 'report.report_xlsx.abstract'
    
    def generate_xlsx_report(self, workbook, data, partners):
        form_datas = data['form_data']
        if not form_datas.get('end_date'):
            form_datas['end_date'] = form_datas['start_date']
        
        account_ids = data['account_datas']
        if form_datas['report_type'] == 'coa':
            account_ids_text = f"('{account_ids}')"
        elif form_datas['report_type'] == 'account_group_report':
            account_ids_text = tuple(account_ids) if len(account_ids) > 1 else f"('{account_ids[0]}')"
        
        currency_query = """ SELECT id,name,CASE WHEN name = 'MMK' THEN 1 ELSE 0 END AS row_number FROM res_currency AS cur WHERE id IN ( SELECT currency_id FROM account_move GROUP BY currency_id ) ORDER BY row_number DESC; """
        self.env.cr.execute(currency_query)
        currency_datas = {data[0]:data[1] for data in  self.env.cr.fetchall()}
            
        # query = f""" 
		# 	SELECT aa.code,sum(balance)
		# 	FROM account_move_line AS aml
		# 	INNER JOIN account_account AS aa
		# 	ON aml.account_id = aa.id
		# 	WHERE aml.date < '{form_datas['start_date']}' AND aa.id IN {account_ids_text}
		# 	GROUP BY aa.id;         
        # """
        
        # self.env.cr.execute(query)
        # account_opening = {data[0]:data[1] for data in self.env.cr.fetchall()}
                    
        date_range = [(datetime.strptime(form_datas['start_date'],'%Y-%m-%d') + timedelta(days=x)).strftime("%Y-%m-%d") for x in range(  (datetime.strptime(form_datas['end_date'],'%Y-%m-%d') - datetime.strptime(form_datas['start_date'],'%Y-%m-%d')).days + 1)]

        # Build the dynamic SQL query
        dynamic_sql = ""
        for date in date_range:
            for currency_id,currency_name in currency_datas.items():
                # dynamic_sql += f"""SUM(CASE WHEN aml.date = '{date}' AND aml.currency_id = {int(currency_id)} THEN COALESCE(amount_currency, 0) ELSE 0 END) AS "{date}_{currency_name}","""
                dynamic_sql += f"""ROUND(SUM(CASE WHEN aml.currency_id = {int(currency_id)} THEN COALESCE(amount_currency, 0) ELSE 0 END),2) AS "{currency_name}","""

        # sql_query = f"""
		# 	SELECT
		# 		MAX(aa.code) AS acccount_code,
		# 		MAX(aa.name) AS account_name,
		# 		MAX(bank.name) AS bank_name,
		# 		MAX(aj.type) AS type,
		# 		{dynamic_sql[:-1]}
		# 	FROM (
		# 		SELECT DISTINCT id AS account_id
		# 		FROM account_account 
		# 		WHERE id IN {account_ids_text}
		# 	) AS account_list
		# 	CROSS JOIN generate_series('{form_datas['start_date']}'::date, '{form_datas['end_date']}'::date, '1 day'::interval) AS g(date)
		# 	LEFT JOIN 
		# 		(   SELECT date, amount_currency, account_id, currency_id
		# 			FROM account_move_line
		# 			WHERE parent_state IN ('{"','".join(form_datas['entry_type'].split(","))}')
		# 		) AS aml
		# 		ON account_list.account_id = aml.account_id AND g.date = aml.date
		# 	LEFT JOIN account_account AS aa
		# 		ON aa.id = account_list.account_id
		# 	LEFT JOIN account_journal AS aj
		# 		ON aj.default_account_id = aa.id
		# 	LEFT JOIN res_partner_bank AS bank_t
		# 		ON bank_t.id = aj.bank_account_id
		# 	LEFT JOIN res_bank AS bank
		# 		ON bank.id = bank_t.bank_id
		# 	GROUP BY aa.id
		# 	ORDER BY aa.id;
        # """
        
        sql_query = f""" 
				SELECT 
					MAX(aa.code) AS acccount_code,
					MAX(aa.name) AS account_name,
					INITCAP(MAX(aj.type)) AS type,
					{dynamic_sql[:-1]}
				FROM account_move_line AS aml	
				LEFT JOIN account_account AS aa
					ON aa.id = aml.account_id
				LEFT JOIN account_journal AS aj
					ON aj.default_account_id = aa.id
				WHERE aml.account_id IN {account_ids_text} AND aml.parent_state IN ('{"','".join(form_datas['entry_type'].split(","))}') AND aml.date <= '{form_datas['start_date']}'
				GROUP BY aa.id
				ORDER BY aa.id        
        """

        sheet = workbook.add_worksheet("Cash & Bank Summary Report")
        currency_format = workbook.add_format({'num_format': '#,##0.00'})
        header = ['Account Code', 'Account Name', 'Account Type'] + list(currency_datas.values())

        # Write the header row
        for col, header_item in enumerate(header):
            sheet.write(0, col, header_item)
            
        print(sql_query)
        self.env.cr.execute(sql_query)
        cash_datas = self.env.cr.fetchall()

        for row, data_tuple in enumerate(cash_datas):
            for col, data in enumerate(data_tuple):
                if col >= 3:
                    sheet.write(row+1, col, data, currency_format)
                else:
                    sheet.write(row+1, col, data)
            # row_data = list(data_tuple)
            # row_data[4] = account_opening.get(data_tuple[0], 0.0)
            # temp_data = 0
            # for col, value in enumerate(row_data):
            #     if col >= 4:
            #         temp_data = value + temp_data
            #         sheet.write(row + 1, col, temp_data)
            #     else:
            #         sheet.write(row + 1, col, value)