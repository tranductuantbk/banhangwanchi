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
        s.commit()
except: pass

# --- KIỂM TRA TÀI NGUYÊN (FONT & LOGO) ---
FONT_PATH = "Arial.ttf"
LOGO_FILES = ["logo.png", "logo.jpg", "LOGO.png", "LOGO.jpg"]
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

class WanchiPDF(FPDF):
    def __init__(self, quote_type="CÔNG TY"):
        super().__init__()
        self.quote_type = quote_type

    def header_wanchi(self):
        # Tải Font
        if os.path.exists(FONT_PATH):
            self.add_font("ArialVN", style="", fname=FONT_PATH, uni=True)
            self.add_font("ArialVN", style="B", fname=FONT_PATH, uni=True)
            font_name = "ArialVN"
        else:
            font_name = "Helvetica"

        # 1. Chèn Logo
        if available_logo:
            self.image(available_logo, x=10, y=8, h=15)
        else:
            self.set_font(font_name, "B", 18)
            self.cell(100, 10, "WANCHI", border=0, align='L')
        
        # 2. Thông tin bên phải
        self.set_font(font_name, "B", 10)
        self.set_xy(130, 8)
        self.multi_cell(70, 5, txt=f"BẢNG BÁO GIÁ {self.quote_type}\nTháng {datetime.now().strftime('%m/%Y')}\nHotline: 0902.580.828", align='R')
        self.ln(10)

def export_pro_pdf(df, mode="AGENCY"):
    title = "ĐẠI LÝ" if mode == "AGENCY" else "CÔNG TY"
    pdf = WanchiPDF(quote_type=title)
    pdf.add_page()
    
    # Xác định Font
    if os.path.exists(FONT_PATH):
        pdf.set_font("ArialVN", size=10)
        font_name = "ArialVN"
    else:
        pdf.set_font("Helvetica", size=10)
        font_name = "Helvetica"
        
    pdf.header_wanchi()
    
    # Header Bảng (Đồng nhất màu xám Wanchi)
    pdf.set_fill_color(230, 230, 230)
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
            for i, head in enumerate(headers):
                pdf.cell(widths[i], 12, txt=head, border=1, fill=True, align='C')
            pdf.ln()

        x, y = pdf.get_x(), pdf.get_y()

        # 1. Hình ảnh
        pdf.rect(x, y, widths[0], row_h)
        img_url = row.get('image_data', '') if mode == "COMPANY" else ""
        if img_url:
            try:
                res = requests.get(img_url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=5)
                if res.status_code == 200:
                    with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as tmp:
                        tmp.write(res.content)
                        pdf.image(tmp.name, x=x+2, y=y+2, w=widths[0]-4, h=row_h-4)
                    os.remove(tmp.name)
            except: pass

        # 2. Mã SP (Canh giữa)
        pdf.set_xy(x + widths[0], y)
        pdf.rect(x + widths[0], y, widths[1], row_h)
        pdf.set_xy(x + widths[0], y + 15)
        pdf.multi_cell(widths[1], 5, txt=str(row.get('product_code', '')), border=0, align='C')

        # 3. Diễn giải (Canh giữa)
        curr_x = x + widths[0] + widths[1]
        pdf.rect(curr_x, y, widths[2], row_h)
        pdf.set_xy(curr_x + 2, y + 10)
        pdf.multi_cell(widths[2]-4, 5, txt=str(row.get('name', '')), border=0, align='C')

        # 4. Kích thước (Nằm ngang chuẩn)
        curr_x += widths[2]
        pdf.rect(curr_x, y, widths[3], row_h)
        pdf.set_xy(curr_x + 2, y + 12)
        pdf.multi_cell(widths[3]-4, 5, txt=str(row.get('size', '')), border=0, align='C')

        # 5. Đơn giá (Lấy theo chế độ)
        curr_x += widths[3]
        pdf.rect(curr_x, y, widths[4], row_h)
        pdf.set_xy(curr_x, y + 15)
        price_val = row.get('price_agency' if mode == "AGENCY" else 'price_company', 0)
        price_str = f"{int(price_val):,}".replace(",", ".")
        pdf.cell(widths[4], 5, txt=price_str, border=0, align='C')

        # 6. Lốc (Lấy theo chế độ)
        curr_x += widths[4]
        pdf.rect(curr_x, y, widths[5], row_h)
        pdf.set_xy(curr_x, y + 15)
        unit = f"{row['unit_per_pack']} cái" if mode == "AGENCY" else "1 cái"
        pdf.cell(widths[5], 5, txt=unit, border=0, align='C')

        pdf.set_xy(x, y + row_h)

    return bytes(pdf.output())

