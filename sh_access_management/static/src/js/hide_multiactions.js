/** @odoo-module **/

import { ListController } from "@web/views/list/list_controller";
import { FormController } from "@web/views/form/form_controller";
import { KanbanController } from "@web/views/kanban/kanban_controller";
import { CalendarController } from "@web/views/calendar/calendar_controller";
import { ExportAll } from "@web/views/list/export_all/export_all";
import { ConfirmationDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { onWillStart, onMounted, useState } from "@odoo/owl";
import { patch } from "@web/core/utils/patch";
import { useService } from "@web/core/utils/hooks";
import { session } from "@web/session";
import { user } from "@web/core/user";

/* ===================================================================== */
/* ==================== FormController Patch ============================ */
/* ===================================================================== */
patch(FormController.prototype, {
    setup() {
        super.setup(...arguments);
        this.state = useState({
            rpc_result: null,
            group_show_create: true,
            group_show_delete: true,
            group_show_duplicate: true,
            group_show_archive: true,
            group_show_unarchive: true,
            group_show_add_properties: true,
            group_show_export: true,
        });
        this.orm = useService("orm");
        this.company = useService("company");
        const self = this;

        onWillStart(async () => {
            const uid = Array.isArray(session.user_id) ? session.user_id[0] : user.userId;
            const model_dic = await this.orm.call(
                "sh.access.model",
                "check_crud_operation",
                [{ user_id: uid, company_id: this.company.currentCompany.id }],
                {}
            );
            self.state.rpc_result = model_dic;
        });

        onMounted(() => self._shOnMountedForm());
    },

    async _shOnMountedForm() {
        
        const model_dic = this.state.rpc_result || {};
        const model_name = this.props.resModel;



        // Defaults: allow everything
        this.state.group_show_create = true;
        this.state.group_show_delete = true;
        this.state.group_show_duplicate = true;
        this.state.group_show_archive = true;
        this.state.group_show_unarchive = true;
        this.state.group_show_add_properties = true;
        this.state.group_show_export = true;

        // --------------------
        // Per-model config
        // --------------------
        if (Object.prototype.hasOwnProperty.call(model_dic, model_name)) {
            const value = model_dic[model_name] || {};
            

            this.state.group_show_create = !value.hide_create;
            this.state.group_show_delete = !value.hide_delete;
            this.state.group_show_duplicate = !value.hide_duplicate;
            // model-wise archive flag: affects both archive & unarchive
            this.state.group_show_archive = !value.hide_archieve;
            this.state.group_show_unarchive = !value.hide_archieve;
            this.state.group_show_export = !value.hide_export;
        }

        // --------------------
        // Global config
        // --------------------
        const global_vals = model_dic["__global__"] || null;
        if (global_vals) {
            
            // Global hide_add_property
            if (global_vals.hide_add_property) {
                this.state.group_show_add_properties = false;
            }

            // Global specific flags (override per-model)
            if (global_vals.sh_global_hide_create) {
                this.state.group_show_create = false;
            }
            if (global_vals.sh_global_hide_delete) {
                this.state.group_show_delete = false;
            }
            if (global_vals.sh_global_hide_duplicate) {
                this.state.group_show_duplicate = false;
            }
            // Separate global archive / unarchive
            if (global_vals.sh_global_hide_archive) {
                this.state.group_show_archive = false;
            }
            if (global_vals.sh_global_hide_unarchive) {
                this.state.group_show_unarchive = false;
            }

            // Global hide all actions (except create, as per design)
            if (global_vals.hide_action) {
                this.state.group_show_duplicate = false;
                this.state.group_show_delete = false;
                this.state.group_show_archive = false;
                this.state.group_show_unarchive = false;
                this.state.group_show_add_properties = false;
                this.state.group_show_export = false;
            }

            // Global export
            if (global_vals.hide_export) {
                this.state.group_show_export = false;
            }

            // Global readonly → no create/delete/duplicate/archive/unarchive
            if (global_vals.sh_readonly) {
                this.state.group_show_create = false;
                this.state.group_show_delete = false;
                this.state.group_show_duplicate = false;
                this.state.group_show_archive = false;
                this.state.group_show_unarchive = false;
            }
        }
        
        

        // Also hide the create button in the DOM for safety
        const formCreateBtns = document.querySelectorAll(".o_form_button_create");
        formCreateBtns.forEach((btn) => {
            btn.style.display = this.state.group_show_create ? "" : "none";
        });
    },

    async create() {
        if (this.state.group_show_create) {
            await super.create();
        }
    },

    getStaticActionMenuItems() {
        const originalItems = super.getStaticActionMenuItems
            ? super.getStaticActionMenuItems()
            : {};
        const { activeActions } = this.archInfo;

        return {
            ...originalItems,
            archive: {
                ...(originalItems.archive || {}),
                isAvailable: () =>
                    this.archiveEnabled &&
                    this.model.root.isActive &&
                    this.state.group_show_archive,
                callback: () => {
                    this.dialogService.add(
                        ConfirmationDialog,
                        this.archiveDialogProps
                    );
                },
            },
            unarchive: {
                ...(originalItems.unarchive || {}),
                isAvailable: () =>
                    this.archiveEnabled &&
                    !this.model.root.isActive &&
                    this.state.group_show_unarchive,
                callback: () => {
                    this.dialogService.add(
                        ConfirmationDialog,
                        this.unarchiveDialogProps
                    );
                },
            },
            duplicate: {
                ...(originalItems.duplicate || {}),
                isAvailable: () =>
                    activeActions.create &&
                    activeActions.duplicate &&
                    this.state.group_show_duplicate,
                callback: () => this.duplicateRecord(),
            },
            delete: {
                ...(originalItems.delete || {}),
                isAvailable: () =>
                    activeActions.delete &&
                    !this.model.root.isNew &&
                    this.state.group_show_delete,
                callback: () => this.deleteRecord(),
                skipSave: true,
            },
            addPropertyFieldValue: {
                ...(originalItems.addPropertyFieldValue || {}),
                isAvailable: () =>
                    activeActions.addPropertyFieldValue &&
                    this.state.group_show_add_properties,
                callback: () =>
                    this.model.bus.trigger("PROPERTY_FIELD:ADD_PROPERTY_VALUE"),
            },
        };
    },
});

/* ===================================================================== */
/* ==================== ListController Patch ============================ */
/* ===================================================================== */
patch(ListController.prototype, {
    setup() {
        super.setup(...arguments);
        this.state = useState({
            rpc_result: null,
            group_show_create: true,
            group_show_export: true,
            group_show_delete: true,
            group_show_duplicate: true,
            group_show_archive: true,
            group_show_unarchive: true,
        });
        this.orm = useService("orm");
        this.company = useService("company");
        const self = this;

        onWillStart(async () => {
            const uid = Array.isArray(session.user_id) ? session.user_id[0] : user.userId;
            const model_dic = await this.orm.call(
                "sh.access.model",
                "check_crud_operation",
                [{ user_id: uid, company_id: this.company.currentCompany.id }],
                {}
            );
            self.state.rpc_result = model_dic;
        });

        onMounted(() => this._shOnMountedList());
    },

    async _shOnMountedList() {
        
        const model_dic = this.state.rpc_result || {};
        const model_name = this.props.resModel;



        // Defaults: allow everything
        this.state.group_show_create = true;
        this.state.group_show_export = true;
        this.state.group_show_delete = true;
        this.state.group_show_duplicate = true;
        this.state.group_show_archive = true;
        this.state.group_show_unarchive = true;

        // --------------------
        // Per-model config
        // --------------------
        if (Object.prototype.hasOwnProperty.call(model_dic, model_name)) {
            const value = model_dic[model_name] || {};
            

            this.state.group_show_create = !value.hide_create;
            this.state.group_show_export = !value.hide_export;
            this.state.group_show_delete = !value.hide_delete;
            this.state.group_show_duplicate = !value.hide_duplicate;
            this.state.group_show_archive = !value.hide_archieve;
            this.state.group_show_unarchive = !value.hide_archieve;
        }

        // --------------------
        // Global config
        // --------------------
        const global_vals = model_dic["__global__"] || null;
        if (global_vals) {
            
            if (global_vals.sh_global_hide_create) {
                this.state.group_show_create = false;
            }
            if (global_vals.sh_global_hide_delete) {
                this.state.group_show_delete = false;
            }
            if (global_vals.sh_global_hide_duplicate) {
                this.state.group_show_duplicate = false;
            }
            if (global_vals.sh_global_hide_archive) {
                this.state.group_show_archive = false;
            }
            if (global_vals.sh_global_hide_unarchive) {
                this.state.group_show_unarchive = false;
            }

            if (global_vals.hide_action) {
                this.state.group_show_delete = false;
                this.state.group_show_duplicate = false;
                this.state.group_show_archive = false;
                this.state.group_show_unarchive = false;
                this.state.group_show_export = false;
            }

            if (global_vals.hide_export) {
                this.state.group_show_export = false;
            }

            if (global_vals.sh_readonly) {
                this.state.group_show_create = false;
                this.state.group_show_delete = false;
                this.state.group_show_duplicate = false;
                this.state.group_show_archive = false;
                this.state.group_show_unarchive = false;
            }
        }

        

        // HIDE 'New' Button in List view
        const createBtns = document.querySelectorAll(".o_list_button_add");
        createBtns.forEach((btn) => {
            btn.style.display = this.state.group_show_create ? "" : "none";
        });
    },

    onClickCreate() {
        if (this.state.group_show_create) {
            super.onClickCreate();
        }
    },

    getStaticActionMenuItems() {
        const originalItems = super.getStaticActionMenuItems
            ? super.getStaticActionMenuItems()
            : {};
        const list = this.model.root;
        const isM2MGrouped = list.groupBy.some((groupBy) => {
            const fieldName = groupBy.split(":")[0];
            return list.fields[fieldName].type === "many2many";
        });

        return {
            ...originalItems,
            export: {
                ...(originalItems.export || {}),
                isAvailable: () =>
                    this.isExportEnable && this.state.group_show_export,
                callback: () => this.exportRecords(),
            },
            archive: {
                ...(originalItems.archive || {}),
                isAvailable: () =>
                    this.archiveEnabled &&
                    !isM2MGrouped &&
                    this.state.group_show_archive,
                callback: () =>
                    this.model.root.toggleArchiveWithConfirmation(
                        true,
                        this.archiveDialogProps
                    ),
            },
            unarchive: {
                ...(originalItems.unarchive || {}),
                isAvailable: () =>
                    this.archiveEnabled &&
                    !isM2MGrouped &&
                    this.state.group_show_unarchive,
                callback: () =>
                    this.model.root.toggleArchiveWithConfirmation(false),
            },
            duplicate: {
                ...(originalItems.duplicate || {}),
                isAvailable: () =>
                    this.activeActions.duplicate &&
                    !isM2MGrouped &&
                    this.state.group_show_duplicate,
                callback: () => this.model.root.duplicateRecords(),
            },
            delete: {
                ...(originalItems.delete || {}),
                isAvailable: () =>
                    this.activeActions.delete &&
                    !isM2MGrouped &&
                    this.state.group_show_delete,
                callback: () => this.onDeleteSelectedRecords(),
            },
        };
    },
});

/* ===================================================================== */
/* ==================== KanbanController Patch ========================== */
/* ===================================================================== */
patch(KanbanController.prototype, {
    setup() {
        super.setup(...arguments);
        this.state = useState({
            rpc_result: null,
            group_show_create: true,
        });
        this.orm = useService("orm");
        this.company = useService("company");
        const self = this;

        onWillStart(async () => {
            const uid = Array.isArray(session.user_id) ? session.user_id[0] : user.userId;
            const model_dic = await this.orm.call(
                "sh.access.model",
                "check_crud_operation",
                [{ user_id: uid, company_id: this.company.currentCompany.id }],
                {}
            );
            self.state.rpc_result = model_dic;
        });

        onMounted(() => this._shOnMountedKanban());
    },

    async _shOnMountedKanban() {
        const model_dic = this.state.rpc_result || {};
        const model_name = this.props.resModel;

        this.state.group_show_create = true;

        if (Object.prototype.hasOwnProperty.call(model_dic, model_name)) {
            const value = model_dic[model_name] || {};
            this.state.group_show_create = !value.hide_create;
        }

        const global_vals = model_dic["__global__"] || null;
        if (global_vals) {
            if (global_vals.sh_global_hide_create) {
                this.state.group_show_create = false;
            }

            if (global_vals.sh_readonly) {
                this.state.group_show_create = false;
            }
        }

        const kanbanNewBtns = document.querySelectorAll(".o-kanban-button-new");
        kanbanNewBtns.forEach((btn) => {
            btn.style.display = this.state.group_show_create ? "" : "none";
        });
    },

    async createRecord() {
        const { onCreate } = this.props.archInfo;
        const { root } = this.model;

        if (!this.state.group_show_create) {
            return;
        }

        if (this.canQuickCreate && onCreate === "quick_create") {
            const firstGroup = root.groups[0];
            if (firstGroup && firstGroup.isFolded) {
                await firstGroup.toggle();
            }
            this.quickCreateState.groupId = firstGroup ? firstGroup.id : undefined;
        } else if (onCreate && onCreate !== "quick_create") {
            const options = {
                additionalContext: root.context,
                onClose: async () => {
                    await root.load();
                    this.model.useSampleModel = false;
                    this.render(true);
                },
            };
            await this.actionService.doAction(onCreate, options);
        } else if (this.props.createRecord) {
            await this.props.createRecord();
        }
    },
});

/* ===================================================================== */
/* ==================== CalendarController Patch ======================== */
/* ===================================================================== */
/* Use your old working pattern + extra DOM fallback/logging so Time Off
   and any special calendar variant is covered. */
patch(CalendarController.prototype, {
    setup() {
        super.setup(...arguments);

        const baseState = this.state || {};
        this.state = useState({
            ...baseState,
            rpc_result: null,
            group_show_create: true,
        });

        this.orm = useService("orm");
        this.company = useService("company");
        const self = this;

        onWillStart(async () => {
            const uid = Array.isArray(session.user_id) ? session.user_id[0] : user.userId;
            const model_dic = await this.orm.call(
                "sh.access.model",
                "check_crud_operation",
                [{ user_id: uid, company_id: this.company.currentCompany.id }],
                {}
            );
            self.state.rpc_result = model_dic;
        });

        onMounted(() => this._shOnMountedCalendar());
    },

    async _shOnMountedCalendar() {
        const model_dic = this.state.rpc_result || {};
        const model_name = this.props.resModel;

        let canCreate = true;

        // Per-model rule
        if (Object.prototype.hasOwnProperty.call(model_dic, model_name)) {
            const value = model_dic[model_name] || {};
            if (value.hide_create) {
                canCreate = false;
            }
        }

        // Global rules
        const global_vals = model_dic["__global__"] || null;
        if (global_vals) {
            if (global_vals.sh_global_hide_create) {
                canCreate = false;
            }
            if (global_vals.sh_readonly) {
                canCreate = false;
            }
        }

        this.state.group_show_create = canCreate;

        // -------- DOM fallback (for layouts where the slot isn't used) ------
        const hideButtonsOnce = () => {
            const rootEl = this.el || document;
            const allButtons = rootEl.querySelectorAll("button");

            allButtons.forEach((btn) => {
                const text = (btn.textContent || "").trim();
                const classes = btn.className;
                const hotkey = btn.dataset ? btn.dataset.hotkey : undefined;

                if (!this.state.group_show_create) {
                    const looksLikeNew =
                        hotkey === "c" ||
                        classes.includes("o_calendar_button_new") ||
                        classes.includes("o_button_new") ||
                        (text && text.toLowerCase() === "new");

                    if (looksLikeNew) {
                        btn.style.display = "none";

                    }
                }
            });
        };

        // Run a few times to catch late rendering in some calendar variants
        hideButtonsOnce();
        setTimeout(hideButtonsOnce, 0);
        setTimeout(hideButtonsOnce, 300);
    },

    async createRecord() {
        if (!this.state.group_show_create) {
            return;
        }
        await super.createRecord();
    },
});

/* ===================================================================== */
/* ==================== ExportAll Patch =================================*/
/* ===================================================================== */
patch(ExportAll.prototype, {
    setup() {
        super.setup(...arguments);
        this.state = useState({
            rpc_result: null,
            group_show_export: true,
        });
        this.orm = useService("orm");
        this.company = useService("company");
        const self = this;

        onWillStart(async () => {
            const model_dic = await this.orm.call(
                "sh.access.model",
                "check_crud_operation",
                [{ user_id: session.uid, company_id: this.company.currentCompany.id }],
                {}
            );
            self.state.rpc_result = model_dic;
        });

        onMounted(() => this._shOnMountedExportAll());
    },

    async _shOnMountedExportAll() {
        const model_dic = this.state.rpc_result || {};

        this.state.group_show_export = true;

        const fragment = window.location.hash.substring(1);
        const params = new URLSearchParams(fragment);
        const modelParam = params.get("model");

        if (modelParam && Object.prototype.hasOwnProperty.call(model_dic, modelParam)) {
            const value = model_dic[modelParam] || {};
            this.state.group_show_export = !value.hide_export;
        }

        const global_vals = model_dic["__global__"] || null;
        if (global_vals) {
            if (global_vals.hide_export) {
                this.state.group_show_export = false;
            }

            if (global_vals.hide_action || global_vals.sh_readonly) {
                this.state.group_show_export = false;
            }
        }
    },
});
