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

const env = (k: string, d = "") => Deno.env.get(k) ?? d;
const WHAPI = "https://gate.whapi.cloud";
const PRODUCTOS_URL = "https://raw.githubusercontent.com/negobazar/negobazar-canal/bot-datos/productos.json";
const kv = await Deno.openKv();

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
    `${p.s > 0 ? "con stock" : "SIN STOCK"}${p.mul > 1 ? ` | se vende de a ${p.mul}` : ""}${p.min > 1 ? ` | mínimo ${p.min} u.` : ""}` +
    `${p.et ? " | " + p.et : ""} | link: https://www.negobazar.com.ar/search/?q=${encodeURIComponent(p.c)}`
  ).join("\n");
}

const SISTEMA = `Sos el asistente de WhatsApp de NEGOBAZAR, mayorista de bazar, cocina, hogar, limpieza, textil y camping (Parque Avellaneda, CABA).
Atendés a comerciantes, revendedores y emprendedores. Hablás en español rioplatense (vos, tenés, mirá), cálido, cortito y claro, como un vendedor amable por WhatsApp.
Reglas:
- Respuestas breves: 1 a 5 líneas. Usá *negrita* de WhatsApp para lo importante y como mucho 1 o 2 emojis.
- Respondé SOLO con la información de abajo y con los productos que te paso. Si no sabés algo (stock exacto, fechas de entrega puntuales, descuentos, cosas que no figuran), decí que lo confirma una persona del equipo y agregá la etiqueta [DERIVAR].
- Nunca inventes productos, precios, descuentos ni promociones. Los precios son SIN IVA y se confirman al tomar el pedido.
- Si preguntan por un producto, mostrá hasta 4 opciones con nombre, código, precio y link. Si está sin stock, decilo y ofrecé alternativas.
- Recordá el mínimo de compra ($750.000, combinando rubros) cuando sea útil, sin repetirlo en cada mensaje.
- Si el cliente quiere cerrar el pedido, pagar, coordinar un envío puntual, tiene un reclamo, pide hablar con una persona o está enojado: respondé amable que ya le avisás al equipo y agregá [DERIVAR] al final.
- Si alguien quiere comprar MENOS de $750.000: decile que se puede, pero con un recargo del 20% sobre el precio mayorista, y explicale el motivo (no romper la cadena de venta de nuestros revendedores). Si cotizás productos para esa compra, mostrá el precio ya con el 20% (precio x 1,20, redondeado) y aclará que el pago es solo con transferencia previa del total. Antes, contale que si llega a $750.000 combinando rubros accede al precio mayorista normal.
- Pagos: preguntá de dónde es el cliente cuando haga falta. CABA/GBA: efectivo al recibir, reservando con transferencia del 10%. Interior: transferencia previa del total.
- Si un cliente del interior parece GRANDE (varios locales, distribuidora, mucho volumen, pedidos de varios millones), invitalo a venir a conocer el depósito en su primera compra y agregá [DERIVAR] para que el equipo coordine la visita. No des dirección ni horarios: eso lo coordina el equipo.
- No hables de otros temas que no sean Negobazar.

INFORMACIÓN DE NEGOBAZAR:
${CONOCIMIENTO}`;

async function gemini(historial: { role: string; text: string }[], contexto: string): Promise<string> {
  const modelo = env("GEMINI_MODEL", "gemini-2.5-flash");
  const contents = historial.map((h) => ({ role: h.role === "bot" ? "model" : "user", parts: [{ text: h.text }] }));
  contents[contents.length - 1].parts[0].text += `\n\n[Productos del catálogo relacionados con este mensaje — usalos solo si sirven]\n${contexto}`;
  const r = await fetch(`https://generativelanguage.googleapis.com/v1beta/models/${modelo}:generateContent?key=${env("GEMINI_API_KEY")}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      system_instruction: { parts: [{ text: SISTEMA }] },
      contents,
      generationConfig: { temperature: 0.4, maxOutputTokens: 700 },
    }),
  });
  const j = await r.json();
  const txt = j?.candidates?.[0]?.content?.parts?.map((p: { text?: string }) => p.text ?? "").join("") ?? "";
  if (!txt) console.log("gemini sin respuesta", JSON.stringify(j).slice(0, 500));
  return txt.trim() || "¡Gracias por escribir a Negobazar! En un ratito te responde alguien del equipo 🙌 [DERIVAR]";
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

async function responder(chat: string, texto: string, nombre: string): Promise<string> {
  const clave = ["hist", chat];
  const prev = ((await kv.get<{ role: string; text: string }[]>(clave)).value ?? []).slice(-10);
  const hist = [...prev, { role: "user", text: texto }];
  const ultimosUser = hist.filter((h) => h.role === "user").slice(-2).map((h) => h.text).join(" ");
  const ctx = fichas(buscar(await productos(), ultimosUser));
  let resp = await gemini(hist, (nombre ? `(El cliente se llama ${nombre})\n` : "") + ctx);
  const derivar = resp.includes("[DERIVAR]");
  resp = resp.replaceAll("[DERIVAR]", "").trim();
  await kv.set(clave, [...hist, { role: "bot", text: resp }].slice(-12), { expireIn: 7 * 86400000 });
  if (derivar) {
    await kv.set(["pausa", chat], 1, { expireIn: Number(env("PAUSA_HORAS", "12")) * 3600000 });
    const aviso = env("AVISO_CHAT");
    if (aviso) {
      await enviar(aviso, `🔔 *Cliente para atender*\n${nombre || ""} wa.me/${chat.split("@")[0]}\nÚltimo mensaje: "${texto.slice(0, 300)}"`);
    }
  }
  return resp;
}

async function webhook(req: Request): Promise<Response> {
  const body = await req.json().catch(() => ({}));
  for (const m of body?.messages ?? []) {
    const chat: string = m.chat_id ?? "";
    if (!chat.endsWith("@s.whatsapp.net")) continue; // ni grupos, ni canales, ni estados
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
    if ((await kv.get(["pausa", chat])).value) continue;
    const texto: string = m.text?.body ?? m.image?.caption ?? m.video?.caption ?? "";
    if (!texto) {
      if (m.type === "audio" || m.type === "voice") await enviar(chat, "¡Hola! Por ahora no puedo escuchar audios 🙈 ¿Me lo escribís así te respondo al toque?");
      continue;
    }
    const resp = await responder(chat, texto, m.from_name ?? "");
    await enviar(chat, resp);
  }
  return new Response("ok");
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
  if (url.pathname === "/") return new Response(`Bot Negobazar OK · ${(await productos()).length} productos`);
  return new Response("not found", { status: 404 });
});
