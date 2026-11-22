"""Exercise the simulation tasks, films, archives and mobile layout in Chromium."""
from pathlib import Path
from playwright.sync_api import expect, sync_playwright

ROOT = Path(__file__).resolve().parent
MEDIA = ROOT / "media"


def main():
    with sync_playwright() as pw:
        browser = pw.chromium.launch(args=["--enable-unsafe-swiftshader"])
        page = browser.new_page(viewport={"width":1440,"height":900}, reduced_motion="reduce")
        errors = []
        page.on("pageerror", lambda exc: errors.append(str(exc)))
        page.goto("http://127.0.0.1:8766/")
        page.wait_for_load_state("networkidle")
        def ready():
            expect(page.locator("#play")).to_be_enabled(timeout=60000)
        def task(key):
            page.locator(f'[data-task="{key}"]').click()
            ready()
        def seek(value):
            page.locator("#scrub").fill(str(value))
        def settings(opened):
            details=page.locator("#settings")
            if details.evaluate("el=>el.open")!=opened:
                details.locator("summary").click()
        def film(name):
            page.locator("#watch").click()
            page.wait_for_function("document.getElementById('video').readyState>=2")
            assert page.locator("video").evaluate("v=>v.currentSrc").endswith(name)
            assert page.locator("video").evaluate("v=>v.duration")>3
            page.locator("#closeFilm").click()
        ready()
        expect(page.locator("#sceneTitle")).to_have_text("Two-peg relay")
        settings(True)
        expect(page.locator("#paths")).to_be_checked()
        film("relay.mp4")
        task("transfer")
        seek(1000)
        expect(page.locator("#outcome")).to_have_text("Rail cleared and nut seated")
        film("transfer.mp4")
        task("puck")
        settings(False)
        expect(page.locator("#settings")).not_to_have_attribute("open","")
        expect(page.locator("#outcome")).to_contain_text("Ready")
        seek(500)
        page.locator("#scrub").blur()
        page.wait_for_timeout(180)
        page.screenshot(path=str(MEDIA/"simulator.png"))
        seek(1000)
        expect(page.locator("#outcome")).to_have_text("On target · 4.6 mm from center")
        page.locator("#controller").select_option("direct")
        seek(1000)
        expect(page.locator("#outcome")).to_have_text("Outside target · 12.5 mm from center")
        page.locator("#play").click()
        expect(page.locator("#play")).to_have_text("Pause")
        page.locator("#play").click()
        settings(True)
        film("puck.mp4")
        page.locator("#camera").select_option("top")
        page.locator("#resetView").click()
        page.locator("#distance").fill("77")
        with page.expect_response(lambda r:"/api/run?" in r.url and "distance=77" in r.url) as response:
            page.locator("#run").click()
        assert response.value.ok
        ready()
        with page.expect_response(lambda r:"/api/run?" in r.url) as response:
            page.locator("#new").click()
        assert response.value.json()["seed"]!=2402
        ready()
        task("shelf")
        page.locator("#closest").click()
        expect(page.locator(".surface-note span")).to_contain_text("0.75 mm")
        page.locator("#section").uncheck()
        page.locator("#paths").check()
        page.locator("#camera").select_option("mouth")
        film("shelf.mp4")
        for i,learned,fixed in [("1","Inspection complete","Contact"),("2","Contact","Inspection complete")]:
            page.locator("#examples").select_option(i)
            ready()
            seek(1000)
            expect(page.locator("#outcome")).to_have_text(learned)
            page.locator("#controller").select_option("fixed")
            seek(1000)
            expect(page.locator("#outcome")).to_have_text(fixed)
        page.locator("#width").fill("90")
        page.locator("#depth").fill("83")
        page.locator("#run").click()
        ready()
        task("reach")
        seek(1000)
        expect(page.locator("#outcome")).to_have_text("Target reached")
        page.locator("#controller").select_option("direct")
        seek(1000)
        expect(page.locator("#outcome")).to_have_text("Contact")
        film("demo.mp4")
        for idx in ["1","2"]:
            page.locator("#family").select_option(idx)
            ready()
        page.locator("#offset").fill("3")
        page.locator("#run").click()
        ready()
        page.locator('#logTab').click()
        expect(page.locator("#research")).to_be_visible()
        expect(page.get_by_text("45 / 64",exact=True)).to_be_visible()
        expect(page.get_by_text("74 / 96",exact=True).first).to_be_visible()
        page.locator("#findings summary").last.click()
        expect(page.get_by_text("723 / 800",exact=True)).to_be_visible()
        page.locator("#workTab").click()
        task("puck")
        settings(False)
        page.set_viewport_size({"width":390,"height":844})
        seek(700)
        page.locator("#scrub").blur()
        page.wait_for_timeout(200)
        assert page.evaluate("document.documentElement.scrollWidth<=innerWidth")
        page.screenshot(path=str(MEDIA/"simulator-mobile.png"),full_page=True)
        settings(True)
        assert page.evaluate("document.documentElement.scrollWidth<=innerWidth")
        page.goto("http://127.0.0.1:8766/?study=shelf")
        ready()
        expect(page.locator("#sceneTitle")).to_have_text("Shelf inspection")
        assert not errors,errors
        browser.close()
        print("Passed physics replays, live outcomes, all tasks and films, previous deep link, archived results and mobile layout.")


if __name__=="__main__":
    main()
