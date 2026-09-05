import os
import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv

from synapse.utils.logger import get_logger
from synapse.utils.llm_utils import generate_content

# Load variables from .env
load_dotenv()

logger = get_logger(__name__)


class NewsScraper:

    def __init__(self):

        guardian_api_key = os.getenv("GUARDIAN_API_KEY")

        if not guardian_api_key:
            raise ValueError(
                "GUARDIAN_API_KEY is missing. Please add it to your .env file."
            )

        self.base_url = (
            "https://content.guardianapis.com/search"
        )

        self.api_key = guardian_api_key

        self.headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/58.0.3029.110 Safari/537.3"
            )
        }

    def extract(self, date):

        def get_main_content(response):

            if not response:
                return ""

            if not getattr(response, "candidates", None):
                return ""

            candidate = response.candidates[0]

            if not candidate:
                return ""

            if not getattr(candidate, "content", None):
                return ""

            parts = getattr(candidate.content, "parts", None)

            if not parts:
                return ""

            return "".join(
                part.text
                for part in parts
                if hasattr(part, "text")
            )

        main_data = []

        try:

            # Guardian API parameters
            params = {
                "section": "technology",
                "tag": "technology/artificialintelligenceai",
                "api-key": self.api_key,
                "from-date": date,
                "to-date": date,
                "page-size": 20
            }

            response = requests.get(
                self.base_url,
                params=params,
                timeout=20
            )

            if response.status_code != 200:

                logger.error(
                    f"Guardian API failed: "
                    f"{response.status_code} - {response.text}"
                )

                return None

            data = response.json()

            total_pages = data["response"]["pages"]

            logger.info(
                f"Found {data['response']['total']} articles "
                f"across {total_pages} page(s)"
            )

            for page in range(1, total_pages + 1):

                params["page"] = page

                response = requests.get(
                    self.base_url,
                    params=params,
                    timeout=20
                )

                if response.status_code != 200:

                    logger.error(
                        f"Failed to get page {page}: "
                        f"{response.status_code}"
                    )

                    continue

                data = response.json()

                articles = data["response"]["results"]

                for article in articles:

                    title = article.get(
                        "webTitle",
                        "Unknown"
                    )

                    url = article.get(
                        "webUrl",
                        ""
                    )

                    section = article.get(
                        "sectionName",
                        "Unknown"
                    )

                    publication_date = article.get(
                        "webPublicationDate",
                        date
                    )

                    # Get article page
                    content_response = requests.get(
                        url,
                        headers=self.headers,
                        timeout=20
                    )

                    if content_response.status_code != 200:

                        logger.warning(
                            f"Could not access article: {url}"
                        )

                        continue

                    soup = BeautifulSoup(
                        content_response.text,
                        "html.parser"
                    )

                    # -----------------------------
                    # SAFE AUTHOR EXTRACTION
                    # -----------------------------

                    author_tag = soup.select_one(
                        'address a[rel="author"]'
                    )

                    if author_tag:

                        author = author_tag.get_text(
                            strip=True
                        )

                    else:

                        author = "Unknown"

                    # -----------------------------
                    # ARTICLE CONTENT
                    # -----------------------------

                    paragraphs = soup.select(
                        "div.article-body-viewer-selector p"
                    )

                    content = "\n".join(
                        p.get_text(strip=True)
                        for p in paragraphs
                    )

                    # If content is empty
                    if not content:

                        logger.warning(
                            f"No content found for article: {title}"
                        )

                        continue

                    # -----------------------------
                    # GENERATE SUMMARY
                    # -----------------------------

                    news_summary = generate_content(
                        prompt_name="summary_prompt",
                        article=content
                    )

                    summary = get_main_content(
                        news_summary
                    )

                    # -----------------------------
                    # STORE ARTICLE
                    # -----------------------------

                    main_data.append({

                        "title": title,

                        "url": url,

                        "section": section,

                        "date": publication_date,

                        "author": author,

                        "content": content,

                        "summary": summary

                    })

            return main_data

        except Exception as e:

            logger.error(
                f"Failed to extract news for {date}: {str(e)}"
            )

            return None