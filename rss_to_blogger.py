import feedparser
import os
from datetime import datetime
import re
from groq import Groq
from dotenv import load_dotenv
import markdownify
import html
import time
from googleapiclient.discovery import build
from oauth2client.client import flow_from_clientsecrets
from oauth2client.file import Storage
from oauth2client.tools import run_flow
from concurrent.futures import ThreadPoolExecutor
import threading
import json

# Load environment variables
load_dotenv()

# Configuration
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
BLOGGER_BLOG_ID = os.getenv("BLOGGER_BLOG_ID")
BLOGGER_BLOG_URL = os.getenv("BLOGGER_BLOG_URL")

RSS_FEEDS = [
    "https://www.channelstv.com/feed/",                          # Nigerian News - Channels TV
    "https://edition.cnn.com/rss/edition.rss",                   # Global News - CNN
    "https://www.theverge.com/rss/index.xml",                    # Technology & Innovation - The Verge
    "https://nairametrics.com/feed/",                            # Nigerian Business & Economy - Nairametrics
    "https://www.tmz.com/rss.xml"                                # Celebrity Gossip & Entertainment - TMZ
]

# Custom prompts for each feed
CUSTOM_PROMPTS = {
    "https://www.channelstv.com/feed/": """
    You are an expert journalist specializing in Nigerian news. Rewrite the article with a professional, informative tone, focusing on clarity and local context. Ensure the content is at least 500 words, SEO-optimized with relevant keywords (e.g., Nigeria, news, politics), and includes a meta description (150-160 characters) and 3-5 SEO keywords. Maintain the core idea but enrich with Nigerian cultural or political insights. The tone should suit {BLOGGER_BLOG_URL}.
    """,
    "https://edition.cnn.com/rss/edition.rss": """
    You are a global news writer with a formal, authoritative tone. Rewrite the article to be engaging, SEO-optimized, and at least 500 words. Use keywords like global news, international, or current events. Include a meta description (150-160 characters) and 3-5 SEO keywords. Add global context or analysis to enrich the content, suitable for {BLOGGER_BLOG_URL}.
    """,
    "https://www.theverge.com/rss/index.xml": """
    You are a tech journalist with a conversational yet professional tone. Rewrite the article to be SEO-optimized, at least 500 words, focusing on tech trends and innovation. Use keywords like technology, gadgets, or innovation. Include a meta description (150-160 characters) and 3-5 SEO keywords. Enrich with industry insights, suitable for {BLOGGER_BLOG_URL}.
    """,
    "https://nairametrics.com/feed/": """
    You are a business analyst specializing in Nigerian economics. Rewrite the article with a professional, data-driven tone, at least 500 words, SEO-optimized with keywords like Nigeria, economy, finance. Include a meta description (150-160 characters) and 3-5 SEO keywords. Add economic context or market trends, suitable for {BLOGGER_BLOG_URL}.
    """,
    "https://www.tmz.com/rss.xml": """
    You are an entertainment writer with a lively, sensational tone. Rewrite the article to be engaging, SEO-optimized, at least 500 words, using keywords like celebrity, gossip, entertainment. Include a meta description (150-160 characters) and 3-5 SEO keywords. Enrich with celebrity context or pop culture trends, suitable for {BLOGGER_BLOG_URL}.
    """
}

ARTICLES_PER_FEED = 4
SKIPPED_LOG = "skipped_articles.txt"
MIN_WORD_COUNT = 15  # Initial minimum word count
CREDENTIALS_FILE = "blogger_credentials.json"
CLIENT_SECRETS_FILE = "client_secrets.json"
MAX_WORKERS = 3  # Number of parallel workers for feed processing

# Thread-safe set for processed articles
PROCESSED_ARTICLES = set()
PROCESSED_ARTICLES_LOCK = threading.Lock()

# Summary metrics
SUMMARY = {
    "feeds_processed": 0,
    "articles_posted": 0,
    "duplicates_skipped": 0,
    "images_included": 0,
    "articles_skipped_short": 0
}

