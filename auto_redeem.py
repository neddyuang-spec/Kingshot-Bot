# -*- coding: utf-8 -*-
import csv
import io
import time
import requests
from playwright.sync_api import sync_playwright

# ================= 參數設定 =================
SHEET_CSV_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vQFecEwf1fYIKawFfBVIZ51q-DrAx-yxeWNMHtwhlRWwkL585YTtEl9s31cBuA4yk3UVc5xna0Sc0k0/pub?output=csv"
DISCORD_WEBHOOK_URL = "https://discord.com/api/webhooks/1536658271593828372/lF8PouLi3QYo3gXliwf0qMq_9KnwuxBGQGxiUFUnuKhiq-ujWwqGtPFLAPlGCp9EpaU9"
REDEEM_PAGE_URL = "https://ks-giftcode.centurygame.com/"
# ============================================

def get_players():
    """自動從 Google 試算表讀取盟友資料"""
    print("正在讀取 Google 試算表盟友資料...")
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    try:
        res = requests.get(SHEET_CSV_URL, headers=headers, timeout=15)
        res.raise_for_status()
        
        csv_text = res.content.decode('utf-8-sig')
        reader = csv.DictReader(io.StringIO(csv_text))
        
        players = []
        for row in reader:
            row_lower = {str(k).strip().lower(): str(v).strip() for k, v in row.items() if k}
            
            kingdom = row_lower.get("kingdom") or row_lower.get("服號") or "1641"
            name = row_lower.get("name") or row_lower.get("名字") or row_lower.get("player") or "盟友"
            player_id = row_lower.get("playerid") or row_lower.get("player_id") or row_lower.get("id") or row_lower.get("玩家id")
            
            if player_id:
                players.append({"kingdom": kingdom, "name": name, "player_id": player_id})
        
        if players:
            print(f"👉 成功讀取 {len(players)} 位盟友資料")
            return players
    except Exception as e:
        print(f"❌ 試算表讀取失敗: {e}")

    # 備用名單
    return [
        {"kingdom": "1641", "name": "Light", "player_id": "246147093"},
        {"kingdom": "1641", "name": "Pig", "player_id": "264788350"},
        {"kingdom": "1641", "name": "Ogre", "player_id": "279237769"},
        {"kingdom": "1641", "name": "MiniLight", "player_id": "306868384"},
        {"kingdom": "1641", "name": "Hinoki", "player_id": "265085587"},
        {"kingdom": "1641", "name": "Flora", "player_id": "327944637"},
        {"kingdom": "628", "name": "Handsome", "player_id": "347892324"}
    ]

def get_latest_gift_code():
    """自動爬取最新禮包碼"""
    print("正在爬取最新禮物碼...")
    url = "https://r.jina.ai/https://kingshotoptimizer.com/gift-codes/"
    try:
        res = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=15)
        if res.status_code == 200 and "Active codes" in res.text:
            active_part = res.text.split("Active codes")[1].split("Expired codes")[0]
            import re
            codes = re.findall(r'\b[A-Za-z0-9]{5,15}\b', active_part)
            ignore_list = {"ACTIVE", "EXPIRED", "COPY", "SOURCE", "VERIFIED", "ADDED", "GIFTS"}
            for code in codes:
                if code.upper() not in ignore_list and not code.isdigit():
                    return code
    except Exception as e:
        print(f"⚠️ 爬取失敗: {e}")
        
    return "KS0810" # 預設 fallback

def redeem_with_browser(page, player_id, kingdom, gift_code):
    """執行瀏覽器自動兌換"""
    try:
        page.goto(REDEEM_PAGE_URL, timeout=30000)
        page.wait_for_selector("input", timeout=15000)

        inputs = page.locator("input")
        inputs.nth(0).fill(str(player_id).strip())
        inputs.nth(1).fill(str(kingdom).strip())
        inputs.nth(2).fill(str(gift_code).strip())

        try:
            page.locator("button, .btn, [type='submit']").first.click()
        except:
            page.locator("text=/确认|兌換|Confirm|Redeem/i").first.click()

        time.sleep(3.5)
        
        body_text = page.inner_text("body")
        try:
            toast_text = page.locator(".el-message, .toast, .alert, .modal, [class*='message'], [class*='toast']").all_inner_texts()
            full_text = body_text + " " + " ".join(toast_text)
        except:
            full_text = body_text

        if any(word in full_text for word in ["已领取", "已領取", "重复领取", "重複領取", "same gift"]):
            return "claimed", "⚠️ 已經領取過該禮物"
        elif any(word in full_text for word in ["成功", "success", "Successfully"]):
            return "success", "✅ 兌換成功！"
        elif any(word in full_text for word in ["无效", "無效", "过期", "過期", "不存在", "invalid", "expired"]):
            return "failed", f"❌ 禮包碼無效或已過期"
        else:
            return "success", "✅ 兌換指令已送出"

    except Exception as e:
        return "failed", f"❌ 網頁操作異常: {str(e)}"

def send_discord_webhook(gift_code, results):
    """將結果發送至 Discord Webhook"""
    print("正在傳送結果給 Discord...")
    
    success_count = sum(1 for r in results if r["status"] == "success")
    claimed_count = sum(1 for r in results if r["status"] == "claimed")
    fail_count = sum(1 for r in results if r["status"] == "failed")
    
    details = [f"**{r['name']}** (`{r['player_id']}`) - {r['msg']}" for r in results]
    details_str = "\n".join(details)
    if len(details_str) > 3000:
        details_str = details_str[:3000] + "\n...(筆數過多略過)"
        
    embed = {
        "title": "🎁 Kingshot 盟友禮物碼每日自動兌換報告",
        "color": 3066993 if fail_count == 0 else 15158332,
        "fields": [
            {"name": "最新禮物碼", "value": f"`{gift_code}`", "inline": True},
            {"name": "兌換統計", "value": f"成功: **{success_count}** 人\n重複領取: **{claimed_count}** 人\n失敗: **{fail_count}** 人", "inline": True},
            {"name": "詳細兌換清單", "value": details_str or "無資料", "inline": False}
        ],
        "footer": {"text": "自動化排程任務 • 每日定時執行"}
    }
    
    try:
        requests.post(DISCORD_WEBHOOK_URL, json={"username": "Kingshot 兌換小幫手", "embeds": [embed]}, timeout=10)
    except Exception as e:
        print(f"❌ Discord Webhook 發送失敗: {e}")

def main():
    players = get_players()
    gift_code = get_latest_gift_code()
    print(f"👉 取得最新禮物碼：{gift_code}")
    
    results = []
    
    if players:
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True,
                args=["--no-sandbox", "--disable-setuid-sandbox"]
            )
            context = browser.new_context(viewport={"width": 1280, "height": 720})
            page = context.new_page()

            for p_info in players:
                print(f"正在為 [{p_info['kingdom']}服] {p_info['name']} (ID: {p_info['player_id']}) 兌換 {gift_code}...")
                status, msg = redeem_with_browser(page, p_info['player_id'], p_info['kingdom'], gift_code)
                results.append({
                    "name": p_info['name'],
                    "player_id": p_info['player_id'],
                    "status": status,
                    "msg": msg
                })
                time.sleep(2)

            browser.close()

    send_discord_webhook(gift_code, results)
    print("🎉 任務執行完畢！")

if __name__ == "__main__":
    main()
