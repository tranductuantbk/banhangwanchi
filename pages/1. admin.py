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
# KHỐI TỰ ĐỘNG SỬA LỖI DATABASE
# ==========================================
try:
    with conn.session as s:
        s.execute(text("""
            CREATE TABLE IF NOT EXISTS agency_products (
                id SERIAL PRIMARY KEY,
                product_code TEXT UNIQUE,
                name TEXT,
                size TEXT,
                price_agency NUMERIC
            );
        """))
        s.execute(text("""
            CREATE TABLE IF NOT EXISTS company_products (
                id SERIAL PRIMARY KEY,
                product_code TEXT UNIQUE,
                name TEXT,
                size TEXT,
                price_agency NUMERIC,
                price_company NUMERIC,
                image_data TEXT
            );
        """))
        s.execute(text("ALTER TABLE agency_products ADD COLUMN IF NOT EXISTS unit_per_pack INTEGER DEFAULT 100;"))
        s.execute(text("ALTER TABLE company_products ADD COLUMN IF NOT EXISTS unit_per_pack INTEGER DEFAULT 100;"))
        s.execute(text("ALTER TABLE company_products ADD COLUMN IF NOT EXISTS price_agency NUMERIC;"))
        s.execute(text("ALTER TABLE company_products ADD COLUMN IF NOT EXISTS price_company NUMERIC;"))
        s.execute(text("ALTER TABLE company_products ADD COLUMN IF NOT EXISTS image_data TEXT;"))
        try: s.execute(text("ALTER TABLE agency_products ADD UNIQUE (product_code);"))
        except: pass
        try: s.execute(text("ALTER TABLE company_products ADD UNIQUE (product_code);"))
        except: pass
        s.commit()
except: pass

# --- KIỂM TRA FONT & LOGO ---
FONT_FILES = ["arial.ttf", "Arial.ttf", "ARIAL.TTF"]
available_font = None
for f in FONT_FILES:
    if os.path.exists(f):
        available_font = f
        break

LOGO_FILES = ["logo.png", "logo.jpg", "LOGO.png", "LOGO.jpg", "logo.jpeg"]
available_logo = None
for l in LOGO_FILES:
    if os.path.exists(l):
        available_logo = l
        break

# --- HÀM HỖ TRỢ ---
def convert_drive_link(raw_url):
    if not raw_url: return ""
    match = re.search(r"(?<=/d/)[a-zA-Z0-9_-]+|(?<=id=)[a-zA-Z0-9_-]+", raw_url)
    if match: return f"https://drive.google.com/thumbnail?id={match.group(0)}&sz=w1000"
    return raw_url

def load_font_to_pdf(pdf):
    if available_font:
        try:
            pdf.add_font("ArialVN", style="", fname=available_font, uni=True)
            pdf.add_font("ArialVN", style="B", fname=available_font, uni=True)
        except:
            try:
                pdf.add_font("ArialVN", style="", fname=available_font)
                pdf.add_font("ArialVN", style="B", fname=available_font)
            except: pass

def get_font_name():
    return "ArialVN" if available_font else "Helvetica"

class WanchiPDF(FPDF):
    def header_wanchi(self):
        font_name = get_font_name()
        
        # 1. Chèn Logo
        if available_logo:
            self.image(available_logo, x=10, y=8, h=15)
        else:
            self.set_font(font_name, "B", 18)
            self.cell(100, 10, "WANCHI", border=0, align='L')
        
        # 2. Thông tin bên phải
        self.set_font(font_name, "B", 10)
        self.set_xy(130, 8)
        self.multi_cell(70, 5, txt=f"BẢNG BÁO GIÁ CÔNG TY\nTháng {datetime.now().strftime('%m/%Y')}\nHotline: 0902.580.828", align='R')
        self.ln(10)

# --- XUẤT PDF CHO ĐẠI LÝ ---
def export_pdf_agency(df):
    if not available_font: return None
    
    pdf = FPDF()
    pdf.add_page()
    load_font_to_pdf(pdf)
    font_name = get_font_name()
        
    pdf.set_font(font_name, "B", 16)
    pdf.cell(200, 10, txt="BẢNG BÁO GIÁ ĐẠI LÝ", ln=True, align='C')
    pdf.ln(5)
    
    pdf.set_font(font_name, "B", 10)
    pdf.set_fill_color(230, 230, 230)
    cols = ["Mã SP", "Tên SP", "Kích thước", "Giá ĐL", "Lốc"]
    widths = [35, 60, 40, 30, 25]
    
    for i, col in enumerate(cols):
        pdf.cell(widths[i], 10, txt=str(col), border=1, fill=True, align='C')
    pdf.ln()
    
    pdf.set_font(font_name, "", 9)
    for _, row in df.iterrows():
        pdf.cell(widths[0], 10, txt=str(row['product_code']), border=1, align='C')
        pdf.cell(widths[1], 10, txt=str(row['name'])[:35], border=1, align='L')
        pdf.cell(widths[2], 10, txt=str(row['size']), border=1, align='C')
        pdf.cell(widths[3], 10, txt=f"{int(row['price_agency']):,}".replace(",", "."), border=1, align='R')
        pdf.cell(widths[4], 10, txt=str(row['unit_per_pack']), border=1, align='C')
        pdf.ln()
    return bytes(pdf.output())