# Validate environment variables
if not GROQ_API_KEY:
    print("Error: GROQ_API_KEY is not set in .env file.")
    exit(1)
if not BLOGGER_BLOG_ID:
    print("Error: BLOGGER_BLOG_ID is not set in .env file.")
    exit(1)
if not BLOGGER_BLOG_URL:
    print("Error: BLOGGER_BLOG_URL is not set in .env file.")
    exit(1)

# Initialize GROQ client
try:
    client = Groq(api_key=GROQ_API_KEY)
except Exception as e:
    print(f"Failed to initialize Groq client: {e}")
    exit(1)

# Initialize Blogger API client
def get_blogger_service():
    """Authenticate and return Blogger API service."""
    scope = "https://www.googleapis.com/auth/blogger"
    storage = Storage(CREDENTIALS_FILE)
    credentials = storage.get()

    if not credentials or credentials.invalid:
        try:
            flow = flow_from_clientsecrets(CLIENT_SECRETS_FILE, scope=scope)
        except Exception as e:
            print(f"Error loading client_secrets.json: {type(e).__name__}: {str(e)}")
            print("Ensure client_secrets.json exists and contains valid OAuth credentials.")
            exit(1)
        
        try:
            credentials = run_flow(flow, storage)
        except Exception as e:
            print(f"Authentication failed: {type(e).__name__}: {str(e)}")
            print("Check your Google Cloud Console OAuth settings and try again.")
            exit(1)

    try:
        return build("blogger", "v3", credentials=credentials)
    except Exception as e:
        print(f"Failed to initialize Blogger API service: {type(e).__name__}: {str(e)}")
        exit(1)

