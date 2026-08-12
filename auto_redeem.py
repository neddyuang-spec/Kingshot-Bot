# -*- coding: utf-8 -*-
import csv
import io
import time
import random
import re
import requests
from playwright.sync_api import sync_playwright

# ================= 參數設定 =================
SHEET_CSV_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vQFecEwf1fYIKawFfBVIZ51q-DrAx-yxeWNMHtwhlRWwkL585YTtEl9s31cBuA4yk3UVc5xna0Sc0k0/pub?output=csv"
DISCORD_WEBHOOK_URL = "https://discord.com/api/webhooks/1536658271593828372/lF8PouLi3QYo3gXliwf0qMq_9KnwuxBGQGxiUFUnuKhiq-ujWwqGtPFLAPlGCp9EpaU9"
REDEEM_PAGE_URL = "https://ks-giftcode.centurygame.com/"
GIFT_CODES_API_URL = "https://kingshot.net/api/gift-codes"
# ============================================

def get_players():
    """自動從 Google 試算表讀取盟友資料"""
    print("正在讀取 Google 試算表盟友資料...", flush=True)
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
            print(f"👉 成功讀取 {len(players)} 位盟友資料", flush=True)
            return players
    except Exception as e:
        print(f"❌ 試算表讀取失敗: {e}", flush=True)

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
    """從指定的 API 取得最新禮包碼"""
    print("正在從官方 API 取得最新禮物碼...", flush=True)
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    
    try:
        res = requests.get(GIFT_CODES_API_URL, headers=headers, timeout=15)
        res.raise_for_status()
        
        try:
            data = res.json()
        except:
            data = res.text
            
        codes = []
        if isinstance(data, list):
            for item in data:
                if isinstance(item, str):
                    codes.append(item)
                elif isinstance(item, dict):
                    code_val = item.get("code") or item.get("gift_code") or item.get("giftCode") or item.get("value")
                    if code_val:
                        codes.append(str(code_val))
        elif isinstance(data, dict):
            for key in ["codes", "data", "result", "list"]:
                if key in data and isinstance(data[key], list):
                    for item in data[key]:
                        if isinstance(item, str):
                            codes.append(item)
                        elif isinstance(item, dict):
                            code_val = item.get("code") or item.get("gift_code") or item.get("giftCode") or item.get("value")
                            if code_val:
                                codes.append(str(code_val))
        
        if not codes:
            codes = re.findall(r'\b[A-Z0-9]{5,25}\b', res.text)
            
        ignore_list = {"ACTIVE", "EXPIRED", "COPY", "SOURCE", "VERIFIED", "ADDED", "GIFTS", "MARKDOWN", "CONTENT", "OPTIMIZER", "HOME", "GUIDES", "API"}
        valid_codes = []
        for code in codes:
            code_str = str(code).strip().upper()
            if code_str not in ignore_list and not code_str.isdigit():
                if code_str not in valid_codes:
                    valid_codes.append(code_str)
                    
        print(f"👉 篩選後的有效禮包碼清單: {valid_codes}", flush=True)
        if valid_codes:
            latest = valid_codes[0]
            print(f"👉 決定使用最新禮包碼: {latest}", flush=True)
            return latest
    except Exception as e:
        print(f"❌ API 取得禮物碼失敗: {e}", flush=True)
        
    raise ValueError("❌ 無法從 API 取得有效的禮包碼！請檢查 API 狀態。")

def human_type(locator, text):
    """模擬真人不規則打字速度與停頓"""
    locator.click()
    for char in str(text):
        locator.press(char)
        time.sleep(random.uniform(0.07, 0.22))