# --- XUẤT PDF CÔNG TY ---
def export_pdf_company_pro(df):
    if not available_font: return None
    
    pdf = WanchiPDF()
    load_font_to_pdf(pdf)
    pdf.add_page()
    font_name = get_font_name()
        
    pdf.header_wanchi()
    
    # Header Bảng
    pdf.set_fill_color(230, 230, 230)
    pdf.set_text_color(0, 0, 0)
    pdf.set_font(font_name, "", 10)
    
    # Tổng độ rộng = 190 (Vừa khít khổ A4)
    widths = [40, 30, 50, 35, 20, 15]
    headers = ["Hình ảnh", "Mã SP", "Diễn giải", "Kích thước", "Đơn giá", "Lốc"]
    
    for i, head in enumerate(headers):
        pdf.cell(widths[i], 12, txt=head, border=1, fill=True, align='C')
    pdf.ln()
    
    # Nội dung Bảng
    pdf.set_font(font_name, "", 9)
    row_h = 35 
    
    for _, row in df.iterrows():
        if pdf.get_y() + row_h > 270:
            pdf.add_page()
            pdf.set_fill_color(230, 230, 230)
            pdf.set_font(font_name, "", 10)
            for i, head in enumerate(headers):
                pdf.cell(widths[i], 12, txt=head, border=1, fill=True, align='C')
            pdf.ln()
            pdf.set_font(font_name, "", 9)

        x = pdf.get_x()
        y = pdf.get_y()

        # 1. Hình ảnh
        pdf.rect(x, y, widths[0], row_h)
        img_url = row.get('image_data', '')
        if img_url and str(img_url).strip() != "":
            try:
                # Thêm headers để vượt qua tường lửa tải ảnh
                req_headers = {'User-Agent': 'Mozilla/5.0'}
                res = requests.get(img_url, headers=req_headers, timeout=5)
                if res.status_code == 200 and 'image' in res.headers.get('Content-Type', ''):
                    with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as tmp:
                        tmp.write(res.content)
                        tmp_path = tmp.name
                    pdf.image(tmp_path, x=x+2, y=y+2, w=widths[0]-4, h=row_h-4)
                    os.remove(tmp_path)
            except: pass

        # 2. Mã SP
        pdf.set_xy(x + widths[0], y)
        pdf.rect(x + widths[0], y, widths[1], row_h)
        pdf.set_xy(x + widths[0], y + 15)
        pdf.multi_cell(widths[1], 5, txt=str(row.get('product_code', '')), border=0, align='C')

        # 3. Diễn giải
        curr_x = x + widths[0] + widths[1]
        pdf.rect(curr_x, y, widths[2], row_h)
        pdf.set_xy(curr_x + 2, y + 10)
        pdf.multi_cell(widths[2]-4, 5, txt=str(row.get('name', '')), border=0, align='C')

        # 4. Kích thước (Nằm ngang chuẩn)
        curr_x += widths[2]
        pdf.rect(curr_x, y, widths[3], row_h)
        pdf.set_xy(curr_x + 2, y + 12)
        size_clean = str(row.get('size', '')).strip()
        pdf.multi_cell(widths[3]-4, 5, txt=size_clean, border=0, align='C')

        # 5. Đơn giá
        curr_x += widths[3]
        pdf.rect(curr_x, y, widths[4], row_h)
        pdf.set_xy(curr_x, y + 15)
        price = f"{int(row.get('price_company', 0)):,}".replace(",", ".")
        pdf.cell(widths[4], 5, txt=price, border=0, align='C')

        # 6. Lốc
        curr_x += widths[4]
        pdf.rect(curr_x, y, widths[5], row_h)
        pdf.set_xy(curr_x, y + 15)
        pdf.cell(widths[5], 5, txt="1 cái", border=0, align='C')

        pdf.set_xy(x, y + row_h)

    return bytes(pdf.output())

