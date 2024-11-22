from playwright.sync_api import sync_playwright
import csv
import time
import random
import requests
from urllib.parse import urlparse, parse_qs
from bs4 import BeautifulSoup

# Base URLs for categories
categories = {
    "ruang_tamu_keluarga": "https://www.tokopedia.com/p/rumah-tangga/ruang-tamu-keluarga",
    "tempat_penyimpanan": "https://www.tokopedia.com/p/rumah-tangga/tempat-penyimpanan",
    "elektronik_dapur": "https://www.tokopedia.com/p/elektronik/elektronik-dapur",
    "elektronik_rumah_tangga": "https://www.tokopedia.com/p/elektronik/elektronik-rumah-tangga",
}

# Utility functions
def extract_direct_link(tracking_url):
    try:
        parsed_url = urlparse(tracking_url)
        query_params = parse_qs(parsed_url.query)
        return query_params.get('r', [tracking_url])[0]
    except Exception as e:
        print(f"Error processing URL: {tracking_url} - {e}")
        return tracking_url

def extract_price_number(price_text):
    return int(''.join(filter(str.isdigit, price_text)))

def extract_sold_number(sold_text):
    if "rb" in sold_text.lower():
        match = re.search(r"([\d,]+)\s*rb", sold_text, re.IGNORECASE)
        if match:
            number = float(match.group(1).replace(",", "."))
            return int(number * 1000)
    else:
        match = re.search(r"\d+", sold_text)
        if match:
            return int(match.group(0))
    return "N/A"

# Playwright setup and scraping logic
def get_product_details(product_url):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)  # Headless mode for Streamlit Cloud
        page = browser.new_page()
        page.goto(product_url)
        page.wait_for_selector('body')  # Ensure the page loads

        # Extract stock sold
        stock_sold = "N/A"
        try:
            sold_element = page.query_selector("#pdp_comp-product_content > div > div.css-bczdt6 > div > p:nth-child(1)")
            if sold_element:
                stock_sold = sold_element.inner_text()
        except Exception as e:
            print(f"Error extracting stock sold: {e}")

        # Extract seller name
        seller_name = "N/A"
        seller_selectors = [
            "h2.css-1wdzqxj-unf-heading",
            "#pdp_comp-shop_credibility > div.css-1mxqisk > div.css-3v9jg2 > div.css-i9gxme > div > a > h2",
            "a[data-testid='llbPDPFooterShopName']"
        ]

        for selector in seller_selectors:
            try:
                seller_element = page.query_selector(selector)
                if seller_element:
                    seller_name = seller_element.inner_text()
                    break
            except:
                continue

        browser.close()
        return stock_sold, seller_name


# Streamlit interface and scraping process
import streamlit as st

st.title('Tokoijo Scraper')

base_url = st.text_input('Enter the base URL for scraping:', 'https://www.tokopedia.com/p/rumah-tangga/ruang-tamu-keluarga')
pages_to_scrape = st.number_input('Enter the number of pages to scrape:', min_value=1, max_value=100, value=5)

if st.button('Start Scraping'):
    # Prepare CSV for storing scraped data
    csv_urls = f"scraped_urls.csv"
    csv_details = f"scraped_details.csv"

    with open(csv_urls, mode="w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(["Product Name", "Price", "Product URL"])
        
        for page in range(1, pages_to_scrape + 1):
            st.write(f"Scraping page {page}...")
            url = f"{base_url}?page={page}"

            try:
                response = requests.get(url, headers={
                    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36'
                })

                if response.status_code == 200:
                    soup = BeautifulSoup(response.text, "html.parser")
                    product_elements = soup.find_all("a", class_="css-54k5sq")

                    if not product_elements:
                        st.write(f"No more products found on page {page}")
                        break

                    for element in product_elements:
                        tracking_url = element.get("href", "N/A")
                        product_url = extract_direct_link(tracking_url)
                        product_name = element.find("span", class_="css-20kt3o")
                        product_name = product_name.get_text(strip=True) if product_name else "N/A"
                        product_price = element.find("span", class_="css-o5uqvq")
                        if product_price:
                            product_price = extract_price_number(product_price.get_text(strip=True))
                        else:
                            product_price = "N/A"

                        writer.writerow([product_name, product_price, product_url])

                else:
                    st.write(f"Failed to retrieve page {page}. Status code: {response.status_code}")
            except requests.exceptions.RequestException as e:
                st.write(f"Error accessing page {page}: {e}")

    # Scrape additional details (stock sold and seller name)
    with open(csv_urls, mode="r", encoding="utf-8") as infile, open(csv_details, mode="w", newline="", encoding="utf-8") as outfile:
        reader = csv.DictReader(infile)
        writer = csv.writer(outfile)
        writer.writerow(["Product Name", "Price", "Stock Sold", "Seller Name", "Product URL"])

        for row in reader:
            product_name = row["Product Name"]
            product_url = row["Product URL"]
            price = row["Price"]
            stock_sold, seller_name = get_product_details(product_url)
            writer.writerow([product_name, price, stock_sold, seller_name, product_url])

    st.write(f"Scraping completed. Data saved to {csv_details}")
