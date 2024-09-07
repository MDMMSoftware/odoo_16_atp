/** @odoo-module */
import { ListController } from "@web/views/list/list_controller";
import { registry } from '@web/core/registry';
import { listView } from '@web/views/list/list_view';
export class ButtonDeptController extends ListController {
   setup() {
       super.setup();
   }
   OnClickImport() {
       this.actionService.doAction({
          type: 'ir.actions.act_window',
          res_model: 'file.import.wizard',
          name:'Import Approval Users',
          view_mode: 'form',
          view_type: 'form',
          views: [[false, 'form']],
          target: 'new',
          res_id: false,
      });
   }
}
registry.category("views").add("import_button_in_tree", {
   ...listView,
   Controller: ButtonDeptController,
   buttonTemplate: "button_dept_import.ListView.import_btn",
});