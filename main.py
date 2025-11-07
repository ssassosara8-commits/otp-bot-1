import time
import re
import os
import requests
import json
from selenium import webdriver
from selenium.webdriver.edge.options import Options as EdgeOptions
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup

# ====================== إعدادات Railway ======================
LOGIN_PAGE = os.environ.get("LOGIN_PAGE", "http://94.23.120.156/ints/login")
OTP_PAGE = os.environ.get("OTP_PAGE", "http://94.23.120.156/ints/client/SMSCDRStats")
CHEKER_BOT_TOKEN = os.environ.get("CHEKER_BOT_TOKEN", "your_bot_token")
USERNAME = os.environ.get("USERNAME", "your_username")
PASSWORD = os.environ.get("PASSWORD", "your_password")
GROUP_CHAT_IDS = json.loads(os.environ.get("GROUP_CHAT_IDS", '["your_chat_id"]'))
TELEGRAM_CHANNEL_LINK = os.environ.get("TELEGRAM_CHANNEL_LINK", "https://t.me/your_channel")
TELEGRAM_BOT_USERNAME = os.environ.get("TELEGRAM_BOT_USERNAME", "@your_bot")
POLL_INTERVAL_SECONDS = float(os.environ.get("POLL_INTERVAL", "0.5"))
MAX_LOGIN_RETRIES = int(os.environ.get("MAX_RETRIES", "3"))
OTP_QUEUE_FILE = "otp_queue.json"

def open_driver():
    """إنشاء متص Edge معدل لـ Railway"""
    options = EdgeOptions()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--disable-extensions")
    options.add_argument("--disable-notifications")
    options.add_argument("--remote-debugging-port=9222")
    
    # إعدادات للمتصفح على السيرفر
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option('useAutomationExtension', False)
    options.add_argument('--disable-blink-features=AutomationControlled')
    
    driver = webdriver.Edge(options=options)
    driver.set_page_load_timeout(60)
    driver.implicitly_wait(15)
    return driver

def try_find_element(driver, locators, timeout=15):
    """الباحث عن العناصر مع تحسين الوقت"""
    for by, sel in locators:
        try:
            return WebDriverWait(driver, timeout).until(EC.presence_of_element_located((by, sel)))
        except Exception:
            continue
    raise Exception(f"Element not found for any of: {locators}")

def send_telegram_message(chat_id: str, text: str, reply_markup: dict = None):
    """إرسال رسالة تليجرام مع معالجة الأخطاء"""
    payload = {
        "chat_id": chat_id, 
        "text": text, 
        "parse_mode": "HTML", 
        "disable_web_page_preview": True
    }
    
    if reply_markup:
        payload["reply_markup"] = json.dumps(reply_markup)
        
    try:
        r = requests.post(f"https://api.telegram.org/bot{CHEKER_BOT_TOKEN}/sendMessage", 
                         data=payload, timeout=20)
        if r.status_code == 200 and r.json().get('ok'):
            print(f"✅ تم الإرسال إلى المجموعة {chat_id}")
            return r
        else:
            print(f"❌ فشل الإرسال: {r.text}")
    except Exception as e:
        print(f"⚠️ خطأ في الإرسال إلى {chat_id}: {e}")
    return None

def get_sms_rows(html: str):
    """استخراج بيانات الرسائل من الجدول"""
    soup = BeautifulSoup(html, "html.parser")
    rows = []
    try:
        table = soup.find("table", {"id": "dt"})
        if not table: 
            return rows
            
        tbody = table.find("tbody")
        if not tbody: 
            return rows
            
        for tr in tbody.find_all("tr"):
            tds = tr.find_all("td")
            if len(tds) >= 5:
                date = tds[0].get_text(strip=True)
                number = tds[2].get_text(strip=True)
                cli = tds[3].get_text(strip=True)
                sms = tds[4].get_text("\n", strip=True)
                
                if number == "0" or sms == "0" or not number:
                    continue
                    
                rows.append((date, number, cli, sms))
    except Exception as e:
        print(f"⚠️ خطأ في تحليل الجدول: {e}")
    
    return rows

def get_country_with_flag(number):
    """الحصول على الدولة والعلم"""
    country_flags = {
        '98':'🇮🇷','91':'🇮🇳','1':'🇺🇸','44':'🇬🇧','86':'🇨🇳','81':'🇯🇵','82':'🇰🇷','65':'🇸🇬',
        '60':'🇲🇾','63':'🇵🇭','84':'🇻🇳','66':'🇹🇭','62':'🇮🇩','92':'🇵🇰','880':'🇧🇩',
        '93':'🇦🇫','94':'🇱🇰','95':'🇲🇲','975':'🇧🇹','977':'🇳🇵','971':'🇦🇪','966':'🇸🇦',
        '974':'🇶🇦','973':'🇧🇭','968':'🇴🇲','964':'🇮🇶','963':'🇸🇾','962':'🇯🇴','961':'🇱🇧',
        '20':'🇪🇬','90':'🇹🇷','967':'🇾🇪','221':'🇸🇳','222':'🇲🇷','58':'🇻🇪','260':'🇿🇲'
    }
    
    for code, flag in country_flags.items():
        if number.startswith(code):
            return f"{flag} {get_country_name(code)}"
    return "🌐 دولة غير معروفة"

