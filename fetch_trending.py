import os
import json
import datetime
import requests
import re
import html as html_lib
from typing import List, Dict

# 配置
DATA_FILE = "data/weekly_trending.json"
MAX_DAILY_ITEMS = 5  # 每日新增项目数
RETENTION_DAYS = 7   # 保留天数

def get_session():
    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    })
    return session

def fetch_trending_raw(top_n=20) -> List[Dict]:
    """从 GitHub Trending 页面抓取原始数据"""
    url = "https://github.com/trending?since=daily"
    items = []
    try:
        r = get_session().get(url, timeout=20)
        if r.status_code != 200: return []
        
        html = r.text
        article_pattern = re.compile(r"(?si)<article\b[^>]*>(.*?)</article>")
        articles = article_pattern.findall(html)
        
        for art_html in articles[:top_n]:
            m_href = re.search(r'href="([^"/]+/[^"/]+)"', art_html)
            if not m_href: continue
            full_name = m_href.group(1).strip("/")
            
            desc_m = re.search(r'(?si)<p\b[^>]*>(.*?)</p>', art_html)
            desc = html_lib.unescape(re.sub(r'<[^>]+>', '', desc_m.group(1)).strip()) if desc_m else ""
            
            items.append({
                "full_name": full_name,
                "url": f"https://github.com/{full_name}",
                "description": desc,
                "date_added": datetime.date.today().isoformat()
            })
    except Exception as e:
        print(f"Error fetching: {e}")
    return items

def load_history() -> List[Dict]:
    """加载历史数据"""
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            try:
                return json.load(f)
            except:
                return []
    return []

def save_data(data: List[Dict]):
    """保存数据"""
    os.makedirs(os.path.dirname(DATA_FILE), exist_ok=True)
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def main():
    # 1. 加载并清理旧数据（只保留过去 7 天）
    history = load_history()
    today = datetime.date.today()
    cutoff_date = today - datetime.timedelta(days=RETENTION_DAYS)
    
    # 过滤掉 7 天前的数据
    history = [item for item in history if datetime.date.fromisoformat(item['date_added']) > cutoff_date]
    
    # 记录已存在的仓库名用于去重
    existing_names = {item['full_name'] for item in history}
    
    # 2. 获取今日热门
    print("Fetching trending...")
    raw_items = fetch_trending_raw(top_n=25)
    
    # 3. 去重并挑选前 5 个新项目
    new_picks = []
    for item in raw_items:
        if item['full_name'] not in existing_names:
            new_picks.append(item)
            existing_names.add(item['full_name'])
            if len(new_picks) >= MAX_DAILY_ITEMS:
                break
    
    if not new_picks:
        print("No new unique projects found today.")
    else:
        print(f"Picked {len(new_picks)} new projects.")
        
    # 4. 合并并保存
    updated_history = history + new_picks
    save_data(updated_history)
    
    # 5. 可选：生成一个简单的 Markdown 预览文件方便查看
    with open("current_trending.md", "w", encoding="utf-8") as f:
        f.write(f"# GitHub Weekly Trending (Updated: {today})\n\n")
        for item in new_picks:
            f.write(f"### [{item['full_name']}]({item['url']})\n")
            f.write(f"- **Description:** {item['description']}\n")
            f.write(f"- **Added on:** {item['date_added']}\n\n")

if __name__ == "__main__":
    main()
