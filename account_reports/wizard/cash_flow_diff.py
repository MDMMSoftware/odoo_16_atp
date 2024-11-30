from odoo import models, fields, api, _
from datetime import datetime, timedelta
try:
   from odoo.tools.misc import xlsxwriter
except ImportError:
   import xlsxwriter
import io
try:
    from odoo.tools.misc import xlsxwriter
except ImportError:
    # TODO saas-17: remove the try/except to directly import from misc
    import xlsxwriter
import os
import tempfile
import calendar
import json
from dateutil.relativedelta import relativedelta

class CashFlowDiff(models.TransientModel):
    _name = 'cash.flow.diff'
    _description = 'Cash Flow Diff'
    
    def _get_target_years(self):
        current_year = datetime.now().year
        return [(str(current_year - 1),str(current_year - 1)), (str(current_year),str(current_year)), (str(current_year + 1), str(current_year + 1))]

    target_year = fields.Selection(selection=_get_target_years,string="Target Year",default=str(datetime.now().year))
    target_month = fields.Selection(selection=[('1','Jan'),('2','Feb'),('3','March'),('4','April'),('5','May'),('6','June'),
                                                 ('7','July'),('8','August'),('9','Sep'),('10','Oct'),('11','Nov'),('12','Dec')],string="Target Month",default=str(datetime.now().month))
    no_of_comparison = fields.Integer('Number of Comparison')
    entry_options = fields.Selection(selection=[('draft','Draft'),('posted','Posted'),('all','All Entries')],string="Options",default='posted')
    journal_ids = fields.Many2many("account.journal",string="Journals")
    
    def export_cash_flow(self):
        # params
        # unit_id = self.unit_id.ids if self.unit_id else [0]
        # division_id = self.division_id.ids if self.division_id else [0]
        # department_id = self.department_id.ids if self.department_id else [0]
        # branch_id = self.branch_id.ids if self.branch_id else [0]

        # # header default format
        output = io.BytesIO()
        file_name = os.path.join(tempfile.gettempdir(), f'Cash Flow Diff_{self.target_month}_{self.target_year}.xlsx')
        workbook = xlsxwriter.Workbook(file_name)
        sheet = workbook.add_worksheet("Cash Flow Difference")
        banner_format_small = workbook.add_format({'font_name': 'Arial','bold': True, 'align': 'center', 'valign': 'vcenter', 'text_wrap': True,'border':True})
        header_format = workbook.add_format({'font_name': 'Arial','align': 'left', 'valign': 'vcenter','bold': True,'border':True,'bg_color': '#AAAAAA'})
        text_format = workbook.add_format({'font_name': 'Arial','align': 'left', 'valign': 'vcenter'})
        header_text_format = workbook.add_format({'font_name': 'Arial','align': 'left', 'valign': 'vcenter','font_color':'#FF0000'})
        header_text_format.set_underline(1)
        bold_text_format = workbook.add_format({'font_name': 'Arial','align': 'left','bold': True, 'valign': 'vcenter'})
        date_format = workbook.add_format({'num_format': 'yyyy-mm-dd'})
        time_format = workbook.add_format({'num_format': 'hh:mm:ss'})
        sheet.set_column(0, 0, 50)
        
        y_offset = 5
        x_offset = 3
        sheet.merge_range(0,0,x_offset,y_offset, _("Cash Flow Statement"), banner_format_small)
        x_offset+=2
        sheet.write(5,0,(_("Description")),header_format)
        sheet.write(7,0,(_("Operating Activities")),header_text_format)
        sheet.write(8,0,(_("Net Profit")),text_format)
        sheet.write(10,0,(_("Non-Cash Transactions_Adj:")),header_text_format)
        sheet.write(11,0,(_("Derpreciation")),text_format)
        sheet.write(12,0,(_("Amortisation")),text_format)
        sheet.write(14,0,(_("Changes in Working Capital")),header_text_format)
        sheet.write(15,0,(_("Changes in  Inventory ")),text_format)
        sheet.write(16,0,(_("Changes in  Receivables")),text_format)
        sheet.write(17,0,(_("Changes in  Account Payable ")),text_format)
        sheet.write(18,0,(_("Changes in  Other Current Liabilities")),text_format)
        sheet.write(19,0,(_("Provision for Income Tax (22%)")),text_format)
        sheet.write(20,0,(_("Cash Flow from Operating Activities")),bold_text_format)
        sheet.write(22,0,(_("Investing Activites")),header_text_format)
        sheet.write(23,0,(_("Non Current Assets")),text_format)
        sheet.write(24,0,(_("Intangible Assets")),text_format)
        sheet.write(25,0,(_("Cash Flow from Investing Activities")),bold_text_format)
        sheet.write(27,0,(_("Financing Activites")),header_text_format)
        sheet.write(28,0,(_("Share Capital")),text_format)
        sheet.write(30,0,(_("Cash Flow from Financing Activities")),bold_text_format)
        sheet.write(32,0,(_("Net Changes in Cash and Cash Equivalent during the year")),bold_text_format)
        sheet.write(33,0,(_("Cash Balance at the beginning of the year")),text_format)
        sheet.write(34,0,(_("Adjustment for Opening Retained Earning")),bold_text_format)
        sheet.write(35,0,(_("Cash Balance at the end of of the year")),bold_text_format)
        t_month = int(self.target_month)
        t_year = int(self.target_year)
        t_date_start = datetime.now().replace(day=1,month=t_month,year=t_year).date() 
        # t_date_end = datetime.now().replace(day=calendar.monthrange(t_year,t_month)[1],month=t_month,year=t_year).date()
        date_start = t_date_start- relativedelta(months=self.no_of_comparison)
        i=0
        cash_balance = 0
        while date_start<=t_date_start:
            
            b_date_start = date_start- relativedelta(months=1)
            b_date_start = datetime.now().replace(day=1,month=b_date_start.month,year=b_date_start.year).date()
            b_date_end = datetime.now().replace(day=calendar.monthrange(b_date_start.year,b_date_start.month)[1],month=b_date_start.month,year=b_date_start.year).date()
            date_end = datetime.now().replace(day=calendar.monthrange(date_start.year,date_start.month)[1],month=date_start.month,year=date_start.year).date()
            profit_and_loss_report = self.env.ref('account_reports.profit_and_loss')
            included_line_id = profit_and_loss_report.line_ids.filtered(lambda l: l.code == 'NEP').id
            generic_included_line_id = profit_and_loss_report._get_generic_line_id('account.report.line', included_line_id)
            options = profit_and_loss_report._get_options({
                        'report_id': self.env.ref('account_reports.profit_and_loss').id,
                        'date': {
                            'date_from': date_start.strftime("%Y-%m-%d"),
                            'date_to': date_end.strftime("%Y-%m-%d"),
                            'mode': 'range',
                            'filter': 'custom',
                        }
                    })
            options['unfolded_lines'] = [generic_included_line_id]
            options['hierarchy'] = True
            lines = profit_and_loss_report._get_lines(options,all_column_groups_expression_totals=None)
            profit_loss = self.extract_net_profit(lines)
            opearting_activities = investing_activities = financing_activities = 0
            depreciation = self.generate_deb_credit('Derpreciation',date_start,date_end,self.entry_options)
            amortisation = self.generate_deb_credit('Amortisation',date_start,date_end,self.entry_options)
            change_inv = (self.generate_deb_credit('Changes in Inventory',b_date_start,b_date_end,self.entry_options)-self.generate_deb_credit('Changes in Inventory',date_start,date_end,self.entry_options))
            change_recei = (self.generate_deb_credit('Changes in Receivables',b_date_start,b_date_end,self.entry_options)-self.generate_deb_credit('Changes in Receivables',date_start,date_end,self.entry_options))
            change_pay = (self.generate_deb_credit('Changes in Account Payable',b_date_start,b_date_end,self.entry_options)-self.generate_deb_credit('Changes in Account Payable',date_start,date_end,self.entry_options))
            change_lib = (self.generate_deb_credit('Changes in Other Current Liabilities',b_date_start,b_date_end,self.entry_options)-self.generate_deb_credit('Changes in Other Current Liabilities',date_start,date_end,self.entry_options))
            change_tax = (self.generate_deb_credit('Provision for Income Tax (22%)',b_date_start,b_date_end,self.entry_options)-self.generate_deb_credit('Provision for Income Tax (22%)',date_start,date_end,self.entry_options))
            opearting_activities += depreciation+amortisation+change_inv+change_recei+change_pay+change_lib+change_tax
            sheet.write(5,1+i,date_start.strftime("%b")+","+date_start.strftime("%y"),header_format)
            sheet.write(8,1+i,profit_loss or '-',text_format)
            sheet.write(11,1+i,depreciation or '-',text_format)
            sheet.write(12,1+i,amortisation or '-',text_format)
            sheet.write(15,1+i,change_inv or '-',text_format)
            sheet.write(16,1+i,change_recei or '-',text_format)
            sheet.write(17,1+i,change_pay or '-',text_format)
            sheet.write(18,1+i,change_lib or '-',text_format)
            sheet.write(19,1+i,change_tax or '-',text_format)
            sheet.write(20,1+i,opearting_activities or '-',text_format)
            non_current_asset = intangible_asset = 0
            non_current_asset = self.generate_cre_debit('Non Current Assets',date_start,date_end,self.entry_options)
            intangible_asset = self.generate_cre_debit('Intangible Assets',date_start,date_end,self.entry_options)
            investing_activities += non_current_asset+intangible_asset
            sheet.write(23,1+i,non_current_asset or '-',text_format)
            sheet.write(24,1+i,intangible_asset or '-',text_format)
            sheet.write(25,1+i,investing_activities or '-',text_format)
            share_capital = self.generate_cre_debit('Share Capital',date_start,date_end,self.entry_options)
            financing_activities += share_capital
            sheet.write(28,1+i,share_capital or '-',text_format)
            sheet.write(30,1+i,financing_activities or '-',text_format)
            net_change = 0
            net_change += opearting_activities+investing_activities+financing_activities
            sheet.write(32,1+i,net_change or '-',text_format)
            sheet.write(33,1+i,cash_balance or '-',text_format)
            retain_earning = self.generate_deb_credit('Adjustment for Opening Retained Earning',date_start,date_end,self.entry_options)
            sheet.write(34,1+i,retain_earning or '-',text_format)
            cash_end_balance = retain_earning+cash_balance+net_change
            cash_balance = cash_end_balance
            sheet.write(35,1+i,cash_end_balance or '-',text_format)
            i+=1
            date_start = date_start+relativedelta(months=1)
        workbook.close()
        output.seek(0)
        return self.download_excel_file(file_name)

    def download_excel_file(self, file_name):
        return {
            'type': 'ir.actions.act_url',
            'url': '/web/binary/download_document?model=attendance.export.wizard&id=%s&file_name=%s' % (self.id, file_name),
            'target':'self',
        }      
        
    def extract_net_profit(self,data):
        for entry in data:
            if entry.get('name') == 'Net Profit':
                # Parse the debug_popup_data JSON
                debug_data = json.loads(entry.get('debug_popup_data', '{}'))
                # Navigate to the value
                expressions = debug_data.get('expressions_detail', [])
                for expr in expressions:
                    for item in expr[1]:
                        if item[0] == 'balance':
                            value = item[1].get('value', '0.00\u00a0K')
                            # Clean and format the value
                            value = value.replace('\u00a0', '').replace('K', 'k')
                            return float(value.replace('k', '').replace(',', ''))
        return None     
    
    def generate_deb_credit(self,cash_flow_type,start,end,state):
        cf_type = self.env['cash.flow.type'].search([('name','=',cash_flow_type)])
        if cf_type:
            account_ids = self.env['account.account'].search([('cash_flow_type','=',cf_type.id)])  
            if account_ids:
                self.env.cr.execute("""
                                    SELECT
                                    COALESCE(SUM(debit),0) - COALESCE(SUM(credit), 0) as balance
                                    FROM account_move_line WHERE 
                                    account_id IN %s  AND ("account_move_line"."date" <= %s)
                                    AND ("account_move_line"."date" >= %s) 
                                    AND ("account_move_line"."parent_state" =%s) AND 
                                    (("account_move_line"."company_id" in (%s)) 
                                    OR "account_move_line"."company_id" IS NULL) 
                                    AND (("account_move_line"."display_type" not in (%s,%s)) 
                                    OR "account_move_line"."display_type" IS NULL) 
                                    AND (("account_move_line"."parent_state" != %s) 
                                    OR "account_move_line"."parent_state" IS NULL) 
                                    GROUP BY account_id""",
                                (tuple(account_ids.ids), end,start, state, tuple(self.env.companies.ids), 'line_section', 'line_note',
                                            'cancel'))
                query_result = self.env.cr.fetchall()
                if query_result:
                    return sum(x[0] for x in query_result)
        return 0 
    
    def generate_begin_deb_credit(self,cash_flow_type,end,state):
        cf_type = self.env['cash.flow.type'].search([('name','=',cash_flow_type)])
        if cf_type:
            account_ids = self.env['account.account'].search([('cash_flow_type','=',cf_type.id)])  
            if account_ids:
                self.env.cr.execute("""
                                    SELECT
                                    COALESCE(SUM(debit),0) - COALESCE(SUM(credit), 0) as balance
                                    FROM account_move_line WHERE 
                                    account_id IN %s  AND ("account_move_line"."date" <= %s) 
                                    AND ("account_move_line"."parent_state" =%s) AND 
                                    (("account_move_line"."company_id" in (%s)) 
                                    OR "account_move_line"."company_id" IS NULL) 
                                    AND (("account_move_line"."display_type" not in (%s,%s)) 
                                    OR "account_move_line"."display_type" IS NULL) 
                                    AND (("account_move_line"."parent_state" != %s) 
                                    OR "account_move_line"."parent_state" IS NULL) 
                                    GROUP BY account_id""",
                                (tuple(account_ids.ids), end, state, tuple(self.env.companies.ids), 'line_section', 'line_note',
                                            'cancel'))
                query_result = self.env.cr.fetchall()
                if query_result:
                    return sum(x[0] for x in query_result)
        return 0
    
    
    def generate_cre_debit(self,cash_flow_type,start,end,state):
        cf_type = self.env['cash.flow.type'].search([('name','=',cash_flow_type)])
        if cf_type:
            account_ids = self.env['account.account'].search([('cash_flow_type','=',cf_type.id)])  
            if account_ids:
                self.env.cr.execute("""
                                    SELECT
                                    COALESCE(SUM(credit),0) - COALESCE(SUM(debit), 0) as balance
                                    FROM account_move_line WHERE 
                                    account_id IN %s  AND ("account_move_line"."date" <= %s)
                                    AND ("account_move_line"."date" >= %s) 
                                    AND ("account_move_line"."parent_state" =%s) AND 
                                    (("account_move_line"."company_id" in (%s)) 
                                    OR "account_move_line"."company_id" IS NULL) 
                                    AND (("account_move_line"."display_type" not in (%s,%s)) 
                                    OR "account_move_line"."display_type" IS NULL) 
                                    AND (("account_move_line"."parent_state" != %s) 
                                    OR "account_move_line"."parent_state" IS NULL) 
                                    GROUP BY account_id""",
                                (tuple(account_ids.ids), end,start, state, tuple(self.env.companies.ids), 'line_section', 'line_note',
                                            'cancel'))
                query_result = self.env.cr.fetchall()
                if query_result:
                    return sum(x[0] for x in query_result)
        return 0 

    
    


