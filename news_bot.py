import feedparser
import requests
import os
import json
import textwrap
from datetime import datetime

KAKAO_ACCESS_TOKEN = os.environ.get("KAKAO_ACCESS_TOKEN")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
NEWS_COUNT = 5

BACKUP_FEEDS = {
    "경제/주식": [
        "https://www.hankyung.com/feed/economy",
        "https://www.mk.co.kr/rss/30100041/",
    ],
    "미국주식": [
        "https://www.hankyung.com/feed/international",
    ],
    "스포츠": [
        "https://www.hankyung.com/feed/sports",
        "https://sports.chosun.com/rss/sports.xml",
    ],
}

def fetch_news(category, feeds, count):
    articles = []
    for url in feeds:
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:count]:
                articles.append({
                    "category": category,
                    "title": entry.get("title", ""),
                    "summary": entry.get("summary", entry.get("description", "")),
                })
            if articles:
                break
        except Exception as e:
            print(f"RSS 피드 오류 ({url}): {e}")
    return articles[:count]

def summarize_with_groq(articles):
    today = datetime.now().strftime("%Y년 %m월 %d일")
    articles_text = ""
    for i, a in enumerate(articles, 1):
        articles_text += f"{i}. [{a['category']}] {a['title']}\n{a['summary'][:300]}\n\n"

    prompt = f"""다음은 오늘({today}) 주요 뉴스입니다. 
각 뉴스를 한국어로 친근하고 자연스럽게 2\~3문장으로 요약해주세요.
카카오톡으로 보내기 좋게 이모지를 적절히 사용하고, 전체 메시지는 850자 이내로 유지해주세요.

뉴스 목록:
{articles_text}

출력 형식:
📰 {today} 오늘의 주요 뉴스

[경제/주식]
1. 제목 간단히 - 요약 내용

[미국주식]
1. 제목 간단히 - 요약 내용

[스포츠]
1. 제목 간단히 - 요약 내용

좋은 하루 되세요! 😊"""

    response = requests.post(
        "https://api.groq.com/openai/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {GROQ_API_KEY}",
            "Content-Type": "application/json",
        },
        json={
            "model": "llama-3.1-8b-instant",   # ← 무료 제한 가장 넉넉한 모델 (하루 14,000회 이상)
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 800,
            "temperature": 0.7,
        }
    )

    print("Groq 상태 코드:", response.status_code)

    if response.status_code != 200:
        print(f"❌ Groq API 오류: {response.text}")
        return "❌ 오늘 뉴스 요약에 실패했습니다. 나중에 다시 시도해 주세요 😥"

    data = response.json()
    try:
        return data["choices"][0]["message"]["content"]
    except (KeyError, IndexError):
        return "❌ 뉴스 요약 중 오류가 발생했습니다."

def send_kakao_message(text):
    url = "https://kapi.kakao.com/v2/api/talk/memo/default/send"
    headers = {
        "Authorization": f"Bearer {KAKAO_ACCESS_TOKEN}",
        "Content-Type": "application/x-www-form-urlencoded",
    }
    
    # 카카오톡 한 번에 보내기 편하게 500자 정도로 잘라서 전송 (더 자연스러움)
    chunks = textwrap.wrap(text, width=500, replace_whitespace=False)
    
    for idx, chunk in enumerate(chunks):
        payload = {
            "template_object": json.dumps({
                "object_type": "text",
                "text": chunk,
                "link": {
                    "web_url": "https://news.naver.com",
                    "mobile_web_url": "https://news.naver.com",
                },
            }, ensure_ascii=False)
        }
        response = requests.post(url, headers=headers, data=payload)
        if response.status_code == 200:
            print(f"✅ 카카오톡 전송 성공 ({idx+1}/{len(chunks)})")
        else:
            print(f"❌ 카카오 전송 실패: {response.status_code} - {response.text}")

def main():
    print("📰 뉴스 수집 시작...")
    all_articles = []

    economy_articles = fetch_news("경제/주식", BACKUP_FEEDS["경제/주식"], NEWS_COUNT)
    all_articles.extend(economy_articles)
    print(f"경제 뉴스 {len(economy_articles)}개 수집 완료")

    us_stock_articles = fetch_news("미국주식", BACKUP_FEEDS["미국주식"], NEWS_COUNT)
    all_articles.extend(us_stock_articles)
    print(f"미국주식 뉴스 {len(us_stock_articles)}개 수집 완료")

    sports_articles = fetch_news("스포츠", BACKUP_FEEDS["스포츠"], NEWS_COUNT)
    all_articles.extend(sports_articles)
    print(f"스포츠 뉴스 {len(sports_articles)}개 수집 완료")

    if not all_articles:
        print("❌ 뉴스를 가져오지 못했습니다.")
        return

    print("🤖 Groq으로 요약 중... (무료 모델 사용)")
    summary = summarize_with_groq(all_articles)
    print("요약 완료")

    print("📱 카카오톡 전송 중...")
    send_kakao_message(summary)

if __name__ == "__main__":
    main()