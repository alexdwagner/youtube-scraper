import requests
import pandas as pd

url = 'https://strategyu.co/free-lessons/'

api_key = '1GYHKE0AI5C2JHDT07ZU3ESABQ3UYL1H6NAF3YPO7E8KQ4I85KD7RMK083AX4FPY7E0RA96OQ6PK5248'

# Send a request to ScrapingBee API to scrape the webpage and get the HTML content
response = requests.get(f'https://app.scrapingbee.com/api/v1/?api_key={api_key}&url={url}&render_js=false')

# Convert the response content to a BeautifulSoup object
from bs4 import BeautifulSoup
soup = BeautifulSoup(response.content, 'html.parser')

# Find all the blog post elements
post_elements = soup.find_all('div', class_='bdp-post')

# Create an empty list to store the post data
posts_data = []

# Loop through each post element to extract the data
for post in post_elements:
    # Extract the post title and URL
    title_element = post.find('h2', class_='bdp-post-title')
    title = title_element.text.strip()
    url = title_element.find('a')['href']
    
    # Send a request to ScrapingBee API to scrape the post page and get the HTML content
    post_response = requests.get(f'https://app.scrapingbee.com/api/v1/?api_key={api_key}&url={url}&render_js=false')
    
    # Convert the response content to a BeautifulSoup object
    post_soup = BeautifulSoup(post_response.content, 'html.parser')
    
    # Extract the post body text
    body_text_element = post_soup.find('div', class_='post-content')
    if body_text_element:
        body_text = body_text_element.text.strip()
    else:
        body_text = ''
    
    # Extract the post image links
    image_links = []
    image_elements = post_soup.find_all('img', class_='size-full')
    for image_element in image_elements:
        image_links.append(image_element['src'])
    
    # Extract the number of comments
    comments_element = post_soup.find('div', class_='comments-count')
    if comments_element:
        comments = comments_element.text.strip()
    else:
        comments = '0 comments'
    
    # Add the post data to the list
    posts_data.append({
        'Title': title,
        'URL': url,
        'Body Text': body_text,
        'Image Links': image_links,
        'Comments': comments
    })

# Convert the list of dictionaries to a Pandas DataFrame
posts_df = pd.DataFrame(posts_data)

# Export the DataFrame to a spreadsheet (CSV)
csv_file_name = 'blog_posts.csv'
posts_df.to_csv(csv_file_name, index=False)

# Print success message
print(f"Successfully created {csv_file_name} with {len(posts_data)} blog posts.")
