import json
import os
import re
import time
from datetime import datetime, timezone
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup


# ============================================================
# CONFIG
# ============================================================

BASE_URL = "https://www.upsc.gov.in"
SITEMAP_URL = "https://www.upsc.gov.in/site-map"

REQUEST_DELAY = 0.5
MAX_RETRIES = 3

OUTPUT_DIR = "data"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/131.0.0.0 Safari/537.36"
    ),
    "Accept": (
        "text/html,application/xhtml+xml,application/xml;"
        "q=0.9,image/avif,image/webp,*/*;q=0.8"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Connection": "keep-alive",
}

SESSION = requests.Session()
SESSION.headers.update(HEADERS)


# ============================================================
# HELPERS
# ============================================================

def clean(value):
    if value is None:
        return ""

    value = str(value)
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def absolute_url(url, base=BASE_URL):
    if not url:
        return ""

    return urljoin(base, url)


def normalize_url(url):
    if not url:
        return ""

    url = absolute_url(url)

    parsed = urlparse(url)

    result = parsed._replace(
        fragment=""
    ).geturl()

    return result.rstrip("/")


def is_internal(url):
    try:
        host = urlparse(url).netloc.lower()

        return host in {
            "",
            "upsc.gov.in",
            "www.upsc.gov.in",
        }

    except Exception:
        return False


def is_document(url):
    if not url:
        return False

    path = urlparse(url).path.lower()

    extensions = (
        ".pdf",
        ".doc",
        ".docx",
        ".xls",
        ".xlsx",
        ".zip",
        ".rar",
    )

    return path.endswith(extensions)


# ============================================================
# SAFE REQUEST
# ============================================================

def get(url):

    for attempt in range(1, MAX_RETRIES + 1):

        try:

            print(
                f"GET [{attempt}/{MAX_RETRIES}] {url}"
            )

            response = SESSION.get(
                url,
                timeout=(15, 40),
                allow_redirects=True
            )

            response.raise_for_status()

            time.sleep(REQUEST_DELAY)

            return response

        except requests.exceptions.Timeout:

            print(
                f"TIMEOUT: {url}"
            )

            if attempt < MAX_RETRIES:
                time.sleep(3)

        except requests.exceptions.RequestException as error:

            print(
                f"REQUEST ERROR: {url} | {error}"
            )

            if attempt < MAX_RETRIES:
                time.sleep(3)

        except Exception as error:

            print(
                f"UNKNOWN ERROR: {url} | {error}"
            )

            if attempt < MAX_RETRIES:
                time.sleep(3)

    print(
        f"SKIPPED: {url}"
    )

    return None


# ============================================================
# CATEGORY
# ============================================================

def classify(url, title, text):

    source = (
        f"{url} "
        f"{title} "
        f"{text[:2500]}"
    ).lower()

    # Admit Cards
    if any(x in source for x in [
        "e-admit-card",
        "e-admit card",
        "admit-card",
        "admit card",
    ]):
        return "admit_cards"

    # Answer Keys
    if any(x in source for x in [
        "answer-key",
        "answer key",
    ]):
        return "answer_keys"

    # Final Results
    if any(x in source for x in [
        "final-result",
        "final result",
    ]):
        return "results"

    # Written Results
    if any(x in source for x in [
        "written-result",
        "written result",
    ]):
        return "results"

    # Results
    if "result" in source:
        return "results"

    # Question Papers
    if any(x in source for x in [
        "question-paper",
        "question paper",
        "previous-question",
        "previous question",
    ]):
        return "question_papers"

    # Cut Off
    if any(x in source for x in [
        "cut-off",
        "cutoff",
        "cut off",
    ]):
        return "cut_offs"

    # Marks
    if any(x in source for x in [
        "marks-info",
        "marks information",
        "marks of recommended",
    ]):
        return "marks"

    # Calendar
    if "calendar" in source:
        return "calendars"

    # Examination Notifications
    if any(x in source for x in [
        "examination notification",
        "examination-notification",
    ]):
        return "exam_notifications"

    # Active Exams
    if any(x in source for x in [
        "active-exams",
        "active examination",
    ]):
        return "exams"

    # Forthcoming Exams
    if any(x in source for x in [
        "forthcoming-exams",
        "forthcoming examination",
    ]):
        return "exams"

    # Syllabus
    if "syllabus" in source or "scheme" in source:
        return "syllabus"

    # Recruitment Advertisements = JOBS
    if any(x in source for x in [
        "recruitment-advertisement",
        "recruitment advertisement",
        "recruitment advertisement no",
    ]):
        return "jobs"

    # Recruitment Test
    if any(x in source for x in [
        "recruitment-test",
        "recruitment test",
    ]):
        return "jobs"

    # Recruitment
    if "recruitment" in source:
        return "jobs"

    # Interview
    if "interview" in source:
        return "interviews"

    # Corrigendum
    if "corrigendum" in source:
        return "notices"

    # Scrutiny
    if "scrutiny" in source:
        return "notices"

    # Time Table
    if any(x in source for x in [
        "time-table",
        "time table",
        "timetable",
    ]):
        return "exams"

    # Press Note
    if any(x in source for x in [
        "press-note",
        "press note",
        "press release",
    ]):
        return "notices"

    # Tenders
    if "tender" in source:
        return "other"

    # Annual Reports
    if "annual report" in source:
        return "other"

    # Court Judgments
    if "court judgment" in source:
        return "other"

    # Forms
    if "form" in source:
        return "other"

    # Examination
    if "examination" in source:
        return "exams"

    # Notice
    if "notice" in source:
        return "notices"

    return "other"


