/** @odoo-module **/
import { Many2XAutocomplete } from "@web/views/fields/relational_utils";
import { patch } from "@web/core/utils/patch";
import { useService } from "@web/core/utils/hooks";
import { onWillStart } from "@odoo/owl";
import { user } from "@web/core/user";
import { _t } from "@web/core/l10n/translation";

function getCompanyIdsFromCookie() {
    const cookieValue = document.cookie
        .split('; ')
        .find(row => row.startsWith('cids='))
        ?.split('=')[1];
    if (!cookieValue) {
        return [];
    }
    return cookieValue.split(',').map(Number).filter(id => !isNaN(id));
}

patch(Many2XAutocomplete.prototype, {
    setup() {
        super.setup();
        this.orm = useService("orm");
        this.sh_global_hide_field_create_edit = false;
        onWillStart(async () => {
            try {
                const companyIds = getCompanyIdsFromCookie();
                const result = await this.orm.call(
                    "sh.access.manager",
                    "get_access_restrictions",
                    [],
                    {
                        kwargs: {
                            user_id: user.userId,
                            company_ids: companyIds,
                        },
                    }
                );
                if (result && result.model_restrictions) {
                    this.sh_global_hide_field_create_edit = result.model_restrictions.sh_global_hide_field_create_edit;
                }
            } catch (error) {
                
            }
        });
    },

    async loadOptionsSource(request) {
        const options = await super.loadOptionsSource(request);
        if (this.sh_global_hide_field_create_edit) {
            const filteredOptions = options.filter(option => 
                !option.classList?.includes("o_m2o_dropdown_option_create") && 
                !option.classList?.includes("o_m2o_dropdown_option_create_edit")
            );

            if (filteredOptions.length === 0 && request.length > 0) {
                const hasSearchMore = options.some(option => option.classList?.includes("o_m2o_dropdown_option_search_more"));
                if (!hasSearchMore) {
                    filteredOptions.push({
                        label: _t("No records"),
                        classList: "o_m2o_no_result",
                        unselectable: true,
                    });
                }
            }
            return filteredOptions;
        }
        return options;
    }
});