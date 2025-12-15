import os
from atlassian import Confluence

# create Confluence Client
confluence = Confluence(
    url=os.getenv("CONFLUENCE_URL"),
    username=os.getenv("CONFLUENCE_EMAIL"),
    password=os.getenv("CONFLUENCE_API_TOKEN"))

#get page ID
page_ID = 3354460162 # ID of Sprint Reviews 2025 file
page = confluence.get_page_by_id(page_ID)
print(f"Page title: {page['title']}")

# list all attachments on the page
attachments = confluence.get_attachments_from_content(page_ID)
for att in attachments['results']:
    print(att['title'])

# filter attachments to find video files
video_extensions = (".mp4", ".mov", ".mkv")

video_attachments = [att for att in attachments['results'] if att['title'].lower().endswith(video_extensions)]

print (f"found {len(video_attachments)} videos")
for video in video_attachments:
    print(video['title'])

# download video files
os.makedirs('./downloaded_videos', exist_ok=True)

for video in video_attachments:
    print
    content = confluence.get_attachment_content(video['id'])
    with open(f'./downloaded_videos/{video["title"]}', 'wb') as file:
        file.write(content)
    print(f"Downloaded: {video['title']}")