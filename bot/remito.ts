// Presupuesto (PDF) de Negobazar. Productos sujetos a stock. Sin IVA salvo que el cliente lo pida.
import { jsPDF } from "npm:jspdf@2.5.1";

export type ItemRemito = { codigo: string; nombre: string; cantidad: number; precio: number; foto?: Uint8Array };
export type DatosRemito = {
  numero: string;
  fecha: Date;
  cliente: { nombre: string; documento?: string; direccion?: string; localidad?: string; telefono?: string; email?: string; negocio?: string };
  zona: "CABA" | "GBA" | "INTERIOR" | "";
  pago: string;
  conIva?: boolean; // solo si el cliente lo pide (se suma 21%)
  items: ItemRemito[];
};

export const MINIMO = 750000;
export const RECARGO_MENOR = 0.2;
export const ENVIO_MENOR: Record<string, number> = { CABA: 10000, GBA: 15000, INTERIOR: 10000 };

const pesos = (n: number) => "$ " + Math.round(n).toLocaleString("es-AR");

export function calcular(d: DatosRemito) {
  const base = d.items.reduce((a, it) => a + it.precio * it.cantidad, 0);
  const menor = base < MINIMO;
  const factor = menor ? 1 + RECARGO_MENOR : 1;
  const lineas = d.items.map((it) => ({ ...it, unit: Math.round(it.precio * factor), sub: Math.round(it.precio * factor) * it.cantidad }));
  const subtotal = lineas.reduce((a, l) => a + l.sub, 0);
  const envio = menor ? (ENVIO_MENOR[d.zona] ?? 0) : 0;
  const iva = d.conIva ? Math.round((subtotal + envio) * 0.21) : 0;
  return { lineas, menor, subtotal, envio, iva, total: subtotal + envio + iva };
}

