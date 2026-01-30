import os
import json
import datetime
import requests
import re
import html as html_lib
from typing import List, Dict

# 配置
DATA_FILE = "data/weekly_trending.json"
MAX_DAILY_ITEMS = 5
RETENTION_DAYS = 7

def get_session():
    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
    })
    return session

def fetch_html_with_mirror() -> str:
    """尝试从多个源获取 HTML"""
    sources = [
        "https://github.com/trending?since=daily",
        "https://bgithub.xyz/trending?since=daily",
        "https://mgithub.xyz/trending?since=daily"
    ]
    session = get_session()
    for url in sources:
        try:
            print(f"Trying to fetch: {url}")
            r = session.get(url, timeout=15)
            if r.status_code == 200 and "article" in r.text:
                print(f"Successfully fetched HTML from {url}")
                return r.text
        except Exception as e:
            print(f"Failed to fetch {url}: {e}")
    return ""

def github_api_fallback() -> List[Dict]:
    """终极兜底方案：使用官方 API 获取今日最火项目"""
    print("All HTML sources failed. Using GitHub API Fallback...")
    # 搜索过去 24 小时内创建或活跃且 star 最多的项目
    since = (datetime.date.today() - datetime.timedelta(days=1)).isoformat()
    url = f"https://api.github.com/search/repositories?q=pushed:>{since}&sort=stars&order=desc&per_page=10"
    try:
        r = requests.get(url, timeout=15)
        if r.status_code == 200:
            data = r.json()
            items = []
            for repo in data.get("items", []):
                items.append({
                    "full_name": repo["full_name"],
                    "url": repo["html_url"],
                    "description": repo["description"] or "No description",
                    "date_added": datetime.date.today().isoformat()
                })
            return items
    except Exception as e:
        print(f"API Fallback also failed: {e}")
    return []

def parse_trending_html(html: str) -> List[Dict]:
    """增强版正则解析"""
    items = []
    # 1. 提取所有 article 块
    articles = re.findall(r'(?si)<article\b[^>]*>(.*?)</article>', html)
    print(f"Found {len(articles)} article blocks in HTML.")

    for art in articles:
        try:
            # 2. 提取仓库全名 (处理 href="/user/repo" 或 href="https://...")
            name_match = re.search(r'href=["\']/(?P<name>[^"\'/]+/[^"\'/]+)["\']', art)
            if not name_match:
                continue
            full_name = name_match.group('name').strip("/")
            
            # 3. 提取描述 (适配各种 p 标签或 class)
            desc = ""
            desc_match = re.search(r'(?si)<p\b[^>]*>(.*?)</p>', art)
            if desc_match:
                desc = html_lib.unescape(re.sub(r'<[^>]+>', '', desc_match.group(1)).strip())

            items.append({
                "full_name": full_name,
                "url": f"https://github.com/{full_name}",
                "description": desc,
                "date_added": datetime.date.today().isoformat()
            })
        except:
            continue
    return items

def load_history() -> List[Dict]:
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data if isinstance(data, list) else []
        except:
            return []
    return []

def save_data(data: List[Dict]):
    os.makedirs(os.path.dirname(DATA_FILE), exist_ok=True)
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def main():
    # 1. 加载并清理旧数据（保留过去7天）
    history = load_history()
    today = datetime.date.today()
    cutoff_date = today - datetime.timedelta(days=RETENTION_DAYS)
    history = [item for item in history if datetime.date.fromisoformat(item['date_added']) > cutoff_date]
    existing_names = {item['full_name'] for item in history}

    # 2. 尝试多渠道获取数据
    html = fetch_html_with_mirror()
    raw_items = []
    if html:
        raw_items = parse_trending_html(html)
    
    if not raw_items:
        raw_items = github_api_fallback()

    # 3. 去重挑选新项目
    new_picks = []
    for item in raw_items:
        if item['full_name'] not in existing_names:
            new_picks.append(item)
            existing_names.add(item['full_name'])
            if len(new_picks) >= MAX_DAILY_ITEMS:
                break

    # 4. 合并保存
    if new_picks:
        print(f"Successfully picked {len(new_picks)} new projects today.")
        updated_history = history + new_picks
        save_data(updated_history)
        
        # 更新预览文档
        with open("current_trending.md", "w", encoding="utf-8") as f:
            f.write(f"# GitHub Trending (Added at: {today})\n\n")
            for item in new_picks:
                f.write(f"### [{item['full_name']}]({item['url']})\n")
                f.write(f"- {item['description']}\n\n")
    else:
        print("No new projects to add today.")

if __name__ == "__main__":
    main()
