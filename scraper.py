import json
import re
import time
from datetime import datetime, timezone
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup


BASE_URL = "https://www.upsc.gov.in"
SITEMAP_URL = "https://www.upsc.gov.in/site-map"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/140.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

# Small delay so we don't hammer the official website.
REQUEST_DELAY = 0.25


def clean(text):
    return re.sub(r"\s+", " ", text or "").strip()


def is_internal(url):
    try:
        host = urlparse(url).netloc.lower()

        return (
            host == "www.upsc.gov.in"
            or host == "upsc.gov.in"
        )

    except Exception:
        return False


def absolute_url(url):
    return urljoin(BASE_URL, url)


def get(url):
    time.sleep(REQUEST_DELAY)

    response = requests.get(
        url,
        headers=HEADERS,
        timeout=60,
        allow_redirects=True,
    )

    response.raise_for_status()

    return response


def classify(url, title="", text=""):
    """
    Assign one or more categories based on UPSC's
    own URL structure and page terminology.
    """

    value = (
        f"{url} {title} {text}"
    ).lower()

    categories = set()

    # -------------------------
    # EXAMINATION
    # -------------------------

    if (
        "/examinations/" in url
        or "/exams-related-info/" in url
    ):
        categories.add("examination")

    if "active examination" in value:
        categories.add("active_examination")

    if "forthcoming examination" in value:
        categories.add("forthcoming_examination")

    if "previous question paper" in value:
        categories.add("question_paper")

    if "question paper" in value:
        categories.add("question_paper")

    if "answer key" in value:
        categories.add("answer_key")

    if "cut-off" in value or "cut off" in value:
        categories.add("cut_off")

    if "marks information" in value:
        categories.add("marks")

    if "marks of recommended" in value:
        categories.add("recommended_candidate_marks")

    if "syllabus" in value:
        categories.add("syllabus")

    if "calendar" in value:
        categories.add("calendar")

    if "exam notification" in value:
        categories.add("exam_notification")

    if "examination notification" in value:
        categories.add("exam_notification")

    if "admit card" in value or "e-admit" in value:
        categories.add("admit_card")

    if "written result" in value:
        categories.add("written_result")

    if "final result" in value:
        categories.add("final_result")

    if "result" in value and "written result" not in value:
        categories.add("result")

    if "interview schedule" in value:
        categories.add("interview_schedule")

    if "time table" in value or "timetable" in value:
        categories.add("time_table")

    if "press note" in value or "press release" in value:
        categories.add("press_release")

    # -------------------------
    # RECRUITMENT
    # -------------------------

    if "/recruitment/" in url:
        categories.add("recruitment")

    if "recruitment advertisement" in value:
        categories.add("recruitment_advertisement")

    if "advertisement" in value and "/recruitment/" in url:
        categories.add("recruitment_advertisement")

    if "recruitment test" in value:
        categories.add("recruitment_test")

    if "applicants" in value:
        categories.add("applicants")

    if "corrigendum" in value:
        categories.add("corrigendum")

    if "scrutiny" in value:
        categories.add("scrutiny")

    if "recruitment cases" in value:
        categories.add("recruitment_case")

    if "requisition" in value:
        categories.add("recruitment_requisition")

    if "lateral recruitment" in value:
        categories.add("lateral_recruitment")

    if "online recruitment application" in value:
        categories.add("online_recruitment_application")

    # -------------------------
    # OTHER
    # -------------------------

    if "faq" in value:
        categories.add("faq")

    if "tender" in value:
        categories.add("tender")

    if "annual report" in value:
        categories.add("annual_report")

    if "court judgment" in value:
        categories.add("court_judgment")

    if "rti" in value:
        categories.add("rti")

    if "form" in value:
        categories.add("forms")

    if "notice" in value:
        categories.add("notice")

    if not categories:
        categories.add("other")

    return sorted(categories)


def extract_links(soup, page_url):
    links = []

    for a in soup.find_all("a", href=True):

        href = a.get("href", "").strip()

        if not href:
            continue

        url = absolute_url(href)

        if not is_internal(url):
            continue

        text = clean(
            a.get_text(" ", strip=True)
        )

        links.append({
            "title": text,
            "url": url
        })

    # Remove duplicates.
    output = []
    seen = set()

    for item in links:

        if item["url"] in seen:
            continue

        seen.add(item["url"])
        output.append(item)

    return output


