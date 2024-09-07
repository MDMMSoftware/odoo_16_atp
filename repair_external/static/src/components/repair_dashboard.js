/** @odoo-module */

import { registry } from '@web/core/registry'
const { Component } = owl 

export class OwlRepairDashboard extends Component {}
OwlRepairDashboard.template = "owl.OwlRepairDashboard"

registry.category("actions").add("owl.repair_dashboard", OwlRepairDashboard)