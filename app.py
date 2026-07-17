import streamlit as st
from pypdf import PdfReader
import re
import random
# --- ŞİFRELEME SİSTEMİ BAŞLANGICI ---
if "authenticated" not in st.session_state:
    st.session_state["authenticated"] = False

if not st.session_state["authenticated"]:
    st.title("🔒 Korumalı Alan")
    girilen_sifre = st.text_input("Lütfen erişim şifresini girin:", type="password")
    
    if st.button("Giriş Yap"):
        # Alttaki 'gizli_abi_sifresi' kısmını istediğin şifreyle değiştirebilirsin
        if girilen_sifre == "antalyaçamlıca": 
            st.session_state["authenticated"] = True
            st.rerun()
        else:
            st.error("Hatalı şifre! Lütfen tekrar deneyin.")
            
    st.stop() # Şifre doğru olana kadar aşağıdaki kodları çalıştırmaz.
# --- ŞİFRELEME SİSTEMİ BİTİŞİ ---

st.set_page_config(page_title="Molla Cami Sual-Cevap Çalışma Alanı", page_icon="📖", layout="wide")

# ---------------------------------------------------------------------------
# NEDEN ESKİ KOD ÇALIŞMIYORDU?
# 1) PDF'nin gömülü fontunda ToUnicode eşlemesi bozuk: "11-" metinden "00-",
#    "20-" ise "12-" gibi YANLIŞ rakamlarla çıkıyor. Yani çıkarılan rakam
#    DEĞERİNE güvenemeyiz (sadece 1-10 arası doğru geliyor, sonrası bozuk).
# 2) Eski regex `^\s*(\d+)...` sadece Latin rakamı arıyordu; Arapça rakamlar
#    (٠-٩) hiç eşleşmiyordu, ilk soru ise Farsça-stili "۱" (U+06F1) kullanıyor.
#
# ÇÖZÜM: Rakam değerini hiç okumuyoruz. Sadece "bu satır yeni bir SORU
# sınırı mı?" diye bakıyoruz (satır rakam+tire ile başlıyor VE bir soru
# kalıbı - "؟" ya da "ويريكز/سويله يكز" - içeriyor) ve bulduğumuz sırayla
# 1, 2, 3... diye KENDİMİZ numaralandırıyoruz. Bu şekilde 230/230 soru
# doğru sırayla ayrışıyor (test edildi).
# ---------------------------------------------------------------------------

def clean_and_standardize_text(text):
    if not text:
        return ""
    arabic_digits = {'٠': '0', '١': '1', '٢': '2', '٣': '3', '٤': '4',
                      '٥': '5', '٦': '6', '٧': '7', '٨': '8', '٩': '9'}
    for a, l in arabic_digits.items():
        text = text.replace(a, l)
    text = text.replace('\u200f', '').replace('\u200e', '').replace('\u202a', '').replace('\u202c', '')
    text = re.sub(r'\s+', ' ', text)
    return text.strip()


# Satır başında Arapça (٠-٩), Farsça-stili (۰-۹) veya Latin rakam + tire
Q_START_RE = re.compile(r'^[0-9\u0660-\u0669\u06F0-\u06F9]+\s*[-–]')

# "؟" olmayan ama gerçekten soru olan birkaç satır için (emir kipiyle biten
# sorular, örn. "...معلومات ويريكز.") ek anahtar kelimeler
QUESTION_KEYWORDS = ['ويريكز', 'وير يكز', 'سويله يكز', 'سويلينكز']

# Kitapta bölüm başlığı olarak tek satır halinde geçen, hiçbir sorunun
# cevabına karışmaması gereken satırlar
SECTION_HEADERS = {
    'معلومات', 'كلمه، كلام و اعراب', 'غير منصرف', 'غري منصرف',
    'مرفوعات', 'منصوبات', 'مجرورات', 'جمرورات', 'توابع', 'مبني', 'مبنى',
    'فعل', 'حرف',
}

