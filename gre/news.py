"""The facts behind the news graphics: an article's headline, and the weekly 30-year fixed mortgage rate.

  gre headline <url>                  the headline, outlet and date of an article, read from the page itself
  gre rates [--refresh] [--payment N] the Freddie Mac PMMS weekly average: latest, a week, four weeks and a year ago,
                                      the 52-week high and low (and the monthly payment on a loan of N at each)

Nothing here is ever guessed: a value that is not on the page (or in the data) is reported as missing."""
import gzip, html, json, re, urllib.error, urllib.request, zlib
from datetime import date, timedelta
from urllib.parse import urlparse
from .common import HOME, UserError

# The request goes out from the member's own computer, for a link they gave, the way their own browser would ask for
# the page: one request, with no name of this editor or its makers in it. If the site says no, that is the answer:
# it is never retried under another identity. Claude then asks the member for a screenshot (guide/graphics.md).
BROWSER = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
           "Chrome/130.0.0.0 Safari/537.36")
MONTHS = "Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split()


class CouldNotRead(Exception):
    """The page or the data could not be fetched; the message is the plain-words reason."""


def fetch(url, agent=BROWSER, timeout=10, limit=4_000_000):
    """The text of a web page or file. Raises CouldNotRead with a plain reason."""
    if not re.match(r"https?://[^\s/]+\.[^\s/]+", url or ""):
        raise CouldNotRead("that is not a web address")
    headers = {"User-Agent": agent, "Accept": "text/html,application/xhtml+xml,text/csv;q=0.9,*/*;q=0.8",
               "Accept-Language": "en-US,en;q=0.9"} if agent else {}           # agent=None: a plain request
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=timeout) as r:
            raw = r.read(limit)
            enc = (r.headers.get("Content-Encoding") or "").lower()
            ctype = r.headers.get("Content-Type") or ""
    except urllib.error.HTTPError as e:
        why = {401: "the site wants a login", 402: "the page is behind a paywall", 403: "the site blocked the request",
               404: "the page was not found", 410: "the page is gone", 429: "the site said too many requests",
               451: "the site is not available here"}.get(e.code, "the site answered with an error")
        raise CouldNotRead(f"{why}: {e.code}")
    except TimeoutError:
        raise CouldNotRead(f"the site did not answer in {timeout} seconds")
    except (urllib.error.URLError, OSError, ValueError) as e:
        reason = getattr(e, "reason", e)
        if isinstance(reason, TimeoutError) or "timed out" in str(reason):
            raise CouldNotRead(f"the site did not answer in {timeout} seconds")
        raise CouldNotRead("no internet connection, or the site is down")
    try:
        if "gzip" in enc or raw[:2] == b"\x1f\x8b":
            raw = gzip.decompress(raw)
        elif "deflate" in enc:
            raw = zlib.decompress(raw, -zlib.MAX_WBITS) if raw[:1] != b"\x78" else zlib.decompress(raw)
    except (OSError, EOFError, zlib.error):
        raise CouldNotRead("the page came back in a form this editor cannot open")
    if re.search(r"application/pdf|^image/|^video/|^audio/", ctype, re.I):
        raise CouldNotRead("that link is a file, not an article page")
    m = re.search(r"charset=([\w-]+)", ctype, re.I)
    try:
        return raw.decode(m.group(1) if m else "utf-8", errors="replace")
    except LookupError:
        return raw.decode("utf-8", errors="replace")


# ---------- gre headline ----------

_BLOCKED = re.compile(r"just a moment|access denied|are you a robot|robot or human|attention required|verify you are "
                      r"(a )?human|pardon our interruption|security check|please enable (js|javascript|cookies)|"
                      r"403 forbidden|page not found|^404\b|unusual (activity|traffic)|access to this page has been "
                      r"denied|subscribe to (read|continue)|sign in to (read|continue)|^error$|bot detection", re.I)


def _clean(s):
    s = re.sub(r"<[^>]+>", " ", str(s or ""))
    return re.sub(r"\s+", " ", html.unescape(html.unescape(s)).replace("\u00a0", " ")).strip()


