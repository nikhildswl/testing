import json
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
# BASIC HELPERS
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


def is_internal(url):
    try:
        parsed = urlparse(url)
        return parsed.netloc in {
            "",
            "upsc.gov.in",
            "www.upsc.gov.in",
        }
    except Exception:
        return False


def normalize_url(url):
    if not url:
        return ""

    url = absolute_url(url)

    parsed = urlparse(url)

    clean_url = parsed._replace(
        fragment="",
        query=parsed.query
    ).geturl()

    return clean_url.rstrip("/")


def is_document(url):
    lower = url.lower()

    extensions = (
        ".pdf",
        ".doc",
        ".docx",
        ".xls",
        ".xlsx",
        ".zip",
        ".rar",
    )

    return lower.split("?")[0].endswith(extensions)


# ============================================================
# REQUEST FUNCTION
# ============================================================

def get(url):
    """
    Downloads a page safely.

    Important:
    - Timeout will NOT crash the complete scraper.
    - Retries 3 times.
    - Failed pages are skipped.
    """

    for attempt in range(1, MAX_RETRIES + 1):

        try:
            print(
                f"GET {url} "
                f"(attempt {attempt}/{MAX_RETRIES})"
            )

            response = SESSION.get(
                url,
                timeout=(15, 45),
                allow_redirects=True,
            )

            response.raise_for_status()

            time.sleep(REQUEST_DELAY)

            return response

        except requests.exceptions.Timeout:

            print(
                f"TIMEOUT: {url} "
                f"(attempt {attempt}/{MAX_RETRIES})"
            )

            if attempt < MAX_RETRIES:
                time.sleep(3)

        except requests.exceptions.RequestException as error:

            print(
                f"REQUEST ERROR: {url} | {error} "
                f"(attempt {attempt}/{MAX_RETRIES})"
            )

            if attempt < MAX_RETRIES:
                time.sleep(3)

        except Exception as error:

            print(
                f"UNKNOWN ERROR: {url} | {error}"
            )

            if attempt < MAX_RETRIES:
                time.sleep(3)

    print(f"SKIPPED AFTER RETRIES: {url}")

    return None


# ============================================================
# CATEGORY DETECTION
# ============================================================

def classify(url, title="", text=""):
    source = (
        f"{url} "
        f"{title} "
        f"{text[:3000]}"
    ).lower()

    # Admit Card
    if (
        "admit-card" in source
        or "admit card" in source
        or "e-admit" in source
    ):
        return "admit_card"

    # Answer Key
    if (
        "answer-key" in source
        or "answer key" in source
    ):
        return "answer_key"

    # Written Result
    if (
        "written-result" in source
        or "written result" in source
    ):
        return "written_result"

    # Final Result
    if (
        "final-result" in source
        or "final result" in source
    ):
        return "final_result"

    # Question Papers
    if (
        "question-paper" in source
        or "question paper" in source
        or "previous-question" in source
    ):
        return "question_paper"

    # Cutoff
    if (
        "cut-off" in source
        or "cutoff" in source
        or "cut off" in source
    ):
        return "cut_off"

    # Marks
    if (
        "marks-info" in source
        or "marks information" in source
        or "marks of recommended" in source
    ):
        return "marks"

    # Calendar
    if (
        "calendar" in source
        or "exam-calendar" in source
    ):
        return "calendar"

    # Examination Notification
    if (
        "examination-notification" in source
        or "examination notification" in source
    ):
        return "exam_notification"

    # Active Examination
    if (
        "active-exams" in source
        or "active examination" in source
    ):
        return "active_examination"

    # Forthcoming Examination
    if (
        "forthcoming-exams" in source
        or "forthcoming examination" in source
    ):
        return "forthcoming_examination"

    # Syllabus
    if (
        "syllabus" in source
        or "scheme" in source
    ):
        return "syllabus"

    # Recruitment Advertisement
    if (
        "recruitment-advertisement" in source
        or "recruitment advertisement" in source
    ):
        return "recruitment_advertisement"

    # Recruitment Test
    if (
        "recruitment-test" in source
        or "recruitment test" in source
    ):
        return "recruitment_test"

    # Recruitment
    if "recruitment" in source:
        return "recruitment"

    # Applicants
    if (
        "applicant" in source
        or "applicants" in source
    ):
        return "applicants"

    # Interview
    if (
        "interview" in source
        or "interview schedule" in source
    ):
        return "interview_schedule"

    # Corrigendum
    if "corrigendum" in source:
        return "corrigendum"

    # Scrutiny
    if "scrutiny" in source:
        return "scrutiny"

    # Time Table
    if (
        "time-table" in source
        or "time table" in source
        or "timetable" in source
    ):
        return "time_table"

    # Press Release
    if (
        "press-note" in source
        or "press note" in source
        or "press release" in source
    ):
        return "press_release"

    # Tenders
    if "tender" in source:
        return "tender"

    # Annual Reports
    if (
        "annual-report" in source
        or "annual report" in source
    ):
        return "annual_report"

    # Court Judgments
    if (
        "court-judgment" in source
        or "court judgment" in source
        or "judgment" in source
    ):
        return "court_judgment"

    # RTI
    if "rti" in source:
        return "rti"

    # Forms
    if (
        "form" in source
        or "forms" in source
    ):
        return "forms"

    # Notices
    if "notice" in source:
        return "notice"

    # Examination
    if (
        "/examinations/" in source
        or "examination" in source
    ):
        return "examination"

    return "other"