export function remitoPDF(d: DatosRemito): Uint8Array {
  const c = calcular(d);
  const doc = new jsPDF({ unit: "mm", format: "a4" });
  const AM: [number, number, number] = [252, 196, 25];
  const NE: [number, number, number] = [17, 17, 17];
  const W = 210;

  // Encabezado
  doc.setFillColor(...NE); doc.rect(0, 0, W, 34, "F");
  doc.setTextColor(255, 255, 255); doc.setFont("helvetica", "bold"); doc.setFontSize(16);
  doc.text("Negobazar · Venta mayorista", 12, 16);
  doc.setFont("helvetica", "normal"); doc.setFontSize(8.5);
  doc.text("www.negobazar.com.ar · WhatsApp 11 2537-1053", 12, 24);
  doc.setFont("helvetica", "bold"); doc.setFontSize(9);
  doc.text(`Presupuesto N° ${d.numero}`, W - 12, 15, { align: "right" });
  doc.setFont("helvetica", "normal");
  doc.text(d.fecha.toLocaleDateString("es-AR", { timeZone: "America/Argentina/Buenos_Aires" }), W - 12, 21, { align: "right" });

  // Leyenda
  doc.setFillColor(...AM); doc.roundedRect(12, 40, W - 24, 14, 3, 3, "F");
  doc.setTextColor(...NE); doc.setFont("helvetica", "bold"); doc.setFontSize(15);
  doc.text("PRESUPUESTO — PRODUCTOS SUJETOS A STOCK", W / 2, 49.5, { align: "center" });

  // Cliente
  let y = 64;
  doc.setFontSize(10); doc.text("DATOS DEL CLIENTE", 12, y); y += 2;
  doc.setDrawColor(...AM); doc.setLineWidth(0.8); doc.line(12, y, W - 12, y); y += 6;
  doc.setFont("helvetica", "normal"); doc.setFontSize(9.5);
  const cl = d.cliente;
  const filas: [string, string][] = [
    ["Nombre / Razón social", cl.nombre || "-"], ["CUIT / DNI", cl.documento || "-"],
    ["Dirección de entrega", [cl.direccion, cl.localidad].filter(Boolean).join(", ") || "-"],
    ["Teléfono", cl.telefono || "-"], ["Email", cl.email || "-"], ["Tipo de negocio", cl.negocio || "-"],
    ["Forma de pago", d.pago || "-"],
  ];
  for (const [k, v] of filas) {
    doc.setFont("helvetica", "bold"); doc.text(k + ":", 12, y);
    doc.setFont("helvetica", "normal"); doc.text(doc.splitTextToSize(v, 130)[0], 60, y); y += 5.5;
  }

  // Tabla
  y += 4;
  const col = { foto: 13, cod: 31, desc: 48, cant: 132, unit: 152, sub: W - 12 };
  doc.setFillColor(...NE); doc.rect(12, y, W - 24, 8, "F");
  doc.setTextColor(255, 255, 255); doc.setFont("helvetica", "bold"); doc.setFontSize(9);
  doc.text("FOTO", col.foto + 1, y + 5.4); doc.text("CÓD.", col.cod, y + 5.4); doc.text("PRODUCTO", col.desc, y + 5.4);
  doc.text("CANT.", col.cant + 12, y + 5.4, { align: "right" }); doc.text("P. UNIT.", col.unit + 22, y + 5.4, { align: "right" });
  doc.text("SUBTOTAL", col.sub - 2, y + 5.4, { align: "right" });
  y += 8; doc.setTextColor(...NE); doc.setFont("helvetica", "normal");
  c.lineas.forEach((l, i) => {
    const desc = doc.splitTextToSize(l.nombre, 74) as string[];
    const h = Math.max(17, desc.length * 4.2 + 4);
    if (y + h > 262) { doc.addPage(); y = 20; }
    if (i % 2 === 0) { doc.setFillColor(250, 246, 232); doc.rect(12, y, W - 24, h, "F"); }
    // fotito del producto (cuadrado blanco de 15 mm)
    doc.setFillColor(255, 255, 255); doc.roundedRect(col.foto, y + 1, 15, 15, 1.5, 1.5, "F");
    if (l.foto) { try { doc.addImage(l.foto, "JPEG", col.foto + 0.5, y + 1.5, 14, 14); } catch (_) { /* sin foto */ } }
    const ty = y + h / 2 + 1.2 - (desc.length - 1) * 2.1;
    doc.text(l.codigo, col.cod, y + h / 2 + 1.2); doc.text(desc, col.desc, ty);
    doc.text(String(l.cantidad), col.cant + 12, y + h / 2 + 1.2, { align: "right" });
    doc.text(pesos(l.unit), col.unit + 22, y + h / 2 + 1.2, { align: "right" });
    doc.text(pesos(l.sub), col.sub - 2, y + h / 2 + 1.2, { align: "right" });
    y += h;
  });

  // Totales
  y += 4;
  const tot = (k: string, v: string, fuerte = false) => {
    doc.setFont("helvetica", fuerte ? "bold" : "normal"); doc.setFontSize(fuerte ? 12 : 10);
    doc.text(k, 140, y, { align: "right" }); doc.text(v, W - 14, y, { align: "right" }); y += fuerte ? 8 : 6;
  };
  tot("Subtotal", pesos(c.subtotal));
  if (c.menor) tot(`Envío (${d.zona || "a confirmar"})`, c.envio ? pesos(c.envio) : "A confirmar");
  if (d.conIva) tot("IVA 21%", pesos(c.iva));
  doc.setFillColor(...AM); doc.roundedRect(100, y - 5, W - 112, 10, 2, 2, "F");
  y += 1.5; tot("TOTAL", pesos(c.total), true);

  // Condiciones
  y += 4;
  const cond: string[] = [
    "Presupuesto: los productos, cantidades y precios quedan sujetos a confirmación de stock por parte de Negobazar.",
    "No válido como factura.",
  ];
  if (d.conIva) cond.push("Incluye IVA 21% a pedido del cliente.");
  if (c.menor) {
    cond.push("Compra menor al mínimo de $750.000: precios con recargo del 20% sobre el precio mayorista.");
    cond.push("Pago únicamente por transferencia anticipada del total: el pedido se arma cuando se acredita el pago.");
    if (d.zona === "INTERIOR") cond.push("Envío por Vía Cargo: el flete lo abona el comprador. Los $10.000 corresponden al traslado desde nuestro depósito hasta Vía Cargo.");
  } else {
    cond.push("Compra mayorista: envío sin cargo en CABA y GBA (zonas habilitadas). Interior: despachamos al transporte que elijas; el flete lo abona el comprador.");
  }
  cond.push("Una vez enviados los datos de pago, hay 72 horas para abonar y enviar el comprobante.");
  doc.setFont("helvetica", "bold"); doc.setFontSize(9.5); doc.text("CONDICIONES", 12, y); y += 5;
  doc.setFont("helvetica", "normal"); doc.setFontSize(8.5);
  for (const t of cond) {
    const ls = doc.splitTextToSize("• " + t, W - 24) as string[];
    doc.text(ls, 12, y); y += ls.length * 4 + 1;
  }

  // Pie
  doc.setFillColor(...NE); doc.rect(0, 287, W, 10, "F");
  doc.setTextColor(...AM); doc.setFont("helvetica", "bold"); doc.setFontSize(9);
  doc.text("www.negobazar.com.ar · WhatsApp 11 2537-1053", W / 2, 293.5, { align: "center" });
  return new Uint8Array(doc.output("arraybuffer"));
}
