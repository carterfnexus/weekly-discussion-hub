import os
import re
import json
import time
import random
from pathlib import Path
import urllib.request
import feedparser
from google import genai
from google.genai import types
from jinja2 import Environment, FileSystemLoader

# Initialize Gemini Client using environment variable
client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))

FEEDS = [
    # --- Youth & Classroom Current Affairs ---
    {
        "category": "📺 CNN 10 (Student News)",
        "url": "https://www.youtube.com/feeds/videos.xml?channel_id=UCTOoRgpHTjAQPk6Ak70u-pA",
        "is_video": True
    },
    {
        "category": "📰 The Day (Teen News & Debates)",
        "url": "https://theday.co.uk/feed/",
        "is_video": False
    },
    {
        "category": "🎓 BBC Education & Youth News",
        "url": "https://feeds.bbci.co.uk/news/education/rss.xml",
        "is_video": False
    },
    {
        "category": "🎓 NYT Education",
        "url": "https://rss.nytimes.com/services/xml/rss/nyt/Education.xml",
        "is_video": False
    },
    {
        "category": "🇺🇸 PBS NewsHour Headlines",
        "url": "https://www.pbs.org/newshour/feeds/rss/headlines",
        "is_video": False
    },

    # --- Regional & Global News Headlines ---
    {
        "category": "🇸🇬 Singapore & Asia News",
        "url": "https://www.channelnewsasia.com/api/v1/rss-outbound-feed?form=cna_rss_singapore",
        "is_video": False
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

    # --- Technology, Science & Space ---
    {
        "category": "🚀 MIT Technology Review",
        "url": "https://www.technologyreview.com/feed/",
        "is_video": False
    },
    {
        "category": "🌌 NASA Breaking News",
        "url": "https://www.nasa.gov/rss/dyn/breaking_news.rss",
        "is_video": False
    },
    {
        "category": "💻 Consumer Tech & Innovation",
        "url": "https://www.theverge.com/rss/index.xml",
        "is_video": False
    },

    # --- Philosophy, Ethics & Deep Thought ---
    {
        "category": "🤔 Daily Philosophy",
        "url": "https://daily-philosophy.com/index.xml",
        "is_video": False
    },
    {
        "category": "🏛️ Daily Nous (Philosophy & Ethics)",
        "url": "https://dailynous.com/feed/",
        "is_video": False
    },

    # --- Discussion & Debate Podcasts ---
    {
        "category": "🎙️ The Rest Is History (Podcast)",
        "url": "https://feeds.megaphone.fm/GLT4787413333",
        "is_video": False
    },
    {
        "category": "🗣️ The Rest Is Politics: Leading",
        "url": "https://feeds.megaphone.fm/THE7221379133",
        "is_video": False
    },
    {
        "category": "🗞️ The News Agents (Podcast)",
        "url": "https://feeds.captivate.fm/the-news-agents/",
        "is_video": False
    },
    {
        "category": "🎧 BBC Newscast (Podcast)",
        "url": "https://podcasts.files.bbci.co.uk/p052992m.rss",
        "is_video": False
    },

    # --- Environment, Culture & Arts ---
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
    entry_link = getattr(entry, 'link', '')
    if entry_link:
        match = re.search(r"(?:v=|\/embed\/|\/watch\?v=|\/v\/|youtu\.be\/|\/shorts\/)([a-zA-Z0-9_-]{11})", entry_link)
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

def generate_ai_widgets(count=6):
    """Generates dynamic Form Time widgets using a single Gemini batch API call."""
    prompt = f"""
    Create {count} distinct, highly engaging form-time activities for 16-year-old secondary students.
    Return a list of JSON objects with these types:
    1. Riddle (type: "🧩 Quick Riddle", title: question, answer: answer)
    2. Joke (type: "😄 Classroom Joke", title: setup, answer: punchline)
    3. Interesting Fact (type: "💡 Did You Know?", title: mind-blowing fact, answer: empty string)
    4. Country Flag & Trivia (type: "🌐 Flag & Country Quiz", title: flag emoji + question, answer: country name + cool detail)
    5. Math Problem (type: "🔢 60-Second Math Challenge", title: clever brain-teaser math problem, answer: solution)
    6. Inspiring Quote (type: "💬 Quote of the Week", title: inspiring quote + author, answer: empty string)
    """
    try:
        response = client.models.generate_content(
            model="models/gemini-flash-latest",
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema={
                    "type": "ARRAY",
                    "items": {
                        "type": "OBJECT",
                        "properties": {
                            "type": {"type": "STRING"},
                            "title": {"type": "STRING"},
                            "answer": {"type": "STRING"}
                        },
                        "required": ["type", "title", "answer"]
                    }
                }
            )
        )
        widgets = json.loads(response.text)
        for w in widgets:
            w["is_widget"] = True
        print(f"✅ Generated {len(widgets)} AI Form Time Widgets!")
        return widgets
    except Exception as e:
        print(f"⚠️ Widget Generation Error: {e}")
        # Smart fallback widgets in case API lags
        return [
            {"is_widget": True, "type": "🧩 Quick Riddle", "title": "What has to be broken before you can use it?", "answer": "An egg."},
            {"is_widget": True, "type": "💡 Did You Know?", "title": "Honey never spoils. Organisms can't grow in it due to low moisture content.", "answer": ""},
            {"is_widget": True, "type": "🔢 Math Challenge", "title": "If 3 cats catch 3 mice in 3 minutes, how many cats catch 100 mice in 100 minutes?", "answer": "3 cats! Every cat catches 1 mouse every 3 minutes."},
            {"is_widget": True, "type": "🌐 Country Quiz", "title": "🇸🇬 Which country has a flag featuring a crescent moon and 5 white stars?", "answer": "Singapore! The 5 stars represent democracy, peace, progress, justice, and equality."}
        ]

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
    elif any(k in text for k in ["philosophy", "ethics", "moral", "thought", "mind", "justice"]):
        q1 = "What core ethical dilemma or societal principle is at the heart of this perspective?"
        q2 = "How can students apply this line of thinking to real-world personal choices today?"
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

    Analyze this article, video, podcast episode, or educational topic summary:
    Title: {title}
    Summary: {summary}

    Generate 2 unique, highly insightful room discussion starters based strictly on this specific topic.
    - Question 1: Focus on real-world policy, ethical dilemmas, societal trade-offs, or human nature.
    - Question 2: Focus on critical thinking, differing perspectives, or future implications.
    - Style: Concise (1-2 sentences), engaging, and vocabulary-appropriate for Year 11.
    """
    try:
        response = client.models.generate_content(
            model="models/gemini-flash-latest",
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
        print(f"✅ Gemini AI generated questions for: {title[:30]}...")
        return [data["question_1"], data["question_2"]]
        
    except Exception as e:
        print(f"⚠️ Gemini API Error for '{title[:30]}...': {e}")
        return generate_smart_fallback_prompts(title, summary)

def main():
    processed_items = []
    
    # Generate fresh AI Widgets before processing news
    widgets = generate_ai_widgets(count=6)
    widget_idx = 0

    for i, feed_info in enumerate(FEEDS):
        print(f"Fetching: {feed_info['category']}...")
        raw_xml = fetch_feed_data(feed_info["url"])
        if not raw_xml:
            continue
            
        parsed = feedparser.parse(raw_xml)
        if not parsed.entries:
            continue
            
        entry = parsed.entries[0]
        title = getattr(entry, 'title', 'Untitled Entry')
        
        # Safely extract link
        link = getattr(entry, 'link', '#')
        if link == '#' and hasattr(entry, 'links') and len(entry.links) > 0:
            link = entry.links[0].get('href', '#')
        
        raw_summary = getattr(entry, 'summary', getattr(entry, 'description', 'Read or listen for full details.'))
        
        video_id = extract_youtube_id(entry) if feed_info["is_video"] else None
        image_url = extract_image_url(entry, raw_summary) if not video_id else None

        cleaned_summary = re.sub('<[^<]+?>', '', raw_summary).strip()
        cleaned_summary = (cleaned_summary[:200] + '...') if len(cleaned_summary) > 200 else cleaned_summary
        
        prompts = generate_discussion_prompts(title, cleaned_summary)
        
        # Pacing delay (4s) to keep free-tier rate limits safe
        time.sleep(4)

        processed_items.append({
            "category": feed_info["category"],
            "title": title,
            "link": link,
            "summary": cleaned_summary,
            "video_id": video_id,
            "image_url": image_url,
            "prompts": prompts,
            "is_widget": False
        })

        # Inject a fresh AI widget after every 3 news cards
        if (i + 1) % 3 == 0 and widget_idx < len(widgets):
            processed_items.append(widgets[widget_idx])
            widget_idx += 1

    base_dir = Path(__file__).resolve().parent
    templates_dir = base_dir / "templates"

    env = Environment(loader=FileSystemLoader(str(templates_dir)))
    template_name = "index_template.html" if (templates_dir / "index_template.html").exists() else "index.html"
    template = env.get_template(template_name)
    output_html = template.render(items=processed_items)

    with open(base_dir / "index.html", "w", encoding="utf-8") as f:
        f.write(output_html)
        
    print(f"Successfully rendered {len(processed_items)} total items (News + Form Time Widgets)!")

if __name__ == "__main__":
    main()
