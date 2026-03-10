/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { SearchBar } from "@web/search/search_bar/search_bar";
import { useService } from "@web/core/utils/hooks";
import { onWillStart } from "@odoo/owl";
import { user } from "@web/core/user";

patch(SearchBar.prototype, {
    setup() {
        super.setup();
        this.orm = useService("orm");
        this.company = useService("company");

        onWillStart(async () => {
            const { model_restrictions } = await this.orm.call(
                "sh.access.manager",
                "get_access_restrictions",
                [{ user_id: user.userId, company_id: this.company.currentCompany.id }]
            );

            const restrictions = model_restrictions || {};
            const searchModel = this.env.searchModel;

            searchModel.sh_hide_custom_filter = !!restrictions.global_hide_custom_filter;
            searchModel.sh_hide_custom_group_by = !!restrictions.global_hide_custom_group_by;
            searchModel.sh_hide_filter_tab = !!restrictions.global_hide_filter;
            searchModel.sh_hide_group_by_tab = !!restrictions.global_hide_group_by;
            searchModel.sh_global_hide_favorite_edit = !!restrictions.sh_global_hide_favorite_edit;
        });
    },
});
