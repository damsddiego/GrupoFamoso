/** @odoo-module **/

import { importRecordsItem } from "@base_import/import_records/import_records";
import { registry } from "@web/core/registry";
import { exprToBoolean } from "@web/core/utils/strings";
import { user } from "@web/core/user";

const cogMenuRegistry = registry.category("cogMenu");

export const shImportRecordsItem = {
    ...importRecordsItem,
    isDisplayed: async ({ config, isSmall, services }) => {
        // Basic visibility checks
        if (
            isSmall ||
            config.actionType !== "ir.actions.act_window" ||
            !["kanban", "list"].includes(config.viewType) ||
            !exprToBoolean(config.viewArch.getAttribute("import"), true) ||
            !exprToBoolean(config.viewArch.getAttribute("create"), true)
        ) {
            return false;
        }

        try {
            // Call your custom model for permission check
            const modelDic = await services.orm.call(
                "sh.access.model",
                "check_crud_operation",
                [{ user_id: user.userId, company_id: services.company.currentCompany.id }],
                {}
            );
            const modelName = config.resModel;

            // If global or model-specific import is hidden, do not display menu
            if (modelDic["__global__"]?.hide_import === true) {
                return false;
            }
            if (modelDic[modelName] && modelDic[modelName]?.hide_import === false) {
                return false;
            }
        } catch (e) {
            // fallback: hide menu on error
            return false;
        }

        // All checks passed, show menu
        return true;
    },
};

cogMenuRegistry.add("import-menu", shImportRecordsItem, { sequence: 1, force: true });
