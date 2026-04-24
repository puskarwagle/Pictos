#!/usr/bin/env python3.13
"""
Pinterest Image Scraper – all-in-one script.
Usage: python pinterest_scraper.py <username> <tag> <num_images> [--headless]
"""

import argparse
import time
import random
import urllib.request
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

from camoufox.sync_api import Camoufox


def get_image_urls(url, num_images=10, scroll_attempts_limit=250, headless=True):
    """
    Open a Pinterest board URL, scroll down, and collect image URLs.
    Returns a list of image URLs (up to `num_images`).
    """
    with Camoufox(headless=headless) as browser:
        page = browser.new_page()
        try:
            page.goto(url, timeout=0)
            page.wait_for_selector("img", timeout=60000)
        except Exception as e:
            print(f"Error loading page: {e}")
            return []

        img_urls = set()
        scroll_attempts = 0

        while len(img_urls) < num_images and scroll_attempts < scroll_attempts_limit:
            page.wait_for_selector("img", timeout=60000)
            img_elements = page.query_selector_all("img")

            for img in img_elements:
                src = img.get_attribute("src")
                if src and src.startswith("http"):
                    img_urls.add(src)
                if len(img_urls) >= num_images:
                    break

            # Scroll to the bottom
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            print(f"Scrolling: {scroll_attempts}", end="\r")
            t = random.randint(4, 8)
            time.sleep(t)
            scroll_attempts += 1

        return list(img_urls)[:num_images]


def download_image(img_url, output_path):
    """Download a single image from `img_url` to `output_path`."""
    try:
        urllib.request.urlretrieve(img_url, output_path)
        print(f"Downloaded: {output_path.name}", end="\r")
    except Exception as e:
        print(f"Error downloading {output_path.name}: {e}")


def download_images(img_urls, name_img):
    """
    Download all images in `img_urls` to a subfolder `downloaded_images/name_img/`,
    using a thread pool.
    """
    output_dir = Path("downloaded_images") / name_img
    output_dir.mkdir(parents=True, exist_ok=True)

    # Use only the last component of the name for the filename to avoid creating subdirectories
    filename_base = Path(name_img).name

    with ThreadPoolExecutor(max_workers=10) as executor:
        for index, img_url in enumerate(img_urls):
            file_name = output_dir / f"{filename_base}_{index + 1}.jpg"
            executor.submit(download_image, img_url, file_name)


def parse_args():
    parser = argparse.ArgumentParser(description="Pinterest Image Scraper (single script)")
    parser.add_argument("username", type=str, help="Pinterest username or page")
    parser.add_argument("tag", type=str, help="Board tag or name")
    parser.add_argument("num_images", type=int, help="Number of images to download")
    parser.add_argument("--headless", action="store_true", help="Run browser in headless mode")
    return parser.parse_args()


def get_pinterest_images(tag, num_images=5, headless=True):
    """
    Search for a tag on Pinterest and return image URLs.
    """
    url = f"https://www.pinterest.com/search/pins/?q={tag}"
    print(f"Searching Pinterest for: {tag}")
    return get_image_urls(url, num_images=num_images, headless=headless)

def main():
    args = parse_args()
    # Support both username/tag and direct search
    if args.username and args.tag:
        pinterest_url = f"https://www.pinterest.com/{args.username}/{args.tag}/"
        name_img = args.username
    else:
        pinterest_url = f"https://www.pinterest.com/search/pins/?q={args.tag}"
        name_img = args.tag
        
    print(f"Starting with URL: {pinterest_url}")

    img_urls = get_image_urls(
        pinterest_url,
        num_images=args.num_images,
        headless=args.headless,
    )

    if not img_urls:
        print("No images found. Please try again.")
        return

    print(f"\nNumber of images found: {len(img_urls)}")
    download_images(img_urls, name_img)
    print("\nImage download has finished.")


if __name__ == "__main__":
    main()
