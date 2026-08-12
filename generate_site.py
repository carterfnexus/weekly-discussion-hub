import os
import re
from pathlib import Path
import urllib.request
import feedparser
from google import genai
from google.genai import types
from jinja2 import Environment, FileSystemLoader

client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))

# Working feeds with validated YouTube channel IDs
FEEDS = [
    {
        "category": "🇸🇬 Singapore & Asia",
        "url": "https://www.youtube.com/feeds/videos.xml?channel_id=UC83JT2sFZlC6O3I1yL54Fxg",  # CNA
        "is_video": True
    },
    {
        "category": "🔬 Science & Tech",
        "url": "https://www.youtube.com/feeds/videos.xml?channel_id=UCsXVk37bltHxD1rDPwtNM8Q",  # Kurzgesagt
        "is_video": True
    },
    {
        "category": "🌍 World News",
        "url": "https://www.youtube.com/feeds/videos.xml?channel_id=UC16niRr50-MSBwiO3YDb3RA",  # BBC News YT
        "is_video": True
    },
    {
        "category": "⚽ Sports & Culture",
        "url": "https://www.youtube.com/feeds/videos.xml?channel_id=UCNAf1k0yIjyGu3k9BwAg3lg",  # Sky Sports
        "is_video": True
    },
    {
        "category": "💡 Global Economy",
        "url": "http://feeds.bbci.co.uk/news/business/rss.xml",
        "is_video": False
    }
]

def fetch_feed_data(url):
    """Bypasses GitHub cloud blocks by fetching RSS via urllib with a Browser User-Agent."""
    try:
        req = urllib.request.Request(
            url, 
            headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'}
        )
        with urllib.request.urlopen(req, timeout=10) as response:
            return response.read()
    except Exception as e:
        print(f"Error fetching URL {url}: {e}")
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
    except Exception as e:
        print(f"AI Call error: {e}")
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
            print(f"No entries found for {feed_info['category']}")
            continue
            
        entry = parsed.entries[0]
        title = entry.title
        link = entry.link
        
        raw_summary = getattr(entry, 'summary', getattr(entry, 'description', 'No summary available.'))
        cleaned_summary = re.sub('<[^<]+?>', '', raw_summary).strip()
        cleaned_summary = (cleaned_summary[:200] + '...') if len(cleaned_summary) > 200 else cleaned_summary
        
        video_id = extract_youtube_id(entry) if feed_info["is_video"] else None
        
        print(f"Successfully retrieved: {title} (Video ID: {video_id})")
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
        
    print(f"Successfully generated index.html with {len(processed_items)} items.")

if __name__ == "__main__":
    main()
