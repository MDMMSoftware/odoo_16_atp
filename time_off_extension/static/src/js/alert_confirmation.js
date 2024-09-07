odoo.define('time_off_extension.AlertConfimration', function (require) {
    'use strict';

    var FormController = require('web.FormController');
    var Dialog = require('web.Dialog');
    console.log('*********formcontroaller')    
    
    const MyFormController = FormController.include({
        events: _.extend({}, FormController.prototype.events, {
            'click #check_condition': '_onActionRegisterClick',
        }),

        _onActionRegisterClick: function (event) {
            event.preventDefault();
            const self = this;

            // Example condition check
            const someCondition = true; // Replace with your actual condition

            if (someCondition) {
                Dialog.confirm(this, "Are you sure you want to register?", {
                    confirm_callback: function () {
                        self._registerAction();
                    },
                });
            } else {
                this.do_warn('Warning', 'Condition not met');
            }
        },

        _registerAction: function () {
            // Your custom action here
            console.log('Register action confirmed');
            // Implement your actual register logic here
        },
    });

    return MyFormController;

    // FormController.include({
    
    //     _onButtonClicked: function (event) {

    //         console.log(event.data.attrs.id)
    //         var self = this;
    //         if (event.data.attrs.id === "check_condition") {
    //             this._rpc({
    //                 model: 'hr.leave.prepare.timeoff',
    //                 method: 'check_condition',
    //                 args: [this.initialState.data.id],
    //             }).then(function (result) {
    //                 if (result) {
    //                     Dialog.confirm(self, 'Condition met! Do you want to continue?', {
    //                         confirm_callback: function () {
    //                             self._rpc({
    //                                 model: 'hr.leave.prepare.timeoff',
    //                                 method: 'action_register',
    //                                 args: [self.initialState.data.id],
    //                             }).then(function () {
    //                                 self.trigger_up('history_back');
    //                             });
    //                         }
    //                     });
    //                 } else {
    //                     self._super(event);
    //                 }
    //             });
    //         } else {
    //             this._super(event);
    //         }
    //     }
    // });
});

// odoo.define('time_off_extension.confirm_dialog', function (require) {
//     "use strict";
//     console.log('hello world')
//     const Dialog = require('web.Dialog');
//     const core = require('web.core');
//     const _t = core._t;
//     document.addEventListener('DOMContentLoaded', function () {
//         function showConfirmationDialog() {
//             Dialog.confirm(this, _t("Are you sure you want to proceed?"), {
//                 title: _t("Confirmation"),
//                 size: 'medium',
//                 buttons: [
//                     {
//                         text: _t('Cancel'),
//                         close: true,
//                         classes: 'btn-secondary',
//                         click: function () {
//                             console.log("User cancelled the action.");
//                         }
//                     },
//                     {
//                         text: _t('Confirm'),
//                         classes: 'btn-primary',
//                         click: function () {
//                             console.log("User confirmed the action.");
//                         }
//                     }
//                 ]
//             });
//         }
    
//         // Example usage
//         document.getElementById('action_register').addEventListener('click', showConfirmationDialog);
    
//     })
// });
