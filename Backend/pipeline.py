from scraper import scrape_multiple, scrape_with_follow
from planner import generate_plan, synthesize_results
from browser_use import Browser
from browser_use.agent.service import Agent
from browser_use.browser.browser import BrowserConfig


async def find_leads(query, llm):
    plan = await generate_plan(query)
    urls = [step["url"] for step in plan]

    # pages = await scrape_multiple(urls)
    pages = await scrape_with_follow(urls, max_follows=4)

    js_pages = [p for p in pages if p.need_js]
    if js_pages:
        for page in js_pages:
            agent = Agent(
                llm=llm,
                task=f"Go to {page.url} and extract all people names, titles and contact information",
                browser=browser,
                max_actions_per_step=3,
                max_input_tokens=16000,
            )
            result = await agent.run()
            page.text = result.final_result() or ""
            page.success = True

    
    return await synthesize_results(query, pages)


browser = Browser(config=BrowserConfig(headless=True))

