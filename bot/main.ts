// Bot de WhatsApp de Negobazar (11 2537-1053) — Whapi.Cloud + Gemini + Deno Deploy.
//
// Variables de entorno (se cargan en Deno Deploy, nunca en el codigo):
//   WHAPI_TOKEN      token de Whapi (el mismo del canal)
//   GEMINI_API_KEY   clave de Google AI Studio
//   GEMINI_MODEL     opcional (por defecto gemini-2.5-flash)
//   MODO             "prueba" (solo responde a PERMITIDOS) o "activo"
//   PERMITIDOS       numeros que el bot atiende en modo prueba, separados por coma (ej: 5491112345678)
//   AVISO_CHAT       numero al que avisa cuando un cliente quiere cerrar pedido o pide una persona (opcional)
//   CLAVE_ADMIN      clave para usar /probar desde el navegador
//   PAUSA_HORAS      horas que el bot se calla en un chat cuando contesta una persona (por defecto 12)

import { CONOCIMIENTO } from "./conocimiento.ts";
import { remitoPDF, calcular, type DatosRemito } from "./remito.ts";

const env = (k: string, d = "") => Deno.env.get(k) ?? d;
const WHAPI = "https://gate.whapi.cloud";
const PRODUCTOS_URL = "https://raw.githubusercontent.com/negobazar/negobazar-canal/bot-datos/productos.json";
const kv = await Deno.openKv();

// Limpieza unica: saca las pausas que quedaron por la falla de la IA del 30/10.
if (!(await kv.get(["limpieza", "pausas-2026-10-30"])).value) {
  for await (const x of kv.list({ prefix: ["pausa"] })) await kv.delete(x.key);
  for await (const x of kv.list({ prefix: ["hist"] })) await kv.delete(x.key);
  await kv.set(["limpieza", "pausas-2026-10-30"], 1);
}

type Prod = { c: string; n: string; m: string; p: number; s: number; min: number; mul: number; cat: string; sub: string; et: string; img: string };
let cache: { t: number; data: Prod[] } = { t: 0, data: [] };

async function productos(): Promise<Prod[]> {
  if (Date.now() - cache.t < 60 * 60 * 1000 && cache.data.length) return cache.data;
  try {
    const r = await fetch(PRODUCTOS_URL);
    if (r.ok) cache = { t: Date.now(), data: await r.json() };
  } catch (_) { /* se queda con lo que tenia */ }
  return cache.data;
}

const norm = (s: string) => s.toLowerCase().normalize("NFD").replace(/[̀-ͯ]/g, "").replace(/[^a-z0-9 ]/g, " ");
const VACIAS = new Set("de la el los las un una y o para con sin por que en a mi me te tenes tienen hay tenés busco quiero precio cuanto sale vale x".split(" "));
const pesos = (n: number) => "$" + n.toLocaleString("es-AR");

function buscar(lista: Prod[], texto: string, max = 8): Prod[] {
  const toks = norm(texto).split(/\s+/).filter((t) => t.length > 2 && !VACIAS.has(t));
  if (!toks.length) return [];
  const raiz = (t: string) => t.replace(/(es|s)$/, "");
  const out: [number, Prod][] = [];
  for (const p of lista) {
    const hay = norm(`${p.n} ${p.m} ${p.cat} ${p.sub} ${p.c}`);
    let sc = 0;
    for (const t of toks) {
      if (p.c === t) sc += 10;
      else if (hay.includes(" " + raiz(t)) || hay.startsWith(raiz(t))) sc += norm(p.n).includes(raiz(t)) ? 3 : 1;
    }
    if (sc > 0) out.push([sc + (p.s > 0 ? 1 : 0), p]);
  }
  return out.sort((a, b) => b[0] - a[0]).slice(0, max).map((x) => x[1]);
}

function fichas(ps: Prod[]): string {
  if (!ps.length) return "(No se encontraron productos relacionados con la consulta en el catálogo.)";
  return ps.map((p) =>
    `- Cód. ${p.c} | ${p.n}${p.m ? " | Marca " + p.m : ""} | ${pesos(p.p)} c/u (sin IVA) | ` +
    `${p.s > 0 ? `stock: ${p.s} unidades` : "SIN STOCK"}${p.mul > 1 ? ` | se vende de a ${p.mul}` : ""}${p.min > 1 ? ` | mínimo ${p.min} u.` : ""}` +
    `${p.et ? " | " + p.et : ""} | link: https://www.negobazar.com.ar/search/?q=${encodeURIComponent(p.c)}`
  ).join("\n");
}

