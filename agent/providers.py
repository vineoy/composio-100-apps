"""Free providers: Gemini LLM (rate-limit aware, model fallback), DuckDuckGo search,
docs fetching, and Composio toolkit-catalog matching (via cached SDK fetch)."""
import os, re, json, time, pathlib
import httpx
from bs4 import BeautifulSoup
from dotenv import load_dotenv

load_dotenv()
ROOT = pathlib.Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
EVIDENCE = DATA / "evidence"

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"}

# ---------------- Gemini ----------------
from google import genai
from google.genai import types

_client = None
def gemini_client():
    global _client
    if _client is None:
        _client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    return _client

MODEL_CHAIN = ["gemini-3.5-flash", "gemini-3.6-flash", "gemini-3.1-flash-lite"]
_last_call = 0.0
MIN_GAP = 6.5  # ~9 requests/min, under the free-tier 10 RPM ceiling
usage = {"calls": 0, "by_model": {}}

def llm_json(prompt, model=None, max_retries=3):
    """Call Gemini expecting JSON. Paces requests, backs off on 429, falls back across models."""
    global _last_call
    models = [model] if model else MODEL_CHAIN
    last_err = None
    for m in models:
        for attempt in range(max_retries):
            wait = MIN_GAP - (time.time() - _last_call)
            if wait > 0:
                time.sleep(wait)
            _last_call = time.time()
            try:
                r = gemini_client().models.generate_content(
                    model=m, contents=prompt,
                    config=types.GenerateContentConfig(
                        response_mime_type="application/json", temperature=0.1))
                txt = (r.text or "").strip()
                if txt.startswith("```"):
                    txt = re.sub(r"^```(?:json)?\s*", "", txt)
                    txt = re.sub(r"\s*```$", "", txt)
                out = json.loads(txt)
                usage["calls"] += 1
                usage["by_model"][m] = usage["by_model"].get(m, 0) + 1
                return out, m
            except json.JSONDecodeError as e:
                last_err = f"bad json: {e}"
                continue
            except Exception as e:
                last_err = str(e)[:400]
                s = str(e)
                if "429" in s or "RESOURCE_EXHAUSTED" in s or "quota" in s.lower():
                    if "per day" in s.lower() or "daily" in s.lower():
                        break  # daily quota gone -> next model immediately
                    m2 = re.search(r"retry in (\d+(?:\.\d+)?)", s)
                    delay = float(m2.group(1)) + 2 if m2 else 30
                    time.sleep(min(delay, 90))
                    continue
                if "404" in s or "not found" in s.lower() or "not supported" in s.lower():
                    break  # model unavailable -> next model
                time.sleep(5)
    raise RuntimeError(f"LLM failed after retries: {last_err}")

# ---------------- DuckDuckGo search ----------------
from ddgs import DDGS
_last_search = 0.0

def search(query, max_results=5):
    global _last_search
    for attempt in range(4):
        gap = 1.2 - (time.time() - _last_search)
        if gap > 0:
            time.sleep(gap)
        _last_search = time.time()
        try:
            r = DDGS().text(query, max_results=max_results) or []
            if r:
                return r
        except Exception as e:
            s = str(e).lower()
            if "ratelimit" in s or "rate limit" in s or "202" in s:
                time.sleep(15 * (attempt + 1))
            else:
                time.sleep(3)
    return _bing(query, max_results)  # free fallback when ddgs is exhausted


def _bing(query, max_results):
    try:
        r = httpx.get("https://www.bing.com/search", params={"q": query, "count": max_results},
                      headers=UA, timeout=15, follow_redirects=True)
        soup = BeautifulSoup(r.text, "html.parser")
        out = []
        for li in soup.select("li.b_algo")[:max_results]:
            a = li.find("a", href=True)
            if a and a["href"].startswith("http"):
                out.append({"title": a.get_text(" ", strip=True), "href": a["href"]})
        return out
    except Exception:
        return []