# --- UI ADMIN ---
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
        st.subheader("Nhập sản phẩm Đại lý mới")
        with st.form("agency_add"):
            c1, c2 = st.columns(2)
            code = c1.text_input("Mã sản phẩm")
            name = c2.text_input("Tên diễn giải")
            size = c1.text_input("Kích thước (D x R x C)")
            price = c2.number_input("Giá gốc Đại lý", min_value=0)
            pack = st.number_input("Quy cách Lốc", value=100)
            if st.form_submit_button("Lưu kho Đại lý"):
                with conn.session as s:
                    s.execute(text("INSERT INTO agency_products (product_code, name, size, price_agency, unit_per_pack) VALUES (:c, :n, :s, :p, :pk) ON CONFLICT (product_code) DO UPDATE SET name=:n, size=:s, price_agency=:p, unit_per_pack=:pk"), 
                              {"c":str(code), "n":str(name), "s":str(size), "p":float(price), "pk":int(pack)})
                    s.commit()
                st.success("Đã lưu!")
        
        st.divider()
        st.subheader("Bảng giá Đại lý (Nội bộ)")
        df_a = conn.query("SELECT * FROM agency_products ORDER BY id DESC", ttl=0)
        if not df_a.empty:
            st.dataframe(df_a[['product_code', 'name', 'size', 'price_agency', 'unit_per_pack']])
            if st.button("🚀 XUẤT PDF BÁO GIÁ ĐẠI LÝ CHUYÊN NGHIỆP"):
                with st.spinner("Đang đóng gói file..."):
                    pdf_agency = export_pro_pdf(df_a, mode="AGENCY")
                    st.download_button("📥 TẢI PDF ĐẠI LÝ", data=pdf_agency, file_name=f"Bao_Gia_DaiLy_Wanchi_{datetime.now().strftime('%d%m%y')}.pdf", mime="application/pdf")

    with tab2:
        st.subheader("Bước 2: Gắn ảnh thiết kế & Tính giá Công ty")
        df_a2 = conn.query("SELECT * FROM agency_products", ttl=0)
        if not df_a2.empty:
            sel = st.selectbox("Chọn sản phẩm:", df_a2['product_code'])
            target = df_a2[df_a2['product_code'] == sel].iloc[0]
            price_co = round(float(target['price_agency']) / 0.55, 0)
            
            with st.form("co_form"):
                st.info(f"Sản phẩm: {target['name']}")
                st.write(f"Giá Công ty tự động: {int(price_co):,} đ")
                raw_img = st.text_input("Dán link ảnh Google Drive của thiết kế:")
                if st.form_submit_button("Xác nhận Báo giá Công ty"):
                    final_i = convert_drive_link(raw_img)
                    with conn.session as s:
                        s.execute(text("INSERT INTO company_products (product_code, name, size, price_company, image_data) VALUES (:c, :n, :s, :p, :i) ON CONFLICT (product_code) DO UPDATE SET price_company=:p, image_data=:i"),
                                  {"c":str(target['product_code']), "n":str(target['name']), "s":str(target['size']), "p":float(price_co), "i":str(final_i)})
                        s.commit()
                    st.success("Đã lưu kho Công ty!")

    with tab3:
        st.subheader("Xuất báo giá PDF Công ty")
        df_c = conn.query("SELECT * FROM company_products ORDER BY id DESC", ttl=0)
        if not df_c.empty:
            st.dataframe(df_c[['product_code', 'name', 'size', 'price_company']])
            if st.button("🚀 XUẤT PDF BÁO GIÁ CÔNG TY (KÈM ẢNH)"):
                with st.spinner("Đang tải ảnh và đóng gói..."):
                    pdf_company = export_pro_pdf(df_c, mode="COMPANY")
                    st.download_button("📥 TẢI PDF CÔNG TY", data=pdf_company, file_name=f"Bao_Gia_Wanchi_{datetime.now().strftime('%d%m%y')}.pdf", mime="application/pdf")

    with tab4:
        st.subheader("Lịch sử Đơn hàng")
        df_o = conn.query("SELECT * FROM orders ORDER BY order_date DESC", ttl=0)
        if not df_o.empty:
            for _, row in df_o.iterrows():
                with st.container(border=True):
                    st.write(f"👤 {row['customer_name']} - 💰 {int(row['total_amount']):,} đ")
                    with st.expander("Chi tiết"): st.text(row['order_items'])