def extract_documents(soup, page_url):
    documents = []

    for a in soup.find_all("a", href=True):

        href = a.get("href", "").strip()

        if not href:
            continue

        url = absolute_url(href)

        if not url.lower().endswith(
            (
                ".pdf",
                ".doc",
                ".docx",
                ".xls",
                ".xlsx",
                ".zip"
            )
        ):
            continue

        title = clean(
            a.get_text(" ", strip=True)
        )

        documents.append({
            "title": title,
            "url": url
        })

    output = []
    seen = set()

    for item in documents:

        if item["url"] in seen:
            continue

        seen.add(item["url"])
        output.append(item)

    return output


def extract_tables(soup):
    tables = []

    for table in soup.find_all("table"):

        rows = []

        for tr in table.find_all("tr"):

            cells = tr.find_all(
                ["th", "td"]
            )

            if not cells:
                continue

            row = [
                clean(
                    cell.get_text(
                        " ",
                        strip=True
                    )
                )
                for cell in cells
            ]

            rows.append(row)

        if rows:
            tables.append(rows)

    return tables


def extract_key_values(soup):
    """
    Converts simple two-column UPSC information tables into
    key/value data.
    """

    result = {}

    for table in soup.find_all("table"):

        for tr in table.find_all("tr"):

            cells = tr.find_all(
                ["th", "td"]
            )

            if len(cells) != 2:
                continue

            key = clean(
                cells[0].get_text(
                    " ",
                    strip=True
                )
            )

            value = clean(
                cells[1].get_text(
                    " ",
                    strip=True
                )
            )

            if not key or not value:
                continue

            if len(key) > 150:
                continue

            result[key] = value

    return result


def extract_job_fields(text):
    """
    Best-effort extraction from recruitment/examination pages.
    Missing fields remain null.
    """

    fields = {
        "post_name": None,
        "vacancy": None,
        "qualification": None,
        "age_limit": None,
        "experience": None,
        "salary": None,
        "pay_level": None,
        "application_start": None,
        "application_last_date": None,
        "exam_date": None,
        "application_fee": None,
        "selection_process": None,
    }

    patterns = {

        "qualification": [
            r"essential qualifications?\s*[:\-]\s*(.{20,1000})",
            r"educational qualifications?\s*[:\-]\s*(.{20,1000})",
        ],

        "age_limit": [
            r"age\s*(?:limit)?\s*[:\-]\s*(.{3,300})",
            r"maximum age\s*[:\-]\s*(.{3,300})",
        ],

        "experience": [
            r"experience\s*[:\-]\s*(.{10,600})",
        ],

        "salary": [
            r"salary\s*[:\-]\s*(.{3,300})",
            r"pay scale\s*[:\-]\s*(.{3,300})",
        ],

        "pay_level": [
            r"pay level\s*[:\-]\s*(.{3,200})",
            r"level\s*[:\-]\s*(.{3,100})",
        ],

        "application_start": [
            r"date of commencement of application\s*[:\-]\s*(.{3,100})",
            r"application start\s*[:\-]\s*(.{3,100})",
        ],

        "application_last_date": [
            r"last date for receipt of applications?\s*[:\-]\s*(.{3,150})",
            r"last date.*applications?\s*[:\-]\s*(.{3,150})",
        ],

        "exam_date": [
            r"date of commencement of examination\s*[:\-]\s*(.{3,150})",
            r"date.*examination\s*[:\-]\s*(.{3,150})",
        ],

        "application_fee": [
            r"application fee\s*[:\-]\s*(.{3,200})",
            r"fee\s*[:\-]\s*(.{3,200})",
        ],

        "selection_process": [
            r"selection process\s*[:\-]\s*(.{10,500})",
        ],
    }

    for field, field_patterns in patterns.items():

        for pattern in field_patterns:

            match = re.search(
                pattern,
                text,
                re.IGNORECASE
            )

            if match:

                value = clean(
                    match.group(1)
                )

                # Prevent extremely long accidental captures.
                if len(value) > 1200:
                    value = value[:1200]

                fields[field] = value
                break

    # Vacancy count
    vacancy_match = re.search(
        r"(\d+)\s+(?:posts?|vacancies?)",
        text,
        re.IGNORECASE
    )

    if vacancy_match:
        fields["vacancy"] = vacancy_match.group(1)

    return fields


