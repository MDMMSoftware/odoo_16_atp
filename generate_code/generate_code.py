from odoo.exceptions import ValidationError

def generate_code(sequence,model,branch,company,date,type,action_xml_id,request_type=None):
    seq = 0
    result = False
    if not model.id:
        raise ValidationError("There is no available for Sequence")
    if not date:
        raise ValidationError("There is no available for Sequence")
    if not company.id:
        raise ValidationError("There is no available for Sequence")
    else:
        if action_xml_id:
            action_id = model.env['ir.actions.act_window']._for_xml_id(action_xml_id)
            if branch:
                sequence = sequence.sudo().search([('model_id.model','=',model._name),('branch_id','=',branch.id),('transfer_type','=',type),('ir_action_id.id','=',action_id['id'])],limit=1)
            else:
                sequence = sequence.sudo().search([('model_id.model','=',model._name),('company_id','=',company.id),('transfer_type','=',type),('ir_action_id.id','=',action_id['id'])],limit=1)
        else:
            if branch:
                if model._name == 'repair.request':
                    sequence = sequence.sudo().search([('model_id.model','=',model._name),('branch_id','=',branch.id),('transfer_type','=',type),('ir_action_id','=',False),('request_type_id','=',request_type)],limit=1)
                elif hasattr(sequence, 'repair_sequence_prefix_id'):
                    sequence = sequence.sudo().search([('model_id.model','=',model._name),('branch_id','=',branch.id),('transfer_type','=',type),('ir_action_id','=',False),('repair_sequence_prefix_id','=',request_type)],limit=1)
                else:
                    sequence = sequence.sudo().search([('model_id.model','=',model._name),('branch_id','=',branch.id),('transfer_type','=',type),('ir_action_id','=',False)],limit=1)
            else:
                if model._name == 'repair.request':
                    sequence = sequence.sudo().search([('model_id.model','=',model._name),('company_id','=',company.id),('transfer_type','=',type),('ir_action_id','=',False),('request_type_id','=',request_type)],limit=1)
                elif hasattr(sequence, 'repair_sequence_prefix_id'):
                    sequence = sequence.sudo().search([('model_id.model','=',model._name),('company_id','=',company.id),('transfer_type','=',type),('ir_action_id','=',False),('repair_sequence_prefix_id','=',request_type)],limit=1)
                else:
                    sequence = sequence.sudo().search([('model_id.model','=',model._name),('company_id','=',company.id),('transfer_type','=',type),('ir_action_id','=',False)],limit=1)
        if not sequence:
            raise ValidationError("Sequence Not Found.Please Contact to the Administrator.")
        if not sequence.sequence_line_ids:
            raise ValidationError("Sequence Model need line for date range")
        for line in sequence.sequence_line_ids:
            seq_line = line.sudo().search([('start_date','<=',date),('end_date','>=',date),('sequence_id','=',sequence.ids)])
            if seq_line:
                if line.sequence==0:
                    seq +=1
                else:
                    seq = line.sequence
                if len(str(seq)) > seq_line.padding:
                    raise ValidationError('Count Number Limited.')
                seq_str = seq_line.padding_str + str(seq)  
                seq_str = seq_str[-(seq_line.padding):]
                seq_line.write({'sequence':seq+1})
                result = str(seq_line.sequence_id.code)+'/'+(seq_line.sequence_id.prefix)+'/'+str(seq_str)
                if request_type and not seq_line.sequence_id.fleet_service:
                    raise ValidationError("Fleet Service must be on for repair sequences..")
                if seq_line.sequence_id.fleet_service:
                    return date.strftime("%y"),str(seq_str)
                return result
        raise ValidationError("Sequence Model need to set up line for date range")