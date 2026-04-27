import streamlit as st
import pandas as pd
from sqlalchemy import text
from fpdf import FPDF
import re
import base64
from datetime import datetime
import requests
import tempfile
import os

st.set_page_config(page_title="Wanchi Admin - Quản lý Kho", layout="wide")
conn = st.connection("postgresql", type="sql", pool_pre_ping=True)

# ==========================================
# KHỐI TỰ ĐỘNG TẢI FONT & LOGO
# ==========================================
FONT_PATH = "Arial.ttf"
LOGO_PATH = "logo.png" # Hoặc logo.jpg

# --- HÀM HỖ TRỢ PDF ---
def convert_drive_link(raw_url):
    if not raw_url: return ""
    match = re.search(r"(?<=/d/)[a-zA-Z0-9_-]+|(?<=id=)[a-zA-Z0-9_-]+", raw_url)
    if match: return f"https://drive.google.com/thumbnail?id={match.group(0)}&sz=w1000"
    return raw_url

class WanchiPDF(FPDF):
    def header_wanchi(self):
        # 1. Chèn Logo
        if os.path.exists(LOGO_PATH):
            self.image(LOGO_PATH, x=10, y=8, h=15)
        elif os.path.exists("logo.jpg"):
            self.image("logo.jpg", x=10, y=8, h=15)
        else:
            self.set_font("Arial", "B", 16)
            self.cell(100, 10, "WANCHI FACTORY", 0, 0, 'L')
        
        # 2. Thông tin bên phải
        self.set_font("Arial", "", 10)
        self.set_xy(140, 8)
        self.multi_cell(60, 5, txt=f"BẢNG BÁO GIÁ\nTháng {datetime.now().strftime('%m/%Y')}\nHotline: 0902.580.828", align='R')
        self.ln(10)

def export_pdf_company_pro(df):
    pdf = WanchiPDF()
    pdf.add_page()
    
    # Load Font
    if os.path.exists(FONT_PATH):
        pdf.add_font("Arial", style="", fname=FONT_PATH, uni=True)
        pdf.set_font("Arial", size=10)
    else:
        pdf.set_font("Helvetica", size=10)
        
    pdf.header_wanchi()
    
    # Header Bảng
    pdf.set_fill_color(41, 128, 185) # Màu xanh chuyên nghiệp
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Arial", "B", 10)
    
    # [Hình ảnh, Mã SP, Diễn giải, Kích thước, Đơn giá, Lốc]
    widths = [40, 30, 45, 35, 25, 15]
    headers = ["Hình ảnh", "Mã SP", "Diễn giải", "Kích thước", "Đơn giá", "Lốc"]
    
    for i, head in enumerate(headers):
        pdf.cell(widths[i], 12, txt=head, border=1, fill=True, align='C')
    pdf.ln()
    
    # Nội dung Bảng
    pdf.set_text_color(0, 0, 0)
    pdf.set_font("Arial", "", 9)
    row_h = 35 # Chiều cao cố định cho mỗi dòng để cân đối ảnh
    
    for _, row in df.iterrows():
        if pdf.get_y() + row_h > 270:
            pdf.add_page()
            # Vẽ lại header nếu qua trang mới
            pdf.set_fill_color(41, 128, 185)
            pdf.set_text_color(255, 255, 255)
            for i, head in enumerate(headers):
                pdf.cell(widths[i], 12, txt=head, border=1, fill=True, align='C')
            pdf.ln()
            pdf.set_text_color(0, 0, 0)

        x = pdf.get_x()
        y = pdf.get_y()

        # 1. Ô Hình ảnh
        pdf.rect(x, y, widths[0], row_h)
        img_url = row.get('image_data', '')
        if img_url:
            try:
                res = requests.get(img_url, timeout=5)
                if res.status_code == 200:
                    with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as tmp:
                        tmp.write(res.content)
                        pdf.image(tmp.name, x=x+2, y=y+2, w=widths[0]-4, h=row_h-4)
                    os.remove(tmp.name)
            except: pass

        # 2. Ô Mã SP
        pdf.set_xy(x + widths[0], y)
        pdf.cell(widths[1], row_h, txt=str(row['product_code']), border=1, align='C')

        # 3. Ô Diễn giải (Dùng MultiCell để không bị đè chữ)
        pdf.set_xy(x + widths[0] + widths[1], y)
        pdf.rect(x + widths[0] + widths[1], y, widths[2], row_h)
        pdf.set_xy(x + widths[0] + widths[1] + 2, y + 5)
        pdf.multi_cell(widths[2]-4, 5, txt=str(row['name']), border=0, align='L')

        # 4. Ô Kích thước
        curr_x = x + widths[0] + widths[1] + widths[2]
        pdf.rect(curr_x, y, widths[3], row_h)
        pdf.set_xy(curr_x + 2, y + 10)
        size_str = str(row['size']).replace(" ", "")
        pdf.multi_cell(widths[3]-4, 5, txt=size_str, border=0, align='C')

        # 5. Ô Đơn giá
        curr_x += widths[3]
        pdf.set_xy(curr_x, y)
        price = f"{int(row['price_company']):,}".replace(",", ".")
        pdf.cell(widths[4], row_h, txt=price, border=1, align='C')

        # 6. Ô Lốc
        curr_x += widths[4]
        pdf.set_xy(curr_x, y)
        pdf.cell(widths[5], row_h, txt="1 cái", border=1, align='C')

        pdf.set_xy(x, y + row_h)

    return bytes(pdf.output())

