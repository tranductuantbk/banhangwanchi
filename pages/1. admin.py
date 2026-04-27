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

# --- KIỂM TRA FONT CHỮ ---
# Hệ thống sẽ tìm 1 trong 2 tên file này trên Github của bạn
FONT_FILES = ["arial.ttf", "Arial.ttf"]
available_font = None
for f in FONT_FILES:
    if os.path.exists(f):
        available_font = f
        break

# --- HÀM HỖ TRỢ ---
def convert_drive_link(raw_url):
    if not raw_url: return ""
    match = re.search(r"(?<=/d/)[a-zA-Z0-9_-]+|(?<=id=)[a-zA-Z0-9_-]+", raw_url)
    if match: return f"https://drive.google.com/thumbnail?id={match.group(0)}&sz=w1000"
    return raw_url

def setup_font(pdf, size):
    if available_font:
        try:
            pdf.add_font("ArialVN", style="", fname=available_font, uni=True)
            pdf.set_font("ArialVN", size=size)
            return
        except:
            try:
                pdf.add_font("ArialVN", style="", fname=available_font)
                pdf.set_font("ArialVN", size=size)
                return
            except: pass
    pdf.set_font("Helvetica", size=size)

# --- XUẤT PDF CHO ĐẠI LÝ ---
def export_pdf(df, title_pdf):
    if not available_font: return None # Chặn xuất nếu chưa có font
    
    pdf = FPDF()
    pdf.add_page()
    setup_font(pdf, 12)
        
    pdf.cell(200, 10, txt=title_pdf, ln=True, align='C')
    pdf.ln(10)
    
    setup_font(pdf, 10)
    pdf.set_fill_color(230, 230, 230)
    cols = df.columns.tolist()
    widths = [35, 60, 40, 30, 25]
    
    for i, col in enumerate(cols):
        pdf.cell(widths[i] if i < len(widths) else 30, 10, txt=str(col), border=1, fill=True, align='C')
    pdf.ln()
    
    setup_font(pdf, 9)
    for _, row in df.iterrows():
        for i, item in enumerate(row):
            val = f"{int(item):,}" if isinstance(item, (int, float)) and i >= 3 else str(item)
            pdf.cell(widths[i] if i < len(widths) else 30, 10, txt=val, border=1, align='L')
        pdf.ln()
    return bytes(pdf.output())

# --- XUẤT PDF CÔNG TY (CÓ HÌNH ẢNH) ---
def export_pdf_company_with_images(df):
    if not available_font: return None
    
    pdf = FPDF()
    pdf.add_page()
    setup_font(pdf, 18)
        
    pdf.cell(100, 10, txt="WANCHI", ln=0, align='L')
    setup_font(pdf, 10)
    pdf.cell(90, 10, txt=datetime.now().strftime("%m/%Y"), ln=1, align='R')
    pdf.ln(5)
    
    pdf.set_fill_color(230, 230, 230)
    headers = ["Hình ảnh", "Mã SP", "Diễn giải", "Kích thước", "Đơn giá", "Lốc"]
    widths = [35, 30, 50, 40, 20, 15]
    
    for i, col in enumerate(headers):
        pdf.cell(widths[i], 10, txt=str(col), border=1, fill=True, align='C')
    pdf.ln()
    
    setup_font(pdf, 9)
    row_height = 25 
    
    for _, row in df.iterrows():
        if pdf.get_y() + row_height > 280:
            pdf.add_page()
            for i, col in enumerate(headers):
                pdf.cell(widths[i], 10, txt=str(col), border=1, fill=True, align='C')
            pdf.ln()
            
        x_start = pdf.get_x()
        y_start = pdf.get_y()
        
        pdf.rect(x_start, y_start, widths[0], row_height)
        img_url = row.get('image_data', '')
        if pd.notna(img_url) and str(img_url).strip() != "":
            try:
                response = requests.get(str(img_url).strip(), timeout=3)
                if response.status_code == 200:
                    with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as tmp:
                        tmp.write(response.content)
                        tmp_path = tmp.name
                    pdf.image(tmp_path, x=x_start + 2, y=y_start + 2, w=widths[0] - 4, h=row_height - 4)
                    os.remove(tmp_path)
            except: pass
        
        pdf.rect(x_start + widths[0], y_start, widths[1], row_height)
        pdf.set_xy(x_start + widths[0], y_start + 10)
        pdf.cell(widths[1], 5, txt=str(row.get('product_code', '')), border=0, align='C')
        
        pdf.rect(x_start + sum(widths[:2]), y_start, widths[2], row_height)
        pdf.set_xy(x_start + sum(widths[:2]), y_start + 5)
        pdf.multi_cell(widths[2], 5, txt=str(row.get('name', '')), border=0, align='C')
        
        pdf.rect(x_start + sum(widths[:3]), y_start, widths[3], row_height)
        pdf.set_xy(x_start + sum(widths[:3]), y_start + 5)
        size_txt = str(row.get('size', '')).replace(" ", "\n")
        pdf.multi_cell(widths[3], 5, txt=size_txt, border=0, align='C')
        
        pdf.rect(x_start + sum(widths[:4]), y_start, widths[4], row_height)
        pdf.set_xy(x_start + sum(widths[:4]), y_start + 10)
        price = row.get('price_company', 0)
        price_str = f"{int(price):,}".replace(",", ".") if pd.notna(price) else "0"
        pdf.cell(widths[4], 5, txt=price_str, border=0, align='C')
        
        pdf.rect(x_start + sum(widths[:5]), y_start, widths[5], row_height)
        pdf.set_xy(x_start + sum(widths[:5]), y_start + 10)
        pdf.cell(widths[5], 5, txt="1 cái", border=0, align='C')
        
        pdf.set_xy(x_start, y_start + row_height)

    return bytes(pdf.output())