# Kitapta bazı cevaplar TABLO olarak veriliyor (zamir tabloları, fiil-i
# muzari irab tablosu vb). PDF'den metin çıkarılırken tablo satırları farklı
# bir sırada geliyor ve otomatik eşleşmiyor. Bu yüzden bu birkaç soru için
# elle düzeltme ekliyoruz. Soru numarası -> düzeltilmiş cevap.
# İhtiyaç oldukça buraya yeni satır ekleyebilirsin.
MANUAL_ANSWER_OVERRIDES = {
    135: "مرفوع متصل ضميرلر: ضربْتُ - ضربْتِ - ضربْتَ - ضربَتْ - ضربَ (تكيل) | "
         "ضربْنَا - ضربْتُمَا - ضربْتُمَا - ضربَتَا - ضربَا (تثنيه) | "
         "ضربْنَا - ضربْتُمْ - ضربْتُنَّ - ضربُوا - ضربْنَ (جمع)",
    136: "مرفوع منفصل ضميرلر: اَنَا - اَنْتَ - اَنْتِ - هُوَ - هِىَ (تكيل) | "
         "نَحْنُ - اَنْتُمَا - اَنْتُمَا - هُمَا - هُمَا (تثنيه) | "
         "نَحْنُ - اَنْتُمْ - اَنْتُنَّ - هُمْ - هُنَّ (جمع)",
    137: "منصوب متصل (فعله متصل): ضربَنِى - ضربَكَ - ضربَكِ - ضربَهُ - ضربَهَا ... | "
         "منصوب متصل (حرفه متصل): اِنَّنِى - اِنَّكَ - اِنَّكِ - اِنَّهُ - اِنَّهَا ...",
    138: "منصوب منفصل ضميرلر: اِيَّاىَ - اِيَّاكَ - اِيَّاكِ - اِيَّاهُ - اِيَّاهَا - "
         "اِيَّانَا - اِيَّاكُمَا - اِيَّاهُمَا - اِيَّاكُمْ - اِيَّاكُنَّ - اِيَّاهُمْ - اِيَّاهُنَّ",
    139: "مجرور متصل (اسمه متصل): غلامِى - غلامُكَ - غلامُكِ - غلامُهُ - غلامُهَا ... | "
         "مجرور متصل (حرفه متصل): لَِى - لَكَ - لَكِ - لَهُ - لَهَا ...",
    191: "حمل اعراب / حالت رفعى / حالت نصبى / حالت جزمى: "
         "آخرينه مرفوع ضمير بيتيشمين، آخرى حرف صحيح فعل مضارع -> ضمه / فتحه / حركه نك حذفى | "
         "آخرينه مرفوع ضمير بيتيشمين، آخرى حرف علت فعل مضارع -> ضمه / فتحه / آخرينك (حرفك) حذفى | "
         "آخرينه جمع مؤنث نوننك غيرى مرفوع ضمير بيتيشن فعل مضارع -> نون / نونك حذفى / نونك حذفى",
}


def looks_like_question(line: str) -> bool:
    if '؟' in line:
        return True
    return any(k in line for k in QUESTION_KEYWORDS)


@st.cache_data
def load_and_parse_pdf_robust(pdf_path):
    reader = PdfReader(pdf_path)
    all_lines = []

    for page in reader.pages:
        text = page.extract_text()
        if not text:
            continue
        for line in text.split('\n'):
            cleaned = clean_and_standardize_text(line)
            if not cleaned:
                continue
            if re.match(r'^-\s*\d+\s*-$', cleaned):   # sayfa numarası, örn. "-2-"
                continue
            if cleaned in SECTION_HEADERS:             # bölüm başlığı, cevaba karışmasın
                continue
            all_lines.append(cleaned)

    questions = []
    current = None
    q_num = 0

    for line in all_lines:
        if Q_START_RE.match(line) and looks_like_question(line):
            if current:
                questions.append(current)
            q_num += 1
            # numaralı-tire kısmını at, geri kalan soru metnini al
            question_text = Q_START_RE.sub('', line).strip(' -–')
            current = {"num": q_num, "question": f"{q_num} - {question_text}", "answer_lines": []}
        else:
            if current:
                current["answer_lines"].append(line)

    if current:
        questions.append(current)

    final_questions = []
    for q in questions:
        answer = " ".join(q["answer_lines"]).strip()
        if q["num"] in MANUAL_ANSWER_OVERRIDES:
            answer = MANUAL_ANSWER_OVERRIDES[q["num"]]
        if len(answer) < 5:
            answer = "(Bu sorunun cevabı kitapta tablo olarak veriliyor; PDF'den otomatik ayrıştırılamadı. " \
                     "MANUAL_ANSWER_OVERRIDES sözlüğüne elle ekleyebilirsin.)"
        final_questions.append({"num": q["num"], "question": q["question"], "answer": answer})

    return final_questions


