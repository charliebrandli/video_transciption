import os
from atlassian import Confluence
import requests


# make sure env variables are set
if not os.getenv("CONFLUENCE_URL"):
    raise RuntimeError("CONFLUENCE_URL is not set")

# create Confluence Client
confluence = Confluence(
    url=os.getenv("CONFLUENCE_URL"),
    username=os.getenv("CONFLUENCE_EMAIL"),
    password=os.getenv("CONFLUENCE_API_TOKEN"))

#get page ID
page_ID = 4225499148 # ID of Test Page with video attachments
page = confluence.get_page_by_id(page_ID)
print(f"Page title: {page['title']}")
print()

# list all attachments on the page
attachments = confluence.get_attachments_from_content(page_ID)
print("Attachments: ")
for att in attachments['results']:
    print(att['title'])
print()

# filter attachments to find video files
video_extensions = (".mp4", ".mov", ".mkv")

video_attachments = [att for att in attachments['results'] if att['title'].lower().endswith(video_extensions)]

print (f"Found {len(video_attachments)} videos: ")
for video in video_attachments:
    print(video['title'])
print()

# download video files
os.makedirs('./downloaded_videos', exist_ok=True) # make a directory for the downloaded videos

for video in video_attachments:
    print(f"Downloading {video['title']}")  
    download_url = confluence.url + video['_links']['download']
    response = requests.get(download_url, auth=(confluence.username, confluence.password))

    with open(f'./downloaded_videos/{video["title"]}', 'wb') as file:
        file.write(response.content)
    print(f"Downloaded {video['title']}")
print(f"Downloaded {len(video_attachments)} videos")
print()
