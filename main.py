import csv
import os
import time
from bs4 import BeautifulSoup
import requests

# ================= 基礎設定 =================
# 1. 貼上你從 Google 試算表取得的 CSV 發布網址
GOOGLE_SHEET_CSV_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-xxxx/pub?output=csv"

# 2. 貼上你的 Discord Webhook 網址
DISCORD_WEBHOOK_URL = "https://discord.com/api/webhooks/xxxx/xxxx"

# 3. 官方兌換 API 網址 (依實際遊戲後端網址為準)
KINGSHOT_REDEEM_API = "https://ks-giftcode.centurygame.com/api/redeem"


# ================= 核心邏輯 =================


# 1. 從網頁/爬蟲獲取最新禮包碼
def fetch_latest_codes():
    print("🔍 正在抓取最新禮包碼...")
    # 這裡示範從公開整理網站抓取，或可替換成實際有更新 Kingshot 序號的網頁
    codes = []
    try:
        # 範例：爬取特定禮包碼頁面 (請依實際網址調整)
        url = "https://example.com/kingshot-codes"
        headers = {"User-Agent": "Mozilla/5.0"}
        res = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(res.text, "html.parser")

        # 假設序號都包在 <code> 標籤內
        for tag in soup.find_all("code"):
            code_text = tag.text.strip()
            if code_text and code_text not in codes:
                codes.append(code_text)
    except Exception as e:
        print(f"抓取禮包碼失敗: {e}")

    # 如果爬蟲沒抓到，也可以設定預設或備用序號測試
    return codes if codes else ["KS8888", "HAPPY2026"]


# 2. 從 Google 試算表抓取盟友名單
def fetch_player_list():
    print("📊 正在讀取 Google 試算表名單...")
    players = []
    try:
        res = requests.get(GOOGLE_SHEET_CSV_URL, timeout=10)
        res.encoding = "utf-8"
        csv_data = csv.reader(res.text.splitlines())

        header = next(csv_data)  # 跳過第一行標題
        for row in csv_data:
            if len(row) >= 2 and row[1].strip():
                name = row[0].strip()
                player_id = row[1].strip()
                players.append({"name": name, "id": player_id})
    except Exception as e:
        print(f"讀取試算表失敗: {e}")

    return players


# 3. 批次兌換與報告
def run():
    codes = fetch_latest_codes()
    players = fetch_player_list()

    if not codes:
        print("沒有發現新的禮包碼，任務結束。")
        return

    if not players:
        print("試算表中沒有任何玩家資料！")
        return

    report_messages = [f"🤖 **【Kingshot 每日自動兌換報告】**"]

    for code in codes:
        report_messages.append(f"\n🎁 **正在兌換禮包碼：`{code}`**")

        for p in players:
            name = p["name"]
            pid = p["id"]

            payload = {"player_id": pid, "code": code}
            headers = {"Content-Type": "application/json"}

            try:
                res = requests.post(
                    KINGSHOT_REDEEM_API, json=payload, headers=headers, timeout=10
                )
                result = res.json()

                # 假設 200 代表成功 (依實際官方 API 回傳格式為準)
                if res.status_code == 200 and result.get("code") == 200:
                    report_messages.append(
                        f"• **{name}** (`{pid}`): ✅ 成功"
                    )
                else:
                    msg = result.get("msg", "已領取過或無效")
                    report_messages.append(
                        f"• **{name}** (`{pid}`): ⚠️ {msg}"
                    )
            except Exception:
                report_messages.append(f"• **{name}** (`{pid}`): ❌ 連線失敗")

            time.sleep(1.5)  # 避免請求太快

    # 發送結果到 Discord Webhook
    final_report = "\n".join(report_messages)
    requests.post(DISCORD_WEBHOOK_URL, json={"content": final_report})
    print("✅ 兌換任務完成，已發送 Discord 通知！")


if __name__ == "__main__":
    run()
