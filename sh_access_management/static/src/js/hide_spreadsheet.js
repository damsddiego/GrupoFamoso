/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { WebClient } from "@web/webclient/webclient";
import { registry } from "@web/core/registry";
import { user } from "@web/core/user";

patch(WebClient.prototype, {
    __patch_name__: "sh_access_management.hide_spreadsheet",
    setup() {
        super.setup();
        const cogMenuRegistry = registry.category("cogMenu");
        if (cogMenuRegistry.contains("spreadsheet-cog-menu")) {
            const spreadsheetMenuItem = cogMenuRegistry.get("spreadsheet-cog-menu");
            const originalIsDisplayed = spreadsheetMenuItem.isDisplayed;
            spreadsheetMenuItem.isDisplayed = async function (env) {
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
                            
                            if (model_dic["__global__"] && model_dic["__global__"]["hide_spreadsheet"]) {
                                return false;
                            } else if (model_dic[modelName] && model_dic[modelName]["hide_spreadsheet"]) {
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
