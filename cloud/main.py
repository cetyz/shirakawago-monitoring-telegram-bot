import functions_framework
from datetime import datetime
import os
import logging
from dataclasses import dataclass
from typing import Dict, List, Optional
import asyncio

# Telegram imports
from telegram import Bot
from telegram.error import TelegramError

# Selenium imports
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException

# GCP imports
from google.cloud import secretmanager

# function to access secrets from secret manager
def access_secret(secret_name):

    client = secretmanager.SecretManagerServiceClient()
    project_id = 'shirakawago-monitoring'
    name = f"projects/{project_id}/secrets/{secret_name}/versions/latest"
    response = client.access_secret_version(request={"name": name})

    return response.payload.data.decode('UTF-8')

# Data classes
@dataclass
class Hotel:
    id: str
    name: str
    availability: Dict[str, str]

@dataclass
class AvailabilityResult:
    date: datetime
    hotels: List[Hotel]
    error: Optional[str] = None

# Telegram notification class
class TelegramNotifier:
    def __init__(self, token: str, chat_id: str):
        self.bot = Bot(token=token)
        self.chat_id = chat_id
        self.logger = logging.getLogger('shirakawago.telegram')

    async def send_message(self, message: str) -> bool:
        try:
            await self.bot.send_message(
                chat_id=self.chat_id,
                text=message,
                parse_mode='Markdown'
            )
            return True
        except TelegramError as e:
            self.logger.error(f"Failed to send Telegram message: {str(e)}")
            return False

# Scraper class
class ShirakawagoBotScraper:
    MONITORED_HOTELS = {
        '21560043': 'Yokichi',
        '21560029': 'Magoemon',
        '21560055': 'YOSHIRO'
    }
    
    def __init__(self):
        self.logger = logging.getLogger('shirakawago_bot.scraper')
        self.base_url = "https://www6.489pro.com/asp/g/c/calendar.asp?kid=00156&lan=ENG"
        self.driver = None

    def setup_driver(self):
        chrome_options = webdriver.ChromeOptions()
        chrome_options.add_argument('--headless')
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        # Add these options for Cloud Functions environment
        chrome_options.add_argument('--disable-gpu')
        chrome_options.add_argument('--single-process')
        chrome_options.binary_location = '/opt/google/chrome/chrome'
        
        self.driver = webdriver.Chrome(options=chrome_options)
        self.driver.implicitly_wait(10)

    def set_date(self, target_date: datetime) -> bool:
        try:
            year_input = self.driver.find_element(By.ID, "s_year")
            month_input = self.driver.find_element(By.ID, "s_month")
            day_input = self.driver.find_element(By.ID, "s_day")

            year_input.clear()
            year_input.send_keys(str(target_date.year))
            month_input.clear()
            month_input.send_keys(str(target_date.month))
            day_input.clear()
            day_input.send_keys(str(target_date.day))
            return True
        except Exception as e:
            self.logger.error(f"Error setting date: {str(e)}")
            return False

    def click_search(self) -> bool:
        try:
            search_button = self.driver.find_element(
                By.XPATH, 
                "//input[@type='button'][@value='Display the room vacancy by this condition.']"
            )
            search_button.click()
            return True
        except Exception as e:
            self.logger.error(f"Error clicking search: {str(e)}")
            return False

    def parse_availability_status(self, cell) -> str:
        classes = cell.get_attribute('class').split()
        
        if 'm01' in classes and 'm01_col' in classes:
            return "AVAILABLE"
        elif 'm02' in classes and 'm02_col' in classes:
            return "ALMOST_FULL"
        elif 'm03' in classes:
            return "BOOKED"
        else:
            return "NOT_OPEN"

    def get_hotel_availability(self, hotel_id: str) -> Dict[str, str]:
        availability = {}
        
        try:
            for day in range(10):
                cell = None
                row = 0
                while row < 30:
                    try:
                        cell_id = f"ypro_stock_calendar{row}_{day}"
                        cell = self.driver.find_element(By.ID, cell_id)
                        hotel_link = cell.find_element(By.XPATH, "./preceding-sibling::td[@class='cal_gp_hotel']//a")
                        if hotel_id in hotel_link.get_attribute('onclick'):
                            break
                        cell = None
                    except:
                        pass
                    row += 1

                if cell:
                    date_header = self.driver.find_element(
                        By.ID, f"ypro_stock_calendar_header{day}"
                    ).text
                    status = self.parse_availability_status(cell)
                    availability[date_header] = status

        except Exception as e:
            self.logger.error(f"Error getting availability for hotel {hotel_id}: {str(e)}")

        return availability

    def check_availability(self, date: datetime) -> AvailabilityResult:
        try:
            self.setup_driver()
            self.driver.get(self.base_url)
            
            if not self.set_date(date):
                return AvailabilityResult(date=date, hotels=[], error="Failed to set date")
            
            if not self.click_search():
                return AvailabilityResult(date=date, hotels=[], error="Failed to click search")

            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.CLASS_NAME, "ypro_tbl_cal"))
            )

            hotels = []
            for hotel_id, hotel_name in self.MONITORED_HOTELS.items():
                availability = self.get_hotel_availability(hotel_id)
                hotels.append(Hotel(id=hotel_id, name=hotel_name, availability=availability))

            return AvailabilityResult(date=date, hotels=hotels)

        except TimeoutException:
            return AvailabilityResult(date=date, hotels=[], error="Timeout waiting for results")
        except Exception as e:
            return AvailabilityResult(date=date, hotels=[], error=f"Unexpected error: {str(e)}")
        finally:
            if self.driver:
                self.driver.quit()

