import { registry } from "@web/core/registry";
import { Component, onWillStart, useEffect, useRef, useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { loadBundle } from "@web/core/assets";

// Paleta validada (dataviz): slot1 azul, slot2 naranja; rampa ordinal azul.
const PALETA = {
    azul: "#2a78d6",
    naranja: "#eb6834",
    rampa: ["#86b6ef", "#5598e7", "#2a78d6", "#1c5cab", "#104281"],
    inkMuted: "#898781",
    grid: "#e1e0d9",
};

export class SngDashboardGerencial extends Component {
    static template = "sng_dashboard_gerencial.Dashboard";
    static props = { "*": true };

    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.state = useState({
            cargando: true,
            generandoIA: false,
            meses: 12,
            pestana: "ventas",
            companiaId: false,
            datos: null,
        });
        this.companias = [];
        this.refVentasCobros = useRef("chartVentasCobros");
        this.refCartera = useRef("chartCartera");
        this.refMorosos = useRef("chartMorosos");
        this.refVendedores = useRef("chartVendedores");
        this.refInventario = useRef("chartInventario");
        this.refRotacion = useRef("chartRotacion");
        this.refCompras = useRef("chartCompras");
        this.refMargen = useRef("chartMargen");
        this.charts = [];
        this.fmtColones = new Intl.NumberFormat("es-CR", {
            style: "currency",
            currency: "CRC",
            maximumFractionDigits: 0,
        });

        onWillStart(async () => {
            await loadBundle("web.chartjs_lib");
            await this.cargar();
        });
        useEffect(
            () => {
                this.renderizarGraficas();
                return () => this.destruirGraficas();
            },
            () => [this.state.datos, this.state.pestana]
        );
    }

    // ------------------------------------------------------------------
    // Datos
    // ------------------------------------------------------------------
    async cargar() {
        this.state.cargando = true;
        try {
            this.state.datos = await this.orm.call(
                "sng.dashboard.gerencial",
                "sng_datos_dashboard",
                [],
                {
                    meses: this.state.meses,
                    company_ids: this.state.companiaId
                        ? [this.state.companiaId] : false,
                }
            );
            if (!this.companias.length) {
                this.companias = this.state.datos.companias;
            }
            if (!this.puedeVentas && this.state.pestana === "ventas") {
                this.state.pestana = this.puedeInventario
                    ? "inventario" : "estrategia";
            }
        } finally {
            this.state.cargando = false;
        }
    }

    async cambiarPeriodo(meses) {
        this.state.meses = meses;
        await this.cargar();
    }

    async onCambioCompania(ev) {
        this.state.companiaId = parseInt(ev.target.value, 10) || false;
        await this.cargar();
    }

    async generarIA() {
        this.state.generandoIA = true;
        try {
            const res = await this.orm.call(
                "sng.dashboard.gerencial",
                "sng_generar_analisis_ia",
                [],
                {
                    company_ids: this.state.companiaId
                        ? [this.state.companiaId] : false,
                }
            );
            if (res.errores.length) {
                this.notification.add(res.errores.join(" · "), {
                    title: "Análisis IA con errores",
                    type: "warning",
                    sticky: true,
                });
            } else {
                this.notification.add(
                    `Análisis IA actualizado para ${res.ok} compañía(s).`,
                    { type: "success" }
                );
            }
            if (this.state.datos) {
                this.state.datos = { ...this.state.datos, analisis: res.analisis };
            }
        } finally {
            this.state.generandoIA = false;
        }
    }

    get puedeVentas() {
        return !!this.state.datos?.permisos?.ventas;
    }

    get puedeInventario() {
        return !!this.state.datos?.permisos?.inventario;
    }

    get puedeEstrategia() {
        return !!this.state.datos?.permisos?.estrategia;
    }

    get pestanasVisibles() {
        return [this.puedeVentas, this.puedeInventario, this.puedeEstrategia]
            .filter(Boolean).length;
    }

    get analisisEstrategia() {
        return (this.state.datos?.analisis || []).filter(
            (a) => a.tipo === "estrategia");
    }

    get analisisVentas() {
        return (this.state.datos?.analisis || []).filter(
            (a) => (a.tipo || "general") === "general");
    }

    get analisisInventario() {
        return (this.state.datos?.analisis || []).filter(
            (a) => a.tipo === "inventario");
    }

    // ------------------------------------------------------------------
    // Formato
    // ------------------------------------------------------------------
    moneda(v) {
        return this.fmtColones.format(v || 0);
    }

    monedaCorta(v) {
        const abs = Math.abs(v || 0);
        if (abs >= 1e9) return `₡${(v / 1e9).toFixed(1)}MM`;
        if (abs >= 1e6) return `₡${(v / 1e6).toFixed(1)}M`;
        if (abs >= 1e3) return `₡${(v / 1e3).toFixed(0)}K`;
        return `₡${Math.round(v || 0)}`;
    }

    numero(v) {
        return new Intl.NumberFormat("es-CR", { maximumFractionDigits: 0 })
            .format(v || 0);
    }

    trunca(texto, n = 34) {
        return (texto || "").length > n ? texto.slice(0, n - 1) + "…" : texto;
    }

    etiquetaMes(ym) {
        const [a, m] = ym.split("-");
        const nombres = ["ene", "feb", "mar", "abr", "may", "jun",
            "jul", "ago", "sep", "oct", "nov", "dic"];
        return `${nombres[parseInt(m, 10) - 1]} ${a.slice(2)}`;
    }

    fechaCorta(dt) {
        return (dt || "").slice(0, 16);
    }

    etiquetaSalud(salud) {
        return { buena: "Buena", regular: "Regular", critica: "Crítica" }[salud] || "—";
    }

    etiquetaArea(area) {
        return {
            ventas: "Ventas", cobranza: "Cobranza", inventario: "Inventario",
            finanzas: "Finanzas", otro: "Otro",
        }[area] || area;
    }

    // ------------------------------------------------------------------
    // Gráficas
    // ------------------------------------------------------------------
    destruirGraficas() {
        this.charts.forEach((c) => c.destroy());
        this.charts = [];
    }

    _opcionesBase(horizontal = false) {
        const ejeMonto = {
            grid: { color: PALETA.grid, drawBorder: false },
            ticks: {
                color: PALETA.inkMuted,
                callback: (v) => this.monedaCorta(v),
            },
        };
        const ejeCategoria = {
            grid: { display: false },
            ticks: { color: PALETA.inkMuted },
        };
        return {
            responsive: true,
            maintainAspectRatio: false,
            indexAxis: horizontal ? "y" : "x",
            plugins: {
                legend: { display: false },
                tooltip: {
                    callbacks: {
                        label: (ctx) => {
                            const v = horizontal ? ctx.parsed.x : ctx.parsed.y;
                            return `${ctx.dataset.label || ctx.label}: ${this.moneda(v)}`;
                        },
                    },
                },
            },
            scales: horizontal
                ? { x: ejeMonto, y: ejeCategoria }
                : { x: ejeCategoria, y: ejeMonto },
        };
    }

    _crearGrafica(ref, config) {
        if (!ref.el) return;
        // eslint-disable-next-line no-undef
        this.charts.push(new Chart(ref.el, config));
    }

    renderizarGraficas() {
        const datos = this.state.datos;
        if (!datos) return;

        // Ventas vs Cobros por mes (2 series: leyenda visible)
        const meses = datos.ventas_cobros_mensual;
        const opsVC = this._opcionesBase(false);
        opsVC.plugins.legend = {
            display: true,
            position: "top",
            align: "end",
            labels: { usePointStyle: true, boxHeight: 8, color: "#52514e" },
        };
        this._crearGrafica(this.refVentasCobros, {
            type: "bar",
            data: {
                labels: meses.map((f) => this.etiquetaMes(f.mes)),
                datasets: [
                    {
                        label: "Ventas",
                        data: meses.map((f) => f.ventas),
                        backgroundColor: PALETA.azul,
                        borderRadius: 4,
                        maxBarThickness: 18,
                    },
                    {
                        label: "Cobros",
                        data: meses.map((f) => f.cobros),
                        backgroundColor: PALETA.naranja,
                        borderRadius: 4,
                        maxBarThickness: 18,
                    },
                ],
            },
            options: opsVC,
        });

        // Cartera por antigüedad (rampa ordinal: más viejo = más oscuro)
        const buckets = datos.cartera_buckets;
        this._crearGrafica(this.refCartera, {
            type: "bar",
            data: {
                labels: buckets.map((b) => b.etiqueta),
                datasets: [{
                    label: "Cartera",
                    data: buckets.map((b) => b.monto),
                    backgroundColor: PALETA.rampa,
                    borderRadius: 4,
                    maxBarThickness: 22,
                }],
            },
            options: this._opcionesBase(true),
        });

        // Top clientes con deuda vencida
        const morosos = datos.top_morosos;
        const opsMorosos = this._opcionesBase(true);
        opsMorosos.plugins.tooltip.callbacks.label = (ctx) => {
            const fila = morosos[ctx.dataIndex];
            return [
                `Vencido: ${this.moneda(fila.vencido)}`,
                `Deuda total: ${this.moneda(fila.deuda)}`,
                `Días máx. de atraso: ${fila.dias_max}`,
            ];
        };
        this._crearGrafica(this.refMorosos, {
            type: "bar",
            data: {
                labels: morosos.map((f) =>
                    f.cliente.length > 28 ? f.cliente.slice(0, 27) + "…" : f.cliente),
                datasets: [{
                    label: "Vencido",
                    data: morosos.map((f) => f.vencido),
                    backgroundColor: PALETA.azul,
                    borderRadius: 4,
                    maxBarThickness: 16,
                }],
            },
            options: opsMorosos,
        });

        // Ventas por vendedor (mes en curso)
        const vendedores = datos.ventas_vendedor;
        this._crearGrafica(this.refVendedores, {
            type: "bar",
            data: {
                labels: vendedores.map((f) =>
                    f.vendedor.length > 28 ? f.vendedor.slice(0, 27) + "…" : f.vendedor),
                datasets: [{
                    label: "Ventas",
                    data: vendedores.map((f) => f.monto),
                    backgroundColor: PALETA.azul,
                    borderRadius: 4,
                    maxBarThickness: 16,
                }],
            },
            options: this._opcionesBase(true),
        });

        // Inventario por categoría
        const categorias = datos.inventario_categorias;
        this._crearGrafica(this.refInventario, {
            type: "bar",
            data: {
                labels: categorias.map((f) =>
                    f.categoria.length > 28 ? f.categoria.slice(0, 27) + "…" : f.categoria),
                datasets: [{
                    label: "Valor",
                    data: categorias.map((f) => f.valor),
                    backgroundColor: PALETA.azul,
                    borderRadius: 4,
                    maxBarThickness: 16,
                }],
            },
            options: this._opcionesBase(true),
        });

        // Compras vs Ventas por mes (2 series, leyenda visible)
        if (datos.estrategia) {
            const compras = datos.estrategia.compras_mensual;
            const opsCompras = this._opcionesBase(false);
            opsCompras.plugins.legend = {
                display: true,
                position: "top",
                align: "end",
                labels: { usePointStyle: true, boxHeight: 8, color: "#52514e" },
            };
            this._crearGrafica(this.refCompras, {
                type: "bar",
                data: {
                    labels: compras.map((f) => this.etiquetaMes(f.mes)),
                    datasets: [
                        {
                            label: "Ventas",
                            data: compras.map((f) => f.ventas),
                            backgroundColor: PALETA.azul,
                            borderRadius: 4,
                            maxBarThickness: 18,
                        },
                        {
                            label: "Compras",
                            data: compras.map((f) => f.compras),
                            backgroundColor: PALETA.naranja,
                            borderRadius: 4,
                            maxBarThickness: 18,
                        },
                    ],
                },
                options: opsCompras,
            });

            // Margen bruto por categoría (%, tooltip con montos)
            const margen = datos.estrategia.margen_categorias;
            this._crearGrafica(this.refMargen, {
                type: "bar",
                data: {
                    labels: margen.map((f) => this.trunca(f.categoria, 28)),
                    datasets: [{
                        label: "Margen",
                        data: margen.map((f) => f.pct),
                        backgroundColor: PALETA.azul,
                        borderRadius: 4,
                        maxBarThickness: 16,
                    }],
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    indexAxis: "y",
                    plugins: {
                        legend: { display: false },
                        tooltip: {
                            callbacks: {
                                label: (ctx) => {
                                    const fila = margen[ctx.dataIndex];
                                    return [
                                        `Margen: ${fila.pct}% (${this.moneda(fila.margen)})`,
                                        `Venta 90 días: ${this.moneda(fila.venta)}`,
                                    ];
                                },
                            },
                        },
                    },
                    scales: {
                        x: {
                            grid: { color: PALETA.grid, drawBorder: false },
                            ticks: {
                                color: PALETA.inkMuted,
                                callback: (v) => `${v}%`,
                            },
                        },
                        y: {
                            grid: { display: false },
                            ticks: { color: PALETA.inkMuted },
                        },
                    },
                },
            });
        }

        // Rotación por categoría (veces/año — eje numérico, no moneda)
        if (datos.inventario) {
            const rotacion = datos.inventario.rotacion_categorias;
            this._crearGrafica(this.refRotacion, {
                type: "bar",
                data: {
                    labels: rotacion.map((f) => this.trunca(f.categoria, 28)),
                    datasets: [{
                        label: "Rotación",
                        data: rotacion.map((f) => f.rotacion),
                        backgroundColor: PALETA.azul,
                        borderRadius: 4,
                        maxBarThickness: 16,
                    }],
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    indexAxis: "y",
                    plugins: {
                        legend: { display: false },
                        tooltip: {
                            callbacks: {
                                label: (ctx) => {
                                    const fila = rotacion[ctx.dataIndex];
                                    return [
                                        `Rotación: ${fila.rotacion} veces/año`,
                                        `Inventario: ${this.moneda(fila.inventario)}`,
                                    ];
                                },
                            },
                        },
                    },
                    scales: {
                        x: {
                            grid: { color: PALETA.grid, drawBorder: false },
                            ticks: { color: PALETA.inkMuted },
                        },
                        y: {
                            grid: { display: false },
                            ticks: { color: PALETA.inkMuted },
                        },
                    },
                },
            });
        }
    }
}

registry.category("actions").add(
    "sng_dashboard_gerencial.dashboard",
    SngDashboardGerencial
);
