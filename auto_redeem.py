# -*- coding: utf-8 -*-
import csv
import io
import time
import re
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
    """自動爬取最新禮包碼（移除預設值，抓不到直接報錯）"""
    print("正在爬取最新禮物碼...")
    cache_buster = int(time.time())
    url = f"https://r.jina.ai/https://kingshotoptimizer.com/gift-codes/?cb={cache_buster}"
    
    try:
        res = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=15)
        if res.status_code == 200:
            text = res.text
            if "Active codes" in text:
                active_part = text.split("Active codes")[1]
                if "Expired codes" in active_part:
                    active_part = active_part.split("Expired codes")[0]
            else:
                active_part = text
                
            # 尋找所有 5 到 25 字元的大寫英數字組合（如 OFFICIALSTORE08011）
            codes = re.findall(r'\b[A-Z0-9]{5,25}\b', active_part)
            ignore_list = {"ACTIVE", "EXPIRED", "COPY", "SOURCE", "VERIFIED", "ADDED", "GIFTS", "MARKDOWN", "CONTENT"}
            
            valid_codes = []
            for code in codes:
                if code not in ignore_list and not code.isdigit():
                    if code not in valid_codes:
                        valid_codes.append(code)
            
            print(f"👉 篩選後的有效禮包碼清單: {valid_codes}")
            if valid_codes:
                latest = valid_codes[0]
                print(f"👉 決定使用最新禮包碼: {latest}")
                return latest
    except Exception as e:
        print(f"⚠️ 爬取失敗: {e}")
        
    # 💡 嚴格要求：抓不到就直接引發例外，絕不使用舊碼混淆
    raise ValueError("❌ 無法自動抓取到最新的禮包碼！請檢查網站結構或稍後再試。")

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

        time.sleep(6.0)
        
        full_text = page.content()
        try:
            toast_elements = page.locator(".el-message, .toast, .alert, .modal, [class*='message'], [class*='toast'], [role='alert'], div").all_inner_texts()
            if toast_elements:
                full_text += " " + " ".join(toast_elements)
        except:
            pass

        if any(word in full_text for word in ["已领取", "已領取", "重复领取", "重複領取", "same gift", "already"]):
            return "claimed", "⚠️ 已經領取過該禮物"
        elif any(word in full_text for word in ["成功", "success", "Successfully"]):
            return "success", "✅ 兌換成功！"
        elif any(word in full_text for word in ["无效", "無效", "过期", "過期", "不存在", "invalid", "expired"]):
            return "failed", "❌ 禮包碼無效或已過期"
        else:
            return "failed", "❌ 禮包碼無效或伺服器未回應"

    except Exception as e:
        return "failed", f"❌ 網頁操作異常: {str(e)}"

def send_discord_webhook(gift_code, results):
    """將結果發送至 Discord Webhook"""
    print("正在傳送結果給 Discord...")
    
    success_count = sum(1 for r in results if r["status"] == "success" and "成功" in r["msg"])
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
    try:
        gift_code = get_latest_gift_code()
    except Exception as e:
        print(f"❌ {e}")
        return

    players = get_players()
    print(f"👉 最終使用禮物碼：{gift_code}")
    
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
