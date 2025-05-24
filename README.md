# RSS-to-Blogger Automation Tool 📰➡️✍️

**Author**: MrMikeAde  
**GitHub**: [github.com/MrMikeAde](https://github.com/MrMikeAde)  
**Version**: 2.0  
**License**: MIT  

![Workflow Diagram](https://i.imgur.com/example.png) *(Conceptual workflow diagram)*

## 🔍 What This Tool Does

This Python script automatically:
1. **Fetches articles** from multiple RSS feeds (News, Tech, Business, Entertainment)
2. **Rewrites content** using Groq's AI (Llama3-70B) to ensure originality
3. **Optimizes for SEO** with custom prompts per feed category
4. **Posts drafts** to your Blogger account with:
   - Proper attribution
   - Featured images (when available)
   - SEO metadata (titles, descriptions, keywords)

## 🌟 Key Features

| Feature | Implementation Details |
|---------|------------------------|
| Multi-Source Aggregation | Processes 5+ RSS feeds simultaneously |
| AI Content Enhancement | Uses Groq's Llama3-70B for human-like rewriting |
| Category-Specific Optimization | Custom prompts for each feed (News/Tech/Business/etc.) |
| Threaded Processing | Handles 3 feeds in parallel (configurable) |
| Smart Deduplication | Tracks processed articles to avoid reposts |
| Blogger Integration | Automatic draft creation with labels |

## 🛠️ Technical Breakdown

### Core Workflow
```mermaid
graph TD
    A[Fetch RSS Feeds] --> B[Clean/Parse Content]
    B --> C{Word Count Check}
    C -->|≥15 words| D[AI Rewriting]
    C -->|<15 words| E[Log as Skipped]
    D --> F[SEO Enhancement]
    F --> G[Blogger Draft Creation]
    G --> H[Summary Reporting]

AI Rewriting Process
Input Analysis:

Extracts title, body, and source URL

Identifies feed category (for prompt selection)

Prompt Engineering:

python
# Example Tech Article Prompt:
"You are a tech journalist... rewrite focusing on innovation trends...
Include 3-5 keywords like 'AI', 'startups'... Maintain 500+ words"
Output Formatting:

Generates SEO meta description (150-160 chars)

Suggests keyword tags

Ensures natural keyword density (1-2%)

🚀 Custom Recommendations
For Content Creators
Prompt Customization:

python
# Edit CUSTOM_PROMPTS in config to match your brand voice:
"Rewrite as a [friendly/technical/sensational] writer for [your_blog_url]..."
Feed Selection:

Replace default RSS feeds with niche-specific sources

Balance categories (e.g., 3 news + 2 tech + 1 entertainment)

Post-Publishing:

Review drafts for tone consistency

Add custom featured images if auto-extracted ones are low quality

Schedule posts at optimal times (use Blogger's scheduler)

For Developers
Performance Tuning:

python
# config.py
MAX_WORKERS = 4  # Increase if you have strong CPU
ARTICLES_PER_FEED = 3  # Reduce during testing
Error Handling:

Monitor skipped_articles.txt for patterns

Implement retry logic for failed Blogger API calls

Advanced Features:

Add PDF/Word export option

Integrate with WordPress (via REST API)

Implement sentiment analysis for content filtering

⚙️ System Requirements
Minimum
yaml
Python: 3.8+
Memory: 4GB RAM
Storage: 100MB
Dependencies: See requirements.txt
API Keys: Groq + Google Blogger
Recommended
yaml
CPU: 4+ cores (for parallel processing)
Network: Stable 10Mbps+ connection
Blogger: Established blog (avoid new accounts)
Groq: Paid tier for heavy usage
📈 Performance Metrics
bash
[Typical Run]
✔ Processes 20 articles in ~8 minutes
✔ Maintains 3-5s delay between API calls
✔ Uses ~300MB memory with 3 workers
✔ Generates 500-800 word articles
⚠️ Best Practices
Legal Compliance:

Always keep drafts in "review" state

Manually verify rewritten content

Respect source websites' terms

SEO Health:

Avoid keyword stuffing

Vary article lengths (500-1200 words)

Mix AI content with human-written posts

Maintenance:

Rotate RSS sources monthly

Update prompts quarterly

Clear skipped_articles.txt weekly

🛠️ Setup Guide
Install dependencies:

bash
pip install -r requirements.txt
Configure .env:

ini
GROQ_API_KEY=your_key_here
BLOGGER_BLOG_ID=123456789
BLOGGER_BLOG_URL=yourblog.blogspot.com
Run:

bash
python rss_to_blogger.py