def _metas(text):
    out = {}
    for tag in re.findall(r"<meta\b[^>]*>", text, re.I):
        at = {k.lower(): (a or b or c) for k, a, b, c in
              re.findall(r"([\w:.-]+)\s*=\s*(?:\"([^\"]*)\"|'([^']*)'|([^\s\"'>]+))", tag)}
        key = (at.get("property") or at.get("name") or at.get("itemprop") or "").lower()
        if key and at.get("content") and key not in out:
            out[key] = _clean(at["content"])
    return out


def _articles(text):
    """Every JSON-LD object that describes an article, news articles first, in page order."""
    found = []

    def walk(node):
        if isinstance(node, list):
            for x in node:
                walk(x)
        elif isinstance(node, dict):
            types = node.get("@type")
            types = types if isinstance(types, list) else [types]
            if any(isinstance(t, str) and re.search(r"(Article|BlogPosting)$", t) for t in types):
                found.append(node)
            for v in node.values():
                if isinstance(v, (dict, list)):
                    walk(v)

    for raw in re.findall(r"<script\b[^>]*application/ld\+json[^>]*>(.*?)</script>", text, re.S | re.I):
        try:
            walk(json.loads(raw.strip(), strict=False))
        except ValueError:
            continue
    news = lambda a: any("News" in str(t) for t in (a.get("@type") if isinstance(a.get("@type"), list) else [a.get("@type")]))
    return sorted(found, key=lambda a: not news(a))


def _name(v):
    if isinstance(v, list):
        v = v[0] if v else None
    return _clean(v.get("name") if isinstance(v, dict) else v if isinstance(v, str) else "")


def _site(host):
    return host.split(".")[-2] if host.count(".") else host


def _one_outlet(name, host):
    """'Real Estate News & Insights | realtor.com' -> 'realtor.com': when the page gives its outlet name in several
    parts, the part that names the site (else the first part)."""
    key = lambda s: re.sub(r"[^a-z0-9]", "", s.lower())
    parts = [x.strip() for x in re.split(r"\s+[|\u2013\u2014-]\s+", name) if x.strip()]
    if len(parts) < 2:
        return name
    return next((x for x in parts if key(_site(host)) and key(_site(host)) in key(x)), parts[0])


def _strip_outlet(title, outlet, host):
    """'Headline | Outlet' -> 'Headline'. A part after a pipe always goes; a part after a dash only when it is the
    outlet's own name (a dash can be part of a headline)."""
    key = lambda s: re.sub(r"[^a-z0-9]", "", s.lower())
    names = {key(outlet), key(_site(host))} - {""}
    while True:
        m = re.match(r"^(.{12,}?)\s+([|\u2013\u2014-])\s+([^|\u2013\u2014]{2,60})$", title)
        if not m or not (m.group(2) == "|" or any(n and (n in key(m.group(3)) or key(m.group(3)) in n) for n in names)):
            return title
        title = m.group(1).strip()


def pretty_date(iso):
    """'2026-11-12T09:00:00-05:00' -> 'Nov 12, 2026' (the date as the page states it; '' if it is not a date)."""
    m = re.match(r"\s*(\d{4})-(\d{1,2})-(\d{1,2})", str(iso or ""))
    if not m or not 1 <= int(m.group(2)) <= 12 or not 1 <= int(m.group(3)) <= 31:
        return ""
    return f"{MONTHS[int(m.group(2)) - 1]} {int(m.group(3))}, {m.group(1)}"


