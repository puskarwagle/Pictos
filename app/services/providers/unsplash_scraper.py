#!/usr/bin/env python3.13
"""
Unsplash Image Scraper
"""

import asyncio
import argparse
import time
import random
from pathlib import Path
from camoufox.async_api import AsyncCamoufox as Camoufox

import urllib.parse

async def get_unsplash_images_async(tag, num_images=5, headless=True):
    """
    Search for a tag on Unsplash and return image URLs (Async).
    """
    encoded_tag = urllib.parse.quote(tag)
    url = f"https://unsplash.com/s/photos/{encoded_tag}"
    print(f"Searching Unsplash for: {tag}")
    
    async with Camoufox(headless=headless) as browser:
        page = await browser.new_page()
        try:
            await page.goto(url, timeout=0)
            await page.wait_for_selector("img", timeout=60000)
        except Exception as e:
            print(f"Error loading Unsplash page: {e}")
            return []

        img_urls = set()
        scroll_attempts = 0
        scroll_attempts_limit = 10

        while len(img_urls) < num_images and scroll_attempts < scroll_attempts_limit:
            await page.wait_for_selector("img", timeout=60000)
            img_elements = await page.query_selector_all("img")

            for img in img_elements:
                src = await img.get_attribute("src")
                # Unsplash images usually have 'images.unsplash.com' in src
                if src and "images.unsplash.com" in src and "profile" not in src:
                    base_url = src.split('?')[0]
                    high_res_url = f"{base_url}?q=80&fm=jpg&crop=entropy&cs=tinysrgb&w=1080&fit=max"
                    img_urls.add(high_res_url)
                if len(img_urls) >= num_images:
                    break

            # Scroll to the bottom
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await asyncio.sleep(random.uniform(2, 4))
            scroll_attempts += 1

        return list(img_urls)[:num_images]

def get_unsplash_images(tag, num_images=5, headless=True):
    """
    Legacy sync wrapper.
    """
    return asyncio.run(get_unsplash_images_async(tag, num_images, headless))

async def main_async():
    parser = argparse.ArgumentParser(description="Unsplash Image Scraper")
    parser.add_argument("tag", type=str, help="Search tag")
    parser.add_argument("num_images", type=int, help="Number of images to download")
    parser.add_argument("--headless", action="store_true", help="Run browser in headless mode")
    args = parser.parse_args()

    img_urls = await get_unsplash_images_async(args.tag, num_images=args.num_images, headless=args.headless)

    if not img_urls:
        print("No images found.")
        return

    print(f"Found {len(img_urls)} images.")
    for url in img_urls:
        print(url)

if __name__ == "__main__":
    asyncio.run(main_async())
