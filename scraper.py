import json
from datetime import datetime, timezone
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup


BASE_URL = "https://www.upsc.gov.in"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/140.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}


def get_page(url):
    print(f"Opening: {url}")

    response = requests.get(
        url,
        headers=HEADERS,
        timeout=30
    )

    print(f"Status: {response.status_code}")

    response.raise_for_status()

    return response.text


def clean_text(text):
    return " ".join(text.split())


def extract_links(html, page_url):
    soup = BeautifulSoup(html, "lxml")

    results = []
    seen = set()

    for link in soup.find_all("a", href=True):

        title = clean_text(link.get_text(" ", strip=True))
        href = link.get("href")

        if not title or not href:
            continue

        full_url = urljoin(page_url, href)

        if full_url in seen:
            continue

        seen.add(full_url)

        results.append({
            "title": title,
            "url": full_url
        })

    return results


def scrape_section(name, url):

    try:

        html = get_page(url)

        links = extract_links(
            html,
            url
        )

        print(
            f"{name}: {len(links)} links found"
        )

        return {
            "section": name,
            "url": url,
            "links": links
        }

    except Exception as error:

        print(
            f"Error scraping {name}: {error}"
        )

        return {
            "section": name,
            "url": url,
            "links": [],
            "error": str(error)
        }


def main():

    print("=" * 60)
    print("UPSC GOVERNMENT JOB SCRAPER")
    print("=" * 60)

    sections = {

        "What's New":
            f"{BASE_URL}/whats-new",

        "Active Examinations":
            f"{BASE_URL}/examinations/active-exams",

        "Admit Cards":
            f"{BASE_URL}/e-admit-cards",

        "Written Results":
            f"{BASE_URL}/exams-related-info/written-result",

        "Final Results":
            f"{BASE_URL}/exams-related-info/final-result",

        "Recruitment Advertisements":
            f"{BASE_URL}/recruitment/recruitment-advertisements",

        "Answer Keys":
            f"{BASE_URL}/exams-related-info/answer-key",

    }

    output = {
        "source": BASE_URL,
        "scraped_at": datetime.now(
            timezone.utc
        ).isoformat(),

        "sections": []
    }

    for name, url in sections.items():

        data = scrape_section(
            name,
            url
        )

        output["sections"].append(data)

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

    print("=" * 60)
    print("SUCCESS")
    print("data.json created")
    print("=" * 60)


if __name__ == "__main__":
    main()
