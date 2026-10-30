import sys, asyncio, os
from playwright.async_api import async_playwright
URL, FOTO = sys.argv[1], sys.argv[2]
os.makedirs("out", exist_ok=True)
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch()
        pg = await b.new_page(viewport={"width":390,"height":844}, user_agent="Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1")
        await pg.goto(URL, wait_until="networkidle"); await pg.wait_for_timeout(3000)
        await pg.screenshot(path="out/1.png")
        open("out/1.txt","w").write(await pg.inner_text("body"))
        inp = pg.locator("input[type=file]")
        print("inputs", await inp.count())
        await inp.first.set_input_files(FOTO); await pg.wait_for_timeout(4000)
        await pg.screenshot(path="out/2.png"); open("out/2.txt","w").write(await pg.inner_text("body"))
        for t in ["Subir","Usar","Confirmar","Enviar","Upload","Use","Continuar","Listo"]:
            btn = pg.get_by_role("button", name=t)
            if await btn.count():
                print("click", t); await btn.first.click(); await pg.wait_for_timeout(8000); break
        await pg.screenshot(path="out/3.png"); open("out/3.txt","w").write(await pg.inner_text("body"))
        await b.close()
asyncio.run(main())
