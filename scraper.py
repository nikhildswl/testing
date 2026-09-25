import json
import re
from datetime import datetime, timezone
from urllib.parse import urljoin

import requests
import fitz
from bs4 import BeautifulSoup


BASE_URL = "https://www.upsc.gov.in"

RECRUITMENT_URL = (
    "https://www.upsc.gov.in/recruitment/recruitment-advertisement"
)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/140.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}


def clean(text):
    return re.sub(r"\s+", " ", text or "").strip()


def get_page(url):
    response = requests.get(
        url,
        headers=HEADERS,
        timeout=60
    )

    print("URL:", url)
    print("STATUS:", response.status_code)

    response.raise_for_status()

    return response.text


def get_advertisement_pdfs():
    html = get_page(RECRUITMENT_URL)

    soup = BeautifulSoup(html, "lxml")

    advertisements = []

    for link in soup.find_all("a", href=True):

        title = clean(
            link.get_text(" ", strip=True)
        )

        href = link.get("href", "").strip()

        if not href:
            continue

        pdf_url = urljoin(
            BASE_URL,
            href
        )

        # We only want actual PDF files.
        if ".pdf" not in pdf_url.lower():
            continue

        # UPSC advertisement links.
        if not re.search(
            r"advt|advertisement",
            title,
            re.IGNORECASE
        ):
            continue

        advertisements.append({
            "advertisement": title,
            "pdf_url": pdf_url
        })

    # Remove duplicates.
    unique = []
    seen = set()

    for item in advertisements:

        if item["pdf_url"] in seen:
            continue

        seen.add(item["pdf_url"])
        unique.append(item)

    return unique


def download_pdf(url):

    response = requests.get(
        url,
        headers=HEADERS,
        timeout=90
    )

    response.raise_for_status()

    return response.content


def extract_pdf_text(pdf_bytes):

    document = fitz.open(
        stream=pdf_bytes,
        filetype="pdf"
    )

    pages = []

    for page in document:
        pages.append(
            page.get_text("text")
        )

    document.close()

    return "\n".join(pages)


def find(pattern, text):

    match = re.search(
        pattern,
        text,
        re.IGNORECASE | re.DOTALL
    )

    if not match:
        return None

    return clean(match.group(1))


def parse_jobs(text):

    # UPSC PDFs use:
    #
    # 1. (Vacancy No. XXXXX)
    # 2. (Vacancy No. XXXXX)
    #
    blocks = re.split(
        r"(?=\d+\.\s*\(Vacancy No\.)",
        text
    )

    jobs = []

    for block in blocks:

        block = clean(block)

        if "Vacancy No." not in block:
            continue

        vacancy_number = find(
            r"Vacancy No\.\s*([0-9]+)",
            block
        )

        if not vacancy_number:
            continue

        # Example:
        # Four vacancies for the post of Specialist...
        # Sixty vacancies for the post of...
        post = find(
            r"Vacancy No\.\s*[0-9]+\)\s*"
            r"(?:one|two|three|four|five|six|seven|eight|nine|ten|"
            r"eleven|twelve|thirteen|fourteen|fifteen|sixteen|"
            r"seventeen|eighteen|nineteen|twenty|thirty|forty|"
            r"fifty|sixty|seventy|eighty|ninety|hundred|\d+)"
            r"\s+vacancies?\s+for\s+the\s+post\s+of\s+"
            r"(.+?)(?=\s+in\s+|\.)",
            block
        )

        vacancy_count = find(
            r"Vacancy No\.\s*[0-9]+\)\s*"
            r"([A-Za-z0-9 -]+?)\s+vacancies?",
            block
        )

        department = find(
            r"vacancies?\s+for\s+the\s+post\s+of\s+.+?"
            r"\s+in\s+(.+?)(?=\.\s+RESERVATION POSITION:)",
            block
        )

        pay_scale = find(
            r"PAY SCALE:\s*(.+?)(?=\s+AGE:)",
            block
        )

        age_limit = find(
            r"AGE:\s*(.+?)(?=\s+ESSENTIAL QUALIFICATIONS:)",
            block
        )

        qualification = find(
            r"ESSENTIAL QUALIFICATIONS:\s*"
            r"(.+?)(?=\s+DUTIES:|\s+DESIRABLE QUALIFICATIONS:|"
            r"\s+NOTE 1:)",
            block
        )

        experience = find(
            r"\(B\)\s*EXPERIENCE:\s*(.+?)(?=\s+NOTE 1:|"
            r"\s+DUTIES:)",
            block
        )

        probation = find(
            r"PROBATION:\s*(.+?)(?=\s+HEADQUARTERS:)",
            block
        )

        headquarters = find(
            r"HEADQUARTERS:\s*(.+?)(?=\s+ANY OTHER CONDITIONS:|$)",
            block
        )

        reservation = find(
            r"RESERVATION POSITION:\s*(.+?)(?=\s+The post|\s+Category-wise)",
            block
        )

        jobs.append({
            "vacancy_number": vacancy_number,
            "post_name": post,
            "vacancy_count": vacancy_count,
            "department": department,
            "reservation": reservation,
            "pay_scale": pay_scale,
            "age_limit": age_limit,
            "qualification": qualification,
            "experience": experience,
            "probation": probation,
            "headquarters": headquarters
        })

    return jobs


def main():

    print("=" * 70)
    print("UPSC JOB SCRAPER")
    print("=" * 70)

    advertisements = get_advertisement_pdfs()

    print(
        "Advertisement PDFs found:",
        len(advertisements)
    )

    all_jobs = []

    for advertisement in advertisements:

        print()
        print(
            "PROCESSING:",
            advertisement["advertisement"]
        )

        try:

            pdf = download_pdf(
                advertisement["pdf_url"]
            )

            text = extract_pdf_text(pdf)

            jobs = parse_jobs(text)

            print(
                "Jobs found:",
                len(jobs)
            )

            for job in jobs:

                job["organization"] = (
                    "Union Public Service Commission"
                )

                job["category"] = "UPSC"

                job["advertisement"] = (
                    advertisement["advertisement"]
                )

                job["notification_url"] = (
                    advertisement["pdf_url"]
                )

                job["source"] = BASE_URL

                all_jobs.append(job)

        except Exception as error:

            print(
                "ERROR:",
                str(error)
            )

    result = {
        "source": BASE_URL,
        "organization": (
            "Union Public Service Commission"
        ),
        "scraped_at": datetime.now(
            timezone.utc
        ).isoformat(),
        "total_jobs": len(all_jobs),
        "jobs": all_jobs
    }

    with open(
        "data.json",
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            result,
            file,
            ensure_ascii=False,
            indent=2
        )

    print()
    print("=" * 70)
    print(
        "TOTAL JOBS EXTRACTED:",
        len(all_jobs)
    )
    print("=" * 70)


if __name__ == "__main__":
    main()
