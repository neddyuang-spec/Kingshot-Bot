# -*- coding: utf-8 -*-
import csv
import io
import json
import os
import random
import re
import time
import requests
from playwright.sync_api import sync_playwright

# ================= 參數設定 =================
# 正確的 Google 試算表 CSV 網址（已確認零與英文大小寫）
SHEET_CSV_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vQFecEwf1fYIKawFfBVIZ51q-DrAx-yxeWNMHtwhlRWwkL585YTtEl9s31cBuA4yk3UVc5xna0Sc0k0/pub?output=csv"
DISCORD_WEBHOOK_URL = "https://discord.com/api/webhooks/1536658271593828372/lF8PouLi3QYo3gXliwf0qMq_9KnwuxBGQGxiUFUnuKhiq-ujWwqGtPFLAPlGCp9EpaU9"
REDEEM_PAGE_URL = "https://ks-giftcode.centurygame.com/"
GIFT_CODES_API_URL = "https://kingshot.net/api/gift-codes"
RECORD_FILE = "redeemed_history.json"
# ============================================

def get_players():
    """自動從 Google 試算表讀取盟友資料"""
    print("正在讀取 Google 試算表盟友資料...", flush=True)
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    try:
        res = requests.get(SHEET_CSV_URL, headers=headers, timeout=15)
        res.raise_for_status()
        
        csv_text = res.content.decode('utf-8-sig')
        f = io.StringIO(csv_text)
        reader = csv.reader(f)
        
        rows = list(reader)
        if not rows:
            raise ValueError("CSV 檔案內容為空")
            
        header = [str(h).strip().lower() for h in rows[0]]
        print(f"👉 偵測到的試算表欄位標題: {header}", flush=True)
        
        players = []
        for row in rows[1:]:
            if not row or all(not cell.strip() for cell in row):
                continue
                
            row_lower = {header[i]: row[i].strip() for i in range(min(len(header), len(row))) if header[i]}
            
            kingdom = row_lower.get("kingdom") or row_lower.get("服號") or row_lower.get("王國") or row_lower.get("server") or ""
            name = row_lower.get("name") or row_lower.get("名字") or row_lower.get("player") or row_lower.get("暱稱") or ""
            player_id = row_lower.get("playerid") or row_lower.get("player_id") or row_lower.get("id") or row_lower.get("玩家id") or row_lower.get("uid") or ""
            
            if not player_id and len(row) >= 3:
                kingdom = kingdom or row[0].strip()
                name = name or row[1].strip()
                player_id = row[2].strip()
            elif not player_id and len(row) == 2:
                name = name or row[0].strip()
                player_id = row[1].strip()
                kingdom = "1641"
                
            if player_id and player_id.isdigit():
                players.append({
                    "kingdom": kingdom if kingdom else "1641",
                    "name": name if name else f"玩家_{player_id}",
                    "player_id": player_id
                })
        
        if players:
            print(f"👉 成功讀取 {len(players)} 位盟友資料", flush=True)
            return players
    except Exception as e:
        print(f"❌ 試算表讀取失敗: {e}", flush=True)

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

def get_all_gift_codes():
    """從 API 取得禮包碼清單"""
    print("正在從 API 取得禮物碼...", flush=True)
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    
    try:
        res = requests.get(GIFT_CODES_API_URL, headers=headers, timeout=15)
        res.raise_for_status()
        
        try:
            data = res.json()
        except:
            data = res.text
            
        codes = []
        
        def extract_codes(obj):
            if isinstance(obj, list):
                for item in obj:
                    extract_codes(item)
            elif isinstance(obj, dict):
                for k, v in obj.items():
                    if any(key_word in k.lower() for key_word in ["code", "gift", "value", "title", "name"]):
                        if isinstance(v, str) and len(v.strip()) >= 4:
                            codes.append(v.strip())
                    extract_codes(v)
            elif isinstance(obj, str) and 4 <= len(obj.strip()) <= 30:
                codes.append(obj.strip())

        extract_codes(data)
        
        if not codes:
            codes = re.findall(r'\b[A-Z0-9]{5,25}\b', res.text)
            
        ignore_list = {
            "ACTIVE", "EXPIRED", "COPY", "SOURCE", "VERIFIED", "ADDED", 
            "GIFTS", "MARKDOWN", "CONTENT", "OPTIMIZER", "HOME", "GUIDES", 
            "API", "FALSE", "TRUE", "NULL", "SUCCESS", "ERROR"
        }
        
        valid_codes = []
        for code in codes:
            code_str = str(code).strip().upper()
            if code_str not in ignore_list and not code_str.isdigit() and len(code_str) >= 5:
                if re.match(r'^[A-Z0-9\-_]+$', code_str):
                    if code_str not in valid_codes:
                        valid_codes.append(code_str)
                        
        print(f"👉 篩選後的有效禮包碼清單: {valid_codes}", flush=True)
        if valid_codes:
            return valid_codes
    except Exception as e:
        print(f"❌ API 取得禮物碼失敗: {e}", flush=True)
        
    return ["Kingshot888"]

