import streamlit as st
import pandas as pd
from sqlalchemy import text
from fpdf import FPDF
import re
import requests
import tempfile
import os
from datetime import datetime

st.set_page_config(page_title="Wanchi Admin - Quản lý Kho", layout="wide")
conn = st.connection("postgresql", type="sql", pool_pre_ping=True)

# ==========================================
# KHỐI TỰ ĐỘNG SỬA LỖI DATABASE
# ==========================================
try:
    with conn.session as s:
        s.execute(text("ALTER TABLE agency_products ADD COLUMN IF NOT EXISTS unit_per_pack INTEGER DEFAULT 100;"))
        s.execute(text("ALTER TABLE company_products ADD COLUMN IF NOT EXISTS unit_per_pack INTEGER DEFAULT 100;"))
        s.commit()
except: pass

# --- KIỂM TRA TÀI NGUYÊN ---
available_font = None
for f in ["arial.ttf", "Arial.ttf", "ARIAL.TTF", "arial_dl.ttf"]:
    if os.path.exists(f):
        available_font = f
        break

if not available_font:
    try:
        r = requests.get("https://github.com/matomo-org/travis-scripts/raw/master/fonts/Arial.ttf", timeout=5)
        with open("arial_dl.ttf", "wb") as f: f.write(r.content)
        available_font = "arial_dl.ttf"
    except: pass

LOGO_FILES = ["logo.png", "logo.jpg", "LOGO.png", "LOGO.jpg"]
available_logo = next((l for l in LOGO_FILES if os.path.exists(l)), None)

# --- HÀM HỖ TRỢ ---
def convert_drive_link(raw_url):
    if not raw_url: return ""
    match = re.search(r"(?<=/d/)[a-zA-Z0-9_-]+|(?<=id=)[a-zA-Z0-9_-]+", raw_url)
    return f"https://drive.google.com/thumbnail?id={match.group(0)}&sz=w1000" if match else raw_url

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
        if available_logo: self.image(available_logo, x=10, y=8, h=15)
        else:
            self.set_font(self.font_wanchi, "B", 18)
            self.cell(100, 10, "WANCHI", border=0, align='L')
        self.set_font(self.font_wanchi, "B", 10)
        self.set_xy(130, 8)
        self.multi_cell(70, 5, txt=f"BẢNG BÁO GIÁ {self.quote_type}\nTháng {datetime.now().strftime('%m/%Y')}\nHotline: 0902.580.828", align='R')
        self.ln(10)

def export_pro_pdf(df, mode="AGENCY"):
    title = "ĐẠI LÝ" if mode == "AGENCY" else "CÔNG TY"
    pdf = WanchiPDF(quote_type=title)
    pdf.add_page()
    pdf.header_wanchi()
    pdf.set_fill_color(230, 230, 230)
    pdf.set_font(pdf.font_wanchi, "B", 10)
    
    # Thiết lập Cột & Chiều cao (Tối ưu hóa gọn gàng)
    if mode == "COMPANY":
        widths = [35, 30, 55, 35, 20, 15]
        headers = ["Hình ảnh", "Mã SP", "Diễn giải", "Kích thước", "Đơn giá", "Cái"] # Đổi thành Cái
        row_h = 28 # Làm gọn lại từ 35
        y_off = 11
    else:
        widths = [35, 70, 45, 20, 20]
        headers = ["Mã SP", "Diễn giải", "Kích thước", "Đơn giá", "Cái"] # Đổi thành Cái
        row_h = 12
        y_off = 3
    
    for i, head in enumerate(headers):
        pdf.cell(widths[i], 12, txt=head, border=1, fill=True, align='C')
    pdf.ln()
    
    pdf.set_font(pdf.font_wanchi, "", 9)
    for _, row in df.iterrows():
        if pdf.get_y() + row_h > 275:
            pdf.add_page()
            pdf.set_fill_color(230, 230, 230)
            pdf.set_font(pdf.font_wanchi, "B", 10)
            for i, head in enumerate(headers): pdf.cell(widths[i], 12, txt=head, border=1, fill=True, align='C')
            pdf.ln()
            pdf.set_font(pdf.font_wanchi, "", 9)

        x, y = pdf.get_x(), pdf.get_y()
        curr_x = x

        if mode == "COMPANY":
            pdf.rect(curr_x, y, widths[0], row_h)
            img_url = row.get('image_data', '')
            if img_url:
                try:
                    res = requests.get(img_url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=5)
                    if res.status_code == 200:
                        with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as tmp:
                            tmp.write(res.content)
                            pdf.image(tmp.name, x=curr_x+1, y=y+1, w=widths[0]-2, h=row_h-2)
                        os.remove(tmp.name)
                except: pass
            curr_x += widths[0]
            w_list = widths[1:]
        else: w_list = widths

        # Vẽ dữ liệu các cột
        fields = ['product_code', 'name', 'size']
        for i, f in enumerate(fields):
            pdf.rect(curr_x, y, w_list[i], row_h)
            pdf.set_xy(curr_x, y + (y_off if f != 'name' else y_off - 4))
            pdf.multi_cell(w_list[i], 5, txt=str(row.get(f, '')), border=0, align='C')
            curr_x += w_list[i]

        # Đơn giá & Cái
        price_val = row.get('price_agency' if mode == "AGENCY" else 'price_company', 0)
        for i, val in enumerate([f"{int(price_val):,}".replace(",", "."), f"{row['unit_per_pack'] if mode == 'AGENCY' else 1} cái"]):
            pdf.rect(curr_x, y, w_list[3+i], row_h)
            pdf.set_xy(curr_x, y + y_off)
            pdf.cell(w_list[3+i], 5, txt=val, border=0, align='C')
            curr_x += w_list[3+i]

        pdf.set_xy(x, y + row_h)
    return bytes(pdf.output())

