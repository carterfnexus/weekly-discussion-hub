import os
import re
from pathlib import Path
import urllib.request
import feedparser
from google import genai
from google.genai import types
from jinja2 import Environment, FileSystemLoader

client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))

# Backup YouTube Video IDs in case YouTube RSS blocks GitHub Actions IPs
FEEDS = [
    {
        "category": "🇸🇬 Singapore & Asia",
        "url": "https://www.youtube.com/feeds/videos.xml?channel_id=UC83JT2sFZlC6O3I1yL54Fxg",
        "fallback_video_id": "83JT2sFZlC6", 
        "fallback_title": "Singapore's Latest Regional and Social Developments",
        "is_video": True
    },
    {
        "category": "🔬 Science & Tech",
        "url": "https://www.youtube.com/feeds/videos.xml?channel_id=UCsXVk37bltHxD1rDPwtNM8Q",
        "fallback_video_id": "sXVk37bltHx", 
        "fallback_title": "How Science & Future Tech Are Reshaping Tomorrow",
        "is_video": True
    },
    {
        "category": "🌍 World News",
        "url": "https://www.youtube.com/feeds/videos.xml?channel_id=UC16niRr50-MSBwiO3YDb3RA",
        "fallback_video_id": "16niRr50MSB", 
        "fallback_title": "Global Headlines and International Relations Update",
        "is_video": True
    },
    {
        "category": "⚽ Sports & Culture",
        "url": "https://www.youtube.com/feeds/videos.xml?channel_id=UCNAf1k0yIjyGu3k9BwAg3lg",
        "fallback_video_id": "NAf1k0yIjyG", 
        "fallback_title": "Cultural Trends and Major Sporting Events Report",
        "is_video": True
    },
    {
        "category": "💡 Global Economy",
        "url": "http://feeds.bbci.co.uk/news/business/rss.xml",
        "fallback_video_id": None,
        "fallback_title": "Global Markets and Economic Policy Changes",
        "is_video": False
    }
]

def fetch_feed_data(url):
    try:
        req = urllib.request.Request(
            url, 
            headers={'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'}
        )
        with urllib.request.urlopen(req, timeout=8) as response:
            return response.read()
    except Exception:
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
            f"What primary societal or policy trade-offs are highlighted in '{title}'?",
            "How might different global or local stakeholders view this development?"
        ]

def main():
    processed_items = []

    for feed_info in FEEDS:
        print(f"Processing: {feed_info['category']}...")
        raw_xml = fetch_feed_data(feed_info["url"])
        parsed = feedparser.parse(raw_xml) if raw_xml else None
        
        if parsed and parsed.entries:
            entry = parsed.entries[0]
            title = entry.title
            link = entry.link
            raw_summary = getattr(entry, 'summary', getattr(entry, 'description', 'Latest updates and discussion details.'))
            cleaned_summary = re.sub('<[^<]+?>', '', raw_summary).strip()
            cleaned_summary = (cleaned_summary[:180] + '...') if len(cleaned_summary) > 180 else cleaned_summary
            video_id = extract_youtube_id(entry) if feed_info["is_video"] else None
        else:
            # Fallback data guarantee if feed is unreachable
            title = feed_info.get("fallback_title", "Weekly Feature")
            link = feed_info["url"]
            cleaned_summary = "Explore this week's featured story, key global updates, and critical thinking starters for the classroom."
            video_id = feed_info.get("fallback_video_id") if feed_info["is_video"] else None

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
        
    print(f"Generated index.html with {len(processed_items)} items!")

if __name__ == "__main__":
    main()
