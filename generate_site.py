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

# Initialize Gemini Client using environment variable
client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))

# Standard Safety Threshold Settings for Classroom Content
SAFETY_SETTINGS = [
    types.SafetySetting(
        category=types.HarmCategory.HARM_CATEGORY_HATE_SPEECH,
        threshold=types.HarmBlockThreshold.BLOCK_LOW_AND_ABOVE,
    ),
    types.SafetySetting(
        category=types.HarmCategory.HARM_CATEGORY_HARASSMENT,
        threshold=types.HarmBlockThreshold.BLOCK_LOW_AND_ABOVE,
    ),
    types.SafetySetting(
        category=types.HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT,
        threshold=types.HarmBlockThreshold.BLOCK_LOW_AND_ABOVE,
    ),
    types.SafetySetting(
        category=types.HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT,
        threshold=types.HarmBlockThreshold.BLOCK_LOW_AND_ABOVE,
    ),
]

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

def is_age_appropriate(title, summary):
    """Failsafe moderation check to ensure content is suitable for international school students."""
    sensitive_topics = [
        r"\bmurder\b", r"\bkilled\b", r"\bkilling\b", r"\bbombing\b", r"\bbomb\b", 
        r"\bexplosion\b", r"\bair strike\b", r"\bairstrike\b", r"\bwar\b", r"\bwarfare\b",
        r"\bpalestine\b", r"\bpalestinian\b", r"\bisrael\b", r"\bisraeli\b", r"\bgaza\b",
        r"\bukraine\b", r"\bukrainian\b", r"\brussia\b", r"\brussian invasion\b",
        r"\bhostage\b", r"\bcasualty\b", r"\bcasualties\b", r"\bterrorist\b", r"\bterrorism\b",
        r"\bconflict\b", r"\bmilitary strike\b", r"\bsuicide\b", r"\bgraphic\b",
        r"\bporn\b", r"\bexplicit\b", r"\bgore\b", r"\bnsfw\b", r"\bsexual assault\b"
    ]
    
    combined_text = f"{title} {summary}".lower()
    for pattern in sensitive_topics:
        if re.search(pattern, combined_text):
            print(f"🚫 Sensitive Topic Filtered ('{pattern}'): {title[:40]}...")
            return False

    prompt = f"""
    You are a content filter for a highly diverse, international school setting (students aged 16 and under).

    Title: {title}
    Summary: {summary}

    Determine if this topic should be EXCLUDED from a general classroom discussion wall.
    EXCLUDE (appropriate = false) if the content mentions active war, military conflicts, geopolitical violence, graphic topics, or casualties.
    ALLOW (appropriate = true) for general world affairs, technology, climate, space, science, philosophy, economics, culture, and positive educational news.

    Return JSON: {{"appropriate": true}} or {{"appropriate": false}}
    """
    try:
        response = client.models.generate_content(
            model="models/gemini-flash-latest",
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                safety_settings=SAFETY_SETTINGS,
                response_schema={
                    "type": "OBJECT",
                    "properties": {
                        "appropriate": {"type": "BOOLEAN"}
                    },
                    "required": ["appropriate"]
                }
            )
        )
        data = json.loads(response.text)
        return data.get("appropriate", True)
    except Exception as e:
        print(f"⚠️ Moderation Check failed, falling back to safe regex: {e}")
        return True

def generate_ai_widgets_by_type():
    """Generates distinct, isolated pools for each specific activity category."""
    categories = [
        {"type": "🌐 Flag & Country Quiz", "key": "flag", "count": 10},
        {"type": "🧩 Quick Riddle", "key": "riddle", "count": 10},
        {"type": "😄 Classroom Joke", "key": "joke", "count": 10},
        {"type": "💡 Did You Know?", "key": "fact", "count": 10},
        {"type": "🔢 60-Second Math Challenge", "key": "math", "count": 10},
        {"type": "💬 Quote of the Week", "key": "quote", "count": 10},
    ]

    widget_pools = {}

    for cat in categories:
        prompt = f"""
        Create {cat['count']} distinct, highly engaging form-time activities strictly of the type "{cat['type']}" for 16-year-old international school students.

        Return a JSON array of objects with keys:
        - "type": "{cat['type']}"
        - "title": Main question, setup, or quote
        - "answer": The answer/punchline (or empty string for facts/quotes)
        - "flag_code": 2-letter ISO country code (ONLY if type is "🌐 Flag & Country Quiz", e.g. "sg", "jp", "fr", "br", "de", "gb", "us", "in", "au", "ca", "mx", "kr", "it", "es", "ch"). Otherwise empty string.
        """
        try:
            response = client.models.generate_content(
                model="models/gemini-flash-latest",
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    safety_settings=SAFETY_SETTINGS,
                    response_schema={
                        "type": "ARRAY",
                        "items": {
                            "type": "OBJECT",
                            "properties": {
                                "type": {"type": "STRING"},
                                "title": {"type": "STRING"},
                                "answer": {"type": "STRING"},
                                "flag_code": {"type": "STRING"}
                            },
                            "required": ["type", "title", "answer", "flag_code"]
                        }
                    }
                )
            )
            items = json.loads(response.text)
            for item in items:
                item["is_widget"] = True
                item["widget_key"] = cat["key"]
                if item.get("flag_code"):
                    code = item["flag_code"].lower().strip()
                    item["flag_image_url"] = f"https://flagcdn.com/w320/{code}.png"
                else:
                    item["flag_image_url"] = None

            widget_pools[cat["key"]] = items
            print(f"✅ Generated dedicated pool for: {cat['type']}")
            time.sleep(2)
        except Exception as e:
            print(f"⚠️ Error generating pool for {cat['type']}: {e}")
            widget_pools[cat["key"]] = []

    return widget_pools