def get_country_name(code):
    """اسم الدولة"""
    country_names = {
        '98':'إيران','91':'الهند','1':'أمريكا','44':'بريطانيا','86':'الصين','81':'اليابان',
        '82':'كوريا الجنوبية','65':'سنغافورة','60':'ماليزيا','63':'الفلبين','84':'فيتنام',
        '66':'تايلاند','62':'إندونيسيا','92':'باكستان','880':'بنغلاديش','93':'أفغانستان',
        '94':'سريلانكا','95':'ميانمار','975':'بوتان','977':'نيبال','971':'الإمارات',
        '966':'السعودية','974':'قطر','973':'البحرين','968':'عمان','964':'العراق',
        '963':'سوريا','962':'الأردن','961':'لبنان','20':'مصر','90':'تركيا','967':'اليمن',
        '221':'السنغال','222':'موريتانيا','58':'فنزويلا','260':'زامبيا'
    }
    return country_names.get(code, 'غير معروفة')

def detect_service(sms_text):
    """كشف نوع الخدمة"""
    text_lower = sms_text.lower()
    services = {
        'whatsapp':'WhatsApp', 'telegram':'Telegram', 'facebook':'Facebook', 
        'google':'Google', 'apple':'Apple', 'instagram':'Instagram', 
        'twitter':'Twitter', 'amazon':'Amazon', 'microsoft':'Microsoft',
        'netflix':'Netflix', 'bank':'بنك', 'paypal':'PayPal', 'binance':'Binance',
        'grab':'Grab', 'gojek':'Gojek', 'line':'Line', 'wechat':'WeChat',
        'viber':'Viber', 'signal':'Signal', 'discord':'Discord'
    }
    
    for key, service in services.items():
        if key in text_lower:
            return service
    return "خدمة غير معروفة"

def extract_otp(sms_text):
    """استخراج رمز OTP"""
    # البحث عن أرقام 4-8 خانات
    numbers = re.findall(r'\b\d{4,8}\b', sms_text)
    if numbers:
        return numbers[0]
    
    # البحث عن OTP بشرطة
    hyphen_otp = re.findall(r'\b\d{3,4}-\d{3,4}\b', sms_text)
    if hyphen_otp:
        return hyphen_otp[0]
    
    return None

def format_message(date, number, cli, sms):
    """تنسيق الرسالة النهائية"""
    masked_number = number[:3] + '***' + number[6:] if len(number) > 6 else number
    country_with_flag = get_country_with_flag(number)
    service = detect_service(sms)
    otp_code = extract_otp(sms)
    current_time = time.strftime("%Y-%m-%d %H:%M:%S")
    
    return f"""🔥 <b>{service}</b> RECEIVED! ✨

⏰ <b>الوقت:</b> {current_time}
🌍 <b>الدولة:</b> {country_with_flag}
⚙️ <b>الخدمة:</b> {service}
☎️ <b>الرقم:</b> {masked_number}
🔑 <b>OTP:</b> <code>{otp_code if otp_code else 'غير متوفر'}</code>
📩 <b>الرسالة الكاملة:</b>

<blockquote>{sms}</blockquote>"""

def parse_simple_math(text):
    """حل الكابتشا الرياضي"""
    if not text:
        return None
    
    # البحث عن العمليات الحسابية
    m = re.search(r'(-?\d+)\s*([\+\-\*/xX])\s*(-?\d+)', text)
    if not m:
        return None
        
    a = int(m.group(1))
    op = m.group(2)
    b = int(m.group(3))
    
    if op == '+':
        return a + b
    if op == '-':
        return a - b
    if op in ['*', 'x', 'X']:
        return a * b
    if op == '/':
        try:
            return a // b
        except:
            return None
    return None

