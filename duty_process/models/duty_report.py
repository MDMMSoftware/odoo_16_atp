# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, tools


class DutyReport(models.Model):
    _name = "duty.report"
    _description = "Duty Analysis Report"
    _auto = False
    _rec_name = 'date'
    _order = 'date desc'

    name = fields.Char('Duty Process', readonly=True)
    date = fields.Date('Date', readonly=True)
    import_person = fields.Many2one('hr.employee',"Duty Import Person",readonly=True)
    supervisor = fields.Many2one('hr.employee',"Site Supervisor",readonly=True)
    project = fields.Many2one('analytic.project.code',"Project",readonly=True)
    duty_id = fields.Many2one('duty.process', 'Duty #', readonly=True)
    run_hr = fields.Float('Run HR', readonly=True)
    walk_hr = fields.Float('Walk HR', readonly=True)
    general_hr = fields.Float('General HR', readonly=True)
    total_hr = fields.Float('Total HR', readonly=True)
    fill_fuel = fields.Float('Filling Fuel', readonly=True)
    total_use_fuel = fields.Float('Total Use Fuel', readonly=True)
    duty_amt = fields.Float('Duty Amount', readonly=True)
    fuel_amt = fields.Float('Fuel Amount', readonly=True)
    total_amt = fields.Float('Total Amount', readonly=True)
    pj_type_id = fields.Many2one('project.type',"Project Type", readonly=True)
    type = fields.Char('Type',readonly=True)
    machine = fields.Char('Machine',readonly=True)
    machine_capacity = fields.Many2one('machine.capacity',readonly=True)
    attachment_id = fields.Many2one('fleet.attachment',readonly=True)
    operator = fields.Many2one('hr.employee',"Operator",readonly=True)
    owner = fields.Many2one('fleet.owner',string="Owner",readonly=True)
    

    def _with_duty(self):
        return ""

    def _select_duty(self):
        select_ = f"""
            min(l.id) AS id,
            l.date AS date,
            l.duty_import_person AS import_person,
            l.site_supervisor AS supervisor,
            l.project_id AS project,
            l.run_hr AS run_hr,
            l.walk_hr AS walk_hr,
            l.general_hr AS general_hr,
            l.total_hr AS total_hr,
            l.fill_fuel AS fill_fuel,
            l.total_use_fuel AS total_use_fuel,
            l.duty_amt AS duty_amt,
            l.fuel_amt AS fuel_amt,
            l.total_amt AS total_amt,
            pt.name AS type,
            fv.name AS machine,
			fv.machine_capacity AS machine_capacity,
			l.attachment_id AS attachment_id,
			l.owner_id AS operator,
			fv.owner_id AS owner,
			d.id AS duty_id"""

        additional_fields_info = self._select_additional_fields()
        template = """,
            %s AS %s"""
        for fname, query_info in additional_fields_info.items():
            select_ += template % (query_info, fname)

        return select_

    def _case_value_or_one(self, value):
        return f"""CASE COALESCE({value}, 0) WHEN 0 THEN 1.0 ELSE {value} END"""

    def _select_additional_fields(self):
        """Hook to return additional fields SQL specification for select part of the table query.

        :returns: mapping field -> SQL computation of field, will be converted to '_ AS _field' in the final table definition
        :rtype: dict
        """
        return {}

    def _from_duty(self):
        return """
            duty_process_line l 
            LEFT JOIN duty_process d on d.id=l.duty_id
            LEFT JOIN analytic_project_code apc on apc.id=l.project_id
            LEFT JOIN project_type pt on pt.id=apc.pj_type_id
            LEFT JOIN fleet_vehicle fv on fv.id=d.machine_id
            """

    def _where_duty(self):
        return """
            l.display_type IS NULL"""

    def _group_by_duty(self):
        return """
            l.id,
            l.date,
            pt.name,
            fv.machine_capacity,
            fv.id,
            d.id"""

    def _query(self):
        with_ = self._with_duty()
        return f"""
            {"WITH" + with_ + "(" if with_ else ""}
            SELECT {self._select_duty()}
            FROM {self._from_duty()}
            GROUP BY {self._group_by_duty()}
            {")" if with_ else ""}
        """

    @property
    def _table_query(self):
        return self._query()