def load_history():
    """載入誰領過什麼代碼的紀錄"""
    if not os.path.exists(RECORD_FILE):
        return {}
    try:
        with open(RECORD_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {}

def save_history(history):
    """儲存歷史紀錄"""
    with open(RECORD_FILE, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)

def is_player_redeemed(gift_code, player_id):
    """檢查特定玩家是否已經領過該禮包碼"""
    history = load_history()
    code_upper = gift_code.upper()
    redeemed_players = history.get(code_upper, [])
    return str(player_id) in redeemed_players

def mark_player_redeemed(gift_code, player_id):
    """將特定玩家標記為已領過該禮包碼"""
    history = load_history()
    code_upper = gift_code.upper()
    if code_upper not in history:
        history[code_upper] = []
    if str(player_id) not in history[code_upper]:
        history[code_upper].append(str(player_id))
    save_history(history)

def human_type(locator, text):
    """模擬真人不規則打字速度與停頓"""
    locator.click()
    for char in str(text):
        locator.press(char)
        time.sleep(random.uniform(0.07, 0.22))

def redeem_with_browser(page, player_id, kingdom, gift_code):
    """執行瀏覽器自動兌換"""
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

def send_discord_webhook(gift_codes_list, results):
    """將完整結果自動切成多份 Embed 傳送至 Discord"""
    print("正在傳送完整結果給 Discord...", flush=True)
    
    success_count = sum(1 for r in results if r["status"] == "success" and "成功" in r["msg"])
    # 同時計算「網頁偵測已領過」與「歷史紀錄略過」的人數
    claimed_count = sum(1 for r in results if r["status"] == "claimed" or "略過" in r["msg"])
    fail_count = sum(1 for r in results if r["status"] == "failed" and "略過" not in r["msg"])
    
    chunk_size = 10
    chunks = [results[i:i + chunk_size] for i in range(0, len(results), chunk_size)]
    if not chunks:
        chunks = [[]]
        
    embeds = []
    codes_str = ", ".join([f"`{c}`" for c in gift_codes_list])

    for idx, chunk in enumerate(chunks):
        details = [f"**{r['name']}** (`{r['player_id']}`) [{r.get('gift_code', '')}] - {r['msg']}" for r in chunk]
        details_str = "\n".join(details)
        
        embed = {
            "title": f"🎁 Kingshot 盟友禮物碼自動兌換報告 ({idx + 1}/{len(chunks)})" if len(chunks) > 1 else "🎁 Kingshot 盟友禮物碼每日自動兌換報告",
            "color": 3066993 if fail_count == 0 else 15158332,
            "fields": []
        }
        
        if idx == 0:
            embed["fields"].append({"name": "本次檢查禮物碼", "value": codes_str or "無", "inline": False})
            embed["fields"].append({"name": "兌換統計", "value": f"成功執行: **{success_count}** 人\n略過/已領過: **{claimed_count}** 人\n失敗: **{fail_count}** 人", "inline": True})
        
        embed["fields"].append({
            "name": f"詳細兌換清單 (第 {idx + 1} 部分)",
            "value": details_str or "無資料",
            "inline": False
        })
        
        if idx == len(chunks) - 1:
            embed["footer"] = {"text": "自動化排程任務 • 具備防重複與自動補領機制"}
            
        embeds.append(embed)
    
    try:
        res = requests.post(DISCORD_WEBHOOK_URL, json={"username": "Kingshot 兌換小幫手", "embeds": embeds}, timeout=10)
        res.raise_for_status()
        print("👉 Discord 完整訊息發送成功！", flush=True)
    except Exception as e:
        print(f"❌ Discord Webhook 發送失敗: {e}", flush=True)

def main():
    players = get_players()
    gift_codes = get_all_gift_codes()
    
    if not gift_codes:
        print("❌ 沒有取得任何有效的禮包碼，結束任務。", flush=True)
        return

    print(f"👉 最終使用的禮物碼清單：{gift_codes}", flush=True)
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
                p_id = p_info['player_id']
                p_name = p_info['name']
                p_kingdom = p_info['kingdom']

                for gift_code in gift_codes:
                    if is_player_redeemed(gift_code, p_id):
                        msg = "⏩ 本次略過 (先前已領過)"
                        print(f"[{p_kingdom}服] {p_name} 已經領過 {gift_code}，本次略過", flush=True)
                        results.append({
                            "name": p_name,
                            "player_id": p_id,
                            "gift_code": gift_code,
                            "status": "claimed",
                            "msg": msg
                        })
                        continue

                    print(f"正在為 [{p_kingdom}服] {p_name} (ID: {p_id}) 兌換 {gift_code}...", flush=True)
                    status, msg = redeem_with_browser(page, p_id, p_kingdom, gift_code)
                    print(f"  -> 結果: {msg}", flush=True)
                    
                    if status in ["success", "claimed"]:
                        mark_player_redeemed(gift_code, p_id)

                    results.append({
                        "name": p_name,
                        "player_id": p_id,
                        "gift_code": gift_code,
                        "status": status,
                        "msg": msg
                    })
                    time.sleep(random.uniform(1.8, 3.5))

            browser.close()

    send_discord_webhook(gift_codes, results)
    print("🎉 任務執行完畢！", flush=True)

if __name__ == "__main__":
    main()