def auto_login(driver, username, password):
    """تسجيل الدخول التلقائي"""
    for attempt in range(1, MAX_LOGIN_RETRIES + 1):
        try:
            print(f"🔄 محاولة تسجيل الدخول {attempt}...")
            
            driver.get(LOGIN_PAGE)
            time.sleep(3)
            
            # إدخال اسم المستخدم وكلمة المرور
            username_el = try_find_element(driver, [
                (By.NAME, "username"),
                (By.ID, "username"), 
                (By.NAME, "user"),
                (By.XPATH, "//input[@type='text']")
            ])
            
            password_el = try_find_element(driver, [
                (By.NAME, "password"),
                (By.ID, "password"),
                (By.NAME, "pass"), 
                (By.XPATH, "//input[@type='password']")
            ])
            
            username_el.clear()
            username_el.send_keys(username)
            password_el.clear()
            password_el.send_keys(password)
            time.sleep(1)
            
            # حل الكابتشا
            captcha_text = ""
            try:
                lbl = driver.find_element(By.XPATH, "//label[contains(.,'What')]")
                captcha_text = lbl.text.strip()
            except:
                page_txt = driver.page_source
                m = re.search(r'(-?\d+\s*[\+\-\*/xX]\s*-?\d+)', page_txt)
                if m:
                    captcha_text = m.group(1)
            
            captcha_answer = parse_simple_math(captcha_text)
            if captcha_answer is not None:
                captcha_input = try_find_element(driver, [
                    (By.XPATH, "//input[@placeholder='Answer']"),
                    (By.NAME, "answer"),
                    (By.NAME, "captcha")
                ])
                captcha_input.clear()
                captcha_input.send_keys(str(captcha_answer))
                print(f"✅ تم حل الكابتشا: {captcha_answer}")
            
            # النقر على زر الدخول
            login_btn = try_find_element(driver, [
                (By.XPATH, "//button[contains(.,'Sign In') or contains(.,'Login')]"),
                (By.XPATH, "//input[@type='submit']"),
                (By.ID, "login_btn")
            ])
            login_btn.click()
            time.sleep(3)
            
            # الانتقال لصفحة الرسائل
            driver.get(OTP_PAGE)
            time.sleep(2)
            
            print(f"✅ تم التسجيل الدخول بنجاح (المحاولة {attempt})")
            return True
            
        except Exception as e:
            print(f"❌ فشل محاولة الدخول {attempt}: {e}")
            time.sleep(5)
    
    return False

def get_otp_page_html(driver):
    """الحصول على HTML الصفحة"""
    try:
        driver.refresh()
        time.sleep(2)
        return driver.page_source
    except Exception as e:
        print(f"⚠️ خطأ في تحديث الصفحة: {e}")
        return ""

def main_loop():
    """الحلقة الرئيسية للبوت"""
    print("🚀 بدء تشغيل البوت على Railway...")
    
    driver = open_driver()
    
    try:
        if not auto_login(driver, USERNAME, PASSWORD):
            print("❌ فشل التسجيل الدخول بعد جميع المحاولات")
            return
        
        sent_ids = set()
        print("🔍 بدء مراقبة الرسائل...")
        
        while True:
            try:
                html = get_otp_page_html(driver)
                rows = get_sms_rows(html)
                
                for date, number, cli, sms in rows:
                    unique_id = f"{date}|{number}|{sms[:30]}"
                    
                    if unique_id not in sent_ids:
                        msg = format_message(date, number, cli, sms)
                        print(f"📩 رسالة جديدة: {number} - {sms[:40]}...")
                        
                        # إنشاء أزرار التليجرام
                        inline_keyboard = {
                            "inline_keyboard": [[
                                {"text": "➡️ قناة التليجرام", "url": TELEGRAM_CHANNEL_LINK},
                                {"text": "🤖 بوت الأرقام", "url": f"https://t.me/{TELEGRAM_BOT_USERNAME.lstrip('@')}"}
                            ]]
                        }
                        
                        # إرسال لكل المجموعات
                        for chat_id in GROUP_CHAT_IDS:
                            send_telegram_message(chat_id, msg, inline_keyboard)
                        
                        # حفظ في الملف
                        otp_data = {
                            "number": number,
                            "otp": extract_otp(sms),
                            "service": detect_service(sms),
                            "timestamp": time.time()
                        }
                        
                        try:
                            with open(OTP_QUEUE_FILE, "a", encoding="utf-8") as f:
                                json.dump(otp_data, f, ensure_ascii=False)
                                f.write('\n')
                            print(f"✅ تم حفظ بيانات OTP للرقم: {number}")
                        except Exception as e:
                            print(f"⚠️ فشل حفظ الملف: {e}")
                        
                        sent_ids.add(unique_id)
                
                time.sleep(POLL_INTERVAL_SECONDS)
                
            except Exception as e:
                print(f"⚠️ خطأ في الحلقة الرئيسية: {e}")
                time.sleep(10)
                
    except KeyboardInterrupt:
        print("⏹️ إيقاف البوت بواسطة المستخدم")
    except Exception as e:
        print(f"❌ خطأ غير متوقع: {e}")
    finally:
        try:
            driver.quit()
            print("🔴 تم إغلاق المتصفح")
        except:
            pass

if __name__ == "__main__":
    main_loop()
