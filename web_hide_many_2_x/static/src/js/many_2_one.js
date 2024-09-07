/** @odoo-module */
import { Many2OneField } from "@web/views/fields/many2one/many2one_field";
import { patch } from "@web/core/utils/patch";

patch(Many2OneField.prototype, "PatchedRemoveCUm2o" , {
    get Many2XAutocompleteProps() {
        return {
            value: this.displayName,
            id: this.props.id,
            placeholder: this.props.placeholder,
            resModel: this.relation,
            autoSelect: true,
            fieldString: this.string,
            activeActions: this.state.activeActions,
            update: this.update,
            context: this.context,
            getDomain: this.getDomain.bind(this),
            nameCreateField: this.props.nameCreateField,
            setInputFloats: this.setFloating,
            autocomplete_container: this.autocompleteContainerRef,
        };
    },
    computeActiveActions(props) {
        this.state.activeActions = {
            create: false,
            createEdit: false,
            write: false,
        };
    }
});