# ============================================================
# LINKS
# ============================================================

def extract_links(soup, page_url):

    links = {}

    for tag in soup.find_all(
        "a",
        href=True
    ):

        href = tag.get(
            "href",
            ""
        ).strip()

        if not href:
            continue

        if href.startswith("#"):
            continue

        if href.lower().startswith(
            "javascript:"
        ):
            continue

        if href.lower().startswith(
            "mailto:"
        ):
            continue

        full_url = normalize_url(
            absolute_url(
                href,
                page_url
            )
        )

        if not full_url:
            continue

        title = clean(
            tag.get_text(
                " ",
                strip=True
            )
        )

        links[full_url] = {
            "title": title,
            "url": full_url,
            "document": is_document(full_url),
        }

    return list(links.values())


# ============================================================
# DOCUMENTS
# ============================================================

def extract_documents(links):

    documents = []

    for link in links:

        if link.get("document"):

            documents.append({
                "title": link.get(
                    "title",
                    ""
                ),
                "url": link.get(
                    "url",
                    ""
                ),
            })

    return documents


# ============================================================
# TABLES
# ============================================================

def extract_tables(soup):

    tables = []

    for table in soup.find_all("table"):

        rows = []

        for tr in table.find_all("tr"):

            cells = []

            for cell in tr.find_all(
                ["th", "td"]
            ):

                value = clean(
                    cell.get_text(
                        " ",
                        strip=True
                    )
                )

                cells.append(value)

            if cells:
                rows.append(cells)

        if rows:
            tables.append(rows)

    return tables


# ============================================================
# KEY / VALUE DATA
# ============================================================

def extract_key_values(soup):

    data = {}

    # DL format
    for dl in soup.find_all("dl"):

        terms = dl.find_all("dt")
        descriptions = dl.find_all("dd")

        for term, description in zip(
            terms,
            descriptions
        ):

            key = clean(
                term.get_text(
                    " ",
                    strip=True
                )
            )

            value = clean(
                description.get_text(
                    " ",
                    strip=True
                )
            )

            if key and value:
                data[key] = value

    # Label: Value format
    for element in soup.find_all(
        ["p", "li"]
    ):

        text = clean(
            element.get_text(
                " ",
                strip=True
            )
        )

        match = re.match(
            r"^([^:]{2,100})\s*:\s*(.+)$",
            text
        )

        if match:

            key = clean(
                match.group(1)
            )

            value = clean(
                match.group(2)
            )

            if (
                key
                and value
                and len(key) < 100
            ):
                data.setdefault(
                    key,
                    value
                )

    return data


# ============================================================
# JOB FIELDS
# ============================================================

def extract_job_fields(text):

    text = clean(text)

    fields = {}

    patterns = {

        "vacancy": [
            r"vacancies?\s*[:\-]?\s*(\d+)",
            r"no\.?\s*of\s*vacancies?\s*[:\-]?\s*(\d+)",
            r"number\s*of\s*vacancies?\s*[:\-]?\s*(\d+)",
            r"(\d+)\s+vacancies?",
        ],

        "last_date": [
            r"last\s+date.*?([0-9]{1,2}[\/\-][0-9]{1,2}[\/\-][0-9]{2,4})",
            r"last\s+date.*?([0-9]{1,2}\s+[A-Za-z]+\s+[0-9]{4})",
        ],

        "notification_date": [
            r"date\s+of\s+notification.*?([0-9]{1,2}[\/\-][0-9]{1,2}[\/\-][0-9]{2,4})",
            r"date\s+of\s+notification.*?([0-9]{1,2}\s+[A-Za-z]+\s+[0-9]{4})",
        ],

        "exam_date": [
            r"date\s+of\s+commencement.*?([^\n]{3,80})",
            r"exam(?:ination)?\s+date.*?([0-9]{1,2}[\/\-][0-9]{1,2}[\/\-][0-9]{2,4})",
        ],

        "age_limit": [
            r"age\s+limit\s*[:\-]?\s*([^\n;]{3,120})",
            r"maximum\s+age\s*[:\-]?\s*([^\n;]{3,120})",
        ],

        "salary": [
            r"salary\s*[:\-]?\s*([^\n;]{3,150})",
            r"pay\s+scale\s*[:\-]?\s*([^\n;]{3,150})",
            r"pay\s+level\s*[:\-]?\s*([^\n;]{3,150})",
        ],

        "application_fee": [
            r"application\s+fee\s*[:\-]?\s*([^\n;]{2,120})",
            r"fee\s*[:\-]?\s*(?:rs\.?|₹)?\s*([0-9,]+)",
        ],
    }

    for field, regex_list in patterns.items():

        for pattern in regex_list:

            match = re.search(
                pattern,
                text,
                flags=re.IGNORECASE
            )

            if match:

                value = clean(
                    match.group(1)
                )

                if value:
                    fields[field] = value
                    break

    return fields


