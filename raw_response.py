import requests

url = "https://api.scrapingbee.com/v1/"
api_key = "1GYHKE0AI5C2JHDT07ZU3ESABQ3UYL1H6NAF3YPO7E8KQ4I85KD7RMK083AX4FPY7E0RA96OQ6PK5248"

response = requests.get(url, params={"api_key": api_key, "url": "https://strategyu.co/free-lessons/"})

print(response.content)