def scrape_page(url):
    try:

        response = get(url)

        content_type = response.headers.get(
            "content-type",
            ""
        ).lower()

        # PDFs are stored as documents, not parsed as HTML pages here.
        if "application/pdf" in content_type:
            return {
                "url": url,
                "type": "document",
                "categories": classify(
                    url
                ),
                "title": url.split("/")[-1],
                "documents": [
                    {
                        "title": url.split("/")[-1],
                        "url": url
                    }
                ]
            }

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

        # Main page text.
        text = clean(
            soup.get_text(
                " ",
                strip=True
            )
        )

        categories = classify(
            url,
            title,
            text[:10000]
        )

        documents = extract_documents(
            soup,
            url
        )

        links = extract_links(
            soup,
            url
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

        return {

            "url": url,

            "type": "html",

            "title": title,

            "categories": categories,

            "job_details": job_fields,

            "key_values": key_values,

            "tables": tables,

            "documents": documents,

            "links": links,

            "scraped_at": datetime.now(
                timezone.utc
            ).isoformat()
        }

    except Exception as error:

        print(
            "ERROR:",
            url,
            str(error)
        )

        return {
            "url": url,
            "type": "error",
            "categories": ["error"],
            "error": str(error)
        }


def get_sitemap_urls():
    print("Opening UPSC sitemap...")

    response = get(
        SITEMAP_URL
    )

    soup = BeautifulSoup(
        response.text,
        "lxml"
    )

    urls = []

    for a in soup.find_all(
        "a",
        href=True
    ):

        url = absolute_url(
            a["href"]
        )

        if not is_internal(url):
            continue

        if url in urls:
            continue

        urls.append(url)

    print(
        "Sitemap URLs found:",
        len(urls)
    )

    return urls


def main():

    print("=" * 70)
    print("UPSC COMPLETE PUBLIC DATA CRAWLER")
    print("=" * 70)

    sitemap_urls = get_sitemap_urls()

    # Always include important pages even if sitemap markup changes.
    required_urls = [
        BASE_URL,
        f"{BASE_URL}/site-map",
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

    all_urls = []

    seen = set()

    for url in required_urls + sitemap_urls:

        if url in seen:
            continue

        seen.add(url)

        all_urls.append(url)

    print(
        "Total pages to process:",
        len(all_urls)
    )

    records = []

    for index, url in enumerate(
        all_urls,
        start=1
    ):

        print(
            f"[{index}/{len(all_urls)}]",
            url
        )

        record = scrape_page(
            url
        )

        records.append(
            record
        )

    # -------------------------------------------------
    # CATEGORY INDEX
    # -------------------------------------------------

    categories = {}

    for record in records:

        for category in record.get(
            "categories",
            []
        ):

            if category not in categories:
                categories[category] = []

            categories[category].append(
                record
            )

    # -------------------------------------------------
    # FINAL OUTPUT
    # -------------------------------------------------

    output = {

        "source": BASE_URL,

        "source_name": (
            "Union Public Service Commission"
        ),

        "scraped_at": datetime.now(
            timezone.utc
        ).isoformat(),

        "total_pages": len(records),

        "total_categories": len(
            categories
        ),

        "category_counts": {
            key: len(value)
            for key, value in categories.items()
        },

        "categories": {
            key: value
            for key, value in categories.items()
        },

        "all_records": records
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

    print()
    print("=" * 70)
    print("CRAWL COMPLETE")
    print("=" * 70)

    print(
        "Pages:",
        len(records)
    )

    print(
        "Categories:",
        len(categories)
    )

    print()
    print("CATEGORY COUNTS:")

    for category, count in sorted(
        output["category_counts"].items()
    ):

        print(
            f"  {category}: {count}"
        )

    print()
    print("data.json created.")


if __name__ == "__main__":
    main()
