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
_client_beta = None

def gemini_client():
    global _client
    if _client is None:
        _client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    return _client

def gemini_beta_client():
    global _client_beta
    if _client_beta is None:
        _client_beta = genai.Client(api_key=os.environ["GEMINI_API_KEY"],
                                    http_options={"api_version": "v1beta"})
    return _client_beta

def _client_for(model):
    return gemini_beta_client() if (model or "").startswith("gemini-2.5") else gemini_client()

MODEL_CHAIN = ["gemini-3.5-flash-lite"]  # only model with working free quota today (others 20 RPD/503)
_last_call = 0.0
MIN_GAP = 4.2  # ~14 req/min; flash-lite allows 15 RPM, 429 backs off
usage = {"calls": 0, "by_model": {}}

def llm_json(prompt, model=None, max_retries=4, fallback=True):
    """Call Gemini expecting JSON. Paces requests, backs off on 429, falls back across models."""
    global _last_call
    models = ([model] + [m for m in MODEL_CHAIN if m != model]) if model else MODEL_CHAIN
    last_err = None
    for m in models:
        for attempt in range(max_retries):
            wait = MIN_GAP - (time.time() - _last_call)
            if wait > 0:
                time.sleep(wait)
            _last_call = time.time()
            try:
                r = _client_for(m).models.generate_content(
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
                if "503" in s or "UNAVAILABLE" in s or "high demand" in s.lower():
                    # transient demand spike: retry the same model, don't burn the fallback chain
                    time.sleep(6 * (attempt + 1))
                    continue
                time.sleep(5)
    if fallback:
        try:
            return pollinations_json(prompt)
        except Exception as e:
            raise RuntimeError(f"LLM failed after retries: {last_err}; fallback: {e}")
    raise RuntimeError(f"LLM failed after retries: {last_err}")


# ---------------- Free fallback LLM: Pollinations (no API key, 1 req / 45 s per IP) ----------------
_last_poll = 0.0
POLL_MODEL = "openai"  # gpt-oss-20b


def pollinations_json(prompt):
    """Last-resort free LLM when Gemini is unavailable. Returns (dict, model_name)."""
    global _last_poll
    last_err = None
    for attempt in range(3):
        wait = 46 - (time.time() - _last_poll)
        if wait > 0:
            time.sleep(wait)
        _last_poll = time.time()
        try:
            r = httpx.post(
                "https://text.pollinations.ai/openai",
                json={"model": POLL_MODEL, "temperature": 0.1,
                      "messages": [{"role": "user", "content": prompt}]},
                timeout=180,
            )
            if r.status_code == 402:
                m = re.search(r"Retry after (\d+)s", r.text)
                last_err = "rate limited"
                time.sleep(float(m.group(1)) + 2 if m else 45)
                continue
            r.raise_for_status()
            txt = (r.json()["choices"][0]["message"].get("content") or "").strip()
            if txt.startswith("```"):
                txt = re.sub(r"^```(?:json)?\s*", "", txt)
                txt = re.sub(r"\s*```$", "", txt)
            return json.loads(txt), f"pollinations/{POLL_MODEL}"
        except Exception as e:
            last_err = str(e)[:200]
            time.sleep(8)
    raise RuntimeError(f"fallback LLM failed: {last_err}")


# ---------------- DuckDuckGo search ----------------
from ddgs import DDGS
from urllib.parse import urlparse, parse_qs
import base64
_last_search = 0.0

def _ddg_lite(query, max_results):
    """Fast HTML endpoint (no JS). Reliable when the ddgs package gets rate-limited."""
    try:
        r = httpx.post("https://lite.duckduckgo.com/lite/", data={"q": query},
                       headers=UA, timeout=12, follow_redirects=True)
        soup = BeautifulSoup(r.text, "html.parser")
        out = []
        for a in soup.select("a.result-link"):
            href = a.get("href", "")
            if href.startswith("http"):
                out.append({"title": a.get_text(" ", strip=True), "href": href})
            if len(out) >= max_results:
                break
        return out
    except Exception:
        return []

def _decode_bing(u):
    if "bing.com/ck/a" not in u:
        return u
    try:
        v = (parse_qs(urlparse(u).query).get("u") or [""])[0]
        if v.startswith("a1"):
            b = v[2:] + "=" * (-len(v[2:]) % 4)
            return base64.urlsafe_b64decode(b).decode("utf-8", "ignore")
    except Exception:
        pass
    return u

def search(query, max_results=5):
    global _last_search
    r = _ddg_lite(query, max_results)
    if r:
        return r[:max_results]
    # fallback 1: ddgs package (client rotates backends internally)
    for attempt in range(2):
        try:
            r = DDGS().text(query, max_results=max_results) or []
            if r:
                return r
        except Exception:
            time.sleep(4)
    # fallback 2: bing html with redirect decode
    return _bing(query, max_results)


def _bing(query, max_results):
    try:
        r = httpx.get("https://www.bing.com/search", params={"q": query, "count": max_results},
                      headers=UA, timeout=12, follow_redirects=True)
        soup = BeautifulSoup(r.text, "html.parser")
        out = []
        for li in soup.select("li.b_algo")[:max_results]:
            a = li.find("a", href=True)
            if a and a["href"].startswith("http"):
                out.append({"title": a.get_text(" ", strip=True), "href": _decode_bing(a["href"])})
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


def fetch_jina(url, timeout=18):
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
