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
            seen_ids = set()
            deduped_players = []
            for pl in players:
                if pl["player_id"] not in seen_ids:
                    seen_ids.add(pl["player_id"])
                    deduped_players.append(pl)
            removed = len(players) - len(deduped_players)
            players = deduped_players
            if removed > 0:
                print(f"👉 成功讀取 {len(players)} 位盟友資料（已去除 {removed} 筆重複 ID）", flush=True)
            else:
                print(f"👉 成功讀取 {len(players)} 位盟友資料", flush=True)
            return players
    except Exception as e:
        print(f"❌ 試算表讀取失敗: {e}", flush=True)

    return [
        {"kingdom": "1641", "name": "Light", "player_id": "246147093"},
        {"kingdom": "1641", "name": "Pig", "player_id": "264788350"},
        {"kingdom": "1641", "name": "Ogre", "player_id": "279237769"}
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
            codes = re.findall(r'\b[A-Za-z0-9]{5,25}\b', res.text)
            
        ignore_list = {
            "ACTIVE", "EXPIRED", "COPY", "SOURCE", "VERIFIED", "ADDED", 
            "GIFTS", "MARKDOWN", "CONTENT", "OPTIMIZER", "HOME", "GUIDES", 
            "API", "FALSE", "TRUE", "NULL", "SUCCESS", "ERROR"
        }
        
        valid_codes = []
        seen_upper = set()
        for code in codes:
            original = str(code).strip()
            code_upper = original.upper()  # 僅用來做比對與去重，不影響實際送出的碼
            if code_upper not in ignore_list and not code_upper.isdigit() and len(code_upper) >= 5:
                if re.match(r'^[A-Z0-9\-_]+$', code_upper):
                    if code_upper not in seen_upper:
                        seen_upper.add(code_upper)
                        valid_codes.append(original)  # 保留原始大小寫
                        
        print(f"👉 篩選後的有效禮包碼清單: {valid_codes}", flush=True)
        if valid_codes:
            return valid_codes
    except Exception as e:
        print(f"❌ API 取得禮物碼失敗: {e}", flush=True)
        
    return ["Kingshot888"]

def load_history():
    if not os.path.exists(RECORD_FILE):
        return {}
    try:
        with open(RECORD_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {}

def save_history(history):
    with open(RECORD_FILE, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)

def is_player_redeemed(gift_code, player_id):
    history = load_history()
    code_upper = gift_code.upper()
    redeemed_players = history.get(code_upper, [])
    return str(player_id) in redeemed_players

def mark_player_redeemed(gift_code, player_id):
    history = load_history()
    code_upper = gift_code.upper()
    if code_upper not in history:
        history[code_upper] = []
    if str(player_id) not in history[code_upper]:
        history[code_upper].append(str(player_id))
    save_history(history)

def human_type(locator, text):
    locator.click()
    for char in str(text):
        locator.press(char)
        time.sleep(random.uniform(0.07, 0.22))

def close_result_modal(page):
    """嘗試關閉兌換結果彈窗，避免殘留視窗擋住下一次操作（找不到就略過，不影響流程）"""
    try:
        page.locator("text=/確定|确定|OK|Confirm/i").first.click(timeout=2000)
        time.sleep(random.uniform(0.3, 0.6))
    except Exception:
        pass

def redeem_with_browser(page, player_id, kingdom, gift_code, reuse_page=False):
    """
    對單一玩家 + 單一禮包碼執行兌換。
    reuse_page=True 時，假設目前頁面已經在兌換頁且 ID/王國欄位已經填好，
    只重新填寫禮包碼欄位並送出，藉此省下整頁重載的時間；
    若重填失敗，會自動退回整頁重新載入再試一次，不會卡住。
    """
    try:
        filled_via_reuse = False
        if reuse_page:
            try:
                inputs = page.locator("input")
                inputs.nth(2).fill("")
                human_type(inputs.nth(2), str(gift_code).strip())
                time.sleep(random.uniform(0.3, 0.6))
                filled_via_reuse = True
            except Exception:
                filled_via_reuse = False

        if not filled_via_reuse:
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

        # 主動等待畫面跳出已知的結果文字，而不是固定睡 6 秒用猜的
        result_phrases = [
            "兌換成功", "兑换成功",
            "已經領取過", "已经领取过", "已領取", "已领取", "重複領取", "重复领取",
            "無法再次領取", "无法再次领取",
            "兌換碼不存在", "兑换码不存在", "禮包碼不存在", "礼包码不存在",
            "無效", "无效", "過期", "过期",
            "invalid", "expired", "already", "success",
        ]
        try:
            page.wait_for_function(
                "(phrases) => phrases.some(p => document.body.innerText.includes(p))",
                arg=result_phrases,
                timeout=10000
            )
        except Exception:
            pass  # 沒等到已知文字也繼續往下走，用當下畫面實際文字判斷

        # 只讀「畫面上實際顯示的文字」(inner_text)，不要用整包 HTML 原始碼(含隱藏的 script/樣式)去猜
        visible_text = page.inner_text("body")

        if any(word in visible_text for word in ["兌換碼不存在", "兑换码不存在", "禮包碼不存在", "礼包码不存在"]):
            status, msg = "failed", "❌ 兌換碼不存在，請檢查大小寫是否正確"
        elif any(word in visible_text for word in ["已經領取過", "已经领取过", "已領取", "已领取", "重複領取", "重复领取", "無法再次領取", "无法再次领取", "already"]):
            status, msg = "claimed", "⚠️ 已經領取過該禮物"
        elif any(word in visible_text for word in ["兌換成功", "兑换成功"]):
            status, msg = "success", "✅ 兌換成功，請在信件中領取獎勵"
        elif any(word in visible_text for word in ["無效", "无效", "過期", "过期", "invalid", "expired"]):
            status, msg = "failed", "❌ 禮包碼無效或已過期"
        else:
            # 沒對到任何已知訊息時，直接回報畫面上實際看到的文字，不要自行猜測成功或失敗
            snippet = visible_text.strip().replace("\n", " ")
            snippet = re.sub(r"\s+", " ", snippet)[:150]
            status, msg = "unknown", f"❓ 無法辨識結果，實際頁面文字: {snippet}"

        close_result_modal(page)
        return status, msg

    except Exception as e:
        return "failed", f"❌ 網頁操作異常: {str(e)}"

def send_discord_webhook(gift_codes_list, results):
    """將完整結果安全地切片並發送至 Discord，避免 400 Bad Request"""
    print("正在傳送完整結果給 Discord...", flush=True)
    
    success_count = sum(1 for r in results if r["status"] == "success" and "成功" in r["msg"])
    claimed_count = sum(1 for r in results if r["status"] == "claimed" or "略過" in r["msg"])
    fail_count = sum(1 for r in results if r["status"] == "failed" and "略過" not in r["msg"])
    unknown_count = sum(1 for r in results if r["status"] == "unknown")
    
    # 將名單切成每組最多 8 筆，確保單個 Field 長度不超過 Discord 1024 字元限制
    chunk_size = 8
    chunks = [results[i:i + chunk_size] for i in range(0, len(results), chunk_size)]
    if not chunks:
        chunks = [[]]
        
    embeds = []
    codes_str = ", ".join([f"`{c}`" for c in gift_codes_list])
    if len(codes_str) > 900:
        codes_str = codes_str[:900] + "..."

    for idx, chunk in enumerate(chunks):
        details = []
        for r in chunk:
            line = f"• **{r['name']}** (`{r['player_id']}`) [{r.get('gift_code', '')}] - {r['msg']}"
            if len(line) > 150:
                line = line[:147] + "..."
            details.append(line)
            
        details_str = "\n".join(details)
        if not details_str:
            details_str = "無資料"
            
        embed = {
            "title": f"🎁 Kingshot 盟友禮物碼自動兌換報告 ({idx + 1}/{len(chunks)})" if len(chunks) > 1 else "🎁 Kingshot 盟友禮物碼每日自動兌換報告",
            "color": 3066993 if fail_count == 0 else 15158332,
            "fields": []
        }
        
        if idx == 0:
            embed["fields"].append({"name": "本次檢查禮物碼", "value": codes_str or "無", "inline": False})
            embed["fields"].append({"name": "兌換統計", "value": f"成功執行: **{success_count}** 人\n略過/已領過: **{claimed_count}** 人\n失敗: **{fail_count}** 人\n無法辨識: **{unknown_count}** 人", "inline": True})
        
        embed["fields"].append({
            "name": f"詳細兌換清單 (第 {idx + 1} 部分)",
            "value": details_str,
            "inline": False
        })
        
        if idx == len(chunks) - 1:
            embed["footer"] = {"text": "自動化排程任務 • 防重複與自動切片機制"}
            
        embeds.append(embed)
    
    # Discord 單則訊息最多 10 個 embeds，超過就分成多則訊息依序發送
    batch_size = 10
    embed_batches = [embeds[i:i + batch_size] for i in range(0, len(embeds), batch_size)]
    if not embed_batches:
        embed_batches = [[]]

    total_batches = len(embed_batches)
    for batch_idx, embed_batch in enumerate(embed_batches):
        try:
            res = requests.post(
                DISCORD_WEBHOOK_URL,
                json={"username": "Kingshot 兌換小幫手", "embeds": embed_batch},
                timeout=10
            )
            res.raise_for_status()
            print(f"👉 Discord 訊息發送成功！({batch_idx + 1}/{total_batches})", flush=True)
        except Exception as e:
            print(f"❌ Discord Webhook 發送失敗 ({batch_idx + 1}/{total_batches}): {e}", flush=True)
            if hasattr(e, 'response') and e.response is not None:
                print(f"   詳細回應內容: {e.response.text}", flush=True)

        # 避免連續請求觸發 Discord 速率限制
        if batch_idx < total_batches - 1:
            time.sleep(1.0)

def main():
    players = get_players()
    gift_codes = get_all_gift_codes()
    
    if not gift_codes:
        print("❌ 沒有取得任何有效的禮包碼，結束任務。", flush=True)
        return

    print(f"👉 最終使用的禮物碼清單：{gift_codes}", flush=True)
    results = []

    try:
        if players:
            with sync_playwright() as p:
                browser = p.chromium.launch(
                    headless=True,
                    args=["--no-sandbox", "--disable-setuid-sandbox"]
                )
                context = browser.new_context(viewport={"width": 1280, "height": 720})
                page = context.new_page()

                try:
                    for p_info in players:
                        p_id = p_info['player_id']
                        p_name = p_info['name']
                        p_kingdom = p_info['kingdom']

                        page_ready = False  # 同一位玩家換下一組碼時，是否可以重複使用目前頁面(已填好ID/王國)

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
                            status, msg = redeem_with_browser(page, p_id, p_kingdom, gift_code, reuse_page=page_ready)
                            print(f"  -> 結果: {msg}", flush=True)

                            # 只要這次沒有整頁重載失敗(網頁操作異常)，下一組碼就可以繼續重複使用頁面
                            page_ready = "網頁操作異常" not in msg

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
                finally:
                    browser.close()
    finally:
        # 不管中途有沒有出錯，都把目前為止收集到的結果送出，避免整批任務靜默失敗
        send_discord_webhook(gift_codes, results)

    print("🎉 任務執行完畢！", flush=True)

if __name__ == "__main__":
    main()