def clean_text(text):
    """Clean HTML and markdown from text and decode entities."""
    text = markdownify.markdownify(text, heading_style="ATX")
    text = html.unescape(text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text

def log_skipped_article(title, feed_url, reason, word_count=None):
    """Log details of skipped articles to a file."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(SKIPPED_LOG, "a", encoding="utf-8") as f:
        if word_count is not None:
            f.write(f"[{timestamp}] Skipped article: '{title}' from {feed_url} (Reason: {reason}, Word count: {word_count})\n")
        else:
            f.write(f"[{timestamp}] Skipped article: '{title}' from {feed_url} (Reason: {reason})\n")

def extract_image(entry):
    """Extract image URL from RSS entry."""
    # Check common RSS fields for images
    for field in ["media_content", "media_thumbnail", "enclosure"]:
        if field in entry and isinstance(entry[field], list) and entry[field]:
            url = entry[field][0].get("url", "")
            if url and url.lower().endswith((".jpg", ".jpeg", ".png", ".gif")):
                return url
    return None

def rewrite_article(title, content, source_url, feed_url):
    """Rewrite article using GROQ for originality and SEO optimization."""
    # Use custom prompt if available, otherwise default
    base_prompt = CUSTOM_PROMPTS.get(feed_url, """
    You are an expert content writer specializing in SEO and original content creation. Rewrite the following article to be unique, engaging, and optimized for SEO. Ensure the content is at least 500 words, includes relevant keywords naturally, and follows best SEO practices (e.g., clear headings, meta description, keyword density of 1-2%). Maintain the core idea but rephrase entirely to avoid plagiarism. If the original content is brief, enrich it with relevant context, such as the celebrity's recent projects, industry trends, or cultural impact, to create a comprehensive article. The tone should be professional yet conversational, suitable for a blog like {BLOGGER_BLOG_URL}. Provide a meta description (150-160 characters) and suggest 3-5 SEO keywords, the best custom permalink (slug should be short, descriptive, keyword-focused, and SEO-friendly).
    """)
    
    prompt = f"""
    {base_prompt.strip()}

    Original Title: {title}
    Original Content: {content[:1500]}... (full content may be longer)
    Source URL: {source_url}

    Output format:
    Title: [Rewritten Title]
    Meta Description: [SEO-friendly meta description]
    Keywords: [3-5 SEO keywords]
    Content: [Rewritten article content]
    """
    
    try:
        response = client.chat.completions.create(
            messages=[
                {"role": "system", "content": "You are a professional content writer."},
                {"role": "user", "content": prompt}
            ],
            model="llama3-70b-8192",
            temperature=0.7,
            max_tokens=2000
        )
        
        rewritten_content = response.choices[0].message.content
        title_match = re.search(r"Title: (.*?)\n", rewritten_content)
        meta_desc_match = re.search(r"Meta Description: (.*?)\n", rewritten_content)
        keywords_match = re.search(r"Keywords: (.*?)\n", rewritten_content)
        content_match = re.search(r"Content: (.*)", rewritten_content, re.DOTALL)
        
        return {
            "title": title_match.group(1) if title_match else title,
            "meta_description": meta_desc_match.group(1) if meta_desc_match else "",
            "keywords": keywords_match.group(1) if keywords_match else "",
            "content": content_match.group(1).strip() if content_match else rewritten_content
        }
    except Exception as e:
        print(f"Error rewriting article '{title}': {e}")
        return None

def post_to_blogger_draft(article_data, feed_title, image_url=None, source_url=""):
    """Post rewritten article to Blogger as a draft."""
    try:
        # Validate article_data
        if not article_data or not isinstance(article_data, dict):
            print("Error: Invalid article_data provided.")
            return None
        required_fields = ["title", "content"]
        for field in required_fields:
            if field not in article_data or not article_data[field]:
                print(f"Error: Missing or empty '{field}' in article_data.")
                return None

        print(f"Attempting to post article: {article_data['title']}")
        
        # Add image to content if available
        if image_url:
            article_data["content"] = f'<img src="{image_url}" alt="{article_data["title"]}" style="max-width:100%;height:auto;"><br>{article_data["content"]}'
            with PROCESSED_ARTICLES_LOCK:
                SUMMARY["images_included"] += 1
        # Add source attribution
        article_data["content"] += f'<br><br><small>Source: <a href="{source_url}">{feed_title}</a></small>'
        
        blogger_service = get_blogger_service()
        posts = blogger_service.posts()
        
        # Prepare post data
        post_body = {
            "kind": "blogger#post",
            "blog": {"id": BLOGGER_BLOG_ID},
            "title": article_data["title"],
            "content": article_data["content"],
            "labels": article_data["keywords"].split(", ") if article_data["keywords"] else ["News"],
            "isDraft": True
        }
        
        # Insert post as draft
        post = posts.insert(blogId=BLOGGER_BLOG_ID, body=post_body, isDraft=True).execute()
        print(f"Posted draft to Blogger: {article_data['title']} (Post ID: {post['id']})")
        
        with PROCESSED_ARTICLES_LOCK:
            SUMMARY["articles_posted"] += 1
        return post["id"]
    except Exception as e:
        print(f"Error posting to Blogger: {type(e).__name__}: {str(e)}")
        import traceback
        traceback.print_exc()
        return None

def process_feed(feed_url, articles_to_fetch, min_word_count=MIN_WORD_COUNT):
    """Process a single RSS feed, rewrite articles, and handle duplicates."""
    feed = feedparser.parse(feed_url)
    feed_title = feed.feed.get("title", "Unknown_Feed").replace(" ", "_")
    articles_processed = 0
    entries = feed.entries
    entry_index = 0
    
    while articles_processed < articles_to_fetch and entry_index < len(entries):
        entry = entries[entry_index]
        entry_index += 1
        title = entry.get("title", "No Title")
        content = entry.get("description", "") or entry.get("content", [{}])[0].get("value", "")
        source_url = entry.get("link", "")
        image_url = extract_image(entry)
        
        # Check for duplicates using title and source_url
        article_identifier = (title, source_url)
        with PROCESSED_ARTICLES_LOCK:
            if article_identifier in PROCESSED_ARTICLES:
                print(f"Skipping duplicate article: {title} from {feed_url}")
                log_skipped_article(title, feed_url, "Duplicate article")
                SUMMARY["duplicates_skipped"] += 1
                continue
        
        # Clean the content
        cleaned_content = clean_text(content)
        word_count = len(cleaned_content.split())
        if word_count < min_word_count:
            print(f"Skipping short article: {title} (Word count: {word_count})")
            log_skipped_article(title, feed_url, "Below word count", word_count)
            with PROCESSED_ARTICLES_LOCK:
                SUMMARY["articles_skipped_short"] += 1
            continue
        
        # Add to processed articles
        with PROCESSED_ARTICLES_LOCK:
            PROCESSED_ARTICLES.add(article_identifier)
        
        # Rewrite article with custom prompt
        rewritten_article = rewrite_article(title, cleaned_content, source_url, feed_url)
        if rewritten_article:
            post_to_blogger_draft(rewritten_article, feed_title, image_url, source_url)
            articles_processed += 1
        
        # Respect API rate limits
        time.sleep(3)
    
    # Retry with no minimum word count if needed
    if articles_processed < articles_to_fetch and min_word_count != -1:
        print(f"Could not fetch {articles_to_fetch} articles from {feed_url} with word count >= {min_word_count}. Retrying with no minimum word count.")
        log_skipped_article("N/A", feed_url, f"Insufficient articles, retrying with min_word_count=-1")
        entry_index = 0
        while articles_processed < articles_to_fetch and entry_index < len(entries):
            entry = entries[entry_index]
            entry_index += 1
            title = entry.get("title", "No Title")
            content = entry.get("description", "") or entry.get("content", [{}])[0].get("value", "")
            source_url = entry.get("link", "")
            image_url = extract_image(entry)
            
            article_identifier = (title, source_url)
            with PROCESSED_ARTICLES_LOCK:
                if article_identifier in PROCESSED_ARTICLES:
                    continue
            
            # Clean the content (no word count check)
            cleaned_content = clean_text(content)
            
            # Add to processed articles
            with PROCESSED_ARTICLES_LOCK:
                PROCESSED_ARTICLES.add(article_identifier)
            
            # Rewrite article
            rewritten_article = rewrite_article(title, cleaned_content, source_url, feed_url)
            if rewritten_article:
                post_to_blogger_draft(rewritten_article, feed_title, image_url, source_url)
                articles_processed += 1
            
            time.sleep(3)
    
    print(f"Processed {articles_processed} articles from {feed_url}")
    with PROCESSED_ARTICLES_LOCK:
        SUMMARY["feeds_processed"] += 1
    return articles_processed

def generate_summary():
    """Generate a summary report of the processing results."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    summary_file = f"summary_{timestamp.replace(':', '-')}.txt"
    with open(summary_file, "w", encoding="utf-8") as f:
        f.write(f"Article Processing Summary - {timestamp}\n")
        f.write(f"=====================================\n")
        f.write(f"Total Feeds Processed: {SUMMARY['feeds_processed']}\n")
        f.write(f"Total Articles Posted: {SUMMARY['articles_posted']}\n")
        f.write(f"Duplicates Skipped: {SUMMARY['duplicates_skipped']}\n")
        f.write(f"Articles Skipped (Short): {SUMMARY['articles_skipped_short']}\n")
        f.write(f"Articles with Images: {SUMMARY['images_included']}\n")
    print(f"Summary written to {summary_file}")

def main():
    """Main function to process all RSS feeds in parallel."""
    print("Starting RSS article generation and Blogger draft posting...")
    
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        executor.map(lambda feed: process_feed(feed, ARTICLES_PER_FEED), RSS_FEEDS)
    
    generate_summary()
    print("Article generation and draft posting completed.")

if __name__ == "__main__":
    main()