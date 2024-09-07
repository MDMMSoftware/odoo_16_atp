import odoo
import odoo.modules.registry
from odoo import http
from odoo.modules import module
from odoo.exceptions import AccessError, UserError, AccessDenied
from odoo.http import request
from odoo.tools.translate import _
from odoo.addons.web.controllers.session import Session


class Session(http.Controller):
    @http.route('/web/session/authenticate', type='json', auth="none")
    def authenticate(self, db, login, password,noti_token, base_location=None, phone=False):
        if not http.db_filter([db]):
            raise AccessError("Database not found.")
        pre_uid = request.session.authenticate(db, login, password)
        # if not noti_token:
        #     raise ValueError("Noti Token is required!!!")
        if pre_uid != request.session.uid:
            # Crapy workaround for unupdatable Odoo Mobile App iOS (Thanks Apple :@) and Android
            # Correct behavior should be to raise AccessError("Renewing an expired session for user that has multi-factor-authentication is not supported. Please use /web/login instead.")
            return {'uid': None}
        uid = request.env['res.users'].browse(pre_uid)
        if uid and noti_token:
            # if not phone:
            #     raise AccessError("Phone number is required!!!")
            # if uid.employee_id:
            #     if ( not uid.employee_id.mobile_phone and not uid.employee_id.work_phone):
            #         raise AccessDenied("Phone number is not provided in the database!! ")
            #     else:
            #         if not any(
            #                 phone.strip() == getattr(uid.employee_id, field).strip()
            #                 for field in ['mobile_phone', 'work_phone']
            #                 if getattr(uid.employee_id, field)
            #             ):
            #             raise AccessDenied("Invalid phone number!!")           
            uid.sudo().noti_token = noti_token
        request.session.db = db
        registry = odoo.modules.registry.Registry(db)
        with registry.cursor() as cr:
            env = odoo.api.Environment(cr, request.session.uid, request.session.context)
            if not request.db and not request.session.is_explicit:
                # request._save_session would not update the session_token
                # as it lacks an environment, rotating the session myself
                http.root.session_store.rotate(request.session, env)
                request.future_response.set_cookie(
                    'session_id', request.session.sid,
                    max_age=http.SESSION_LIFETIME, httponly=True
                )
            return env['ir.http'].session_info()