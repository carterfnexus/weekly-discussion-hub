import os
import re
import json
import time
from pathlib import Path
import urllib.request
import feedparser
from google import genai
from google.genai import types
from jinja2 import Environment, FileSystemLoader

# Initialize modern Gemini Client
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
    if hasattr(entry, 'media_thumbnail') and len(entry.media_thumbnail) > 0:
        return entry.media_thumbnail[0].get('url')
    if hasattr(entry, 'media_content') and len(entry.media_content) > 0:
        return entry.media_content[0].get('url')
    if hasattr(entry, 'enclosures') and len(entry.enclosures) > 0:
        for enc in entry.enclosures:
            if enc.get('type', '').startswith('image/'):
                return enc.get('href')

    img_match = re.search(r'<img [^>]*src=["\'](https?://[^"\']+)["\']', raw_summary, re.IGNORECASE)
    if img_match:
        return img_match.group(1)

    return None

def generate_smart_fallback_prompts(title, summary):
    text = f"{title} {summary}".lower()
    if any(k in text for k in ["ai", "tech", "data", "digital", "algorithm", "cyber", "device"]):
        q1 = "How should regulatory bodies balance rapid technological innovation against ethics and public safety here?"
        q2 = "What long-term skills or adaptations will the future workforce need in response to this shift?"
    elif any(k in text for k in ["climate", "environment", "energy", "nature", "green", "pylon", "carbon"]):
        q1 = "What economic or societal trade-offs must local communities accept to support the environmental goals mentioned?"
        q2 = "Is individual consumer behavior or central government regulation more effective in addressing this issue?"
    elif any(k in text for k in ["economy", "bill", "price", "market", "cost", "business", "tax", "trade"]):
        q1 = "How might the financial changes discussed impact lower-income versus higher-income groups differently?"
        q2 = "What broader economic risks or opportunities does this development create for global markets?"
    elif any(k in text for k in ["singapore", "asia", "local", "government", "policy"]):
        q1 = "How relevant are the issues raised in this story to Singapore's current social or policy landscape?"
        q2 = "What proactive steps can local decision-makers take to manage this situation effectively?"
    else:
        q1 = "Who are the main stakeholders affected by this development, and how do their priorities conflict?"
        q2 = "If you were advising policy-makers on this issue, what immediate action would you recommend?"
    return [q1, q2]

def generate_discussion_prompts(title, summary):
    prompt_text = f"""
    You are an expert secondary school educator framing classroom discussion starters for 16-year-old Year 11 students in Singapore.

    Analyze this news story:
    Title: {title}
    Summary: {summary}

    Generate 2 unique, highly insightful discussion starters based strictly on this specific story.
    - Question 1: Focus on real-world policy, societal trade-offs, or ethical impact.
    - Question 2: Focus on critical thinking, global perspectives, or future implications.
    - Style: Concise (1-2 sentences), engaging, and vocabulary-appropriate for Year 11.
    """
    try:
        # Dynamically discover which active Flash model is supported by your key
        active_model = "gemini-2.0-flash" # Default fallback
        for m in client.models.list():
            # Grab the first available flash model returned by your key's endpoint
            if "flash" in m.name.lower():
                active_model = m.name
                break

        response = client.models.generate_content(
            model=active_model,
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
        data = json.loads(response.text)
        print(f"✅ Gemini AI generated questions using {active_model} for: {title[:30]}...")
        return [data["question_1"], data["question_2"]]

    except Exception as e:
        print(f"⚠️ Gemini API Error for '{title[:30]}...': {e}")
        return generate_smart_fallback_prompts(title, summary)

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
        
        video_id = extract_youtube_id(entry) if feed_info["is_video"] else None
        image_url = extract_image_url(entry, raw_summary) if not video_id else None

        cleaned_summary = re.sub('<[^<]+?>', '', raw_summary).strip()
        cleaned_summary = (cleaned_summary[:200] + '...') if len(cleaned_summary) > 200 else cleaned_summary
        
        prompts = generate_discussion_prompts(title, cleaned_summary)
        time.sleep(1)

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
        
    print(f"Successfully rendered {len(processed_items)} items!")

if __name__ == "__main__":
    main()
