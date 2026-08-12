import os
import re
import feedparser
from google import genai
from jinja2 import Environment, FileSystemLoader

# Initialize Gemini Client
client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))

# Categories & Feeds Configuration
FEEDS = [
    {
        "category": "🇸🇬 Singapore & Asia",
        "url": "https://www.youtube.com/feeds/videos.xml?channel_id=UC83JT2sFZlC6O3I1yL54Fxg",  # CNA Insider
        "is_video": True
    },
    {
        "category": "🔬 Science & Future Tech",
        "url": "https://www.youtube.com/feeds/videos.xml?channel_id=UCsXVk37bltHxD1rDPwtNM8Q",  # Kurzgesagt
        "is_video": True
    },
    {
        "category": "🌍 World & Politics",
        "url": "https://www.youtube.com/feeds/videos.xml?channel_id=UC16niRr50-MSBwiO3YDb3RA",  # BBC News
        "is_video": True
    },
    {
        "category": "⚽ Sports & Culture",
        "url": "https://www.youtube.com/feeds/videos.xml?channel_id=UCNAf1k0yIjyGu3k9BwAg3lg",  # Sky Sports News
        "is_video": True
    },
    {
        "category": "💡 Global Economy",
        "url": "http://feeds.bbci.co.uk/news/business/rss.xml",
        "is_video": False
    }
]

def extract_youtube_id(entry, url):
    """Extracts YouTube ID from feed entry structure or link string."""
    # Method 1: Look for YouTube element ID tag in entry
    if hasattr(entry, 'yt_videoid'):
        return entry.yt_videoid
    
    # Method 2: Regex check on link URL
    match = re.search(r"(?:v=|\/embed\/|\/watch\?v=|\/v\/|youtu\.be\/|\/shorts\/)([a-zA-Z0-9_-]{11})", url)
    if match:
        return match.group(1)
        
    return None

def generate_discussion_prompts(title, summary):
    prompt_text = f"""
    You are an international school educator for 16-year-old Year 11 students in Singapore.
    Analyze this news item:
    Title: {title}
    Summary: {summary}

    Write 2 concise room discussion starters:
    1. A real-world lens question (society, policy, or ethics).
    2. A critical thinking question (TOK/knowledge questions or future implications).
    
    Format: Return ONLY two bullet points starting with '- '.
    """
    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt_text
        )
        lines = response.text.strip().split("\n")
        prompts = [line.lstrip("-* ").strip() for line in lines if line.strip().startswith(("-", "*"))]
        
        if len(prompts) >= 2:
            return prompts[:2]
        return [
            "What are the primary societal or ethical trade-offs highlighted in this story?",
            "How might this development impact different global or local communities?"
        ]
    except Exception as e:
        print(f"Error calling AI: {e}")
        return [
            "What are the main societal or policy implications of this development?",
            "How reliable are the perspectives presented in this story?"
        ]

def main():
    processed_items = []

    for feed_info in FEEDS:
        print(f"Fetching feed: {feed_info['category']}...")
        parsed = feedparser.parse(feed_info["url"])
        
        if not parsed.entries:
            print(f"Warning: Couldn't retrieve items for {feed_info['category']}")
            continue
            
        entry = parsed.entries[0]
        title = entry.title
        link = entry.link
        
        raw_summary = getattr(entry, 'summary', getattr(entry, 'description', 'No summary available.'))
        cleaned_summary = re.sub('<[^<]+?>', '', raw_summary)[:280] + "..."
        
        video_id = extract_youtube_id(entry, link) if feed_info["is_video"] else None
        
        print(f"Processing story: {title} (Video ID: {video_id})")
        prompts = generate_discussion_prompts(title, cleaned_summary)

        processed_items.append({
            "category": feed_info["category"],
            "title": title,
            "link": link,
            "summary": cleaned_summary,
            "video_id": video_id,
            "prompts": prompts
        })

    print("Rendering HTML template...")
    env = Environment(loader=FileSystemLoader("templates"))
    template = env.get_template("index_template.html")
    output_html = template.render(items=processed_items)

    with open("index.html", "w", encoding="utf-8") as f:
        f.write(output_html)
        
    print("Done! index.html generated successfully.")

if __name__ == "__main__":
    main()
