from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from datetime import datetime
import logging
from typing import Dict, List, Optional
from dataclasses import dataclass

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
        """Initialize the Chrome driver with appropriate options"""
        chrome_options = webdriver.ChromeOptions()
        chrome_options.add_argument('--headless')
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        
        self.driver = webdriver.Chrome(options=chrome_options)
        self.driver.implicitly_wait(10)

    def set_date(self, target_date: datetime) -> bool:
        """Set the date in the date picker"""
        try:
            # Find and fill year, month, day inputs
            year_input = self.driver.find_element(By.ID, "s_year")
            month_input = self.driver.find_element(By.ID, "s_month")
            day_input = self.driver.find_element(By.ID, "s_day")

            # Clear existing values and send new ones
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
        """Click the search button"""
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
        """
        Parse the availability status from a cell
        ○ (circle) = Available (class "mark m01 m01_col" with anchor)
        △ (triangle) = Almost full (class "mark m02 m02_col" with anchor)
        × (cross) = Booked (class "mark m03")
        － (dash) = Not yet open for booking (class "mark" only)
        """
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
        """Get availability for a specific hotel"""
        availability = {}
        
        try:
            # Find all cells for this hotel (10 days worth)
            for day in range(10):
                # Find cells matching the pattern ypro_stock_calendar{row}_{day}
                # We'll need to search through rows to find our hotel
                cell = None
                row = 0
                while row < 30:  # arbitrary limit to prevent infinite loop
                    try:
                        cell_id = f"ypro_stock_calendar{row}_{day}"
                        cell = self.driver.find_element(By.ID, cell_id)
                        # Check if this cell belongs to our hotel
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
        """Main method to check availability"""
        try:
            self.setup_driver()
            self.driver.get(self.base_url)
            
            if not self.set_date(date):
                return AvailabilityResult(date=date, hotels=[], error="Failed to set date")
            
            if not self.click_search():
                return AvailabilityResult(date=date, hotels=[], error="Failed to click search")

            # Wait for results to load
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.CLASS_NAME, "ypro_tbl_cal"))
            )

            hotels = []
            for hotel_id, hotel_name in self.MONITORED_HOTELS.items():
                availability = self.get_hotel_availability(hotel_id)
                hotels.append(Hotel(id=hotel_id, name=hotel_name, availability=availability))

            return AvailabilityResult(date=date, hotels=hotels)

        except TimeoutException:
            return AvailabilityResult(
                date=date,
                hotels=[],
                error="Timeout waiting for results"
            )
        except Exception as e:
            return AvailabilityResult(
                date=date,
                hotels=[],
                error=f"Unexpected error: {str(e)}"
            )
        finally:
            if self.driver:
                self.driver.quit()

def test_scraper():
    """Test function to verify scraper works"""
    logging.basicConfig(level=logging.INFO)
    scraper = ShirakawagoBotScraper()
    test_date = datetime(2024, 12, 21)
    result = scraper.check_availability(test_date)
    
    print(f"\nResults for {test_date.date()}:")
    if result.error:
        print(f"Error: {result.error}")
    else:
        for hotel in result.hotels:
            print(f"\n{hotel.name}:")
            for date, status in hotel.availability.items():
                print(f"  {date}: {status}")

if __name__ == "__main__":
    test_scraper()