def parse_headline(text, url=""):
    """{'headline', 'outlet', 'date', 'from'} read from a page's own markup; a value that is not there is ''.
    Headline: JSON-LD (NewsArticle / Article), then the first <h1>, then og:title without its ' | Outlet' ending.
    Outlet: the JSON-LD publisher, then og:site_name. Date: datePublished, then article:published_time."""
    host = re.sub(r"^www\.", "", urlparse(url).netloc.lower())
    meta, arts = _metas(text), _articles(text)
    outlet = next((n for n in (_name(a.get("publisher")) for a in arts) if n), "") or meta.get("og:site_name", "")
    outlet = _one_outlet(outlet, host)
    when = next((d for d in (pretty_date(a.get("datePublished")) for a in arts) if d), "") or \
        pretty_date(meta.get("article:published_time")) or pretty_date(meta.get("datepublished")) or \
        pretty_date(meta.get("parsely-pub-date"))
    h1s = [t for t in (_clean(x) for x in re.findall(r"<h1\b[^>]*>(.*?)</h1>", text, re.S | re.I))
           if t and t.lower() != outlet.lower()]
    ld = next((h for h in (_clean(a.get("headline")) for a in arts) if h), "")
    head, src = "", ""
    if ld:
        head, src = ld, "the page's article data"
        cut = re.sub(r"\s*(\.\.\.|\u2026)$", "", ld)            # some sites cut the data headline short at 110 letters
        full = next((h for h in h1s if len(h) > len(cut) and h.lower().startswith(cut.lower()[:40])), "")
        if full and (cut != ld or len(ld) >= 108):
            head, src = full, "the page's main heading"
    elif h1s:
        head, src = h1s[0], "the page's main heading"
    else:
        for key in ("og:title", "twitter:title"):
            if meta.get(key):
                head, src = _strip_outlet(meta[key], outlet, host), "the page's share title"
                break
        else:
            m = re.search(r"<title\b[^>]*>(.*?)</title>", text, re.S | re.I)
            if m and _clean(m.group(1)):
                head, src = _strip_outlet(_clean(m.group(1)), outlet, host), "the page's title"
    return {"headline": head, "outlet": outlet, "date": when, "from": src}


def read_headline(url, get=None):
    """parse_headline for a live page. Raises CouldNotRead when the page is blocked, empty or a robot check."""
    text = (get or fetch)(url)
    d = parse_headline(text, url)
    if not d["headline"]:
        raise CouldNotRead("the page has no headline this editor can find")
    if _BLOCKED.search(d["headline"]) or len(d["headline"]) < 8:
        raise CouldNotRead(f"the site showed a robot check or an error page instead of the article: \"{d['headline'][:60]}\"")
    return d


def cmd_headline(a):
    try:
        d = read_headline(a.url)
    except CouldNotRead as e:
        print(f"COULD NOT READ ({e})")
        print("Do not try the site another way. Ask the member for a screenshot of the article (headline, outlet and "
              "date showing) and read them from it. Never guess them.")
        return 0
    print(f"HEADLINE: {d['headline']}")
    print(f"OUTLET: {d['outlet'] or '(not on the page)'}")
    print(f"DATE: {d['date'] or '(not on the page)'}")
    print(f"READ FROM: {d['from']}")
    print(f"URL: {a.url}")
    return 0


# ---------- gre rates ----------

FRED = "https://fred.stlouisfed.org/graph/fredgraph.csv?id=MORTGAGE30US"
PMMS = "https://www.freddiemac.com/pmms/docs/PMMS_history.csv"
SOURCE = "Freddie Mac PMMS"
# FRED leaves a browser-like request hanging and answers a plain one; Freddie Mac refuses a plain one.
SOURCES = (("FRED", FRED, None), ("Freddie Mac", PMMS, BROWSER))


def parse_rates(text):
    """[(iso date, rate)] oldest first, from FRED's CSV (date,value) or Freddie Mac's history CSV (date first, the
    30-year average second, dates as M/D/YYYY). Rows without a number are skipped."""
    out = {}
    for line in text.splitlines():
        cells = [c.strip().strip('"') for c in line.split(",")]
        if len(cells) < 2:
            continue
        m = re.fullmatch(r"(\d{4})-(\d{1,2})-(\d{1,2})", cells[0])
        ymd = m.groups() if m else None
        if not m:
            m = re.fullmatch(r"(\d{1,2})/(\d{1,2})/(\d{4})", cells[0])
            ymd = (m.group(3), m.group(1), m.group(2)) if m else None
        try:
            d, v = date(*map(int, ymd)), float(cells[1])
        except (TypeError, ValueError):
            continue
        if 0.5 < v < 30:
            out[d.isoformat()] = v
    return sorted(out.items())


def _cache():
    return HOME / "rates.json"


def read_cache():
    try:
        d = json.loads(_cache().read_text(encoding="utf-8"))
        d["series"] = [(str(a), float(b)) for a, b in d["series"]]
        return d if len(d["series"]) >= 2 else None
    except (OSError, ValueError, KeyError, TypeError):
        return None


