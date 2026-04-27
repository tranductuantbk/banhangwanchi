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

# ==========================================
# LỚP BẢO VỆ TÀI NGUYÊN (FONT & LOGO)
# ==========================================
available_font = None
for f in ["arial.ttf", "Arial.ttf", "ARIAL.TTF", "arial_dl.ttf"]:
    if os.path.exists(f):
        available_font = f
        break

if not available_font:
    try:
        r = requests.get("https://github.com/matomo-org/travis-scripts/raw/master/fonts/Arial.ttf", timeout=5)
        with open("arial_dl.ttf", "wb") as f:
            f.write(r.content)
        available_font = "arial_dl.ttf"
    except: pass

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

def register_wanchi_font(pdf):
    if available_font:
        try:
            pdf.add_font("ArialVN", style="", fname=available_font)
            pdf.add_font("ArialVN", style="B", fname=available_font)
            return "ArialVN"
        except: pass
    return "Helvetica"

class WanchiPDF(FPDF):
    def __init__(self, quote_type="CÔNG TY"):
        super().__init__()
        self.quote_type = quote_type
        self.font_wanchi = register_wanchi_font(self)

    def header_wanchi(self):
        if available_logo:
            self.image(available_logo, x=10, y=8, h=15)
        else:
            self.set_font(self.font_wanchi, "B", 18)
            self.cell(100, 10, "WANCHI", border=0, align='L')
        
        self.set_font(self.font_wanchi, "B", 10)
        self.set_xy(130, 8)
        self.multi_cell(70, 5, txt=f"BẢNG BÁO GIÁ {self.quote_type}\nTháng {datetime.now().strftime('%m/%Y')}\nHotline: 0902.580.828", align='R')
        self.ln(10)