const SISTEMA = `Sos el asistente de WhatsApp de NEGOBAZAR, mayorista de bazar, cocina, hogar, limpieza, textil y camping (Parque Avellaneda, CABA).
Atendés a comerciantes, revendedores y emprendedores. Hablás en español rioplatense (vos, tenés, mirá), cálido, cortito y claro, como un vendedor amable por WhatsApp.
Reglas:
- Respuestas breves: 1 a 5 líneas. Usá *negrita* de WhatsApp para lo importante y como mucho 1 o 2 emojis.
- Respondé SOLO con la información de abajo y con los productos que te paso. Si no sabés algo (fechas de entrega puntuales, descuentos especiales, cosas que no figuran), decí que lo confirma una persona del equipo y agregá la etiqueta [DERIVAR].
- Nunca inventes productos, precios, descuentos ni promociones. Los precios son SIN IVA y se confirman al tomar el pedido.
- Si preguntan por un producto, mostrá hasta 4 opciones con nombre, código, precio y link, y aclarale una vez que los precios son *sin IVA*. Si está sin stock, decilo y ofrecé alternativas.
- Recordá el mínimo de compra ($750.000, combinando rubros) cuando sea útil, sin repetirlo en cada mensaje.
- CATÁLOGO: si el cliente pide el catálogo, la lista de precios, "qué productos tienen" en general o "mandame todo", respondé algo corto tipo "¡Te mando nuestro catálogo completo en PDF! 📒 Tiene fotos, códigos y precios mayoristas (sin IVA)." y agregá la etiqueta [CATALOGO] al final. El PDF se manda solo. Después ofrecé ayudarlo a armar el pedido o buscarle algún producto puntual. Si ya se lo mandaste en esta conversación, no lo vuelvas a mandar salvo que lo pida de nuevo.
- CIERRE DE PEDIDO: cuando el cliente quiere hacer o cerrar el pedido:
  1) Confirmá la lista final de productos (código y cantidad), respetando el mínimo y el múltiplo de cada producto.
  2) Pedí los datos que falten, de a uno o dos por mensaje: nombre y apellido o razón social; CUIT o DNI; dirección de entrega con localidad; mail (opcional); forma de pago según su zona. El teléfono ya lo tenemos.
  3) El presupuesto va SIN IVA. Solo si el cliente pide factura o pregunta por el IVA, avisale que se le suma el 21% de IVA y marcá "iva": true.
  4) Cuando tengas todo y el cliente confirme, respondé con un mensaje corto diciendo que le mandás el presupuesto (productos sujetos a stock) y que el equipo lo contacta para confirmar, y agregá AL FINAL, sin mostrarlo de otra forma:
  [PEDIDO]{"items":[{"c":"código","q":cantidad}],"nombre":"","documento":"","direccion":"","localidad":"","zona":"CABA|GBA|INTERIOR","email":"","negocio":"","pago":"","iva":false}[/PEDIDO]
- Si el cliente quiere pagar algo ya presupuestado, coordinar un envío puntual, tiene un reclamo, pide hablar con una persona o está enojado: respondé amable que ya le avisás al equipo y agregá [DERIVAR] al final.
- STOCK: si preguntan por stock, informá la cantidad disponible que figura en el producto. Si no queda claro de qué producto habla, preguntale el nombre o el código antes de responder. No derives por una consulta de stock.
- Si la cantidad que quiere (o el stock disponible) no alcanza para llegar al mínimo de $750.000, ofrecé primero combinar con otros productos; si igual quiere comprar menos, explicale la opción de compra menor con recargo y el costo de envío (ver "COMPRAS MENORES A $750.000").
- Si alguien quiere comprar MENOS de $750.000: decile que se puede, pero con un recargo del 20% sobre el precio mayorista, y explicale el motivo (no romper la cadena de venta de nuestros revendedores). Si cotizás productos para esa compra, mostrá el precio ya con el 20% (precio x 1,20, redondeado) y aclará que el pago es solo con transferencia anticipada del total (el pedido se arma recién cuando se acredita) y que el envío NO es gratis (CABA $10.000; GBA $15.000; resto de la provincia de Buenos Aires y del país por Vía Cargo, flete a cargo del comprador + $10.000 por llevarlo de nuestro depósito a Vía Cargo). Antes, contale que si llega a $750.000 combinando rubros accede al precio mayorista normal.
- Pagos: preguntá de dónde es el cliente cuando haga falta. CABA/GBA: efectivo al recibir, reservando con transferencia del 10%. Interior: transferencia previa del total.
- Si un cliente del interior parece GRANDE (varios locales, distribuidora, mucho volumen, pedidos de varios millones), invitalo a venir a conocer el depósito en su primera compra y agregá [DERIVAR] para que el equipo coordine la visita. No des dirección ni horarios: eso lo coordina el equipo.
- CONOCÉ AL CLIENTE: como un buen vendedor, hacé preguntas para averiguar qué tipo de negocio tiene (local a la calle, bazar, kiosco, revendedor, tienda online, distribuidora, cantidad de locales), de dónde es, qué rubros vende más y cada cuánto compra. UNA pregunta por mensaje, natural, sin que parezca un formulario, y aprovechando lo que ya te contó.
- Si detectás que es un POTENCIAL CLIENTE de volumen (comercio establecido, varios locales, distribuidora, compras frecuentes o grandes), contale que tenemos una ESCALA DE DESCUENTOS: más de $10.000.000 → 5%; más de $20.000.000 → 5% + 3% adicional. No la ofrezcas a quien recién arranca o compra poco; a esos, ayudalos a llegar al mínimo.
- No hables de otros temas que no sean Negobazar.

INFORMACIÓN DE NEGOBAZAR:
${CONOCIMIENTO}`;

