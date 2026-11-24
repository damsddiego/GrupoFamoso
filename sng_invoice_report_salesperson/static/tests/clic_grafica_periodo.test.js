import { animationFrame } from "@odoo/hoot-mock";
import { describe, expect, test } from "@odoo/hoot";

import { createSpreadsheetWithChart } from "@spreadsheet/../tests/helpers/chart";
import { mockService } from "@web/../tests/web_test_helpers";
import {
    getBasicServerData,
    defineSpreadsheetActions,
    defineSpreadsheetModels,
} from "@spreadsheet/../tests/helpers/data";
import { waitForDataLoaded } from "@spreadsheet/helpers/model";

// Pruebas del parche de sng_invoice_report_salesperson: en un tablero, el
// clic en un punto de una gráfica agrupada por fecha abre todo el rango de
// la gráfica; Ctrl+clic conserva el comportamiento de Odoo (solo el punto).
// Se ejecutan con el runner de hoot de Odoo (/web/tests), no con unittest.

describe.current.tags("headless");
defineSpreadsheetModels();
defineSpreadsheetActions();

const datosServidor = getBasicServerData();
datosServidor.models.partner.records = [
    { date: "2022-01-05", probability: 3 },
    { date: "2022-03-10", probability: 4 },
    { date: "2022-06-20", probability: 5 },
];

const dominioGrafica = [
    ["date", ">=", "2022-01-01"],
    ["date", "<=", "2022-12-31"],
];

const definicionPorMes = {
    type: "odoo_line",
    metaData: {
        groupBy: ["date:month"],
        measure: "probability",
        order: null,
        resModel: "partner",
    },
    searchParams: {
        comparison: null,
        context: {},
        domain: dominioGrafica,
        groupBy: ["date:month"],
        orderBy: [],
    },
    title: { text: "Partners" },
    dataSourceId: "42",
    id: "42",
};

function servicioAccionQueGuarda(acciones) {
    return {
        doAction: async (request) => {
            if (request.type === "ir.actions.act_window") {
                acciones.push(request);
            }
        },
        loadAction() {
            throw new Error("sin actionXmlId");
        },
    };
}

async function tableroConGraficaPorMes() {
    const { model } = await createSpreadsheetWithChart({
        type: "odoo_line",
        serverData: datosServidor,
        definition: definicionPorMes,
    });
    model.updateMode("dashboard");
    const sheetId = model.getters.getActiveSheetId();
    const chartId = model.getters.getChartIds(sheetId)[0];
    await waitForDataLoaded(model);
    return { model, runtime: model.getters.getChartRuntime(chartId) };
}

test("clic en un punto abre todo el rango de la gráfica en el tablero", async () => {
    const acciones = [];
    mockService("action", servicioAccionQueGuarda(acciones));
    const { runtime } = await tableroConGraficaPorMes();

    await runtime.chartJsConfig.options.onClick({ native: {} }, [{ datasetIndex: 0, index: 1 }]);
    await animationFrame();

    expect(acciones.length).toBe(1);
    expect(acciones[0].domain).toEqual(dominioGrafica);
    expect(acciones[0].name).toBe("January 2022 – June 2022 / Probability");
    expect(acciones[0].res_model).toBe("partner");
});

test("Ctrl+clic en un punto abre solo ese mes", async () => {
    const acciones = [];
    mockService("action", servicioAccionQueGuarda(acciones));
    const { runtime } = await tableroConGraficaPorMes();

    await runtime.chartJsConfig.options.onClick({ native: { ctrlKey: true } }, [
        { datasetIndex: 0, index: 1 },
    ]);
    await animationFrame();

    expect(acciones.length).toBe(1);
    expect(acciones[0].name).toBe("March 2022 / Probability");
    expect(acciones[0].domain).not.toEqual(dominioGrafica);
    expect(JSON.stringify(acciones[0].domain)).toInclude("2022-03-01");
});

test("fuera del tablero el clic conserva el comportamiento de Odoo", async () => {
    const acciones = [];
    mockService("action", servicioAccionQueGuarda(acciones));
    const { model } = await createSpreadsheetWithChart({
        type: "odoo_line",
        serverData: datosServidor,
        definition: definicionPorMes,
    });
    const sheetId = model.getters.getActiveSheetId();
    const chartId = model.getters.getChartIds(sheetId)[0];
    await waitForDataLoaded(model);
    const runtime = model.getters.getChartRuntime(chartId);

    await runtime.chartJsConfig.options.onClick({ native: {} }, [{ datasetIndex: 0, index: 1 }]);
    await animationFrame();

    expect(acciones.length).toBe(1);
    expect(acciones[0].name).toBe("March 2022 / Probability");
});
