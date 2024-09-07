/** @odoo-module */
import { Many2ManyTagsField } from "@web/views/fields/many2many_tags/many2many_tags_field";
import { patch } from "@web/core/utils/patch";
import { _t } from "@web/core/l10n/translation";
import {
    Many2XAutocomplete,
    useActiveActions,
    useX2ManyCrud,
} from "@web/views/fields/relational_utils";
import { usePopover } from "@web/core/popover/popover_hook";
import { useService } from "@web/core/utils/hooks";
import { useTagNavigation } from "@web/core/record_selectors/tag_navigation_hook";

import { Component, useRef } from "@odoo/owl";


patch(Many2ManyTagsField.prototype, "PatchedRemoveCUm2m", {
    setup() {
        this.orm = useService("orm");
        this.previousColorsMap = {};
        this.popover = usePopover(this.constructor.components.Popover);
        this.dialog = useService("dialog");
        this.dialogClose = [];
        this.onTagKeydown = useTagNavigation(
            "many2ManyTagsField",
            this.deleteTagByIndex.bind(this)
        );
        this.autoCompleteRef = useRef("autoComplete");

        const { saveRecord, removeRecord } = useX2ManyCrud(
            () => this.props.record.data[this.props.name],
            true
        );

        this.activeActions = useActiveActions({
            fieldType: "many2many",
            crudOptions: {
                onDelete: removeRecord,
            },
            getEvalParams: (props) => {
                return {
                    evalContext: this.evalContext,
                    readonly: props.readonly,
                };
            },
        });

        this.update = (recordlist) => {
            if (!recordlist) {
                return;
            }
            if (Array.isArray(recordlist)) {
                const resIds = recordlist.map((rec) => rec.id);
                return saveRecord(resIds);
            }
            return saveRecord(recordlist);
        };
    }

});