# ============================================================
# LINK EXTRACTION
# ============================================================

def extract_links(soup, page_url):
    links = []

    for tag in soup.find_all("a", href=True):

        href = tag.get("href", "").strip()

        if not href:
            continue

        if href.startswith("#"):
            continue

        if href.lower().startswith("javascript:"):
            continue

        if href.lower().startswith("mailto:"):
            continue

        full_url = normalize_url(
            absolute_url(href, page_url)
        )

        if not full_url:
            continue

        text = clean(
            tag.get_text(" ", strip=True)
        )

        links.append({
            "title": text,
            "url": full_url,
            "internal": is_internal(full_url),
            "document": is_document(full_url),
        })

    # Remove duplicates
    unique = {}
    for item in links:
        unique[item["url"]] = item

    return list(unique.values())


# ============================================================
# DOCUMENT EXTRACTION
# ============================================================

def extract_documents(links):
    documents = []

    for link in links:

        if link["document"]:

            documents.append({
                "title": link["title"],
                "url": link["url"],
            })

    return documents


# ============================================================
# TABLE EXTRACTION
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
                cells.append(
                    clean(
                        cell.get_text(
                            " ",
                            strip=True
                        )
                    )
                )

            if cells:
                rows.append(cells)

        if rows:
            tables.append(rows)

    return tables


# ============================================================
# KEY VALUE EXTRACTION
# ============================================================