def categorize_questions_strict(questions):
    categories = {
        "Giriş & Mukaddime (1-7)": [],
        "Kelime, Kelam ve İrab (8-26)": [],
        "Gayri Munsarif (27-42)": [],
        "Merfuat (Fail, Mübteda, Haber) (43-64)": [],
        "Mansubat (Mefuller, Hal, Temyiz, Müstesna) (65-100)": [],
        "Mecrurat & İzafet (101-111)": [],
        "Tevabi (Naat, Atıf, Tekid, Bedel) (112-127)": [],
        "Mebni & Zamirler & İsim Soylu Kelimeler (128-185)": [],
        "Fiiller (Mazi, Muzari, Avamil) (186-215)": [],
        "Harfler (Harf-i Cerler, Edatlar, Tanvin) (216-230)": [],
    }
    for q in questions:
        n = q["num"]
        if 1 <= n <= 7: categories["Giriş & Mukaddime (1-7)"].append(q)
        elif 8 <= n <= 26: categories["Kelime, Kelam ve İrab (8-26)"].append(q)
        elif 27 <= n <= 42: categories["Gayri Munsarif (27-42)"].append(q)
        elif 43 <= n <= 64: categories["Merfuat (Fail, Mübteda, Haber) (43-64)"].append(q)
        elif 65 <= n <= 100: categories["Mansubat (Mefuller, Hal, Temyiz, Müstesna) (65-100)"].append(q)
        elif 101 <= n <= 111: categories["Mecrurat & İzafet (101-111)"].append(q)
        elif 112 <= n <= 127: categories["Tevabi (Naat, Atıf, Tekid, Bedel) (112-127)"].append(q)
        elif 128 <= n <= 185: categories["Mebni & Zamirler & İsim Soylu Kelimeler (128-185)"].append(q)
        elif 186 <= n <= 215: categories["Fiiller (Mazi, Muzari, Avamil) (186-215)"].append(q)
        elif 216 <= n <= 230: categories["Harfler (Harf-i Cerler, Edatlar, Tanvin) (216-230)"].append(q)
    return {k: v for k, v in categories.items() if len(v) > 0}


# --- Arayüz ---
st.title("📖 Molla Cami Sual ve Cevapları Çalışma Kartları")
st.markdown("---")

try:
    all_questions = load_and_parse_pdf_robust("Molla_Cami.pdf")
    st.sidebar.success(f"Toplam {len(all_questions)} soru bulundu (beklenen: 230)")

    bölümler = categorize_questions_strict(all_questions)

    st.sidebar.header("📚 Çalışma Menüsü")
    secilen_bölüm = st.sidebar.selectbox("Bir Çalışma Başlığı Seçiniz:", list(bölümler.keys()))

    bölüm_soruları = bölümler[secilen_bölüm]

    st.subheader(f"📍 Mevcut Bölüm: {secilen_bölüm}")
    st.info(f"Bu bölümde toplam **{len(bölüm_soruları)}** soru bulunmaktadır.")

    if "current_question" not in st.session_state or st.session_state.get("last_section") != secilen_bölüm:
        st.session_state["current_question"] = random.choice(bölüm_soruları) if bölüm_soruları else None
        st.session_state["last_section"] = secilen_bölüm
        st.session_state["show_answer"] = False

    if st.button("🎲 Başka Bir Rastgele Soru Getir", type="primary"):
        if bölüm_soruları:
            st.session_state["current_question"] = random.choice(bölüm_soruları)
        st.session_state["show_answer"] = False
        st.rerun()

    aktif_soru = st.session_state["current_question"]

    if aktif_soru:
        st.markdown("---")
        st.markdown("### ❓ SORU")
        st.info(aktif_soru["question"])

        if st.session_state["show_answer"]:
            if st.button("👁️ Cevabı Gizle"):
                st.session_state["show_answer"] = False
                st.rerun()
            st.markdown("### 💡 CEVAP")
            st.success(aktif_soru["answer"])
        else:
            if st.button("👁️ Cevabı Göster"):
                st.session_state["show_answer"] = True
                st.rerun()
    else:
        st.warning("Bu kategoride görüntülenecek soru bulunamadı.")

except FileNotFoundError:
    st.error("❌ PDF Dosyası Bulunamadı! Lütfen dosya adının doğru olduğundan emin olun.")
except Exception as e:
    st.error(f"⚠️ Bir hata oluştu: {e}")