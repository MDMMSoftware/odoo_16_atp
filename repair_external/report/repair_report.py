# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, tools


class RepairReport(models.Model):
    _name = "repair.report"
    _description = "Repair Analysis Report"
    _auto = False
    

    
    employee = fields.Many2one('hr.employee',"Technician",readonly=True)
    quotation = fields.Many2one('request.quotation',"Quotation",readonly=True)
    fleet = fields.Many2one('fleet.vehicle',"Fleet",readonly=True)
    branch = fields.Many2one('res.branch', 'Branch', readonly=True)
    balance = fields.Float('Balance', readonly=True)
    job_type_id = fields.Many2one("custom.group.class",string="Job Type",readonly=True)
    job_code = fields.Char('Job Code',readonly=True)
    job_desc = fields.Char('Job Desc',readonly=True)
    quotation_date = fields.Datetime('Quotation Date', readonly=True)
    issued_date = fields.Datetime('Issued Date', readonly=True)
    customer = fields.Many2one('res.partner',"Customer",readonly=True)
    pic = fields.Many2one('hr.employee',"Service Advisor",readonly=True)
    state = fields.Selection([('draft','Draft'),('job_start','Job Start'),('qc_check','QC Pass'),('job_close','Job Closed'),('cancel','Cancelled')],default='draft',tracking=True,readonly=False)

    def _with_repair(self):
        return ""

    def _select_repair(self):
        select_ = f"""
            min(a.rate) as id,
            a.employee,
            a.quotation,
            a.fleet,
            a.branch,
            a.pic1_amt+a.pic2_amt+a.pic3_amt+a.pic4_amt+a.pic5_amt as balance,
            a.job_code,
            a.job_desc,
            a.job_type_id,
            a.quotation_date,
            a.issued_date,
            a.customer,
            a.pic,
            a.state"""

        return select_

    

    def _from_repair(self):
        return """
            (select jrl.id as rate ,he.id as employee,rq.id as quotation,fv.id as fleet,rb.id as branch,
            CASE WHEN jrl.pic1=he.id THEN jrl.pic1_amt ELSE 0 end as pic1_amt,
            CASE WHEN jrl.pic2=he.id THEN jrl.pic2_amt ELSE 0 end as pic2_amt,
            CASE WHEN jrl.pic3=he.id THEN jrl.pic3_amt ELSE 0 end as pic3_amt,
            CASE WHEN jrl.pic4=he.id THEN jrl.pic4_amt ELSE 0 end as pic4_amt,
            CASE WHEN jrl.pic5=he.id THEN jrl.pic5_amt ELSE 0 end as pic5_amt,
            pt.name->'en_US' as job_code,jrl.job_desc->'en_US' as job_desc,jrl.job_type_id,rq.quotation_date::date as quotation_date,rq.customer,rq.pic,
 			rq.issued_date::date as issued_date,jo.state as state
            from hr_employee he 
            LEFT JOIN  job_rate_line jrl on jrl.pic1=he.id or jrl.pic2=he.id or jrl.pic3=he.id or jrl.pic4=he.id or jrl.pic5=he.id
            LEFT JOIN job_order jo on jo.id=jrl.job_order_id
            LEFT JOIN request_quotation rq on rq.id=jo.quotation_id
            LEFT JOIN product_product pp on pp.id=jrl.job_code
            LEFT JOIN product_template pt on pt.id=pp.product_tmpl_id
            LEFT JOIN fleet_vehicle fv on fv.id=jo.fleet_id
            LEFT JOIN res_branch rb on rb.id=jo.branch_id
            LEFT JOIN custom_group_class jt on jt.id=jrl.job_type_id
            where he.is_technician = 'true' and jo.state<>'cancel' )a
            """

    def _where_repair(self):
        return ""

    def _group_by_repair(self):
        return """
            a.employee,
            a.quotation,
            a.fleet,
            a.branch,
            a.job_code,
            a.job_desc,
            a.job_type_id,
            a.pic1_amt,
            a.pic2_amt,
            a.pic3_amt,
            a.pic4_amt,
            a.pic5_amt,
            a.quotation_date,
            a.issued_date,
            a.customer,
            a.pic,
            a.state"""

    def _query(self):
        with_ = self._with_repair()
        return f"""
            {"WITH" + with_ + "(" if with_ else ""}
            SELECT {self._select_repair()}
            FROM {self._from_repair()}
            GROUP BY {self._group_by_repair()}
            {")" if with_ else ""}
        """

    @property
    def _table_query(self):
        return self._query()
