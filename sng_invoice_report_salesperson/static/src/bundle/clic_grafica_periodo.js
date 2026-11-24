/** @odoo-module */

import { patch } from "@web/core/utils/patch";
import { OdooChartUIPlugin } from "@spreadsheet/chart/plugins/odoo_chart_ui_plugin";
import { navigateTo } from "@spreadsheet/actions/helpers";

/**
 * En los tableros (Tableros > Facturación, etc.), al hacer clic en un punto de
 * una gráfica agrupada por fecha, Odoo abre solo los registros de ese punto
 * (un mes). Compras necesita ver todo el período que tiene filtrado, así que:
 *
 *  - clic normal      → abre todos los registros del rango de la gráfica
 *                       (dominio de la gráfica + filtros globales del tablero);
 *  - Ctrl/Cmd + clic  → comportamiento original de Odoo: solo ese punto.
 *
 * Fuera de los tableros (editor de hojas) y en gráficas no agrupadas por
 * fecha no cambia nada.
 */

function agrupadaPorFecha(chart) {
    const grupo = chart.metaData?.groupBy?.[0];
    return typeof grupo === "string" && grupo.includes(":");
}

patch(OdooChartUIPlugin.prototype, {
    getChartDatasetActionCallbacks(chart) {
        const originales = super.getChartDatasetActionCallbacks(chart);
        if (!this.getters.isDashboard() || !agrupadaPorFecha(chart)) {
            return originales;
        }
        const env = this.custom.env;
        return {
            ...originales,
            onClick: async (event, items) => {
                const nativo = event?.native;
                if (nativo?.ctrlKey || nativo?.metaKey) {
                    return originales.onClick(event, items);
                }
                const { datasets, labels } = chart.dataSource.getData();
                if (!items.length || !env || items[0].datasetIndex >= datasets.length) {
                    return;
                }
                const dataset = datasets[items[0].datasetIndex];
                let name =
                    labels.length > 1 ? `${labels[0]} – ${labels[labels.length - 1]}` : labels[0];
                if (dataset.label) {
                    name += ` / ${dataset.label}`;
                }
                await navigateTo(
                    env,
                    chart.actionXmlId,
                    {
                        name,
                        type: "ir.actions.act_window",
                        res_model: chart.metaData.resModel,
                        views: [
                            [false, "list"],
                            [false, "form"],
                        ],
                        domain: chart.dataSource.getComputedDomain(),
                    },
                    { viewType: "list" }
                );
            },
        };
    },
});
