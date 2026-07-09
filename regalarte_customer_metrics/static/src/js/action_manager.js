/** @odoo-module **/

import { registry } from "@web/core/registry";
import { download } from "@web/core/network/download";

registry.category("ir.actions.report handlers").add("regalarte_customer_metrics_xlsx", async (action) => {
    if (action.report_type !== "regalarte_customer_metrics_xlsx") {
        return false;
    }
    await download({
        url: "/regalarte_customer_metrics/xlsx",
        data: action.data,
    });
    return true;
});
