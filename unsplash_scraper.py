#!/usr/bin/env python3.13
"""
Unsplash Image Scraper
"""

import argparse
import time
import random
from pathlib import Path
from camoufox.sync_api import Camoufox

def get_unsplash_images(tag, num_images=5, headless=True):
    """
    Search for a tag on Unsplash and return image URLs.
    """
    url = f"https://unsplash.com/s/photos/{tag}"
    print(f"Searching Unsplash for: {tag}")
    
    with Camoufox(headless=headless) as browser:
        page = browser.new_page()
        try:
            page.goto(url, timeout=0)
            page.wait_for_selector("img", timeout=60000)
        except Exception as e:
            print(f"Error loading Unsplash page: {e}")
            return []

        img_urls = set()
        scroll_attempts = 0
        scroll_attempts_limit = 10

        while len(img_urls) < num_images and scroll_attempts < scroll_attempts_limit:
            page.wait_for_selector("img", timeout=60000)
            img_elements = page.query_selector_all("img")

            for img in img_elements:
                src = img.get_attribute("src")
                # Unsplash images usually have 'images.unsplash.com' in src
                # We want to get a decent resolution. The src usually has params like ?w=...&q=...
                if src and "images.unsplash.com" in src and "profile" not in src:
                    # Clean up URL to get a higher quality version if possible, 
                    # or just take the src as is (it's often responsive)
                    # For Unsplash, we can often just remove the width/quality params to get original or set them high.
                    base_url = src.split('?')[0]
                    high_res_url = f"{base_url}?q=80&fm=jpg&crop=entropy&cs=tinysrgb&w=1080&fit=max"
                    img_urls.add(high_res_url)
                if len(img_urls) >= num_images:
                    break

            # Scroll to the bottom
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            time.sleep(random.uniform(2, 4))
            scroll_attempts += 1

        return list(img_urls)[:num_images]

def main():
    parser = argparse.ArgumentParser(description="Unsplash Image Scraper")
    parser.add_argument("tag", type=str, help="Search tag")
    parser.add_argument("num_images", type=int, help="Number of images to download")
    parser.add_argument("--headless", action="store_true", help="Run browser in headless mode")
    args = parser.parse_args()

    img_urls = get_unsplash_images(args.tag, num_images=args.num_images, headless=args.headless)

    if not img_urls:
        print("No images found.")
        return

    print(f"Found {len(img_urls)} images.")
    for url in img_urls:
        print(url)

if __name__ == "__main__":
    main()