# ==========================================
# PHẦN GIAO DIỆN ADMIN CHÍNH
# ==========================================
if 'is_admin' not in st.session_state:
    st.session_state.is_admin = False

st.title("⚙️ Quản lý Báo giá WANCHI Pro")

if not st.session_state.is_admin:
    pwd = st.text_input("Mật khẩu Admin", type="password")
    if st.button("Đăng nhập"):
        if pwd == st.secrets["admin"]["password"]:
            st.session_state.is_admin = True
            st.rerun()
        else: st.error("Sai mật khẩu!")
else:
    tab1, tab2, tab3, tab4 = st.tabs(["➕ Nhập SP Đại lý", "🏢 Lên đời SP Công ty", "📈 Danh sách Công ty", "📜 Đơn hàng"])

    with tab1:
        st.subheader("Bước 1: Nhập hàng thô từ xưởng")
        with st.form("agency_add"):
            c1, c2 = st.columns(2)
            code = c1.text_input("Mã sản phẩm")
            name = c2.text_input("Tên diễn giải")
            size = c1.text_input("Kích thước (D x R x C)")
            price = c2.number_input("Giá gốc Đại lý", min_value=0)
            pack = st.number_input("Quy cách Lốc", value=100)
            if st.form_submit_button("Lưu kho Đại lý"):
                with conn.session as s:
                    s.execute(text("INSERT INTO agency_products (product_code, name, size, price_agency, unit_per_pack) VALUES (:c, :n, :s, :p, :pk) ON CONFLICT (product_code) DO UPDATE SET price_agency=:p"), 
                              {"c":code, "n":name, "s":size, "p":price, "pk":pack})
                    s.commit()
                st.success("Đã lưu!")

    with tab2:
        st.subheader("Bước 2: Gắn ảnh thiết kế & Tính giá Công ty")
        df_a = conn.query("SELECT * FROM agency_products", ttl=0)
        if not df_a.empty:
            sel = st.selectbox("Chọn sản phẩm:", df_a['product_code'])
            target = df_a[df_a['product_code'] == sel].iloc[0]
            price_co = round(float(target['price_agency']) / 0.55, 0)
            
            with st.form("co_form"):
                st.write(f"Sản phẩm: **{target['name']}**")
                st.write(f"Giá Công ty tự động (/0.55): **{int(price_co):,} đ**")
                raw_img = st.text_input("Dán link ảnh Google Drive của thiết kế:")
                if st.form_submit_button("Xác nhận Báo giá Công ty"):
                    final_i = convert_drive_link(raw_img)
                    with conn.session as s:
                        s.execute(text("INSERT INTO company_products (product_code, name, size, price_company, image_data) VALUES (:c, :n, :s, :p, :i) ON CONFLICT (product_code) DO UPDATE SET price_company=:p, image_data=:i"),
                                  {"c":target['product_code'], "n":target['name'], "s":target['size'], "p":price_co, "i":final_i})
                        s.commit()
                    st.success("Đã lên đời sản phẩm Công ty!")

    with tab3:
        st.subheader("Xuất báo giá PDF chuẩn WANCHI")
        df_c = conn.query("SELECT * FROM company_products ORDER BY id DESC", ttl=0)
        if not df_c.empty:
            st.dataframe(df_c[['product_code', 'name', 'size', 'price_company']])
            
            if st.button("🚀 BẮT ĐẦU ĐÓNG GÓI PDF (KÈM LOGO & ẢNH)"):
                with st.spinner("Đang vẽ bảng và chèn ảnh..."):
                    pdf_bytes = export_pdf_company_pro(df_c)
                    st.session_state.ready_pdf = pdf_bytes
            
            if 'ready_pdf' in st.session_state:
                st.download_button("📥 TẢI FILE BÁO GIÁ.PDF", data=st.session_state.ready_pdf, file_name=f"Bao_Gia_Wanchi_{datetime.now().strftime('%d%m%y')}.pdf")
