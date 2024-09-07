odoo.define('attendance_extension.attendances', function (require) {
    "use strict";
    
    var MyAttendances = require('hr_attendance.my_attendances');
    var core = require('web.core');
    var field_utils = require('web.field_utils');
    const session = require("web.session");
    var latitude;
    var longitude;
    var Dialog = require('web.Dialog');
    var flag = false;

    function isMobile() {
        return /Mobi|Android|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(navigator.userAgent);
    }

    var MyAttendances = MyAttendances.include({
        willStart: function () {
            var self = this;

            var def = this._rpc({
                    model: 'hr.employee',
                    method: 'search_read',
                    args: [[['user_id', '=', this.getSession().uid]], ['attendance_state', 'name', 'hours_today','att_allow_all_device']],
                    context: session.user_context,
                })
                .then(function (res) {
                    self.employee = res.length && res[0];
                    if (res.length) {
                        self.hours_today = field_utils.format.float_time(self.employee.hours_today);
                        self.att_allow_all_device = res[0].att_allow_all_device
                    }
                });

            return Promise.all([def, this._super.apply(this, arguments)]);
        },

        update_attendance: function () {
            var self = this;

            if (!self.att_allow_all_device & !isMobile()) {
                Dialog.alert(this, "Please check in / checkout  with your phone.", {
                    title: "Mobile Check-In Required",
                });
                return;
            }

            navigator.geolocation.getCurrentPosition(function(position) {
                const ctx = Object.assign(session.user_context, {
                    latitude: position.coords.latitude,
                    longitude: position.coords.longitude,
                });
                latitude = position.coords.latitude;
                longitude = position.coords.longitude;
                if (self.employee.attendance_state=='checked_out' && !flag){
                    flag = true;
                    self._rpc({
                        model: 'hr.employee',
                        method: 'attendance_manual',
                        args: [[self.employee.id], 'hr_attendance.hr_attendance_action_my_attendances'],
                        context: ctx,
                        
                    })
                    .then(function(result) {
                        if (result.action) {
                            self.do_action(result.action);
                        } else if (result.warning) {
                            self.do_warn(result.warning);
                        }
                    });
                }else{
                    Dialog.confirm(
                        this,
                        "Are you sure to CHECK OUT???",
                        {
                            onForceClose: function(){
                                
                            },
                            confirm_callback: function(){
                                self._rpc({
                                    model: 'hr.employee',
                                    method: 'attendance_manual',
                                    args: [[self.employee.id], 'hr_attendance.hr_attendance_action_my_attendances'],
                                    context: ctx,
                                    
                                })
                                .then(function(result) {
                                    if (result.action) {
                                        self.do_action(result.action);
                                    } else if (result.warning) {
                                        self.do_warn(result.warning);
                                    }
                                });
                                
                            },
                            cancel_callback: function(){
                               
                            }
                        }
                    );   
                    flag = false;
                }
            });
            
        },
    });
});
    