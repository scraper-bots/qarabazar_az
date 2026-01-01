#!/usr/bin/env python3
"""
QaraBazar.az Robust Async Real Estate Market Scraper
Crash-proof scraper with automatic retry, resume, and error handling
"""

import asyncio
import aiohttp
from bs4 import BeautifulSoup
import csv
import json
import time
import signal
import sys
from datetime import datetime
from typing import List, Dict, Optional, Set
import re
from pathlib import Path
import logging
from dataclasses import dataclass, asdict
import pickle


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('scraper.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


@dataclass
class ScraperState:
    """State for resume functionality"""
    completed_pages: Set[int]
    completed_details: Set[str]
    listings: List[Dict]
    details: List[Dict]
    start_page: int
    end_page: int
    scrape_details: bool


class RobustAsyncScraper:
    """Crash-proof async scraper with retry and resume capabilities"""

    def __init__(self, max_concurrent: int = 10, delay: float = 0.5, max_retries: int = 3):
        """
        Initialize robust scraper

        Args:
            max_concurrent: Maximum concurrent requests
            delay: Delay between requests in seconds
            max_retries: Maximum retry attempts for failed requests
        """
        self.base_url = "https://qarabazar.az"
        self.max_concurrent = max_concurrent
        self.delay = delay
        self.max_retries = max_retries
        self.semaphore = asyncio.Semaphore(max_concurrent)

        self.state_file = Path("scraper_state.pkl")
        self.output_dir = Path("scraped_data")
        self.output_dir.mkdir(exist_ok=True)

        self.state: Optional[ScraperState] = None
        self.shutdown_requested = False

        # Statistics
        self.stats = {
            'total_listings': 0,
            'total_details': 0,
            'errors': 0,
            'retries': 0,
            'start_time': None
        }

        # Register signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)

    def signal_handler(self, signum, frame):
        """Handle shutdown signals gracefully"""
        logger.warning(f"\n🛑 Received shutdown signal ({signum}). Saving progress...")
        self.shutdown_requested = True

    def save_state(self):
        """Save current state for resume"""
        if self.state:
            try:
                with open(self.state_file, 'wb') as f:
                    pickle.dump(self.state, f)
                logger.info(f"💾 State saved to {self.state_file}")
            except Exception as e:
                logger.error(f"Failed to save state: {e}")

    def load_state(self) -> Optional[ScraperState]:
        """Load saved state if exists"""
        if self.state_file.exists():
            try:
                with open(self.state_file, 'rb') as f:
                    state = pickle.load(f)
                logger.info(f"📂 Loaded previous state: {len(state.completed_pages)} pages completed")
                return state
            except Exception as e:
                logger.error(f"Failed to load state: {e}")
                return None
        return None

    def clear_state(self):
        """Clear saved state"""
        if self.state_file.exists():
            self.state_file.unlink()
            logger.info("🗑️  Cleared saved state")

    async def fetch_with_retry(self, session: aiohttp.ClientSession, url: str) -> Optional[str]:
        """
        Fetch a page with automatic retry

        Args:
            session: aiohttp session
            url: URL to fetch

        Returns:
            HTML content or None if all retries failed
        """
        async with self.semaphore:
            for attempt in range(self.max_retries):
                if self.shutdown_requested:
                    return None

                try:
                    await asyncio.sleep(self.delay)
                    async with session.get(
                        url,
                        timeout=aiohttp.ClientTimeout(total=30)
                    ) as response:
                        response.raise_for_status()
                        return await response.text()

                except asyncio.TimeoutError:
                    logger.warning(f"⏱️  Timeout on {url} (attempt {attempt + 1}/{self.max_retries})")
                    self.stats['retries'] += 1
                    if attempt < self.max_retries - 1:
                        await asyncio.sleep(2 ** attempt)  # Exponential backoff
                except aiohttp.ClientError as e:
                    logger.warning(f"🌐 Network error on {url}: {e} (attempt {attempt + 1}/{self.max_retries})")
                    self.stats['retries'] += 1
                    if attempt < self.max_retries - 1:
                        await asyncio.sleep(2 ** attempt)
                except Exception as e:
                    logger.error(f"❌ Unexpected error on {url}: {e}")
                    self.stats['errors'] += 1
                    break

            logger.error(f"❌ Failed to fetch {url} after {self.max_retries} attempts")
            self.stats['errors'] += 1
            return None

    def parse_price(self, price_text: str) -> tuple[Optional[int], str]:
        """Parse price from text"""
        if not price_text:
            return None, None

        price_text_clean = price_text.replace(' ', '').replace('\xa0', '')
        price_match = re.search(r'([\d,]+)', price_text_clean)
        numeric_price = None
        if price_match:
            try:
                numeric_price = int(price_match.group(1).replace(',', ''))
            except:
                pass

        currency = None
        if 'azn' in price_text.lower() or 'manat' in price_text.lower():
            currency = 'AZN'
        elif '$' in price_text or 'dollar' in price_text.lower():
            currency = 'USD'
        elif '€' in price_text or 'euro' in price_text.lower():
            currency = 'EUR'

        return numeric_price, currency

    def parse_date(self, date_text: str) -> Optional[str]:
        """Parse and normalize date"""
        if not date_text:
            return None

        months = {
            'yanvar': '01', 'fevral': '02', 'mart': '03', 'aprel': '04',
            'may': '05', 'iyun': '06', 'iyul': '07', 'avqust': '08',
            'sentyabr': '09', 'oktyabr': '10', 'noyabr': '11', 'dekabr': '12'
        }

        date_text = date_text.strip().lower()

        for month_name, month_num in months.items():
            if month_name in date_text:
                parts = date_text.split()
                if len(parts) >= 3:
                    try:
                        day = parts[0].zfill(2)
                        year = parts[2]
                        return f"{year}-{month_num}-{day}"
                    except:
                        pass

        return date_text

    def extract_property_specs(self, listing_div) -> Dict:
        """Extract all property specifications"""
        specs = {}

        for span in listing_div.find_all('span'):
            span_class = ' '.join(span.get('class', []))

            if 'Elan növü' in span_class:
                specs['listing_type'] = span.get_text(strip=True)
            elif 'Otaq sayı' in span_class:
                room_text = span.get_text(strip=True)
                specs['rooms'] = room_text
                room_match = re.search(r'(\d+)', room_text)
                if room_match:
                    specs['rooms_numeric'] = int(room_match.group(1))
            elif 'Sahəsi' in span_class or 'Sahəsi (kv.m)' in span_class:
                area_text = span.get_text(strip=True)
                specs['area'] = area_text
                area_match = re.search(r'([\d.]+)', area_text)
                if area_match:
                    specs['area_sqm'] = float(area_match.group(1))
            elif 'Mərtəbə' in span_class and 'Mərtəbəli' not in span_class:
                floor_text = span.get_text(strip=True)
                specs['floor'] = floor_text
                floor_match = re.search(r'(\d+)', floor_text)
                if floor_match:
                    specs['floor_numeric'] = int(floor_match.group(1))
            elif 'Mərtəbəli bina' in span_class:
                total_floors_text = span.get_text(strip=True)
                specs['total_floors'] = total_floors_text
                floors_match = re.search(r'(\d+)', total_floors_text)
                if floors_match:
                    specs['total_floors_numeric'] = int(floors_match.group(1))
            elif 'Tikili növü' in span_class:
                specs['building_type'] = span.get_text(strip=True)
            elif 'Kupça-Çıxarış' in span_class:
                specs['ownership_document'] = span.get_text(strip=True)
            elif 'ELAN VERƏN' in span_class:
                seller_type = span.get_text(strip=True)
                specs['seller_type'] = seller_type
                if 'sahibi' in seller_type.lower():
                    specs['seller_category'] = 'owner'
                elif 'makler' in seller_type.lower() or 'vasitəçi' in seller_type.lower():
                    specs['seller_category'] = 'agent'
                else:
                    specs['seller_category'] = 'other'

        return specs

    async def extract_listing_summary(self, listing_div, page_num: int) -> Optional[Dict]:
        """Extract comprehensive market data from listing"""
        try:
            data = {
                'source_page': page_num,
                'scraped_at': datetime.now().isoformat()
            }

            # Title and URL
            title_elem = listing_div.select_one('a.title_synopsis_adv')
            if title_elem:
                data['title'] = title_elem.get_text(strip=True)
                data['detail_url'] = title_elem.get('href', '')
                if data['detail_url'] and not data['detail_url'].startswith('http'):
                    data['detail_url'] = self.base_url + data['detail_url']

            # Price
            price_elem = listing_div.select_one('.value_cost_adv')
            if price_elem:
                price_text = price_elem.get_text(strip=True)
                numeric_price, currency = self.parse_price(price_text)
                data['price'] = numeric_price
                data['currency'] = currency
                data['price_text'] = price_text

            # Category
            category_elem = listing_div.select_one('.block_name_category_adv')
            if category_elem:
                category_text = category_elem.get_text(strip=True)
                data['category'] = category_text

                category_lower = category_text.lower()
                if 'kiraye' in category_lower or 'icare' in category_lower:
                    data['transaction_type'] = 'rent'
                elif 'satılan' in category_lower or 'satilan' in category_lower:
                    data['transaction_type'] = 'sale'
                else:
                    data['transaction_type'] = 'other'

                if 'torpaq' in category_lower:
                    data['property_type'] = 'land'
                elif 'həyət' in category_lower or 'heyet' in category_lower or 'villa' in category_lower:
                    data['property_type'] = 'house'
                elif 'obyekt' in category_lower or 'ofis' in category_lower:
                    data['property_type'] = 'commercial'
                elif 'mənzil' in category_lower or 'menzil' in category_lower or 'tikili' in category_lower:
                    data['property_type'] = 'apartment'
                else:
                    data['property_type'] = 'other'

            # Location
            location_elem = listing_div.select_one('.block_name_region_adv_search')
            if location_elem:
                location_text = location_elem.get_text(strip=True)
                data['location_full'] = location_text

                if '♦' in location_text:
                    parts = [p.strip() for p in location_text.split('♦')]
                    data['city'] = parts[0] if len(parts) > 0 else None
                    data['district'] = parts[1] if len(parts) > 1 else None
                elif 'Bakı' in location_text:
                    data['city'] = 'Bakı'
                    district_match = re.search(r'Bakı\s+(.+)', location_text)
                    if district_match:
                        data['district'] = district_match.group(1).strip()
                else:
                    data['city'] = location_text

            # Date
            date_elem = listing_div.select_one('.value_data_advert')
            if date_elem:
                date_text = date_elem.get_text(strip=True)
                data['listing_date_raw'] = date_text
                data['listing_date'] = self.parse_date(date_text)

            # Ad number
            ad_num_elem = listing_div.find(string=re.compile(r'Elan\s*№\s*\d+'))
            if ad_num_elem:
                ad_match = re.search(r'(\d+)', ad_num_elem)
                if ad_match:
                    data['ad_id'] = ad_match.group(1)

            # Image count
            img_count_elem = listing_div.select_one('.image-count-search span')
            if img_count_elem:
                try:
                    data['image_count'] = int(img_count_elem.get_text(strip=True))
                except:
                    data['image_count'] = None

            # Short description
            desc_elem = listing_div.select_one('.short-text-ads')
            if desc_elem:
                data['short_description'] = desc_elem.get_text(strip=True)

            # Property specifications
            specs = self.extract_property_specs(listing_div)
            data.update(specs)

            # Calculate price per sqm
            if data.get('price') and data.get('area_sqm'):
                data['price_per_sqm'] = round(data['price'] / data['area_sqm'], 2)

            return data

        except Exception as e:
            logger.error(f"Error extracting listing on page {page_num}: {e}")
            self.stats['errors'] += 1
            return None

    async def scrape_listing_page(self, session: aiohttp.ClientSession, page_num: int) -> List[Dict]:
        """Scrape one listing page with error handling"""
        if self.shutdown_requested:
            return []

        url = f"{self.base_url}/elanlar/ev-emlak/num{page_num}.html"
        logger.info(f"📄 Scraping page {page_num}...")

        html = await self.fetch_with_retry(session, url)
        if not html:
            return []

        try:
            soup = BeautifulSoup(html, 'html.parser')
            listing_divs = soup.select('.block_one_synopsis_advert')

            logger.info(f"✅ Found {len(listing_divs)} listings on page {page_num}")

            listings = []
            for listing_div in listing_divs:
                if self.shutdown_requested:
                    break

                data = await self.extract_listing_summary(listing_div, page_num)
                if data:
                    listings.append(data)

            self.stats['total_listings'] += len(listings)
            return listings

        except Exception as e:
            logger.error(f"Error parsing page {page_num}: {e}")
            self.stats['errors'] += 1
            return []

    async def scrape_all_listings(self, start_page: int = 1, end_page: int = 25,
                                   resume: bool = True) -> List[Dict]:
        """Scrape all listing pages with resume capability"""
        self.stats['start_time'] = time.time()

        # Load or create state
        if resume:
            self.state = self.load_state()

        if self.state is None:
            self.state = ScraperState(
                completed_pages=set(),
                completed_details=set(),
                listings=[],
                details=[],
                start_page=start_page,
                end_page=end_page,
                scrape_details=False
            )

        # Determine which pages to scrape
        pages_to_scrape = [
            p for p in range(start_page, end_page + 1)
            if p not in self.state.completed_pages
        ]

        if not pages_to_scrape:
            logger.info("✅ All pages already scraped!")
            return self.state.listings

        logger.info(f"\n🚀 Starting scrape: {len(pages_to_scrape)} pages remaining")
        logger.info(f"⚙️  Max concurrent: {self.max_concurrent}, Delay: {self.delay}s\n")

        async with aiohttp.ClientSession(
            headers={'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'},
            connector=aiohttp.TCPConnector(limit=self.max_concurrent, force_close=True)
        ) as session:
            for page_num in pages_to_scrape:
                if self.shutdown_requested:
                    logger.warning("🛑 Shutdown requested, saving progress...")
                    break

                try:
                    listings = await self.scrape_listing_page(session, page_num)
                    self.state.listings.extend(listings)
                    self.state.completed_pages.add(page_num)

                    # Save state periodically (every 5 pages)
                    if len(self.state.completed_pages) % 5 == 0:
                        self.save_state()
                        logger.info(f"💾 Progress saved ({len(self.state.completed_pages)}/{end_page} pages)")

                except Exception as e:
                    logger.error(f"Error on page {page_num}: {e}")
                    self.stats['errors'] += 1
                    continue

        # Final save
        self.save_state()

        elapsed = time.time() - self.stats['start_time']
        logger.info(f"\n✨ Listing scrape completed in {elapsed:.2f} seconds")
        logger.info(f"📊 Total listings: {self.stats['total_listings']}")
        logger.info(f"🔄 Retries: {self.stats['retries']}")
        logger.info(f"❌ Errors: {self.stats['errors']}")

        return self.state.listings

    def save_to_csv(self, data: List[Dict], filename: str):
        """Save data to CSV with error handling"""
        try:
            if not data:
                logger.warning("No data to save")
                return

            # Flatten nested dicts
            flattened_data = []
            for item in data:
                flat_item = {}
                for key, value in item.items():
                    if isinstance(value, dict):
                        for nested_key, nested_value in value.items():
                            flat_item[f"{key}_{nested_key}"] = nested_value
                    else:
                        flat_item[key] = value
                flattened_data.append(flat_item)

            # Get all field names
            fieldnames = set()
            for item in flattened_data:
                fieldnames.update(item.keys())
            fieldnames = sorted(fieldnames)

            filepath = self.output_dir / filename
            with open(filepath, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(flattened_data)

            logger.info(f"💾 Saved {len(data)} records to {filepath}")

        except Exception as e:
            logger.error(f"Error saving CSV: {e}")

    def save_to_json(self, data: List[Dict], filename: str):
        """Save data to JSON with error handling"""
        try:
            filepath = self.output_dir / filename
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

            logger.info(f"💾 Saved {len(data)} records to {filepath}")

        except Exception as e:
            logger.error(f"Error saving JSON: {e}")


async def main():
    """Main execution function"""
    print("=" * 60)
    print("QaraBazar.az Robust Async Real Estate Market Scraper")
    print("=" * 60)

    # Initialize scraper
    scraper = RobustAsyncScraper(
        max_concurrent=10,
        delay=0.5,
        max_retries=3
    )

    # Check for existing state
    existing_state = scraper.load_state()
    if existing_state:
        try:
            resume = input("\n📂 Found previous progress. Resume from where you left off? (y/n): ").lower().strip()
        except EOFError:
            # Non-interactive mode, default to yes
            resume = 'y'
            logger.info("Running in non-interactive mode, resuming from saved state")

        if resume != 'y':
            scraper.clear_state()
            existing_state = None

    # Scrape listings
    try:
        listings = await scraper.scrape_all_listings(start_page=1, end_page=25, resume=True)

        # Save results (CSV only)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        csv_filename = f"listings_{timestamp}.csv"
        scraper.save_to_csv(listings, csv_filename)

        # Clear state on successful completion
        if not scraper.shutdown_requested:
            scraper.clear_state()

        print("\n" + "=" * 60)
        print("✅ Scraping completed successfully!")
        print(f"📁 CSV saved: scraped_data/{csv_filename}")
        print(f"📊 Total properties: {len(listings)}")
        print("=" * 60)

    except KeyboardInterrupt:
        logger.warning("\n🛑 Interrupted by user. Progress saved.")
    except Exception as e:
        logger.error(f"\n❌ Unexpected error: {e}")
        logger.info("💾 Progress saved. You can resume later.")
    finally:
        scraper.save_state()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Goodbye!")
        sys.exit(0)