// Modelos "Lite": responden en menos de 1 segundo. Si uno esta saturado, se prueba el siguiente.
const MODELOS = (Deno.env.get("GEMINI_MODEL") ?? "gemini-3.5-flash-lite,gemini-3.1-flash-lite,gemini-flash-lite-latest")
  .split(",").map((x) => x.trim()).filter(Boolean);

async function gemini(historial: { role: string; text: string }[], contexto: string): Promise<string> {
  const contents = historial.map((h) => ({ role: h.role === "bot" ? "model" : "user", parts: [{ text: h.text }] }));
  contents[contents.length - 1].parts[0].text += `\n\n[Productos del catálogo relacionados con este mensaje — usalos solo si sirven]\n${contexto}`;
  const llamar = (modelo: string) =>
    fetch(`https://generativelanguage.googleapis.com/v1beta/models/${modelo}:generateContent?key=${env("GEMINI_API_KEY")}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        system_instruction: { parts: [{ text: SISTEMA }] },
        contents,
        generationConfig: { temperature: 0.4, maxOutputTokens: 2048, thinkingConfig: { thinkingLevel: "minimal" } },
      }),
      signal: AbortSignal.timeout(20000),
    }).then((r) => r.json()).catch((e) => ({ error: String(e) }));
  let j: any = {};
  for (const m of MODELOS) {
    j = await llamar(m);
    if (j?.candidates?.length) break;
    console.log("gemini fallo con", m, JSON.stringify(j).slice(0, 300));
  }
  const txt = j?.candidates?.[0]?.content?.parts?.filter((p: { thought?: boolean }) => !p.thought)
    .map((p: { text?: string }) => p.text ?? "").join("") ?? "";
  if (!txt) {
    const err = JSON.stringify(j).replace(env("GEMINI_API_KEY") || "@@", "***").slice(0, 600);
    console.log("gemini sin respuesta", err);
    await kv.set(["ultimo_error"], { cuando: new Date().toISOString(), err }, { expireIn: 7 * 86400000 });
    return "[FALLA_IA]";
  }
  // WhatsApp usa *un* asterisco para negrita
  return txt.replace(/\*\*(.+?)\*\*/g, "*$1*").replace(/\[([^\]]+)\]\((https?:[^)\s]+)\)/g, "$2").trim() ||
    "¡Gracias por escribir a Negobazar! En un ratito te responde alguien del equipo 🙌 [DERIVAR]";
}

async function enviar(to: string, body: string) {
  const r = await fetch(`${WHAPI}/messages/text`, {
    method: "POST",
    headers: { Authorization: `Bearer ${env("WHAPI_TOKEN")}`, "Content-Type": "application/json" },
    body: JSON.stringify({ to, body }),
  });
  const j = await r.json().catch(() => ({}));
  if (j?.message?.id) await kv.set(["enviado", j.message.id], 1, { expireIn: 86400000 });
  return j;
}

const pendientes = new Map<string, Record<string, unknown>>();
const catalogos = new Set<string>();
const CATALOGO_URL = "https://github.com/negobazar/negobazar-canal/releases/download/catalogo/catalogo-negobazar.pdf";

async function enviarCatalogo(chat: string) {
  const r = await fetch(`${WHAPI}/messages/document`, {
    method: "POST", headers: { Authorization: `Bearer ${env("WHAPI_TOKEN")}`, "Content-Type": "application/json" },
    body: JSON.stringify({ to: chat, media: CATALOGO_URL, filename: "Catalogo-Negobazar.pdf", caption: "📒 Catálogo mayorista Negobazar — precios sin IVA, sujetos a stock. Compra mínima $750.000." }),
  });
  const j = await r.json().catch(() => ({}));
  if (j?.message?.id) await kv.set(["enviado", j.message.id], 1, { expireIn: 86400000 });
  return j;
}

async function bajarFoto(url: string): Promise<Uint8Array | undefined> {
  try {
    const r = await fetch(url, { signal: AbortSignal.timeout(8000), headers: { "User-Agent": "Mozilla/5.0" } });
    if (r.ok && (r.headers.get("content-type") ?? "").includes("jpeg")) return new Uint8Array(await r.arrayBuffer());
  } catch (_) { /* sin foto */ }
  return undefined;
}

async function enviarPresupuesto(chat: string, nombreWa: string, ped: Record<string, unknown>) {
  const cat = await productos();
  const items = [];
  for (const it of (ped.items as { c: string; q: number }[] ?? [])) {
    const p = cat.find((x) => x.c === String(it.c).trim());
    if (!p || !(Number(it.q) > 0)) continue;
    items.push({ codigo: p.c, nombre: p.n, cantidad: Math.round(Number(it.q)), precio: p.p, foto: p.img ? await bajarFoto(p.img) : undefined });
  }
  if (!items.length) return;
  const n = ((await kv.get<number>(["contador_presupuesto"])).value ?? 0) + 1;
  await kv.set(["contador_presupuesto"], n);
  const hoy = new Date();
  const numero = `${hoy.toISOString().slice(2, 10).replaceAll("-", "")}-${String(n).padStart(4, "0")}`;
  const zona = String(ped.zona ?? "").toUpperCase();
  const d: DatosRemito = {
    numero, fecha: hoy, zona: (["CABA", "GBA", "INTERIOR"].includes(zona) ? zona : "") as DatosRemito["zona"],
    pago: String(ped.pago ?? ""), conIva: ped.iva === true, items,
    cliente: { nombre: String(ped.nombre || nombreWa || ""), documento: String(ped.documento ?? ""), direccion: String(ped.direccion ?? ""),
      localidad: String(ped.localidad ?? ""), email: String(ped.email ?? ""), negocio: String(ped.negocio ?? ""), telefono: "+" + chat.split("@")[0] },
  };
  const pdf = remitoPDF(d);
  const c = calcular(d);
  let b64 = ""; const CH = 0x8000;
  for (let i = 0; i < pdf.length; i += CH) b64 += String.fromCharCode(...pdf.subarray(i, i + CH));
  const media = "data:application/pdf;base64," + btoa(b64);
  const archivo = `Presupuesto-Negobazar-${numero}.pdf`;
  const mandarDoc = (to: string, caption: string) => fetch(`${WHAPI}/messages/document`, {
    method: "POST", headers: { Authorization: `Bearer ${env("WHAPI_TOKEN")}`, "Content-Type": "application/json" },
    body: JSON.stringify({ to, media, filename: archivo, caption }),
  }).then((r) => r.json()).then(async (j) => { if (j?.message?.id) await kv.set(["enviado", j.message.id], 1, { expireIn: 86400000 }); return j; })
    .catch((e) => console.log("error doc", String(e)));
  await mandarDoc(chat, `📄 Presupuesto N° ${numero} — productos sujetos a stock.\nEn breve te contacta alguien del equipo para confirmar. ¡Gracias!`);
  const aviso = env("AVISO_CHAT");
  if (aviso) await mandarDoc(aviso, `🔔 *Pedido para confirmar* · ${d.cliente.nombre} · wa.me/${chat.split("@")[0]}\nTotal ${"$" + c.total.toLocaleString("es-AR")}${c.menor ? " (compra menor)" : ""}`);
}

async function responder(chat: string, texto: string, nombre: string): Promise<string> {
  const clave = ["hist", chat];
  const prev = ((await kv.get<{ role: string; text: string }[]>(clave)).value ?? []).slice(-10);
  const hist = [...prev, { role: "user", text: texto }];
  const ultimosUser = hist.filter((h) => h.role === "user").slice(-2).map((h) => h.text).join(" ");
  const ctx = fichas(buscar(await productos(), ultimosUser));
  let resp = await gemini(hist, (nombre ? `(El cliente se llama ${nombre})\n` : "") + ctx);
  if (resp === "[FALLA_IA]") {
    // No pausa el chat ni guarda historial: el proximo mensaje se vuelve a intentar.
    return "¡Hola! Gracias por escribir a Negobazar 🙌 En un momento te respondemos.";
  }
  let pedido: Record<string, unknown> | null = null;
  const mp = resp.match(/\[PEDIDO\]([\s\S]*?)\[\/PEDIDO\]/);
  if (mp) {
    try { pedido = JSON.parse(mp[1].trim().replace(/^```json|```$/g, "")); } catch (_) { pedido = null; }
    resp = resp.replace(mp[0], "").trim();
  }
  if (resp.includes("[CATALOGO]")) { catalogos.add(chat); resp = resp.replaceAll("[CATALOGO]", "").trim(); }
  const derivar = resp.includes("[DERIVAR]") || !!pedido;
  resp = resp.replaceAll("[DERIVAR]", "").trim();
  if (pedido) pendientes.set(chat, pedido);
  await kv.set(clave, [...hist, { role: "bot", text: resp }].slice(-12), { expireIn: 7 * 86400000 });
  if (derivar) {
    await kv.set(["pausa", chat], 1, { expireIn: Number(env("PAUSA_HORAS", "12")) * 3600000 });
    const aviso = env("AVISO_CHAT");
    if (aviso && !pedido) {
      await enviar(aviso, `🔔 *Cliente para atender*\n${nombre || ""} wa.me/${chat.split("@")[0]}\nÚltimo mensaje: "${texto.slice(0, 300)}"`);
    }
  }
  return resp;
}

async function webhook(req: Request): Promise<Response> {
  const body = await req.json().catch(() => ({}));
  const log = async (m: Record<string, unknown>, que: string) => {
    const l = ((await kv.get(["log"])).value as unknown[] ?? []);
    l.unshift({ t: new Date().toISOString(), chat: String(m.chat_id ?? "").split("@")[0].slice(-4), from_me: m.from_me, tipo: m.type, que });
    await kv.set(["log"], l.slice(0, 15));
  };
  if (!(body?.messages ?? []).length) await log({ type: Object.keys(body ?? {}).join(",") }, "webhook sin mensajes");
  for (const m of body?.messages ?? []) {
    const chat: string = m.chat_id ?? "";
    await log(m, "recibido");
    if (!chat.endsWith("@s.whatsapp.net")) continue; // ni grupos, ni canales, ni estados
    const cmd = String(m.text?.body ?? "").trim().toLowerCase();
    // "#bot" (desde el celular de Negobazar, dentro del chat) o "#reiniciar" (desde el cliente):
    // el bot vuelve a atender ese chat y arranca la conversación de cero.
    if ((m.from_me && cmd === "#bot") || (!m.from_me && cmd === "#reiniciar")) {
      await kv.delete(["pausa", chat]);
      await kv.delete(["hist", chat]);
      if (!m.from_me) await enviar(chat, "🔄 Listo, empezamos de nuevo. ¿En qué te puedo ayudar?");
      continue;
    }
    if (m.from_me) {
      // Si no lo mandó el bot, es una persona del equipo: el bot se calla en ese chat.
      const fueBot = (await kv.get(["enviado", m.id])).value || m.source === "api";
      if (!fueBot) await kv.set(["pausa", chat], 1, { expireIn: Number(env("PAUSA_HORAS", "12")) * 3600000 });
      continue;
    }
    if ((await kv.get(["visto", m.id])).value) continue;
    await kv.set(["visto", m.id], 1, { expireIn: 86400000 });
    const numero = chat.split("@")[0];
    if (env("MODO", "prueba") !== "activo" && !env("PERMITIDOS").split(",").map((x) => x.trim()).includes(numero)) continue;
    if ((await kv.get(["pausa", chat])).value) { await log(m, "chat en pausa"); continue; }
    const texto: string = m.text?.body ?? m.image?.caption ?? m.video?.caption ?? "";
    if (!texto) {
      if (m.type === "audio" || m.type === "voice") await enviar(chat, "¡Hola! Por ahora no puedo escuchar audios 🙈 ¿Me lo escribís así te respondo al toque?");
      continue;
    }
    try {
      const resp = await responder(chat, texto, m.from_name ?? "");
      const r = await enviar(chat, resp);
      await log(m, "respondido " + JSON.stringify(r ?? "").slice(0, 80));
      if (catalogos.has(chat)) { catalogos.delete(chat); const rc = await enviarCatalogo(chat); await log(m, "catalogo " + JSON.stringify(rc).slice(0, 80)); }
      const ped = pendientes.get(chat);
      if (ped) { pendientes.delete(chat); await enviarPresupuesto(chat, m.from_name ?? "", ped); }
    } catch (e) {
      await log(m, "ERROR " + String(e).slice(0, 200));
    }
  }
  return new Response("ok");
}

// Prueba unica de envio despues de pasar Whapi al plan pago.
if (!(await kv.get(["prueba_envio", "2026-10-30-pago"])).value && env("AVISO_CHAT")) {
  await kv.set(["prueba_envio", "2026-10-30-pago"], { t: new Date().toISOString(), r: "enviando" });
  const r = await enviar(env("AVISO_CHAT"), "✅ Bot de Negobazar activo: Whapi en plan pago, ya puede responder a todos los clientes.").catch((e) => String(e));
  await kv.set(["prueba_envio", "2026-10-30-pago"], { t: new Date().toISOString(), r: JSON.stringify(r).slice(0, 300) });
}

Deno.serve(async (req) => {
  const url = new URL(req.url);
  if (req.method === "POST" && url.pathname === "/webhook") return webhook(req);
  if (url.pathname === "/probar") {
    if (!env("CLAVE_ADMIN") || url.searchParams.get("clave") !== env("CLAVE_ADMIN")) return new Response("no", { status: 403 });
    const chat = "prueba-" + (url.searchParams.get("chat") ?? "1");
    if (url.searchParams.get("reset")) await kv.delete(["hist", chat]);
    const q = url.searchParams.get("q") ?? "";
    const resp = q ? await responder(chat, q, "Prueba") : "";
    return new Response(resp, { headers: { "content-type": "text/plain; charset=utf-8" } });
  }
  if (url.pathname === "/diag") {
    const e = (await kv.get(["ultimo_error"])).value;
    const faltan = ["WHAPI_TOKEN", "GEMINI_API_KEY", "MODO", "AVISO_CHAT"].filter((k) => !env(k));
    return Response.json({ modo: env("MODO", "prueba"), faltan, gemini_key_largo: env("GEMINI_API_KEY").length,
      gemini_key_empieza: env("GEMINI_API_KEY").slice(0, 4), version: "2026-10-30d", ultimo_error: e,
      prueba_envio: (await kv.get(["prueba_envio", "2026-10-30-pago"])).value,
      pausados: (await Array.fromAsync(kv.list({ prefix: ["pausa"] }))).length,
      whapi: await (async () => { try {
        const h = await fetch(`${WHAPI}/health?wakeup=false`, { headers: { Authorization: `Bearer ${env("WHAPI_TOKEN")}` } });
        const j = await h.json(); return { http: h.status, status: j?.status, trial: j?.trial ?? j?.channel?.trial, limits: j?.limits, raw: JSON.stringify(j).slice(0, 400) };
      } catch (e) { return String(e); } })(), log: (await kv.get(["log"])).value });
  }
  if (url.pathname === "/despausar") {
    if (!env("CLAVE_ADMIN") || url.searchParams.get("clave") !== env("CLAVE_ADMIN")) return new Response("no", { status: 403 });
    let n = 0;
    for await (const x of kv.list({ prefix: ["pausa"] })) { await kv.delete(x.key); n++; }
    return new Response(`Listo: ${n} chats despausados`);
  }
  if (url.pathname === "/") return new Response(`Bot Negobazar OK · ${(await productos()).length} productos`);
  return new Response("not found", { status: 404 });
});
