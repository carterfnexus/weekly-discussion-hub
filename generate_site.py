import os
import re
from pathlib import Path
import urllib.request
import feedparser
from google import genai
from google.genai import types
from jinja2 import Environment, FileSystemLoader

client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))

FEEDS = [
    {
        "category": "🇸🇬 Singapore & Asia News",
        "url": "https://www.channelnewsasia.com/api/v1/rss-outbound-feed?form=cna_rss_singapore",
        "is_video": False
    },
    {
        "category": "🔬 Science & Tech (Video)",
        "url": "https://www.youtube.com/feeds/videos.xml?channel_id=UCsXVk37bltHxD1rDPwtNM8Q",
        "is_video": True
    },
    {
        "category": "🌍 World Headlines",
        "url": "http://feeds.bbci.co.uk/news/world/rss.xml",
        "is_video": False
    },
    {
        "category": "💡 Global Economy",
        "url": "https://search.cnbc.com/rs/search/combinedrender/story?partnerId=wrss01&id=20910258",
        "is_video": False
    },
    {
        "category": "🌱 Climate & Environment",
        "url": "https://www.theguardian.com/environment/rss",
        "is_video": False
    },
    {
        "category": "🦁 Conservation & Wildlife",
        "url": "https://news.mongabay.com/feed/",
        "is_video": False
    },
    {
        "category": "🏢 Architecture & Design",
        "url": "https://www.archdaily.com/feed",
        "is_video": False
    },
    {
        "category": "🎨 Art & Visual Culture",
        "url": "https://www.thecoolhunter.net/feed/",
        "is_video": False
    },
    {
        "category": "🎧 Music & Sound Culture",
        "url": "https://www.youtube.com/feeds/videos.xml?channel_id=UC44KxL04a_7m1uR4O6sU89Q",
        "is_video": True
    },
    {
        "category": "💻 Consumer Tech & Innovation",
        "url": "https://www.theverge.com/rss/index.xml",
        "is_video": False
    }
]

def fetch_feed_data(url):
    try:
        req = urllib.request.Request(
            url, 
            headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
        )
        with urllib.request.urlopen(req, timeout=8) as response:
            return response.read()
    except Exception as e:
        print(f"Error reading feed {url}: {e}")
        return None

def extract_youtube_id(entry):
    if hasattr(entry, 'yt_videoid'):
        return entry.yt_videoid
    if hasattr(entry, 'link'):
        match = re.search(r"(?:v=|\/embed\/|\/watch\?v=|\/v\/|youtu\.be\/|\/shorts\/)([a-zA-Z0-9_-]{11})", entry.link)
        if match:
            return match.group(1)
    return None

def extract_image_url(entry, raw_summary):
    """Extracts lead image URL from media tags or description HTML."""
    # 1. Check media_thumbnail tag
    if hasattr(entry, 'media_thumbnail') and len(entry.media_thumbnail) > 0:
        return entry.media_thumbnail[0].get('url')
    
    # 2. Check media_content tag
    if hasattr(entry, 'media_content') and len(entry.media_content) > 0:
        return entry.media_content[0].get('url')
        
    # 3. Check enclosures tag
    if hasattr(entry, 'enclosures') and len(entry.enclosures) > 0:
        for enc in entry.enclosures:
            if enc.get('type', '').startswith('image/'):
                return enc.get('href')

    # 4. Extract first <img> src tag from summary HTML
    img_match = re.search(r'<img [^>]*src=["\'](https?://[^"\']+)["\']', raw_summary, re.IGNORECASE)
    if img_match:
        return img_match.group(1)

    return None

def generate_discussion_prompts(title, summary):
    prompt_text = f"Analyze for Year 11 Singapore students:\nTitle: {title}\nSummary: {summary}\nGenerate 2 concise room discussion starters."
    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt_text,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema={
                    "type": "OBJECT",
                    "properties": {
                        "question_1": {"type": "STRING"},
                        "question_2": {"type": "STRING"}
                    },
                    "required": ["question_1", "question_2"]
                }
            )
        )
        import json
        data = json.loads(response.text)
        return [data["question_1"], data["question_2"]]
    except Exception:
        return [
            f"What primary societal or policy trade-offs are highlighted in '{title}'?",
            "How might different global or local stakeholders view this development?"
        ]

def main():
    processed_items = []

    for feed_info in FEEDS:
        print(f"Fetching: {feed_info['category']}...")
        raw_xml = fetch_feed_data(feed_info["url"])
        if not raw_xml:
            continue
            
        parsed = feedparser.parse(raw_xml)
        if not parsed.entries:
            continue
            
        entry = parsed.entries[0]
        title = entry.title
        link = entry.link
        
        raw_summary = getattr(entry, 'summary', getattr(entry, 'description', 'Read full article for details.'))
        
        # Extract lead image if it's not a video
        video_id = extract_youtube_id(entry) if feed_info["is_video"] else None
        image_url = extract_image_url(entry, raw_summary) if not video_id else None

        # Clean HTML tags out of summary text
        cleaned_summary = re.sub('<[^<]+?>', '', raw_summary).strip()
        cleaned_summary = (cleaned_summary[:200] + '...') if len(cleaned_summary) > 200 else cleaned_summary
        
        prompts = generate_discussion_prompts(title, cleaned_summary)

        processed_items.append({
            "category": feed_info["category"],
            "title": title,
            "link": link,
            "summary": cleaned_summary,
            "video_id": video_id,
            "image_url": image_url,
            "prompts": prompts
        })

    base_dir = Path(__file__).resolve().parent
    templates_dir = base_dir / "templates"

    env = Environment(loader=FileSystemLoader(str(templates_dir)))
    template_name = "index_template.html" if (templates_dir / "index_template.html").exists() else "index.html"
    template = env.get_template(template_name)
    output_html = template.render(items=processed_items)

    with open(base_dir / "index.html", "w", encoding="utf-8") as f:
        f.write(output_html)

if __name__ == "__main__":
    main()
