from odoo import models, fields,api,_


class ResUser(models.Model):
    _inherit = "res.users"

    def get_branch_domain(self):
        branch_ids = self.env.user.branch_ids.ids
        company_ids = self.env.user.company_ids.ids
        for branch in branch_ids:
            branch_id = self.env.user.branch_ids.browse(branch)
            if branch_id.company_id.id in company_ids:
                company_ids.remove(branch_id.company_id.id)
        return ['|',('branch_id','in',branch_ids),('branch_id','in',False),'|',('company_id','in',False),('company_id','in',company_ids)]
    
    def get_requisition_branch_domain(self):
        branch_ids = self.env.user.branch_ids.ids
        company_ids = self.env.user.company_ids.ids
        for branch in branch_ids:
            branch_id = self.env.user.branch_ids.browse(branch)
            if branch_id.company_id.id in company_ids:
                company_ids.remove(branch_id.company_id.id)
        return ['|','|','|',('from_branch','in',branch_ids),('company_id','in',company_ids),('from_branch','in',False),('company_id','in',False)]
    

    def get_branches_domain(self):
        branch_ids = self.env.user.branch_ids.ids
        company_ids = self.env.user.company_ids.ids
        for branch in branch_ids:
            branch_id = self.env.user.branch_ids.browse(branch)
            if branch_id.company_id.id in company_ids:
                company_ids.remove(branch_id.company_id.id)
        return ['|','|','|',('branch_ids','in',branch_ids),('company_id','in',company_ids),('branch_ids','in',False),('company_id','in',False)]