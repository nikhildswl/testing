import json
import re
from datetime import datetime, timezone
from urllib.parse import urljoin

import requests
import fitz
from bs4 import BeautifulSoup


BASE_URL = "https://www.upsc.gov.in"
RECRUITMENT_URL = "https://www.upsc.gov.in/recruitment/recruitment-advertisement"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/140.0.0.0 Safari/537.36"
    )
}


def clean(text):
    if not text:
        return ""
    return re.sub(r"\s+", " ", text).strip()


def download_page(url):
    response = requests.get(
        url,
        headers=HEADERS,
        timeout=40
    )
    response.raise_for_status()
    return response.text


def get_latest_advertisements():
    print("Opening UPSC recruitment page...")

    html = download_page(RECRUITMENT_URL)
    soup = BeautifulSoup(html, "lxml")

    advertisements = []

    for link in soup.find_all("a", href=True):

        title = clean(link.get_text(" ", strip=True))
        href = link.get("href", "").strip()

        if not title or not href:
            continue

        full_url = urljoin(BASE_URL, href)

        if ".pdf" not in full_url.lower():
            continue

        if "advertisement" not in title.lower() and "advt" not in title.lower():
            continue

        advertisements.append({
            "advertisement": title,
            "pdf_url": full_url
        })

    # Remove duplicates
    unique = []
    seen = set()

    for item in advertisements:
        if item["pdf_url"] not in seen:
            seen.add(item["pdf_url"])
            unique.append(item)

    return unique


def download_pdf(url):
    print("Downloading PDF:")
    print(url)

    response = requests.get(
        url,
        headers=HEADERS,
        timeout=60
    )

    response.raise_for_status()

    return response.content


def pdf_to_text(pdf_bytes):
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


def find_value(text, pattern):
    match = re.search(
        pattern,
        text,
        flags=re.IGNORECASE
    )

    if not match:
        return None

    return clean(match.group(1))


def parse_vacancies(text):
    """
    UPSC recruitment PDFs generally use:

    1. (Vacancy No. XXXXX) ...
    2. (Vacancy No. XXXXX) ...

    We split the PDF into individual vacancies.
    """

    pattern = r"(?=\d+\.\s*\(Vacancy No\.)"

    blocks = re.split(
        pattern,
        text
    )

    vacancies = []

    for block in blocks:

        block = clean(block)

        if not re.search(
            r"\(Vacancy No\.",
            block,
            re.IGNORECASE
        ):
            continue

        vacancy = parse_single_vacancy(block)

        if vacancy:
            vacancies.append(vacancy)

    return vacancies


def parse_single_vacancy(block):

    vacancy_number = find_value(
        block,
        r"\(Vacancy No\.\s*([0-9]+)"
    )

    if not vacancy_number:
        return None

    # -------------------------------------------------
    # POST NAME + VACANCY COUNT
    # -------------------------------------------------

    post_match = re.search(
        r"\(Vacancy No\.\s*[0-9]+\)\s*"
        r"(.+?)"
        r"(?:\.|,)\s*"
        r"(?:in|under|at)\s+",
        block,
        re.IGNORECASE
    )

    post_name = None
    vacancy_count = None

    if post_match:

        post_name = clean(
            post_match.group(1)
        )

    # Search phrases such as:
    # Four vacancies
    # Sixty vacancies
    # One vacancy
    # 10 vacancies

    vacancy_match = re.search(
        r"(\d+|one|two|three|four|five|six|seven|eight|nine|ten|"
        r"eleven|twelve|thirteen|fourteen|fifteen|sixteen|seventeen|"
        r"eighteen|nineteen|twenty|thirty|forty|fifty|sixty|seventy|"
        r"eighty|ninety|hundred)\s+vacancies?",
        block,
        re.IGNORECASE
    )

    if vacancy_match:
        vacancy_count = clean(
            vacancy_match.group(1)
        )

    # -------------------------------------------------
    # DEPARTMENT / MINISTRY
    # -------------------------------------------------

    department = None

    department_match = re.search(
        r"(?:in|under)\s+(.{5,250}?)"
        r"(?:\.|RESERVATION POSITION:)",
        block,
        re.IGNORECASE
    )

    if department_match:
        department = clean(
            department_match.group(1)
        )

    # -------------------------------------------------
    # PAY SCALE
    # -------------------------------------------------

    pay_scale = find_value(
        block,
        r"PAY SCALE:\s*(.*?)(?=AGE:|ESSENTIAL QUALIFICATIONS:)"
    )

    # -------------------------------------------------
    # AGE
    # -------------------------------------------------

    age_limit = find_value(
        block,
        r"AGE:\s*(.*?)(?=ESSENTIAL QUALIFICATIONS:|DUTIES:)"
    )

    # -------------------------------------------------
    # QUALIFICATION
    # -------------------------------------------------

    qualification = find_value(
        block,
        r"ESSENTIAL QUALIFICATIONS:\s*"
        r"(.*?)(?=DESIRABLE QUALIFICATIONS:|DUTIES:|OTHER DETAILS:)"
    )

    # -------------------------------------------------
    # EXPERIENCE
    # -------------------------------------------------

    experience = None

    experience_match = re.search(
        r"(?:\(B\)\s*EXPERIENCE:|EXPERIENCE:)\s*"
        r"(.*?)(?=DESIRABLE QUALIFICATIONS:|NOTE\s+1:|DUTIES:)",
        block,
        re.IGNORECASE
    )

    if experience_match:
        experience = clean(
            experience_match.group(1)
        )

    # -------------------------------------------------
    # HEADQUARTERS
    # -------------------------------------------------

    headquarters = find_value(
        block,
        r"HEADQUARTERS:\s*(.*?)(?=ANY OTHER CONDITIONS:|$)"
    )

    # -------------------------------------------------
    # PROBATION
    # -------------------------------------------------

    probation = find_value(
        block,
        r"PROBATION:\s*(.*?)(?=HEADQUARTERS:|$)"
    )

    return {
        "vacancy_number": vacancy_number,
        "post_name": post_name,
        "vacancy_count": vacancy_count,
        "department": department,
        "pay_scale": pay_scale,
        "age_limit": age_limit,
        "qualification": qualification,
        "experience": experience,
        "probation": probation,
        "headquarters": headquarters
    }


def main():

    print("=" * 70)
    print("UPSC JOB DETAILS SCRAPER")
    print("=" * 70)

    advertisements = get_latest_advertisements()

    print(
        f"Found {len(advertisements)} recruitment PDF(s)."
    )

    all_jobs = []

    for advertisement in advertisements:

        print()
        print("=" * 70)
        print(
            "ADVERTISEMENT:",
            advertisement["advertisement"]
        )

        try:

            pdf_bytes = download_pdf(
                advertisement["pdf_url"]
            )

            text = pdf_to_text(
                pdf_bytes
            )

            jobs = parse_vacancies(
                text
            )

            print(
                f"Jobs extracted: {len(jobs)}"
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

                job["scraped_at"] = (
                    datetime.now(
                        timezone.utc
                    ).isoformat()
                )

                all_jobs.append(job)

        except Exception as error:

            print(
                "ERROR:",
                error
            )

    # -------------------------------------------------
    # SAVE FINAL DATABASE
    # -------------------------------------------------

    output = {
        "source": BASE_URL,
        "organization": "Union Public Service Commission",
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
            output,
            file,
            ensure_ascii=False,
            indent=2
        )

    print()
    print("=" * 70)
    print("DONE")
    print(
        f"TOTAL JOBS: {len(all_jobs)}"
    )
    print("data.json created")
    print("=" * 70)


if __name__ == "__main__":
    main()
    