# Helper functions
def escape_markdown(text: str) -> str:
    special_chars = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
    for char in special_chars:
        text = text.replace(char, f"\\{char}")
    return text

def format_availability_message(result: AvailabilityResult) -> str:
    if result.error:
        return f"❌ Error checking availability: {escape_markdown(result.error)}"
    
    message_parts = [
        f"🏡 *Shirakawago Availability Report*",
        f"Date: {result.date.strftime('%Y-%m-%d')}\n"
    ]
    
    target_date_str = result.date.strftime("%m").lstrip("0") + '/' + result.date.strftime("%d").lstrip("0")
    
    for hotel in result.hotels:
        status = "UNKNOWN"
        for date, avail_status in hotel.availability.items():
            if date.startswith(target_date_str):
                status = avail_status
                break
        
        status_emoji = {
            "AVAILABLE": "⭕⭕⭕⭕⭕",
            "ALMOST_FULL": "⚠⚠⚠⚠⚠⚠",
            "BOOKED": "❌",
            "NOT_OPEN": "➖",
            "UNKNOWN": "❓"
        }.get(status, "❓")
        
        hotel_name = escape_markdown(hotel.name)
        date_str = escape_markdown(target_date_str)
        status_str = escape_markdown(status)
        
        message_parts.append(f"*{hotel_name}*:\n{status_emoji} {status_str}")
    
    return "\n\n".join(message_parts)

# Cloud Function entry point
@functions_framework.http
def check_shirakawago_availability(request):
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    logger = logging.getLogger('shirakawago.function')

    try:
        # Get credentials from secret manager
        token = access_secret('telegram-bot')
        chat_id = access_secret('chat-id')

        if not token or not chat_id:
            raise ValueError("Missing required environment variables")

        # Initialize services
        scraper = ShirakawagoBotScraper()
        notifier = TelegramNotifier(token, chat_id)
        
        # Check availability for specific date
        target_date = datetime(2025, 2, 9)
        logger.info(f"Checking availability for {target_date.date()}")
        
        # Run the async operations
        async def run_check():
            result = scraper.check_availability(target_date)
            message = format_availability_message(result)
            success = await notifier.send_message(message)
            return success

        # Run the async function
        success = asyncio.run(run_check())
        
        if success:
            logger.info("Notification sent successfully!")
            return ('Success', 200)
        else:
            logger.error("Failed to send notification")
            return ('Failed to send notification', 500)

    except Exception as e:
        logger.error(f"Error in cloud function: {str(e)}")
        return (f'Error: {str(e)}', 500)