# ============================================================
# PAGE SCRAPER
# ============================================================

def scrape_page(url):

    response = get(url)

    if response is None:

        return {
            "url": url,
            "status": "failed",
            "title": "",
            "category": "other",
            "documents": [],
            "links": [],
            "tables": [],
            "key_values": {},
            "job_fields": {},
        }

    try:

        soup = BeautifulSoup(
            response.text,
            "lxml"
        )

        title = ""

        if soup.title:

            title = clean(
                soup.title.get_text(
                    " ",
                    strip=True
                )
            )

        # Only keep useful page text.
        # Do NOT save the entire HTML/text,
        # otherwise files become enormous.
        text = clean(
            soup.get_text(
                " ",
                strip=True
            )
        )

        links = extract_links(
            soup,
            url
        )

        documents = extract_documents(
            links
        )

        tables = extract_tables(
            soup
        )

        key_values = extract_key_values(
            soup
        )

        job_fields = extract_job_fields(
            text
        )

        category = classify(
            url,
            title,
            text
        )

        # Keep records reasonably small
        useful_links = links[:250]

        useful_tables = tables[:50]

        # Limit very large tables
        limited_tables = []

        for table in useful_tables:

            limited_tables.append(
                table[:200]
            )

        return {

            "url": url,

            "status": "success",

            "title": title,

            "category": category,

            "documents": documents,

            "links": useful_links,

            "tables": limited_tables,

            "key_values": key_values,

            "job_fields": job_fields,
        }

    except Exception as error:

        print(
            f"PARSE ERROR: {url} | {error}"
        )

        return {

            "url": url,

            "status": "parse_error",

            "title": "",

            "category": "other",

            "documents": [],

            "links": [],

            "tables": [],

            "key_values": {},

            "job_fields": {},

            "error": str(error),
        }


# ============================================================
# SITEMAP
# ============================================================

def get_sitemap_urls():

    print("=" * 70)
    print("LOADING UPSC SITEMAP")
    print("=" * 70)

    response = get(
        SITEMAP_URL
    )

    if response is None:

        return []

    try:

        soup = BeautifulSoup(
            response.text,
            "lxml"
        )

        urls = set()

        for tag in soup.find_all(
            "a",
            href=True
        ):

            href = tag.get(
                "href",
                ""
            ).strip()

            if not href:
                continue

            full_url = normalize_url(
                absolute_url(
                    href,
                    SITEMAP_URL
                )
            )

            if not full_url:
                continue

            if not is_internal(
                full_url
            ):
                continue

            if is_document(
                full_url
            ):
                continue

            urls.add(
                full_url
            )

        print(
            f"SITEMAP URLS: {len(urls)}"
        )

        return sorted(urls)

    except Exception as error:

        print(
            f"SITEMAP ERROR: {error}"
        )

        return []


# ============================================================
# IMPORTANT UPSC PAGES
# ============================================================

def seed_urls():

    return [

        BASE_URL,

        SITEMAP_URL,

        f"{BASE_URL}/examinations/active-exams",

        f"{BASE_URL}/examinations/exam-calendar",

        f"{BASE_URL}/e-admit-cards",

        f"{BASE_URL}/exams-related-info/written-result",

        f"{BASE_URL}/exams-related-info/final-result",

        f"{BASE_URL}/exams-related-info/answer-key",

        f"{BASE_URL}/exams-related-info/cutoff-marks",

        f"{BASE_URL}/exams-related-info/marks-info",

        f"{BASE_URL}/recruitment/recruitment-advertisement",

        f"{BASE_URL}/recruitment/recruitment-test/notices",

    ]


# ============================================================
# SAVE JSON
# ============================================================

