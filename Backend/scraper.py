import httpx
from bs4 import BeautifulSoup
from dataclasses import dataclass
import asyncio
from urllib.parse import urlparse


@dataclass
class ScrapedPage:
    url: str
    title: str
    text: str
    links: list[dict]
    success: bool
    need_js: bool = False


async def scrape(url, client: httpx.AsyncClient):
    try:
        resp = await client.get(url, follow_redirects=True, timeout=10)
        if resp.status_code == 403 or len(resp.content) < 500:
            return ScrapedPage(url=url, title="", text="", links=[], success=False, need_js=True)

        soup = BeautifulSoup(resp.text, "html.parser")

        for tag in soup(["script", "style", "nav", "footer", "header"]):
            tag.decompose()

        links = []
        for a in soup.find_all("a", href=True):
            href = a["href"]
            text = a.get_text(strip=True)
            if text and len(text)>3:
                links.append({"text": text, "href": href})
        
        return ScrapedPage(
            url=url, 
            title=soup.title.string.strip() if soup.title else "",
            text = soup.get_text(separator="\n", strip=True)[:8000],
            links = links[:50],
            success = True 
        )
    
    except Exception as e:
        return ScrapedPage(url=url, title="", text = str(e), links = [], success=False, need_js=False)



async def scrape_multiple(urls):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                       "AppleWebKit/537.36 (KHTML, like Gecko) "
                       "Chrome/120.0.0.0 Safari/537.36"
    }

    async with httpx.AsyncClient(headers=headers) as client:
        tasks = [scrape(url, client) for url in urls]
        return await asyncio.gather(*tasks)

    
async def scrape_with_follow(urls, max_follows):
    pages = await scrape_multiple(urls)

    follow_urls = []
    for page in pages:
        if not page.success:
            continue
        for link in page.links:
            href = link["href"]
            text = link["text"].lower()
            if any(kw in text for kw in ["team", "people", "author", "speaker", "engineer", "staff", "about us", "our team", "leadership"]):
                if href.startswith("/"):
                    parsed = urlparse(page.url)
                    href = f"{parsed.scheme}://{parsed.netloc}{href}"
                if href.startswith("http"):
                    follow_urls.append(href)

    follow_urls = list(dict.fromkeys(follow_urls))[:max_follows]

    if follow_urls:
        print(f"=== FOLLOWING {len(follow_urls)} links ===")
        for u in follow_urls:
            print(f"-> {u}")
        followed_pages = await scrape_multiple(follow_urls)
        pages.extend(followed_pages)

    return pages
