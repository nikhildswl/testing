import json
import re
from datetime import datetime, timezone
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup


URL = "https://www.upsc.gov.in/recruitment/recruitment-test/notices"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/140.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}


def clean(text):
    return re.sub(r"\s+", " ", text or "").strip()


def scrape():

    print("Opening UPSC Notices...")
    print(URL)

    response = requests.get(
        URL,
        headers=HEADERS,
        timeout=60
    )

    print("HTTP STATUS:", response.status_code)

    response.raise_for_status()

    soup = BeautifulSoup(
        response.text,
        "lxml"
    )

    jobs = []

    # Find the table containing:
    # Advertisement Number
    # Vacancy Number
    # Name of Post
    # Documents
    # Date of Upload

    table = None

    for candidate in soup.find_all("table"):

        headers = [
            clean(th.get_text(" ", strip=True)).lower()
            for th in candidate.find_all("th")
        ]

        header_text = " ".join(headers)

        if (
            "advertisement number" in header_text
            and "vacancy number" in header_text
            and "name of post" in header_text
        ):
            table = candidate
            break

    if table is None:
        print("ERROR: UPSC jobs table not found.")
        print("Available tables:", len(soup.find_all("table")))
        raise RuntimeError("UPSC jobs table not found")

    print("UPSC jobs table found.")

    rows = table.find_all("tr")

    print("Rows found:", len(rows))

    for row in rows:

        cells = row.find_all("td")

        if len(cells) < 4:
            continue

        advertisement = clean(
            cells[0].get_text(" ", strip=True)
        )

        vacancy_number = clean(
            cells[1].get_text(" ", strip=True)
        )

        post_name = clean(
            cells[2].get_text(" ", strip=True)
        )

        date_uploaded = clean(
            cells[-1].get_text(" ", strip=True)
        )

        if not advertisement:
            continue

        if not vacancy_number:
            continue

        if not post_name:
            continue

        # Document links
        documents = []

        for link in cells[3].find_all(
            "a",
            href=True
        ):

            href = link.get("href")

            if not href:
                continue

            document_url = urljoin(
                URL,
                href
            )

            document_title = clean(
                link.get_text(
                    " ",
                    strip=True
                )
            )

            documents.append({
                "title": document_title,
                "url": document_url
            })

        # Try to extract number of posts from title.
        vacancy_count = None

        number_match = re.search(
            r"(\d+)\s+(?:posts?|vacancies?)",
            post_name,
            re.IGNORECASE
        )

        if number_match:
            vacancy_count = int(
                number_match.group(1)
            )

        jobs.append({
            "organization": "Union Public Service Commission",
            "category": "UPSC",

            "advertisement_number": advertisement,

            "vacancy_number": vacancy_number,

            "post_name": post_name,

            "vacancy_count": vacancy_count,

            "date_uploaded": date_uploaded,

            "documents": documents,

            "source_url": URL
        })

    # Remove duplicates
    unique_jobs = []

    seen = set()

    for job in jobs:

        key = (
            job["advertisement_number"],
            job["vacancy_number"]
        )

        if key in seen:
            continue

        seen.add(key)

        unique_jobs.append(job)

    output = {

        "source": "UPSC",

        "source_url": URL,

        "scraped_at": datetime.now(
            timezone.utc
        ).isoformat(),

        "total_jobs": len(unique_jobs),

        "jobs": unique_jobs
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
    print("=" * 60)
    print("SCRAPING COMPLETE")
    print("=" * 60)

    print(
        "TOTAL JOBS:",
        len(unique_jobs)
    )

    print(
        "data.json created successfully."
    )


if __name__ == "__main__":
    scrape()