def save_json(filename, data):

    os.makedirs(
        OUTPUT_DIR,
        exist_ok=True
    )

    path = os.path.join(
        OUTPUT_DIR,
        filename
    )

    with open(
        path,
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            data,
            file,
            ensure_ascii=False,
            indent=2
        )

    print(
        f"CREATED: {path}"
    )


# ============================================================
# MAIN
# ============================================================

def main():

    started = datetime.now(
        timezone.utc
    ).isoformat()

    print("=" * 70)
    print("UPSC DATA SCRAPER")
    print("=" * 70)

    # --------------------------------------------------------
    # Get URLs
    # --------------------------------------------------------

    sitemap = get_sitemap_urls()

    urls = set()

    for url in sitemap:
        urls.add(
            normalize_url(url)
        )

    for url in seed_urls():
        urls.add(
            normalize_url(url)
        )

    urls = sorted(
        url
        for url in urls
        if url
        and is_internal(url)
        and not is_document(url)
    )

    print("=" * 70)
    print(
        f"TOTAL PAGES: {len(urls)}"
    )
    print("=" * 70)

    # --------------------------------------------------------
    # Scrape
    # --------------------------------------------------------

    records = []

    for number, url in enumerate(
        urls,
        start=1
    ):

        print(
            f"[{number}/{len(urls)}]"
        )

        record = scrape_page(
            url
        )

        records.append(
            record
        )

    # --------------------------------------------------------
    # Categories
    # --------------------------------------------------------

    categories = {}

    for record in records:

        category = record.get(
            "category",
            "other"
        )

        categories.setdefault(
            category,
            []
        )

        categories[
            category
        ].append(record)

    # --------------------------------------------------------
    # Documents
    # --------------------------------------------------------

    documents = []

    for record in records:

        for document in record.get(
            "documents",
            []
        ):

            documents.append({

                "page_url": record.get(
                    "url",
                    ""
                ),

                "page_title": record.get(
                    "title",
                    ""
                ),

                "category": record.get(
                    "category",
                    "other"
                ),

                "title": document.get(
                    "title",
                    ""
                ),

                "url": document.get(
                    "url",
                    ""
                ),
            })

    # Deduplicate documents
    document_map = {}

    for document in documents:

        document_map[
            document["url"]
        ] = document

    documents = list(
        document_map.values()
    )

    # --------------------------------------------------------
    # Counts
    # --------------------------------------------------------

    category_counts = {}

    for category, items in categories.items():

        category_counts[
            category
        ] = len(items)

    category_counts = dict(
        sorted(
            category_counts.items()
        )
    )

    # --------------------------------------------------------
    # Save individual categories
    # --------------------------------------------------------

    file_names = {

        "jobs": "jobs.json",

        "results": "results.json",

        "admit_cards": "admit_cards.json",

        "answer_keys": "answer_keys.json",

        "question_papers": "question_papers.json",

        "exams": "exams.json",

        "cut_offs": "cut_offs.json",

        "marks": "marks.json",

        "syllabus": "syllabus.json",

        "calendars": "calendars.json",

        "exam_notifications":
            "exam_notifications.json",

        "interviews":
            "interviews.json",

        "notices":
            "notices.json",

        "other":
            "other.json",
    }

    for category, filename in file_names.items():

        save_json(
            filename,
            categories.get(
                category,
                []
            )
        )

    # --------------------------------------------------------
    # Documents
    # --------------------------------------------------------

    save_json(
        "documents.json",
        documents
    )

    # --------------------------------------------------------
    # Index
    # --------------------------------------------------------

    index = {

        "source": "UPSC",

        "source_name":
            "Union Public Service Commission",

        "source_url":
            BASE_URL,

        "scraped_at":
            started,

        "total_pages":
            len(records),

        "successful_pages":
            sum(
                1
                for r in records
                if r.get("status")
                == "success"
            ),

        "failed_pages":
            sum(
                1
                for r in records
                if r.get("status")
                != "success"
            ),

        "total_documents":
            len(documents),

        "category_counts":
            category_counts,

        "files": file_names,
    }

    save_json(
        "index.json",
        index
    )

    # --------------------------------------------------------
    # Summary
    # --------------------------------------------------------

    print("=" * 70)
    print("SCRAPER FINISHED")
    print("=" * 70)

    print(
        f"Pages: {len(records)}"
    )

    print(
        f"Documents: {len(documents)}"
    )

    print(
        f"Successful: {index['successful_pages']}"
    )

    print(
        f"Failed: {index['failed_pages']}"
    )

    print("=" * 70)

    for category, count in category_counts.items():

        print(
            f"{category}: {count}"
        )

    print("=" * 70)


if __name__ == "__main__":
    main()