def load_rates(refresh=False, get=None, today=None):
    """The series, from today's saved copy or fetched fresh (FRED first, then Freddie Mac's own file) and saved in the
    editor's home folder. Offline, the saved copy is used and `note` says how old it is.
    Returns {"series", "fetched", "via", "note"}; raises UserError when there is nothing to show."""
    today, get = today or date.today(), get or fetch
    c = read_cache()
    if c and not refresh and c.get("fetched") == today.isoformat():
        return dict(c, note="")
    why = ""
    for via, url, agent in SOURCES:
        try:
            series = parse_rates(get(url, agent=agent))
        except CouldNotRead as e:
            why = str(e)
            continue
        if len(series) < 60:
            why = f"{via} sent a file without the weekly numbers"
            continue
        d = {"fetched": today.isoformat(), "via": via, "series": series[-600:]}
        HOME.mkdir(parents=True, exist_ok=True)
        _cache().write_text(json.dumps(d), encoding="utf-8")
        return dict(d, note="")
    if c:
        try:
            age = (today - date.fromisoformat(c["fetched"])).days
        except (KeyError, ValueError):
            age = None
        old = "saved earlier" if age is None else "saved today" if age == 0 else f"saved {age} day{'s' * (age != 1)} ago"
        return dict(c, note=f"could not reach the rate data just now ({why}): these are the numbers {old}")
    raise UserError(f"could not get the mortgage rate data ({why}) and none is saved on this computer yet. "
                    f"Check the internet connection and try again.")


def window(series, weeks=52):
    """The last `weeks` weekly points."""
    return list(series[-int(weeks):])


def _on_or_before(series, iso):
    best = None
    for d, v in series:
        if d <= iso:
            best = (d, v)
    return best


def summary(series):
    """The numbers members talk about: latest, a week ago, four weeks ago, a year ago, the 52-week high and low."""
    d0 = date.fromisoformat(series[-1][0])
    back = lambda days: _on_or_before(series, (d0 - timedelta(days=days)).isoformat())
    w = window(series, 52)
    return {"latest": series[-1], "week": back(7), "month": back(28), "year": back(364),
            "high": max(w, key=lambda p: (p[1], p[0])), "low": min(w, key=lambda p: (p[1], p[0]))}


def payment(loan, rate, years=30):
    """Monthly principal and interest on a fixed-rate loan."""
    r, n = rate / 100 / 12, years * 12
    return loan / n if r == 0 else loan * r / (1 - (1 + r) ** -n)


def parse_money(s):
    m = re.fullmatch(r"\$?\s*([\d,]*\.?\d+)\s*([kKmM]?)", str(s).strip())
    if not m:
        raise UserError(f"'{s}' is not a loan amount: use a number like 400000")
    v = float(m.group(1).replace(",", "")) * {"": 1, "k": 1e3, "m": 1e6}[m.group(2).lower()]
    if not 1000 <= v <= 1e8:
        raise UserError(f"'{s}' is not a loan amount: use a number like 400000")
    return v


def cmd_rates(a):
    loan = parse_money(a.payment) if a.payment else None
    d = load_rates(refresh=a.refresh)
    s = summary(d["series"])
    rows = (("LATEST", s["latest"]), ("1 WEEK AGO", s["week"]), ("4 WEEKS AGO", s["month"]), ("1 YEAR AGO", s["year"]),
            ("52-WEEK HIGH", s["high"]), ("52-WEEK LOW", s["low"]))
    print("30-YEAR FIXED, weekly average (Freddie Mac Primary Mortgage Market Survey)")
    for label, p in rows:
        print(f"{label}: " + (f"{p[1]:.2f}% ({pretty_date(p[0])})" if p else "(not in the data)"))
    if loan:
        base = payment(loan, s["latest"][1])
        print(f"PAYMENT on ${loan:,.0f} (30 years, principal and interest only: no taxes, insurance or fees)")
        for label, p in rows:
            if p:
                pay = payment(loan, p[1])
                diff = round(pay) - round(base)
                print(f"  {label} {p[1]:.2f}%: ${pay:,.0f} a month"
                      + ("" if label == "LATEST" else f" ({'+' if diff >= 0 else '-'}${abs(diff):,} vs latest)"))
    print(f"SOURCE: {SOURCE} (cite it on screen and in the caption); fetched {d.get('fetched', '?')} via {d.get('via', '?')}")
    if d["note"]:
        print(f"NOTE: {d['note']}")
    return 0