def redeem_with_browser(page, player_id, kingdom, gift_code):
    """執行瀏覽器自動兌換（模擬真人隨機逐字輸入）"""
    try:
        page.goto(REDEEM_PAGE_URL, timeout=30000)
        page.wait_for_selector("input", timeout=15000)

        inputs = page.locator("input")
        
        human_type(inputs.nth(0), str(player_id).strip())
        time.sleep(random.uniform(0.2, 0.5))
        
        human_type(inputs.nth(1), str(kingdom).strip())
        time.sleep(random.uniform(0.2, 0.5))
        
        human_type(inputs.nth(2), str(gift_code).strip())
        time.sleep(random.uniform(0.3, 0.6))

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
            return "success", "✅ 兌換指令已送出"

    except Exception as e:
        return "failed", f"❌ 網頁操作異常: {str(e)}"

def send_discord_webhook(gift_code, results):
    """將完整結果自動切成多份 Embed 傳送至 Discord，確保所有人都能完整顯示"""
    print("正在傳送完整結果給 Discord...", flush=True)
    
    success_count = sum(1 for r in results if r["status"] == "success" and "成功" in r["msg"])
    claimed_count = sum(1 for r in results if r["status"] == "claimed")
    fail_count = sum(1 for r in results if r["status"] == "failed")
    
    chunk_size = 10
    chunks = [results[i:i + chunk_size] for i in range(0, len(results), chunk_size)]
    if not chunks:
        chunks = [[]]
        
    embeds = []
    for idx, chunk in enumerate(chunks):
        details = [f"**{r['name']}** (`{r['player_id']}`) - {r['msg']}" for r in chunk]
        details_str = "\n".join(details)
        
        embed = {
            "title": f"🎁 Kingshot 盟友禮物碼自動兌換報告 ({idx + 1}/{len(chunks)})" if len(chunks) > 1 else "🎁 Kingshot 盟友禮物碼每日自動兌換報告",
            "color": 3066993 if fail_count == 0 else 15158332,
            "fields": []
        }
        
        if idx == 0:
            embed["fields"].append({"name": "最新禮物碼", "value": f"`{gift_code}`", "inline": True})
            embed["fields"].append({"name": "兌換統計", "value": f"成功: **{success_count}** 人\n重複領取: **{claimed_count}** 人\n失敗: **{fail_count}** 人", "inline": True})
        
        embed["fields"].append({
            "name": f"詳細兌換清單 (第 {idx + 1} 部分)",
            "value": details_str or "無資料",
            "inline": False
        })
        
        if idx == len(chunks) - 1:
            embed["footer"] = {"text": "自動化排程任務 • 每日定時執行"}
            
        embeds.append(embed)
    
    try:
        res = requests.post(DISCORD_WEBHOOK_URL, json={"username": "Kingshot 兌換小幫手", "embeds": embeds}, timeout=10)
        res.raise_for_status()
        print("👉 Discord 完整訊息發送成功！", flush=True)
    except Exception as e:
        print(f"❌ Discord Webhook 發送失敗: {e}", flush=True)
        if hasattr(e, 'response') and e.response is not None:
            print(f"回應內容: {e.response.text}", flush=True)

def main():
    players = get_players()
    
    try:
        gift_code = get_latest_gift_code()
    except Exception as e:
        print(f"❌ {e}", flush=True)
        return

    print(f"👉 最終使用禮物碼：{gift_code}", flush=True)
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
                print(f"正在為 [{p_info['kingdom']}服] {p_info['name']} (ID: {p_info['player_id']}) 兌換 {gift_code}...", flush=True)
                status, msg = redeem_with_browser(page, p_info['player_id'], p_info['kingdom'], gift_code)
                
                # 即時印出每位盟友的兌換結果到 Log
                print(f"  -> 結果: {msg}", flush=True)
                
                results.append({
                    "name": p_info['name'],
                    "player_id": p_info['player_id'],
                    "status": status,
                    "msg": msg
                })
                time.sleep(random.uniform(1.8, 3.5))

            browser.close()

    send_discord_webhook(gift_code, results)
    print("🎉 任務執行完畢！", flush=True)

if __name__ == "__main__":
    main()
