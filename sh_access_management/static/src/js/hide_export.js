/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { ListController } from "@web/views/list/list_controller";
import { registry } from "@web/core/registry";
import { user } from "@web/core/user";

patch(ListController.prototype, {
    __patch_name__: "sh_access_management.hide_export",
    setup() {
        super.setup();
        const cogMenuRegistry = registry.category("cogMenu");
        if (cogMenuRegistry.contains("export-all-menu")) {
            const exportMenuItem = cogMenuRegistry.get("export-all-menu");
            const originalIsDisplayed = exportMenuItem.isDisplayed;
            exportMenuItem.isDisplayed = async function (env) {
                var res = originalIsDisplayed(env);
                if (res) {
                    try {
                        const companyId = user.activeCompany ? user.activeCompany.id : null;
                        var model_dic = await env.services.orm.call("sh.access.model", "check_crud_operation", [{
                            'user_id': user.userId,
                            'company_id': companyId
                        }]);
                        if (model_dic) {
                            const modelName = env.searchModel.resModel;
                            
                            if (model_dic["__global__"] && model_dic["__global__"]["hide_export"]) {
                                return false;
                            } else if (model_dic[modelName] && model_dic[modelName]["hide_export"]) {
                                return false;
                            }
                            return true;
                        }
                    } catch (e) {
                        
                        return true;
                    }
                }
                return res;
            };
        }
    },
});