def generate_smart_fallback_prompts(title, summary):
    text = f"{title} {summary}".lower()
    if any(k in text for k in ["ai", "tech", "data", "digital", "algorithm", "cyber"]):
        q1 = "How should regulatory bodies balance rapid technological innovation against ethics and public safety here?"
        q2 = "What long-term skills or adaptations will the future workforce need in response to this shift?"
    elif any(k in text for k in ["climate", "environment", "energy", "nature", "green", "pylon", "carbon"]):
        q1 = "What economic or societal trade-offs must local communities accept to support the environmental goals mentioned?"
        q2 = "Is individual consumer behavior or central government regulation more effective in addressing this issue?"
    elif any(k in text for k in ["economy", "bill", "price", "market", "cost", "business", "tax"]):
        q1 = "How might the financial changes discussed impact lower-income versus higher-income groups differently?"
        q2 = "What broader economic risks or opportunities does this development create for global markets?"
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
                safety_settings=SAFETY_SETTINGS,
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
        print(f"✅ Discussion starters created for: {title[:30]}...")
        return [data["question_1"], data["question_2"]]
        
    except Exception as e:
        print(f"⚠️ Prompt generation error for '{title[:30]}...': {e}")
        return generate_smart_fallback_prompts(title, summary)

def main():
    processed_items = []
    
    # Generate category-specific pools
    pools = generate_ai_widgets_by_type()
    
    # Pop the first element from each pool to act as the initial display card
    initial_widgets = {
        "flag": pools["flag"].pop(0) if pools["flag"] else None,
        "riddle": pools["riddle"].pop(0) if pools["riddle"] else None,
        "joke": pools["joke"].pop(0) if pools["joke"] else None,
        "fact": pools["fact"].pop(0) if pools["fact"] else None,
        "math": pools["math"].pop(0) if pools["math"] else None,
        "quote": pools["quote"].pop(0) if pools["quote"] else None,
    }

    widget_keys_order = ["flag", "riddle", "joke", "fact", "math", "quote"]
    widget_idx = 0

    for i, feed_info in enumerate(FEEDS):
        print(f"Fetching: {feed_info['category']}...")
        raw_xml = fetch_feed_data(feed_info["url"])
        if not raw_xml:
            continue
            
        parsed = feedparser.parse(raw_xml)
        if not parsed.entries:
            continue
            
        # Check top 5 entries to find a safe article
        selected_entry = None
        cleaned_summary = ""

        for entry in parsed.entries[:5]:
            title = getattr(entry, 'title', 'Untitled Entry')
            raw_summary = getattr(entry, 'summary', getattr(entry, 'description', 'Read or listen for full details.'))
            candidate_summary = re.sub('<[^<]+?>', '', raw_summary).strip()
            candidate_summary = (candidate_summary[:200] + '...') if len(candidate_summary) > 200 else candidate_summary

            if is_age_appropriate(title, candidate_summary):
                selected_entry = entry
                cleaned_summary = candidate_summary
                break
            else:
                print(f"⚠️ Skipping sensitive entry in {feed_info['category']}: '{title[:30]}...'")

        if not selected_entry:
            continue

        title = getattr(selected_entry, 'title', 'Untitled Entry')
        link = getattr(selected_entry, 'link', '#')
        if link == '#' and hasattr(selected_entry, 'links') and len(selected_entry.links) > 0:
            link = selected_entry.links[0].get('href', '#')

        video_id = extract_youtube_id(selected_entry) if feed_info["is_video"] else None
        image_url = extract_image_url(selected_entry, getattr(selected_entry, 'summary', '')) if not video_id else None

        prompts = generate_discussion_prompts(title, cleaned_summary)
        time.sleep(3)

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

        # Inject a category-specific widget every 3 feed items
        if (i + 1) % 3 == 0 and widget_idx < len(widget_keys_order):
            key = widget_keys_order[widget_idx]
            if initial_widgets[key]:
                processed_items.append(initial_widgets[key])
            widget_idx += 1

    base_dir = Path(__file__).resolve().parent
    templates_dir = base_dir / "templates"

    env = Environment(loader=FileSystemLoader(str(templates_dir)))
    template_name = "index_template.html" if (templates_dir / "index_template.html").exists() else "index.html"
    template = env.get_template(template_name)

    output_html = template.render(
        items=processed_items,
        widget_pools_json=json.dumps(pools)
    )

    with open(base_dir / "index.html", "w", encoding="utf-8") as f:
        f.write(output_html)
        
    print(f"Successfully generated page with dedicated category pools!")

if __name__ == "__main__":
    main()
