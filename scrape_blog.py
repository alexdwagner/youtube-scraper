import time
import pandas as pd
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# Define the driver variable
driver = webdriver.Chrome()

def scroll_page(driver, num_scrolls=10, scroll_pause_time=2):
    for _ in range(num_scrolls):
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(scroll_pause_time)

def scrape_post_data(post):
    title = post.select_one('h2.bdp-post-title a').text
    link = post.select_one('h2.bdp-post-title a')['href']
    body_text_element = post.select_one('.entry-content')
    if body_text_element is not None:
        body_text = ' '.join([p.text for p in body_text_element.find_all('p') if p.text])
    else:
        body_text = ""
    return {'title': title, 'link': link, 'body_text': body_text}

def scrape_blog_page(url):
    driver.get(url)
    time.sleep(2)

    # Execute the scroll_page function to load all posts on the page
    scroll_page(driver)

    soup = BeautifulSoup(driver.page_source, 'html.parser')
    posts = soup.select('.bdp-post-grid')

    post_data = [scrape_post_data(post) for post in posts]

    return post_data

blog_url = 'https://strategyu.co/free-lessons/'
posts_data = scrape_blog_page(blog_url)

# Convert the list of dictionaries to a Pandas DataFrame
posts_df = pd.DataFrame(posts_data)

# Export the DataFrame to a spreadsheet (CSV)
csv_file_name = 'blog_posts.csv'
posts_df.to_csv(csv_file_name, index=False)

# Print success message
print(f"Successfully created {csv_file_name} with {len(posts_data)} blog posts.")
