import os
import re
import feedparser
from google import genai
from google.genai import types
from jinja2 import Environment, FileSystemLoader

# Initialize Gemini Client
client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))

# Standard YouTube Channel RSS feeds
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
        "category": "💡 Global Economy",
        "url": "http://feeds.bbci.co.uk/news/business/rss.xml",
        "is_video": False
    }
]

def extract_youtube_id(entry):
    """Extracts YouTube ID from feed entry structure."""
    if hasattr(entry, 'yt_videoid'):
        return entry.yt_videoid
    if hasattr(entry, 'link'):
        match = re.search(r"(?:v=|\/embed\/|\/watch\?v=|\/v\/|youtu\.be\/|\/shorts\/)([a-zA-Z0-9_-]{11})", entry.link)
        if match:
            return match.group(1)
    return None

def generate_discussion_prompts(title, summary):
    """Calls Gemini using Structured Outputs to guarantee clean discussion questions."""
    prompt_text = f"""
    You are an educator for 16-year-old Year 11 students in Singapore.
    Analyze this news story:
    Title: {title}
    Summary: {summary}

    Generate 2 engaging room discussion starters:
    1. A real-world lens question (focusing on society, ethics, or policy).
    2. A critical thinking question (focusing on global implications or TOK/knowledge evaluation).
    """
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
        print(f"Error calling AI: {e}")
        return [
            f"What primary societal or policy trade-offs are highlighted in '{title}'?",
            "How might different global or local stakeholders view this development?"
        ]

def main():
    processed_items = []

    for feed_info in FEEDS:
        print(f"Fetching: {feed_info['category']}...")
        parsed = feedparser.parse(
            feed_info["url"], 
            agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        
        if not parsed.entries:
            print(f"Failed to fetch feed for {feed_info['category']}")
            continue
            
        entry = parsed.entries[0]
        title = entry.title
        link = entry.link
        
        raw_summary = getattr(entry, 'summary', getattr(entry, 'description', 'No summary available.'))
        cleaned_summary = re.sub('<[^<]+?>', '', raw_summary).strip()
        cleaned_summary = (cleaned_summary[:250] + '...') if len(cleaned_summary) > 250 else cleaned_summary
        
        video_id = extract_youtube_id(entry) if feed_info["is_video"] else None
        
        print(f"Generating prompts for: {title} (Video ID: {video_id})")
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