if 'is_admin' not in st.session_state:
    st.session_state.is_admin = False

st.title("⚙️ Hệ thống quản lý WANCHI")

if not st.session_state.is_admin:
    pwd = st.text_input("Mật khẩu Admin", type="password")
    if st.button("Đăng nhập"):
        if pwd == st.secrets["admin"]["password"]:
            st.session_state.is_admin = True
            st.rerun()
        else: st.error("Sai mật khẩu!")
else:
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "➕ Thêm SP Đại lý", "📋 Danh sách SP Đại lý", 
        "🏢 Thêm SP Công ty", "📈 Danh sách SP Công ty", "📜 Đơn hàng"
    ])

    with tab1:
        st.subheader("Nhập sản phẩm Đại lý mới")
        with st.form("agency_form", clear_on_submit=True):
            c1, c2 = st.columns(2)
            a_code = c1.text_input("Mã sản phẩm")
            a_name = c2.text_input("Tên sản phẩm")
            a_size = c1.text_input("Kích thước")
            a_price = c2.number_input("Giá Đại lý (1 SP)", min_value=0, step=100)
            a_pack = st.number_input("Lốc (Số lượng sản phẩm/kiện)", min_value=1, value=100, step=10)
            
            if st.form_submit_button("Lưu vào kho Đại lý"):
                try:
                    with conn.session as s:
                        s.execute(text("""
                            INSERT INTO agency_products (product_code, name, size, price_agency, unit_per_pack) 
                            VALUES (:c, :n, :s, :p, :pk)
                            ON CONFLICT (product_code) DO UPDATE SET name=:n, size=:s, price_agency=:p, unit_per_pack=:pk
                        """), {"c": str(a_code), "n": str(a_name), "s": str(a_size), "p": float(a_price), "pk": int(a_pack)})
                        s.commit()
                    st.success(f"✅ Đã thêm/cập nhật SP Đại lý: {a_name}")
                except Exception as e: st.error(f"❌ Lỗi khi lưu: {e}")

    with tab2:
        st.subheader("Bảng giá Đại lý")
        try:
            df_a = conn.query("SELECT product_code as \"Mã\", name as \"Tên\", size as \"Kích thước\", price_agency as \"Giá ĐL\", unit_per_pack as \"Lốc\" FROM agency_products ORDER BY id DESC", ttl=0)
            if not df_a.empty:
                st.dataframe(df_a, use_container_width=True)
                
                if not available_font:
                    st.error("⚠️ TÍNH NĂNG XUẤT PDF ĐANG BỊ KHÓA: Hệ thống chưa tìm thấy file `Arial.ttf` trên GitHub của bạn. Vui lòng làm theo Hướng dẫn Bước 1 để tính năng này hoạt động.")
                else:
                    pdf_data_a = export_pdf(df_a, "BANG GIA DAI LY WANCHI")
                    if pdf_data_a:
                        st.download_button("📥 Tải file PDF Đại lý", data=pdf_data_a, file_name="Gia_Dai_Ly_Wanchi.pdf")
            else: st.info("Kho Đại lý hiện đang trống.")
        except: pass

    with tab3:
        st.subheader("Nâng cấp sản phẩm lên dòng Công ty")
        try:
            df_a_select = conn.query("SELECT * FROM agency_products", ttl=0)
            if not df_a_select.empty:
                list_a = {row['id']: f"[{row['product_code']}] {row['name']}" for _, row in df_a_select.iterrows()}
                sel_id = st.selectbox("Chọn từ danh sách Đại lý:", options=list(list_a.keys()), format_func=lambda x: list_a[x])
                
                target = df_a_select[df_a_select['id'] == sel_id].iloc[0]
                price_co = round(float(target['price_agency']) / 0.55, 0)
                
                with st.form("company_form"):
                    st.info(f"Đang xử lý: {target['name']} ({target['product_code']})")
                    st.write(f"💵 Đơn giá Đại lý: {int(target['price_agency']):,} đ")
                    st.write(f"🏷️ **Đơn giá Công ty (Gốc ĐL / 0.55): {int(price_co):,} đ**")
                    raw_img = st.text_input("🔗 Chèn link ảnh thiết kế (Google Drive)")
                    
                    if st.form_submit_button("Xác nhận chuyển sang kho Công ty"):
                        try:
                            img_final = convert_drive_link(raw_img)
                            with conn.session as s:
                                s.execute(text("""
                                    INSERT INTO company_products (product_code, name, size, price_agency, price_company, image_data)
                                    VALUES (:c, :n, :s, :pa, :pc, :i)
                                    ON CONFLICT (product_code) DO UPDATE SET price_company = :pc, image_data = :i
                                """), {"c": str(target['product_code']), "n": str(target['name']), "s": str(target['size']) if pd.notna(target['size']) else "", "pa": float(target['price_agency']), "pc": float(price_co), "i": str(img_final)})
                                s.commit()
                            st.success("✅ Đã cập nhật sản phẩm vào kho Công ty!")
                        except Exception as e: st.error(f"❌ Lỗi ghi vào kho Công ty: {e}")
            else: st.warning("Vui lòng nhập sản phẩm Đại lý trước.")
        except: pass

    with tab4:
        st.subheader("Bảng giá Công ty (Bán lẻ)")
        try:
            df_c = conn.query("SELECT product_code, name, size, price_company, image_data FROM company_products ORDER BY id DESC", ttl=0)
            if not df_c.empty:
                df_display = df_c.rename(columns={"product_code": "Mã", "name": "Tên", "size": "Kích thước", "price_company": "Đơn giá 1 SP"})
                st.dataframe(df_display.drop(columns=["image_data"]), use_container_width=True)
                
                st.write("---")
                st.write("**Xuất báo giá PDF chuyên nghiệp (kèm Hình Ảnh):**")
                
                if not available_font:
                    st.error("⚠️ TÍNH NĂNG XUẤT PDF ĐANG BỊ KHÓA: Hệ thống chưa tìm thấy file `Arial.ttf` trên GitHub của bạn. Vui lòng tải file font chữ lên.")
                else:
                    if st.button("🔄 Bấm vào đây để đóng gói file PDF"):
                        with st.spinner("⏳ Đang tải ảnh và vẽ PDF... Xin đừng tắt trang..."):
                            pdf_data_c = export_pdf_company_with_images(df_c)
                            if pdf_data_c:
                                st.session_state.pdf_company_data = pdf_data_c
                                st.success("✅ Đã tạo xong! Vui lòng bấm nút tải bên dưới.")
                    
                    if 'pdf_company_data' in st.session_state:
                        st.download_button("📥 TẢI PDF VỀ MÁY", data=st.session_state.pdf_company_data, file_name="Bao_Gia_Cong_Ty_Wanchi.pdf", mime="application/pdf")
            else: st.info("Kho Công ty hiện đang trống.")
        except Exception as e: st.error(f"Lỗi: {e}")

    with tab5:
        st.subheader("Lịch sử chốt đơn")
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