# WITH all_dates AS (
#     SELECT date_trunc('day', dd)::date AS datee
#     FROM generate_series('2024-6-1'::timestamp,'2024-6-30'::timestamp,'1 day'::interval) AS dd
# )	,
# all_leaves AS (
# 	SELECT l_type.code,emp.id AS employee_id,emp.name,generate_series(date_from,date_to,'1 day'::interval)::date as leave_date 
# 	FROM hr_leave AS leave
# 	INNER JOIN hr_employee AS emp ON leave.employee_id = emp.id
# 	INNER JOIN hr_leave_type as l_type ON l_type.id = leave.holiday_status_id
# 	WHERE
# 	CASE WHEN 3 <> 0 THEN emp.unit_id = 3  ELSE emp.id <> 0 END AND
#     CASE WHEN 0 <> 0 THEN emp.division_id = 0 ELSE emp.id <> 0 END AND
#     CASE WHEN 0 <> 0 THEN emp.department_id = 0 ELSE emp.id <> 0 END AND
#     CASE WHEN 0 <> 0 THEN emp.branch_id = 0 ELSE emp.id <> 0 END
# )
# SELECT 
#     emp.employee_id,emp.name as emp_name,DATE(all_dates.datee) as check_date
# 	,leave.code
# 	,TO_CHAR(att.check_in+'6:30','HH24:MI:SS')::text  || '<=>' ||TO_CHAR(att.check_out+'6:30','HH24:MI:SS')::text as timme
# FROM hr_employee AS emp
# CROSS JOIN all_dates
# LEFT JOIN hr_attendance AS att
#     ON att.employee_id = emp.id AND  DATE(att.check_in) = all_dates.datee 
# LEFT JOIN hr_department AS unit
#     ON unit.id = emp.unit_id
# LEFT JOIN hr_department AS div
#     ON div.id = emp.division_id
# LEFT JOIN hr_department AS dept
#     ON dept.id = emp.department_id
# LEFT JOIN hr_branch AS branch
#     ON branch.id = emp.branch_id
# LEFT JOIN all_leaves AS leave
# 	ON (leave.leave_date = DATE(all_dates.datee)) AND (leave.employee_id = emp.id)
# WHERE
#     CASE WHEN 3 <> 0 THEN emp.unit_id = 3  ELSE emp.id <> 0 END AND
#     CASE WHEN 0 <> 0 THEN emp.division_id = 0 ELSE emp.id <> 0 END AND
#     CASE WHEN 0 <> 0 THEN emp.department_id = 0 ELSE emp.id <> 0 END AND
#     CASE WHEN 0 <> 0 THEN emp.branch_id = 0 ELSE emp.id <> 0 END 
# ORDER BY emp.employee_id,all_dates.datee;					