# --- GIAO DIỆN ---
if 'is_admin' not in st.session_state: st.session_state.is_admin = False
st.title("⚙️ Quản lý Báo giá WANCHI Pro")

if not st.session_state.is_admin:
    pwd = st.text_input("Mật khẩu Admin", type="password")
    if st.button("Đăng nhập"):
        if pwd == st.secrets["admin"]["password"]:
            st.session_state.is_admin = True
            st.rerun()
else:
    # Đã sửa tên tab thứ 3 thành "Danh sách SP Công ty"
    tab1, tab2, tab3, tab4 = st.tabs(["➕ Nhập SP Đại lý", "🏢 Lên đời SP Công ty", "📈 Danh sách SP Công ty", "📜 Đơn hàng"])
    with tab1:
        with st.form("agency_add"):
            c1, c2 = st.columns(2)
            code, name = c1.text_input("Mã sản phẩm"), c2.text_input("Tên diễn giải")
            size, price = c1.text_input("Kích thước"), c2.number_input("Giá gốc Đại lý", min_value=0)
            pack = st.number_input("Quy cách Lốc", value=100)
            if st.form_submit_button("Lưu kho Đại lý"):
                with conn.session as s:
                    s.execute(text("INSERT INTO agency_products (product_code, name, size, price_agency, unit_per_pack) VALUES (:c, :n, :s, :p, :pk) ON CONFLICT (product_code) DO UPDATE SET price_agency=:p, name=:n, size=:s, unit_per_pack=:pk"), {"c":code, "n":name, "s":size, "p":price, "pk":pack})
                    s.commit()
                st.success("Đã lưu!")
        df_a = conn.query("SELECT * FROM agency_products ORDER BY id DESC", ttl=0)
        if not df_a.empty:
            st.dataframe(df_a)
            if st.button("🚀 XUẤT PDF ĐẠI LÝ"):
                pdf = export_pro_pdf(df_a, mode="AGENCY")
                st.download_button("📥 TẢI PDF", data=pdf, file_name="Bao_Gia_DaiLy.pdf")

    with tab2:
        df_a2 = conn.query("SELECT * FROM agency_products", ttl=0)
        if not df_a2.empty:
            sel = st.selectbox("Chọn sản phẩm:", df_a2['product_code'])
            target = df_a2[df_a2['product_code'] == sel].iloc[0]
            price_co = round(float(target['price_agency']) / 0.55, 0)
            with st.form("co_form"):
                st.write(f"Giá Công ty tự động: **{int(price_co):,} đ**")
                raw_img = st.text_input("Link ảnh thiết kế:")
                if st.form_submit_button("Xác nhận"):
                    final_i = convert_drive_link(raw_img)
                    with conn.session as s:
                        s.execute(text("INSERT INTO company_products (product_code, name, size, price_company, image_data) VALUES (:c, :n, :s, :p, :i) ON CONFLICT (product_code) DO UPDATE SET price_company=:p, image_data=:i"), {"c":target['product_code'], "n":target['name'], "s":target['size'], "p":price_co, "i":str(final_i)})
                        s.commit()
                    st.success("Đã cập nhật!")

    with tab3:
        df_c = conn.query("SELECT * FROM company_products ORDER BY id DESC", ttl=0)
        if not df_c.empty:
            st.dataframe(df_c[['product_code', 'name', 'size', 'price_company']])
            if st.button("🚀 XUẤT PDF CÔNG TY"):
                pdf_c = export_pro_pdf(df_c, mode="COMPANY")
                st.download_button("📥 TẢI PDF", data=pdf_c, file_name="Bao_Gia_CongTy.pdf")
                
    with tab4:
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
                    with st.expander("Xem chi tiết"): st.text(row['order_items'])