# --- MAIN UI ---
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
                try:
                    with conn.session as s:
                        s.execute(text("INSERT INTO agency_products (product_code, name, size, price_agency, unit_per_pack) VALUES (:c, :n, :s, :p, :pk) ON CONFLICT (product_code) DO UPDATE SET name=:n, size=:s, price_agency=:p, unit_per_pack=:pk"), 
                                  {"c":str(code), "n":str(name), "s":str(size), "p":float(price), "pk":int(pack)})
                        s.commit()
                    st.success("Đã lưu!")
                except: pass
        
        st.divider()
        st.subheader("Bảng giá Đại lý (Nội bộ)")
        df_a = conn.query("SELECT * FROM agency_products ORDER BY id DESC", ttl=0)
        if not df_a.empty:
            st.dataframe(df_a[['product_code', 'name', 'size', 'price_agency', 'unit_per_pack']])
            if not available_font:
                st.error("⚠️ TÍNH NĂNG XUẤT PDF BỊ KHÓA: Chưa có file Arial.ttf trên Github.")
            else:
                if st.button("📄 Xuất PDF Đại lý"):
                    pdf_a_bytes = export_pdf_agency(df_a)
                    st.download_button("📥 TẢI BÁO GIÁ ĐẠI LÝ", data=pdf_a_bytes, file_name="Bao_Gia_Dai_Ly_Wanchi.pdf", mime="application/pdf")

    with tab2:
        st.subheader("Bước 2: Gắn ảnh thiết kế & Tính giá Công ty")
        df_a2 = conn.query("SELECT * FROM agency_products", ttl=0)
        if not df_a2.empty:
            sel = st.selectbox("Chọn sản phẩm:", df_a2['product_code'])
            target = df_a2[df_a2['product_code'] == sel].iloc[0]
            price_co = round(float(target['price_agency']) / 0.55, 0)
            
            with st.form("co_form"):
                st.write(f"Sản phẩm: **{target['name']}**")
                st.write(f"Giá Công ty tự động (/0.55): **{int(price_co):,} đ**")
                raw_img = st.text_input("Dán link ảnh Google Drive của thiết kế:")
                if st.form_submit_button("Xác nhận Báo giá Công ty"):
                    final_i = convert_drive_link(raw_img)
                    with conn.session as s:
                        s.execute(text("INSERT INTO company_products (product_code, name, size, price_company, image_data) VALUES (:c, :n, :s, :p, :i) ON CONFLICT (product_code) DO UPDATE SET name=:n, size=:s, price_company=:p, image_data=:i"),
                                  {"c":str(target['product_code']), "n":str(target['name']), "s":str(target['size']), "p":float(price_co), "i":str(final_i)})
                        s.commit()
                    st.success("Đã lên đời sản phẩm Công ty!")

    with tab3:
        st.subheader("Xuất báo giá PDF chuẩn WANCHI")
        df_c = conn.query("SELECT * FROM company_products ORDER BY id DESC", ttl=0)
        if not df_c.empty:
            st.dataframe(df_c[['product_code', 'name', 'size', 'price_company']])
            
            if not available_font:
                st.error("⚠️ TÍNH NĂNG XUẤT PDF BỊ KHÓA: Chưa có file Arial.ttf trên Github.")
            else:
                if st.button("🚀 BẮT ĐẦU ĐÓNG GÓI PDF (KÈM LOGO & ẢNH)"):
                    with st.spinner("Đang vẽ bảng và chèn ảnh... Có thể mất 10-30s..."):
                        pdf_bytes = export_pdf_company_pro(df_c)
                        st.session_state.ready_pdf = pdf_bytes
                
                if 'ready_pdf' in st.session_state:
                    st.download_button("📥 TẢI FILE BÁO GIÁ", data=st.session_state.ready_pdf, file_name=f"Bao_Gia_Cong_Ty_Wanchi_{datetime.now().strftime('%d%m%y')}.pdf", mime="application/pdf")

    with tab4:
        st.subheader("Lịch sử Đơn hàng")
        try:
            df_o = conn.query("SELECT * FROM orders ORDER BY order_date DESC", ttl=0)
            if not df_o.empty:
                for _, row in df_o.iterrows():
                    with st.container(border=True):
                        c1, c2, c3 = st.columns([3, 2, 1])
                        c1.write(f"👤 **{row['customer_name']}** - 📞 {row['customer_phone']}")
                        c2.write(f"💰 {int(row['total_amount']):,} đ")
                        if c3.button("🗑️ Xóa", key=f"del_{row['id']}"):
                            with conn.session as s:
                                s.execute(text("DELETE FROM orders WHERE id=:id"), {"id": row['id']})
                                s.commit()
                            st.rerun()
                        with st.expander("Xem chi tiết"):
                            st.text(row['order_items'])
        except: pass
