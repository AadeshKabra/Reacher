from scraper import scrape_multiple, scrape_with_follow
from planner import generate_plan, synthesize_results, COMPANY_PLANNER_PROMPT, COMPANY_SYNTHESIZER_PROMPT
from browser_use import Browser
from browser_use.agent.service import Agent
from browser_use.browser.browser import BrowserConfig


async def find_leads(query, llm, resume_text="", resume_profile=None):
    plan = await generate_plan(query, profile=resume_profile)
    urls = [step["url"] for step in plan]

    # pages = await scrape_multiple(urls)
    pages = await scrape_with_follow(urls, max_follows=4)

    await _render_js_pages(pages, llm, "extract all people names, titles and contact information")

    return await synthesize_results(query, pages, resume_text)


async def _render_js_pages(pages, llm, instruction):
    for page in pages:
        if not page.need_js:
            continue
        agent = Agent(llm=llm, task=f"Go to {page.url} and {instruction}", browser=browser, max_actions_per_step=3, max_input_tokens=16000)
        result = await agent.run()
        page.text = result.final_result() or ""
        page.success = True


async def find_companies(query, llm, resume_text="", resume_profile=None):
    plan = await generate_plan(query, COMPANY_PLANNER_PROMPT, profile=resume_profile)
    urls = [step["url"] for step in plan]

    pages = await scrape_multiple(urls)
    await _render_js_pages(pages, llm, "extract all company names, titles and contact information")

    return await synthesize_results(query, pages, resume_text, COMPANY_SYNTHESIZER_PROMPT)


browser = Browser(config=BrowserConfig(headless=True))

