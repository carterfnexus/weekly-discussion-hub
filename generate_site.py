import os
import re
import feedparser
from google import genai
from jinja2 import Environment, FileSystemLoader

# Initialize Gemini Client using the official SDK
client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))

# Feeds Configuration
FEEDS = [
    {
        "category": "Regional & Local (Asia)",
        "url": "https://www.youtube.com/feeds/videos.xml?channel_id=UC83JT2sFZlC6O3I1yL54Fxg",  # CNA Insider YT
        "is_video": True
    },
    {
        "category": "Global Video News",
        "url": "https://www.youtube.com/feeds/videos.xml?channel_id=UC16niRr50-MSBwiO3YDb3RA",  # BBC News YT
        "is_video": True
    },
    {
        "category": "Global Politics & Society",
        "url": "http://feeds.bbci.co.uk/news/world/rss.xml",
        "is_video": False
    },
    {
        "category": "Science & Tech",
        "url": "https://www.nature.com/nature.rss",
        "is_video": False
    }
]

def extract_youtube_id(url):
    """Extracts YouTube ID from standard watch links."""
    match = re.search(r"v=([a-zA-Z0-9_-]+)", url)
    return match.group(1) if match else None

def generate_discussion_prompts(title, summary):
    """Calls Gemini API to construct two structured classroom discussion questions."""
    prompt_text = f"""
    You are an international school educator for 16-year-old Year 11 students in Singapore.
    Analyze this news item:
    Title: {title}
    Summary: {summary}

    Write 2 concise room discussion starters suitable for a high school classroom session:
    1. A real-world lens question (focusing on society, policy, or ethical trade-offs).
    2. A critical thinking question (focusing on global implications or critical evaluation).
    
    Format output: Return ONLY two bullet points starting with '- '. Do not add introductory or concluding text.
    """
    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt_text
        )
        # Parse output into clean bullet strings
        lines = response.text.strip().split("\n")
        prompts = [line.lstrip("-* ").strip() for line in lines if line.strip().startswith(("-", "*"))]
        
        if len(prompts) >= 2:
            return prompts[:2]
        return [
            "What are the main societal or policy trade-offs highlighted in this story?",
            "How might different stakeholders globally or locally view this development?"
        ]
    except Exception as e:
        print(f"Error calling AI: {e}")
        return [
            "What are the main ethical or practical implications of this event?",
            "How does this development impact society on a local or global level?"
        ]

def main():
    processed_items = []

    for feed_info in FEEDS:
        print(f"Fetching feed: {feed_info['category']}...")
        parsed = feedparser.parse(feed_info["url"])
        
        if not parsed.entries:
            print(f"No entries found for {feed_info['category']}")
            continue
            
        # Get the latest entry from the feed
        entry = parsed.entries[0]
        title = entry.title
        link = entry.link
        
        # Get article summary or description
        raw_summary = getattr(entry, 'summary', getattr(entry, 'description', 'No summary available.'))
        cleaned_summary = re.sub('<[^<]+?>', '', raw_summary)[:300] + "..."  # Strip HTML tags
        
        # Determine if video
        video_id = extract_youtube_id(link) if feed_info["is_video"] else None
        
        print(f"Processing story with AI: {title}")
        prompts = generate_discussion_prompts(title, cleaned_summary)

        processed_items.append({
            "category": feed_info["category"],
            "title": title,
            "link": link,
            "summary": cleaned_summary,
            "video_id": video_id,
            "prompts": prompts
        })

    # Render template using Jinja2
    print("Generating index.html...")
    env = Environment(loader=FileSystemLoader("templates"))
    template = env.get_template("index_template.html")
    output_html = template.render(items=processed_items)

    # Save output to root folder
    with open("index.html", "w", encoding="utf-8") as f:
        f.write(output_html)
        
    print("Done! index.html generated successfully.")

if __name__ == "__main__":
    main()
