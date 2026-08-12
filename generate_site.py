import os
import re
from pathlib import Path
import urllib.request
import feedparser
from google import genai
from google.genai import types
from jinja2 import Environment, FileSystemLoader

client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))

# Mixed Sources: Major Global News + Select YouTube Channels
FEEDS = [
    {
        "category": "🇸🇬 Singapore & Asia News",
        "url": "https://www.channelnewsasia.com/api/v1/rss-outbound-feed?form=cna_rss_singapore", # CNA Text
        "is_video": False
    },
    {
        "category": "🔬 Science & Tech (Video)",
        "url": "https://www.youtube.com/feeds/videos.xml?channel_id=UCsXVk37bltHxD1rDPwtNM8Q", # Kurzgesagt YT
        "is_video": True
    },
    {
        "category": "🌍 World Headlines",
        "url": "http://feeds.bbci.co.uk/news/world/rss.xml", # BBC News Text
        "is_video": False
    },
    {
        "category": "💡 Global Economy",
        "url": "https://search.cnbc.com/rs/search/combinedrender/story?partnerId=wrss01&id=20910258", # CNBC Business Text
        "is_video": False
    },
    {
        "category": "⚽ Culture & Environment",
        "url": "https://www.theguardian.com/environment/rss", # The Guardian Text
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
            f"What primary societal trade-offs are highlighted in '{title}'?",
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
        cleaned_summary = re.sub('<[^<]+?>', '', raw_summary).strip()
        cleaned_summary = (cleaned_summary[:220] + '...') if len(cleaned_summary) > 220 else cleaned_summary
        
        video_id = extract_youtube_id(entry) if feed_info["is_video"] else None
        prompts = generate_discussion_prompts(title, cleaned_summary)

        processed_items.append({
            "category": feed_info["category"],
            "title": title,
            "link": link,
            "summary": cleaned_summary,
            "video_id": video_id,
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