def extract_key_values(soup):
    data = {}

    # Definition lists
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

    # Paragraphs that look like:
    # Date: something
    # Last Date - something
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

            key = clean(match.group(1))
            value = clean(match.group(2))

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
# JOB FIELD EXTRACTION
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
            r"last\s+date(?:\s+for\s+application)?\s*[:\-]?\s*([0-9]{1,2}[\/\-][0-9]{1,2}[\/\-][0-9]{2,4})",
            r"last\s+date(?:\s+for\s+application)?\s*[:\-]?\s*([0-9]{1,2}\s+[A-Za-z]+\s+[0-9]{4})",
        ],

        "notification_date": [
            r"date\s+of\s+notification\s*[:\-]?\s*([0-9]{1,2}[\/\-][0-9]{1,2}[\/\-][0-9]{2,4})",
            r"date\s+of\s+notification\s*[:\-]?\s*([0-9]{1,2}\s+[A-Za-z]+\s+[0-9]{4})",
        ],

        "exam_date": [
            r"date\s+of\s+commencement\s+of\s+examination\s*[:\-]?\s*([^\n,;]{3,60})",
            r"exam(?:ination)?\s+date\s*[:\-]?\s*([0-9]{1,2}[\/\-][0-9]{1,2}[\/\-][0-9]{2,4})",
        ],

        "age_limit": [
            r"age\s+limit\s*[:\-]?\s*([^\n;]{3,100})",
            r"maximum\s+age\s*[:\-]?\s*([^\n;]{3,100})",
        ],

        "salary": [
            r"salary\s*[:\-]?\s*([^\n;]{3,120})",
            r"pay\s+scale\s*[:\-]?\s*([^\n;]{3,120})",
            r"pay\s+level\s*[:\-]?\s*([^\n;]{3,120})",
        ],

        "application_fee": [
            r"application\s+fee\s*[:\-]?\s*([^\n;]{2,100})",
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
            "links": [],
            "documents": [],
            "tables": [],
            "key_values": {},
            "job_fields": {},
            "text": "",
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

        # Main visible text
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

        return {
            "url": url,
            "status": "success",
            "title": title,
            "category": category,
            "links": links,
            "documents": documents,
            "tables": tables,
            "key_values": key_values,
            "job_fields": job_fields,
            "text": text,
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
            "links": [],
            "documents": [],
            "tables": [],
            "key_values": {},
            "job_fields": {},
            "text": "",
            "error": str(error),
        }


# ============================================================
# SITEMAP
# ============================================================

def get_sitemap_urls():

    print("=" * 60)
    print("LOADING UPSC SITE MAP")
    print("=" * 60)

    response = get(SITEMAP_URL)

    if response is None:

        print(
            "ERROR: Could not load UPSC sitemap."
        )

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

            if not is_internal(full_url):
                continue

            if is_document(full_url):
                continue

            urls.add(full_url)

        print(
            f"SITEMAP URLS FOUND: {len(urls)}"
        )

        return sorted(urls)

    except Exception as error:

        print(
            f"SITEMAP PARSE ERROR: {error}"
        )

        return []


# ============================================================
# IMPORTANT UPSC PAGES
# ============================================================

def get_seed_urls():

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
# MAIN
# ============================================================

def main():

    print("=" * 70)
    print("UPSC COMPLETE PUBLIC DATA SCRAPER")
    print("=" * 70)

    started_at = datetime.now(
        timezone.utc
    ).isoformat()

    sitemap_urls = get_sitemap_urls()

    seed_urls = get_seed_urls()

    all_urls = set()

    for url in sitemap_urls:
        all_urls.add(
            normalize_url(url)
        )

    for url in seed_urls:
        all_urls.add(
            normalize_url(url)
        )

    all_urls = sorted(
        url
        for url in all_urls
        if url and is_internal(url)
    )

    print("=" * 70)
    print(
        f"TOTAL UNIQUE PAGES TO SCRAPE: {len(all_urls)}"
    )
    print("=" * 70)

    records = []

    for index, url in enumerate(
        all_urls,
        start=1
    ):

        print(
            f"[{index}/{len(all_urls)}] {url}"
        )

        record = scrape_page(url)

        records.append(record)

    # ========================================================
    # CATEGORY ORGANIZATION
    # ========================================================

    categories = {}

    for record in records:

        category = record.get(
            "category",
            "other"
        )

        if category not in categories:
            categories[category] = []

        categories[category].append(
            record
        )

    # ========================================================
    # CATEGORY COUNTS
    # ========================================================

    category_counts = {}

    for category, items in categories.items():

        category_counts[category] = len(
            items
        )

    category_counts = dict(
        sorted(
            category_counts.items(),
            key=lambda x: x[0]
        )
    )

    # ========================================================
    # DOCUMENT INDEX
    # ========================================================

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

    # Remove duplicate documents

    unique_documents = {}

    for document in documents:

        unique_documents[
            document["url"]
        ] = document

    documents = list(
        unique_documents.values()
    )

    # ========================================================
    # FINAL OUTPUT
    # ========================================================

    output = {

        "source": "UPSC",

        "source_name": (
            "Union Public Service Commission"
        ),

        "source_url": BASE_URL,

        "scraped_at": started_at,

        "total_pages": len(records),

        "successful_pages": sum(
            1
            for r in records
            if r.get("status") == "success"
        ),

        "failed_pages": sum(
            1
            for r in records
            if r.get("status") != "success"
        ),

        "total_documents": len(
            documents
        ),

        "total_categories": len(
            categories
        ),

        "category_counts": (
            category_counts
        ),

        "categories": categories,

        "documents": documents,

        "all_records": records,
    }

    with open(
        "data.json",
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            output,
            file,
            ensure_ascii=False,
            indent=2
        )

    print("=" * 70)
    print("SCRAPING COMPLETED")
    print("=" * 70)

    print(
        f"Pages: {len(records)}"
    )

    print(
        f"Successful: {output['successful_pages']}"
    )

    print(
        f"Failed: {output['failed_pages']}"
    )

    print(
        f"Documents: {output['total_documents']}"
    )

    print(
        f"Categories: {output['total_categories']}"
    )

    print("=" * 70)

    print("CATEGORY COUNTS:")

    for category, count in category_counts.items():

        print(
            f"  {category}: {count}"
        )

    print("=" * 70)

    print(
        "data.json CREATED SUCCESSFULLY"
    )


if __name__ == "__main__":
    main()
