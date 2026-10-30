import { remitoPDF } from "../remito.ts";
const foto = async (c: string) => {
  try { const r = await fetch(`https://www.distriecono.com.ar/thumb/${c}_00_800x800.jpg`, { headers: { "User-Agent": "Mozilla/5.0" } });
    return r.ok ? new Uint8Array(await r.arrayBuffer()) : undefined; } catch { return undefined; }
};
const base = {
  numero: "261030-0001", fecha: new Date(),
  cliente: { nombre: "Bazar El Sol de Juan Pérez", documento: "20-12345678-9", direccion: "Av. Rivadavia 1234", localidad: "Lanús, Buenos Aires",
    telefono: "+54 9 11 6816-9442", email: "juan@ejemplo.com", negocio: "Bazar a la calle" },
};
const items1 = [
  { codigo: "0730", nombre: "Gazebo Plegable 3X3 Mts. Lona-Hierro", cantidad: 2, precio: 115579, foto: await foto("0730") },
  { codigo: "0579", nombre: "Silla Plegable Aluminio Sannet Azul Oscuro", cantidad: 6, precio: 31587, foto: await foto("0579") },
  { codigo: "9735", nombre: "Conservadora Soprano 12 Lts Azul", cantidad: 6, precio: 15738, foto: await foto("9735") },
  { codigo: "8847", nombre: "Cafetera Hudson Francesa Blanca 600Ml", cantidad: 6, precio: 20182, foto: await foto("8847") },
  { codigo: "9135", nombre: "Bifera Hudson Harmony 26Cm", cantidad: 4, precio: 35599, foto: await foto("9135") },
];
await Deno.writeFile("out/presupuesto_mayorista.pdf", remitoPDF({ ...base, zona: "GBA", pago: "Efectivo al recibir (seña 10% por transferencia)", items: items1 }));
await Deno.writeFile("out/presupuesto_menor_con_iva.pdf", remitoPDF({ ...base, numero: "261030-0002", zona: "GBA", pago: "Transferencia anticipada del total", conIva: true, items: items1.slice(2, 4) }));
console.log("ok");