# --- XUẤT PDF CHUYÊN NGHIỆP TÙY BIẾN ---
def export_pro_pdf(df, mode="AGENCY"):
    if not available_font: return None
    
    title = "ĐẠI LÝ" if mode == "AGENCY" else "CÔNG TY"
    pdf = WanchiPDF(quote_type=title)
    pdf.add_page()
    pdf.header_wanchi()
    
    pdf.set_fill_color(230, 230, 230)
    pdf.set_font(pdf.font_wanchi, "B", 10)
    
    # Thiết lập Cột & Chiều cao dòng tùy theo loại báo giá
    if mode == "COMPANY":
        widths = [40, 30, 50, 35, 20, 15]
        headers = ["Hình ảnh", "Mã SP", "Diễn giải", "Kích thước", "Đơn giá", "Lốc"]
        row_h = 35   # Cao để chứa hình ảnh
        y_off = 15   # Canh giữa chữ theo chiều dọc
    else:
        widths = [35, 70, 45, 20, 20]
        headers = ["Mã SP", "Diễn giải", "Kích thước", "Đơn giá", "Lốc"]
        row_h = 12   # Gọn gàng như Excel
        y_off = 3    # Canh giữa chữ cho dòng nhỏ
    
    # Vẽ Header
    for i, head in enumerate(headers):
        pdf.cell(widths[i], 12, txt=head, border=1, fill=True, align='C')
    pdf.ln()
    
    # Vẽ Nội dung
    pdf.set_font(pdf.font_wanchi, "", 9)
    
    for _, row in df.iterrows():
        # Ngắt trang nếu hết giấy
        if pdf.get_y() + row_h > 270:
            pdf.add_page()
            pdf.set_fill_color(230, 230, 230)
            pdf.set_font(pdf.font_wanchi, "B", 10)
            for i, head in enumerate(headers):
                pdf.cell(widths[i], 12, txt=head, border=1, fill=True, align='C')
            pdf.ln()
            pdf.set_font(pdf.font_wanchi, "", 9)

        x, y = pdf.get_x(), pdf.get_y()
        curr_x = x

        # 1. Hình ảnh (Chỉ dành cho CÔNG TY)
        if mode == "COMPANY":
            pdf.rect(curr_x, y, widths[0], row_h)
            img_url = row.get('image_data', '')
            if img_url:
                try:
                    res = requests.get(img_url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=5)
                    if res.status_code == 200 and 'image' in res.headers.get('Content-Type', ''):
                        with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as tmp:
                            tmp.write(res.content)
                            tmp_path = tmp.name
                        pdf.image(tmp_path, x=curr_x+2, y=y+2, w=widths[0]-4, h=row_h-4)
                        os.remove(tmp_path)
                except: pass
            curr_x += widths[0]
            w_ma, w_dg, w_kt, w_gia, w_loc = widths[1], widths[2], widths[3], widths[4], widths[5]
        else:
            w_ma, w_dg, w_kt, w_gia, w_loc = widths[0], widths[1], widths[2], widths[3], widths[4]

        # 2. Mã SP
        pdf.rect(curr_x, y, w_ma, row_h)
        pdf.set_xy(curr_x, y + y_off)
        pdf.multi_cell(w_ma, 5, txt=str(row.get('product_code', '')), border=0, align='C')
        curr_x += w_ma

        # 3. Diễn giải
        pdf.rect(curr_x, y, w_dg, row_h)
        pdf.set_xy(curr_x + 2, y + (y_off - 1) if mode == "AGENCY" else y + y_off)
        pdf.multi_cell(w_dg-4, 5, txt=str(row.get('name', '')), border=0, align='C')
        curr_x += w_dg

        # 4. Kích thước
        pdf.rect(curr_x, y, w_kt, row_h)
        pdf.set_xy(curr_x + 2, y + y_off)
        size_clean = str(row.get('size', '')).strip()
        pdf.multi_cell(w_kt-4, 5, txt=size_clean, border=0, align='C')
        curr_x += w_kt

        # 5. Đơn giá
        pdf.rect(curr_x, y, w_gia, row_h)
        pdf.set_xy(curr_x, y + y_off)
        price_val = row.get('price_agency' if mode == "AGENCY" else 'price_company', 0)
        price_str = f"{int(price_val):,}".replace(",", ".")
        pdf.cell(w_gia, 5, txt=price_str, border=0, align='C')
        curr_x += w_gia

        # 6. Lốc
        pdf.rect(curr_x, y, w_loc, row_h)
        pdf.set_xy(curr_x, y + y_off)
        unit = f"{row['unit_per_pack']} cái" if mode == "AGENCY" else "1 cái"
        pdf.cell(w_loc, 5, txt=unit, border=0, align='C')

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
                st.error("⚠️ TÍNH NĂNG XUẤT PDF BỊ KHÓA: Đang tải font dự phòng, vui lòng F5 lại trang.")
            else:
                if st.button("🚀 XUẤT PDF BÁO GIÁ ĐẠI LÝ CHUYÊN NGHIỆP"):
                    with st.spinner("Đang đóng gói file..."):
                        pdf_agency = export_pro_pdf(df_a, mode="AGENCY")
                        if pdf_agency:
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
            if not available_font:
                st.error("⚠️ TÍNH NĂNG XUẤT PDF BỊ KHÓA: Đang tải font dự phòng, vui lòng F5 lại trang.")
            else:
                if st.button("🚀 XUẤT PDF BÁO GIÁ CÔNG TY (KÈM ẢNH)"):
                    with st.spinner("Đang tải ảnh và đóng gói..."):
                        pdf_company = export_pro_pdf(df_c, mode="COMPANY")
                        if pdf_company:
                            st.download_button("📥 TẢI PDF CÔNG TY", data=pdf_company, file_name=f"Bao_Gia_Wanchi_{datetime.now().strftime('%d%m%y')}.pdf", mime="application/pdf")

    with tab4:
        st.subheader("Lịch sử Đơn hàng")
        df_o = conn.query("SELECT * FROM orders ORDER BY order_date DESC", ttl=0)
        if not df_o.empty:
            for _, row in df_o.iterrows():
                with st.container(border=True):
                    st.write(f"👤 {row['customer_name']} - 💰 {int(row['total_amount']):,} đ")
                    with st.expander("Chi tiết"): st.text(row['order_items'])