# ---------------- Docs fetching ----------------
def fetch(url, timeout=12):
    try:
        r = httpx.get(url, follow_redirects=True, timeout=timeout, headers=UA)
        if r.status_code != 200:
            return None
        soup = BeautifulSoup(r.text, "html.parser")
        for tag in soup(["script", "style", "nav", "footer", "header", "noscript", "svg", "iframe"]):
            tag.decompose()
        text = soup.get_text("\n", strip=True)
        text = re.sub(r"\n{3,}", "\n\n", text)
        return {"url": str(r.url), "status": r.status_code, "text": text}
    except Exception:
        return None


def fetch_jina(url, timeout=45):
    """Free JS-rendering reader proxy (no key) for client-side-rendered doc sites."""
    try:
        r = httpx.get("https://r.jina.ai/" + url, timeout=timeout,
                      headers={**UA, "Accept": "text/plain"})
        if r.status_code == 200 and len(r.text) > 300:
            return {"url": url, "status": 200, "text": r.text, "via": "jina-reader"}
    except Exception:
        pass
    return None

def slugify(name):
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")

# ---------------- Composio catalog matching ----------------
_catalog = None
ALIASES = {
    "lark (larksuite)": ["lark"], "monday.com": ["monday"], "whatsapp business": ["whatsapp"],
    "zoho crm": ["zoho_crm", "zoho"], "zoho cliq": ["zoho_cliq"],
    "amazon selling partner": ["amazon_selling_partner", "amazon"],
    "magento (adobe commerce)": ["magento", "adobe_commerce"],
    "salesforce commerce cloud": ["salesforce_commerce_cloud", "salesforce_commerce"],
    "youtube transcript": ["youtube_transcript"], "mermaid cli": ["mermaid_chart_mcp", "mermaid"],
    "notebooklm": ["notebook_lm"], "threads (meta)": ["threads"], "meta ads": ["metaads", "facebook_ads"],
    "google ads": ["google_ads", "googleads"], "linkedin ads": ["linkedin_ads"],
    "gohighlevel": ["highlevel_agency", "highlevel_location", "highlevel"],
    "systeme.io": ["systeme"], "waterfall.io": ["waterfall"], "mongodb atlas": ["mongodb_atlas", "mongodb"],
    "help scout": ["helpscout"], "otter ai": ["otter_ai_mcp", "otter"], "devin": ["devin_mcp", "devin"],
    "pylon": ["pylon_mcp", "pylon"], "bright data": ["brightdata"], "se ranking": ["seranking"],
    "paygent connect": ["paygent"], "quickbooks": ["quickbooks"], "twenty": ["twenty"],
}

def composio_match(name):
    """Does Composio already ship a toolkit for this app? Uses the catalog fetched via Composio SDK."""
    global _catalog
    if _catalog is None:
        p = DATA / "composio_toolkits.json"
        _catalog = json.loads(p.read_text(encoding="utf-8")) if p.exists() else []
    by_slug = {t["slug"]: t for t in _catalog}
    for slug in ALIASES.get(name.lower(), []):
        if slug in by_slug:
            t = by_slug[slug]
            return {"exists": True, "slug": t["slug"], "name": t["name"]}
    norm = re.sub(r"[^a-z0-9]", "", name.lower())
    for t in _catalog:
        slug = re.sub(r"[^a-z0-9]", "", t["slug"].lower())
        tname = re.sub(r"[^a-z0-9]", "", t["name"].lower())
        if norm and norm in (slug, tname, slug + "mcp", slug + "api"):
            return {"exists": True, "slug": t["slug"], "name": t["name"]}
    if len(norm) >= 5:  # conservative fuzzy only for longer names
        for t in _catalog:
            slug = re.sub(r"[^a-z0-9]", "", t["slug"].lower())
            if slug.startswith(norm) or norm.startswith(slug) and len(slug) >= 5:
                return {"exists": True, "slug": t["slug"], "name": t["name"], "fuzzy": True}
    return {"exists": False, "slug": None}
