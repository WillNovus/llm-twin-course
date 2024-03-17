import os
import time
from typing import Dict, List

from bs4 import BeautifulSoup
from bs4.element import Tag
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By

from config import settings
from crawlers.base import BaseAbstractCrawler
from documents import PostDocument
from errors import ImproperlyConfigured


class LinkedInCrawler(BaseAbstractCrawler):

    model = PostDocument

    def set_driver_options(self) -> Options:
        options = Options()
        options.add_experimental_option("detach", True)
        return options

    def extract(self, link: str, **kwargs):
        print(f"Starting to scrape data for profile: {link}")
        self.login()

        soup = self._get_page_content(link)

        data = {
            "Name": self._scrape_section(soup, "h1", class_="text-heading-xlarge"),
            "About": self._scrape_section(soup, "div", class_="display-flex ph5 pv3"),
            "Main Page": self._scrape_section(soup, "div", {"id": "main-content"}),
            "Experience": self._scrape_experience(link),
            "Education": self._scrape_education(link),
        }

        # Scrolling and scraping posts
        self.scroll_page()
        soup = BeautifulSoup(self.driver.page_source, "html.parser")
        post_elements = soup.find_all(
            "div",
            class_="update-components-text relative update-components-update-v2__commentary",
        )
        buttons = soup.find_all("button", class_="update-components-image__image-link")
        post_images = self._extract_image_urls(buttons)

        posts = self._extract_posts(post_elements, post_images)

        self.driver.close()

        self.model.bulk_insert(
            [PostDocument(platform="linkedin", content=post, author_id=kwargs.get("user")) for post in posts]
        )

    def _scrape_section(self, soup: BeautifulSoup, *args, **kwargs):
        """Scrape a specific section of the LinkedIn profile."""
        # Example: Scrape the 'About' section
        parent_div = soup.find(*args, **kwargs)
        return parent_div.get_text(strip=True) if parent_div else ""

    def _extract_image_urls(self, buttons: List[Tag]) -> Dict[str, str]:
        """
        Extracts image URLs from button elements.

        Args:
            buttons (List[Tag]): A list of BeautifulSoup Tag objects representing buttons.

        Returns:
            Dict[str, str]: A dictionary mapping post indexes to image URLs.
        """
        post_images = {}
        for i, button in enumerate(buttons):
            img_tag = button.find("img")
            if img_tag and "src" in img_tag.attrs:
                post_images[f"Post_{i}"] = img_tag["src"]
            else:
                print("No image found in this button")
        return post_images

    def _get_page_content(self, url: str) -> BeautifulSoup:
        """Retrieve the page content of a given URL."""
        self.driver.get(url)
        time.sleep(5)
        return BeautifulSoup(self.driver.page_source, "html.parser")

    def _extract_posts(self, post_elements: List[Tag], post_images: Dict[str, str]) -> Dict[str, Dict[str, str]]:
        """
        Extracts post texts and combines them with their respective images.

        Args:
            post_elements (List[Tag]): A list of BeautifulSoup Tag objects representing post elements.
            post_images (Dict[str, str]): A dictionary containing image URLs mapped by post index.

        Returns:
            Dict[str, Dict[str, str]]: A dictionary containing post data with text and optional image URL.
        """
        posts_data = {}
        for i, post_element in enumerate(post_elements):
            post_text = post_element.get_text(strip=True, separator="\n")
            post_data = {"text": post_text}
            if f"Post_{i}" in post_images:
                post_data["image"] = post_images[f"Post_{i}"]
            posts_data[f"Post_{i}"] = post_data
        return posts_data

    def _scrape_experience(self, profile_url: str):
        """Scrapes the Experience section of the LinkedIn profile."""
        self.driver.get(profile_url + "/details/experience/")
        time.sleep(5)
        soup = BeautifulSoup(self.driver.page_source, "html.parser")
        experience_content = soup.find("section", {"id": "experience-section"})
        return experience_content.get_text(strip=True) if experience_content else ""

    def _scrape_education(self, profile_url: str) -> str:
        self.driver.get(profile_url + "/details/education/")
        time.sleep(5)
        soup = BeautifulSoup(self.driver.page_source, "html.parser")
        education_content = soup.find("section", {"id": "education-section"})
        return education_content.get_text(strip=True) if education_content else ""

    def login(self):
        """Log in to LinkedIn."""
        self.driver.get("https://www.linkedin.com/login")
        if not settings.LINKEDIN_USERNAME and not settings.LINKEDIN_PASSWORD:
            raise ImproperlyConfigured("LinkedIn scraper requires an valid account to perform extraction")

        self.driver.find_element(By.ID, "username").send_keys(settings.LINKEDIN_USERNAME)
        self.driver.find_element(By.ID, "password").send_keys(settings.LINKEDIN_PASSWORD)
        self.driver.find_element(By.CSS_SELECTOR, ".login__form_action_container button").click()


def handler(event, context):
    # Extract the necessary information from the event object
    link = os.getenv("repository_link")
    user = os.getenv("user")

    # Instantiate the GithubCrawler
    crawler = LinkedInCrawler()

    try:
        # Use the crawler to extract data from the repository
        crawler.extract(link=link, user=user)

        return {"statusCode": 200, "body": "Repository processed successfully"}

    except Exception as e:
        # Handle exceptions
        return {"statusCode": 500, "body": f"An error occurred: {str(e)}"}


if __name__ == "__main__":
    crawler = LinkedInCrawler()
    crawler.extract(link="https://www.linkedin.com/in/pauliusztin/", user="Alex")
