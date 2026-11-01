// Arma un presupuesto con el mismo formato del bot y lo manda por WhatsApp (texto + PDF).
// Uso: deno run -A tools/presupuesto_manual.ts pedido.json productos.json
import { remitoPDF, calcular, type DatosRemito } from "../bot/remito.ts";
const [pedRuta, prodRuta] = Deno.args;
const ped = JSON.parse(await Deno.readTextFile(pedRuta));
const cat = JSON.parse(await Deno.readTextFile(prodRuta));
const items = [];
for (const it of ped.items) {
  const p = cat.find((x: any) => x.c === it.c);
  if (!p) throw new Error("no esta " + it.c);
  let foto: Uint8Array | undefined;
  try {
    const r = await fetch(p.img, { headers: { "User-Agent": "Mozilla/5.0" } });
    if (r.ok && (r.headers.get("content-type") ?? "").includes("jpeg")) foto = new Uint8Array(await r.arrayBuffer());
  } catch (_) { /* sin foto */ }
  items.push({ codigo: p.c, nombre: p.n, cantidad: it.q, precio: p.p, foto });
}
const hoy = new Date();
const numero = `${hoy.toISOString().slice(2, 10).replaceAll("-", "")}-M${String(hoy.getUTCHours()).padStart(2, "0")}${String(hoy.getUTCMinutes()).padStart(2, "0")}`;
const d: DatosRemito = {
  numero, fecha: hoy, zona: ped.zona, pago: "", conIva: false, items,
  cliente: { nombre: ped.nombre, documento: "", direccion: "", localidad: ped.localidad ?? "", email: "", negocio: ped.negocio ?? "", telefono: "+" + ped.chat.split("@")[0] },
};
const pdf = remitoPDF(d);
await Deno.writeFile("presupuesto.pdf", pdf);
const c = calcular(d);
console.log("total", c.total, "menor", c.menor);
if (Deno.env.get("ENVIAR") !== "si") Deno.exit(0);
const H = { Authorization: `Bearer ${Deno.env.get("WHAPI_TOKEN")}`, "Content-Type": "application/json" };
const r1 = await fetch("https://gate.whapi.cloud/messages/text", { method: "POST", headers: H, body: JSON.stringify({ to: ped.chat, body: ped.texto }) });
console.log("texto", r1.status);
await new Promise((ok) => setTimeout(ok, 2500));
let b64 = ""; const CH = 0x8000;
for (let i = 0; i < pdf.length; i += CH) b64 += String.fromCharCode(...pdf.subarray(i, i + CH));
const r2 = await fetch("https://gate.whapi.cloud/messages/document", { method: "POST", headers: H, body: JSON.stringify({
  to: ped.chat, media: "data:application/pdf;base64," + btoa(b64), filename: `Presupuesto-Negobazar-${numero}.pdf`,
  caption: `📄 Presupuesto N° ${numero} — precios sin IVA, productos sujetos a stock.` }) });
console.log("pdf", r2.status, (await r2.text()).slice(0, 120));
