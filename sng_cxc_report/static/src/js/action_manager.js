/** @odoo-module **/

import { registry } from "@web/core/registry";
import { download } from "@web/core/network/download";

registry.category("ir.actions.report handlers").add("sng_cxc_report_xlsx", async (action) => {
    if (action.report_type !== "sng_cxc_report_xlsx") {
        return false;
    }
    await download({
        url: "/sng_cxc_report/xlsx",
        data: action.data,
    });
    return true;
});
