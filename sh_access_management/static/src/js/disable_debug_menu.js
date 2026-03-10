/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { DebugMenu } from "@web/core/debug/debug_menu";
import { useService } from "@web/core/utils/hooks";
import { onWillStart } from "@odoo/owl";
import { user } from "@web/core/user";


patch(DebugMenu.prototype, {
    setup() {
        super.setup();
        this.orm = useService("orm");
        this.accessRestrictions = {};
        onWillStart(async () => {
            try {
                const { model_restrictions } = await this.orm.call(
                    "sh.access.manager",
                    "get_access_restrictions",
                    [{ user_id: user.userId, company_id: this.env.services.company.currentCompanyId }]
                );
                this.modelRestrictions = model_restrictions || {};
            } catch (error) {
                
            }
        });
    },
});
